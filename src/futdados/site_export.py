"""Exporta os JSONs que o site estático (site/) lê, em site/public/data.

Regra: só dados DERIVADOS pelo modelo e o dataset financeiro curado (com fonte por número).
Nada de JSON bruto da API nem dos CSVs de terceiros: os jogos disputados entram agregados
(tabela atual e confronto direto), não como lista de partidas.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .db import Repository, utc_now
from .finance import read as read_finance
from .model.features import FEATURES
from .model.predict import FACTOR_LABEL, match_payload
from .pipeline import LINGUAGEM, SOURCES, last_complete_round, load_weights, season_features
from .reports import FACTOR_TEXT
from .simulate.montecarlo import round_plan, simulate_season, split_remaining
from .teams import display_name


def _base(cfg, w, generated_at: str) -> dict:
    return {"aviso": cfg["output"]["aviso"], "atribuicao": cfg["output"]["atribuicao"],
            "gerado_em": generated_at, "versao_modelo": w.model_version}


def clean_json(x):
    """NaN/Infinito não existem em JSON: viram null (o navegador quebraria ao ler)."""
    if isinstance(x, dict):
        return {k: clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def _write(out_dir: Path, name: str, doc: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(
        json.dumps(clean_json(doc), ensure_ascii=False, indent=1, default=float, allow_nan=False), encoding="utf-8")


def simulator_data(feat: pd.DataFrame, w, cfg) -> dict:
    """Tudo que o simulador "e se" precisa para recalcular a tabela no navegador."""
    played, todo, lh, la = split_remaining(feat, w)
    teams = sorted(set(feat.home_id) | set(feat.away_id))
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    stats = {k: [0] * T for k in ("pts", "j", "v", "gp", "gc")}
    h2h = [[0] * T for _ in range(T)]
    for r in played.itertuples():
        hi, ai = idx[r.home_id], idx[r.away_id]
        hg, ag = int(r.home_goals), int(r.away_goals)
        hp = 3 if hg > ag else (1 if hg == ag else 0)
        ap = 3 if ag > hg else (1 if hg == ag else 0)
        for i, gf, ga, pts in ((hi, hg, ag, hp), (ai, ag, hg, ap)):
            stats["pts"][i] += pts
            stats["j"][i] += 1
            stats["v"][i] += pts == 3
            stats["gp"][i] += gf
            stats["gc"][i] += ga
        h2h[hi][ai] += hp
        h2h[ai][hi] += ap
    restantes = [{
        "id": k, "rodada": int(r.round), "mandante": idx[r.home_id], "visitante": idx[r.away_id],
        "inicio_utc": pd.Timestamp(r.kickoff_utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gols_esperados": [round(float(lh[k]), 4), round(float(la[k]), 4)],
    } for k, r in enumerate(todo.itertuples())]
    return {
        "times": [{"id": t, "nome": display_name(t)} for t in teams],
        "atual": stats,
        "confronto_direto_pontos": h2h,
        "restantes": restantes,
        "rho": w.rho,
        "max_gols": int(cfg["model"]["max_goals"]),
        "zonas": cfg["simulation"]["zones"],
        "criterios_desempate": cfg["simulation"]["tiebreakers"],
        "simulacoes_padrao": 2000,
    }


def model_data(cfg, w) -> dict:
    fatores = []
    for f in FEATURES:
        step, phrase, label = FACTOR_TEXT[f]
        b = w.coef[f]
        lo, hi = w.ci_low.get(f), w.ci_high.get(f)
        estimable = w.feature_std.get(f, 1.0) != 0
        fatores.append({
            "fator": f, "rotulo": label, "peso": b, "ic95": [lo, hi],
            "efeito_exemplo": math.exp(b * step) - 1, "exemplo": phrase,
            "estimavel": estimable,
            "distinguivel_de_zero": bool(estimable and lo is not None and not (lo <= 0 <= hi)),
        })
    bt_path = Path(cfg["paths"]["weights"]).with_name("backtest.json")
    backtest = json.loads(bt_path.read_text(encoding="utf-8")) if bt_path.exists() else None
    return {"meia_vida_dias": w.half_life_days, "intercepto": w.intercept,
            "temporadas_treino": [w.train_seasons[0], w.train_seasons[-1]], "jogos_treino": w.n_matches,
            "fatores": fatores, "backtest": backtest}


def finance_data(cfg) -> dict:
    root = Path(cfg["paths"]["finance"])
    rows = read_finance(root / "comparativo_clubes.csv")
    for r in rows:
        r["valor_mil_reais"] = None if r["valor_mil_reais"] == "" else float(r["valor_mil_reais"])
    return {"linhas": rows, "unidade": "R$ mil", "relatorio": "reports/spfc_financas.md"}


def _registry_index(repo: Repository, season: int) -> dict:
    """Última previsão gravada antes do jogo, por (mandante, visitante): hora e hash."""
    reg = repo.predictions(season)
    if reg.empty:
        return {}
    reg = reg[reg.created_at < reg.kickoff_utc].sort_values("id")
    return {(r.home_id, r.away_id): {"gravado_em": r.created_at, "hash": r.hash, "versao_modelo": r.model_version}
            for r in reg.itertuples()}


def team_stats(feat: pd.DataFrame) -> dict[str, dict]:
    """Tabela atual, últimos resultados, casa/fora, forma e força de cada time na temporada."""
    from .simulate.montecarlo import round_plan as _rp

    played = feat[(feat.status == "FINISHED") & feat.home_goals.notna()].sort_values("kickoff_utc")
    _, postponed = _rp(feat)
    teams = sorted(set(feat.home_id) | set(feat.away_id))
    st = {t: {"j": 0, "v": 0, "e": 0, "d": 0, "gp": 0, "gc": 0, "pts": 0, "resultados": [],
              "casa": {"j": 0, "pts": 0, "gp": 0, "gc": 0}, "fora": {"j": 0, "pts": 0, "gp": 0, "gc": 0}}
          for t in teams}
    for r in played.itertuples():
        hg, ag = int(r.home_goals), int(r.away_goals)
        for tid, gf, ga, side, opp in ((r.home_id, hg, ag, "casa", r.away_id), (r.away_id, ag, hg, "fora", r.home_id)):
            s = st[tid]
            res = "V" if gf > ga else ("E" if gf == ga else "D")
            pts = {"V": 3, "E": 1, "D": 0}[res]
            s["j"] += 1; s["gp"] += gf; s["gc"] += ga; s["pts"] += pts
            s[{"V": "v", "E": "e", "D": "d"}[res]] += 1
            s[side]["j"] += 1; s[side]["pts"] += pts; s[side]["gp"] += gf; s[side]["gc"] += ga
            s["resultados"].append({"rodada": int(r.round), "data_utc": pd.Timestamp(r.kickoff_utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "adversario": opp, "local": side, "gols_pro": gf, "gols_contra": ga, "resultado": res})
    order = sorted(teams, key=lambda t: (-st[t]["pts"], -st[t]["v"], -(st[t]["gp"] - st[t]["gc"]), -st[t]["gp"],
                                         display_name(t)))
    for i, t in enumerate(order, start=1):
        st[t]["posicao_atual"] = i
        st[t]["ultimos5"] = [x["resultado"] for x in st[t]["resultados"][-5:]]
        st[t]["adiados"] = int(sum(postponed[(feat.home_id == t) | (feat.away_id == t)]))
    # força e forma no próximo jogo de cada time (ou no último, se não houver próximo)
    for t in teams:
        mine = feat[(feat.home_id == t) | (feat.away_id == t)].sort_values("kickoff_utc")
        nxt = mine[mine.status != "FINISHED"]
        row = (nxt.iloc[0] if len(nxt) else mine.iloc[-1])
        side = "h" if row.home_id == t else "a"
        other = "a" if side == "h" else "h"
        st[t]["forca"] = {"ataque": float(np.exp(row[f"ataque_{side}"])),
                          "defesa": float(np.exp(row[f"defesa_adversario_{other}"])),
                          "pontos_por_jogo_ultimos5": float(row[f"raw_ppg_{side}"])}
    return st


def history_data(repo: Repository, season: int, max_round: int) -> dict:
    hist = repo.projection_history(season, max_round)
    if hist.empty:
        return {"rodadas": [], "times": {}}
    rounds = sorted(int(r) for r in hist.based_on_round.unique())
    times = {}
    for tid, g in hist.groupby("team_id"):
        g = g.set_index("based_on_round")
        times[tid] = {k: [None if r not in g.index else float(g.loc[r, col]) for r in rounds]
                      for k, col in (("titulo", "p_titulo"), ("g4", "p_g4"), ("g6", "p_g6"),
                                     ("rebaixamento", "p_rebaixamento"), ("pontos_esperados", "exp_points"))}
    return {"rodadas": rounds, "times": times}


def export_site(repo: Repository, cfg, season: int, as_of_round: int | None = None,
                n_sims: int | None = None, out_dir: str | Path | None = None) -> Path:
    w = load_weights(cfg)
    out = Path(out_dir or cfg["paths"]["site_data"])
    now = utc_now()
    base = _base(cfg, w, now)
    feat = season_features(repo, cfg, w, season, as_of_round)
    max_round = int(feat["round"].max())
    based_on = last_complete_round(feat)
    table = simulate_season(feat, w, cfg, max_round, n_sims=n_sims)
    if as_of_round is None:  # só projeções ao vivo entram no histórico por rodada
        repo.insert_projection({"season": season, "based_on_round": based_on, "target_round": max_round,
                                "model_version": w.model_version}, table.assign(exp_points=table.exp_points_final))
    stats = team_stats(feat)

    meta = {**base, "temporada": season, "rodada_base": based_on, "rodadas": max_round,
            "demonstracao": as_of_round is not None,
            "nota_demonstracao": (f"Demonstração: temporada {season} reconstituída como se estivéssemos "
                                  f"depois da rodada {as_of_round}. Os pesos usados foram ajustados com "
                                  "dados que incluem essa temporada.") if as_of_round is not None else None,
            "linguagem": LINGUAGEM, "fontes": SOURCES, "time_foco": cfg["output"]["focus_team"]}
    _write(out, "meta", meta)

    linhas = [{
        "time": {"id": r.team_id, "nome": display_name(r.team_id)}, "jogos": int(r.jogos),
        "pontos_atuais": int(r.pontos_atuais), "saldo_atual": int(r.saldo_atual),
        "pontos_esperados": round(float(r.exp_points_final), 1),
        "faixa_posicao": {"p10": int(round(r.pos_p10)), "p90": int(round(r.pos_p90))},
        "chance_titulo": float(r.p_titulo), "chance_g4": float(r.p_g4), "chance_g6": float(r.p_g6),
        "chance_rebaixamento": float(r.p_rebaixamento),
        "distribuicao_posicao": [round(float(x), 4) for x in r.dist],
        "posicao_atual": stats[r.team_id]["posicao_atual"],
        "v": stats[r.team_id]["v"], "e": stats[r.team_id]["e"], "d": stats[r.team_id]["d"],
        "gp": stats[r.team_id]["gp"], "gc": stats[r.team_id]["gc"],
        "ultimos5": stats[r.team_id]["ultimos5"], "adiados": stats[r.team_id]["adiados"],
    } for r in table.itertuples()]
    _write(out, "tabela", {**base, "temporada": season, "rodada_base": based_on,
                           "simulacoes": int(n_sims or cfg["simulation"]["n_sims"]), "linhas": linhas})

    rnd, postponed = round_plan(feat)
    pending = feat.status != "FINISHED"
    jogos, adiados = [], []
    for idx, row in feat[pending].iterrows():
        if postponed.loc[idx]:
            adiados.append({**match_payload(row, w, cfg["model"]["max_goals"]), "adiado": True})
        elif rnd is not None and row["round"] == rnd:
            jogos.append({**match_payload(row, w, cfg["model"]["max_goals"]), "adiado": False})
    registro = _registry_index(repo, season)
    for j in jogos + adiados:
        j["registro"] = registro.get((j["mandante"]["id"], j["visitante"]["id"]))
    _write(out, "rodada", {**base, "temporada": season, "rodada": rnd, "rotulos_fatores": FACTOR_LABEL,
                           "jogos": sorted(jogos, key=lambda j: j["inicio_utc"]),
                           "adiados": sorted(adiados, key=lambda j: j["inicio_utc"])})

    _write(out, "simulador", {**base, "temporada": season, "rodada_base": based_on,
                              **simulator_data(feat, w, cfg)})
    _write(out, "historico", {**base, "temporada": season, **history_data(repo, season, max_round)})

    # páginas por time: jogos restantes (com fatores), resultados, casa/fora, força e forma
    proximos: dict[str, list] = {tid: [] for tid in stats}
    for idx, row in feat[pending].sort_values("kickoff_utc").iterrows():
        pay = {**match_payload(row, w, cfg["model"]["max_goals"]), "adiado": bool(postponed.loc[idx])}
        pay["registro"] = registro.get((row["home_id"], row["away_id"]))
        proximos[row["home_id"]].append(pay)
        proximos[row["away_id"]].append(pay)
    times = {}
    for tid, s in stats.items():
        times[tid] = {"id": tid, "nome": display_name(tid), "posicao_atual": s["posicao_atual"],
                      "j": s["j"], "v": s["v"], "e": s["e"], "d": s["d"], "gp": s["gp"], "gc": s["gc"],
                      "pts": s["pts"], "casa": s["casa"], "fora": s["fora"], "forca": s["forca"],
                      "ultimos5": s["ultimos5"], "adiados": s["adiados"],
                      "resultados": [{**r, "adversario_nome": display_name(r["adversario"])}
                                     for r in s["resultados"][::-1]],
                      "proximos": proximos[tid]}
    _write(out, "times", {**base, "temporada": season, "rodada_base": based_on, "times": times})
    _write(out, "modelo", {**base, **model_data(cfg, w)})
    _write(out, "financas", {**base, **finance_data(cfg)})
    hist = history_site_data(repo)
    if hist:
        _write(out, "temporadas", {**base, **hist["temporadas"]})
        _write(out, "tendencias", {**base, **hist["tendencias"]})
    return out


def history_site_data(repo: Repository) -> dict | None:
    """Temporadas 2006-2026 e tendências, a partir das tabelas derivadas (futdados metrics/trends)."""
    try:
        tss, lss, trs = repo.table("team_season_stats"), repo.table("league_season_stats"), repo.table("team_round_stats")
        elo = repo.table("elo_ratings")
    except Exception:  # noqa: BLE001 - tabelas ainda não calculadas
        return None
    trends = repo.get_json("trends") or {}
    m = repo.matches()
    done = m[(m.status == "FINISHED") & m.home_goals.notna()]
    seasons = {}
    for season, ls in lss.groupby("season"):
        s = int(season)
        t = tss[tss.season == season].sort_values("posicao")
        r = trs[trs.season == season]
        rounds = sorted(int(x) for x in r["round"].unique())
        traj = {tid: {"pts": g.sort_values("round").pts.astype(int).tolist(),
                      "pos": g.sort_values("round").posicao.astype(int).tolist()}
                for tid, g in r.groupby("team_id")}
        d = done[done.season == season].assign(gd=lambda x: (x.home_goals - x.away_goals).abs(),
                                                tot=lambda x: x.home_goals + x.away_goals)
        big = d.sort_values(["gd", "tot"], ascending=False).head(5)
        row = ls.iloc[0]
        seasons[s] = {
            "temporada": s, "encerrada": bool(row.encerrada), "campeao": row.campeao,
            "liga": {k: (None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.number)) else v))
                     for k, v in row.items() if k not in ("season", "campeao")},
            "tabela": [{"pos": int(x.posicao), "time": x.team_id, "nome": display_name(x.team_id), "j": int(x.j),
                        "pts": int(x.pts), "v": int(x.v), "e": int(x.e), "d": int(x.d), "gp": int(x.gp), "gc": int(x.gc),
                        "pts_pitagoricos": round(float(x.pts_pitagoricos), 1),
                        "sorte": round(float(x.pts_menos_pitagoricos), 1),
                        "casa_pts": int(x.casa_pts), "fora_pts": int(x.fora_pts),
                        "maior_seq_invicto": int(x.maior_seq_invicto), "maior_seq_vitorias": int(x.maior_seq_vitorias)}
                       for x in t.itertuples()],
            "rodadas": rounds, "trajetorias": traj,
            "maiores_goleadas": [{"rodada": int(x.round), "mandante": display_name(x.home_id), "visitante": display_name(x.away_id),
                                  "placar": f"{int(x.home_goals)}-{int(x.away_goals)}"} for x in big.itertuples()],
        }
    # histórico por time (todas as temporadas na elite) e Elo no fim de cada temporada
    elo_end = elo.sort_values("kickoff_utc").groupby(["season", "team_id"]).tail(1)
    teams_hist = {}
    for tid, g in tss.sort_values("season").groupby("team_id"):
        e = elo_end[elo_end.team_id == tid].set_index("season").elo
        teams_hist[tid] = {"nome": display_name(tid), "temporadas": [
            {"temporada": int(x.season), "pos": int(x.posicao), "pts": int(x.pts), "j": int(x.j), "gp": int(x.gp),
             "gc": int(x.gc), "elo_fim": None if x.season not in e.index else round(float(e.loc[x.season]), 1)}
            for x in g.itertuples()], "tendencia": (trends.get("times") or {}).get(tid)}
    return {"temporadas": {"temporadas": seasons, "times_historico": teams_hist},
            "tendencias": {"liga": trends.get("liga", {})}}
