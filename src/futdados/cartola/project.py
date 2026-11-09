"""Cartola: pontuação esperada da rodada, registro antes do fechamento e pós-rodada (só local)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..db import Repository, utc_now
from ..model.features import build_features
from ..model.poisson import Weights, fit
from ..pipeline import season_features
from ..teams import display_name
from . import model as cm
from .ingest import fetch_round_points, ingest, load_offline
from .optimize import best_team


def cartola_root(cfg: dict) -> Path:
    return Path(cfg["paths"]["db"]).parent / "cartola"


def past_seasons(cfg: dict, season: int) -> list[int]:
    root = cartola_root(cfg)
    return sorted(int(d.name) for d in root.iterdir() if d.is_dir() and d.name.isdigit() and int(d.name) < season) \
        if root.exists() else []


def backtest(repo: Repository, cfg: dict, data: dict, prev_means: dict | None) -> tuple[dict, pd.DataFrame]:
    """Walk-forward na temporada: modelo de jogos ajustado só até a temporada anterior."""
    c = cfg["cartola"]
    w_live = Weights.load(cfg["paths"]["weights"])
    allf = build_features(repo.matches(), cfg["model"], half_life_days=w_live.half_life_days)
    season = int(data["status"]["temporada"])
    w_bt = fit(allf[(allf.season >= cfg["model"]["train_first_season"]) & (allf.season < season)], cfg["model"],
               w_live.half_life_days, bootstrap=0)
    ctx = cm.match_context(data["partidas"], allf[allf.season == season], w_bt)
    table = cm.training_table(data["pontos"], ctx, c["shrink"], prev_means)
    pred = cm.walk_forward(table, c["first_backtest_round"], c["alpha"])
    return cm.evaluate(pred), pred


def project(repo: Repository, cfg: dict) -> dict:
    c = cfg["cartola"]
    season = int(c["season"])
    root = cartola_root(cfg)
    data = ingest(root, season)
    status = data["status"]
    rnd = int(status["rodada_atual"])
    w = Weights.load(cfg["paths"]["weights"])

    # tabelas de treino: temporadas anteriores do cache + a atual
    tables, prev_means = [], None
    for s in past_seasons(cfg, season):
        off = load_offline(root, s)
        if off is None:
            continue
        ctx_s = cm.match_context(off["partidas"], season_features(repo, cfg, w, s), w)
        tables.append(cm.training_table(off["pontos"], ctx_s, c["shrink"], prev_means))
        prev_means = cm.season_means(off["pontos"])
    ctx = cm.match_context(data["partidas"], season_features(repo, cfg, w, season), w)
    tables.append(cm.training_table(data["pontos"], ctx, c["shrink"], prev_means))
    coefs = cm.fit_position_models(pd.concat(tables, ignore_index=True), c["alpha"])

    played = data["pontos"][data["pontos"].jogou]
    agg = played.groupby("atleta_id").pontos.agg(["sum", "count"])
    pos_mean = played.groupby("posicao").pontos.mean()
    a = data["atletas"].copy()
    a = a[a.status.isin(c["p_jogar"].keys()) & a.team_id.notna()]
    a = a.join(agg, on="atleta_id")
    a[["sum", "count"]] = a[["sum", "count"]].fillna(0)
    prior = a.atleta_id.map(prev_means or {}).fillna(a.posicao.map(pos_mean))
    a["media_ajustada"] = (a["sum"] + c["shrink"] * prior) / (a["count"] + c["shrink"])
    a = a.merge(ctx[ctx.rodada == rnd], on="team_id", how="inner")
    a = a[a.valida]
    a["previsto"] = cm.predict(a, coefs)
    a["p_jogar"] = a.status.map(c["p_jogar"]).astype(float)
    a["esperado"] = a.p_jogar * a.previsto
    players = []
    for _, r in a.iterrows():
        dec = cm.decompose(r, coefs[r.posicao])
        players.append({
            "id": int(r.atleta_id), "apelido": r.apelido, "time": r.team_id, "time_nome": display_name(r.team_id),
            "adversario": display_name(r.adversario), "adversario_id": r.adversario, "mando": bool(r.mando),
            "posicao": r.posicao, "status": r.status, "preco": float(r.preco), "media_cartola": float(r.media),
            "jogos": int(r.jogos), "media_ajustada": round(float(r.media_ajustada), 2), "p_jogar": float(r.p_jogar),
            "previsto_se_jogar": round(float(r.previsto), 2), "esperado": round(float(r.esperado), 2),
            "foto": r.foto,
            "contexto": {"p_sg": round(float(r.p_sg), 3), "gols_time": round(float(r.gols_time), 2),
                         "p_vitoria": round(float(r.p_vitoria), 3)},
            "fatores": {k: round(v, 2) for k, v in dec.items()},
        })
    schemes = {e["nome"]: e["posicoes"] for e in data["esquemas"]}
    ev, _ = backtest(repo, cfg, data, None)
    invalid = data["partidas"][(data["partidas"].rodada == rnd) & ~data["partidas"].valida]
    fech = status.get("fechamento") or {}
    fech_utc = (datetime.fromtimestamp(fech["timestamp"], UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                if fech.get("timestamp") else None)
    return {
        "aviso": cfg["output"]["aviso"], "atribuicao": cfg["output"]["atribuicao"], "gerado_em": utc_now(),
        "versao_modelo": w.model_version, "temporada": season, "rodada": rnd, "mercado_aberto": status.get("status_mercado") == 1,
        "fechamento": fech, "fechamento_utc": fech_utc, "cartoletas_iniciais": status.get("cartoleta_inicial"),
        "multiplicador_capitao": c["captain_multiplier"], "p_jogar": c["p_jogar"], "reservas": c["reservas"],
        "esquemas": schemes, "atletas": sorted(players, key=lambda x: -x["esperado"]),
        "escudos": data["escudos"],
        "coeficientes": {pos: dict(zip(["base", *cm.FEATURES], map(float, v), strict=True)) for pos, v in coefs.items()},
        "rotulos_fatores": cm.LABELS, "temporadas_no_treino": [*past_seasons(cfg, season), season],
        "jogos_fora_da_rodada": [f"{display_name(r.home_id)} x {display_name(r.away_id)}" for r in invalid.itertuples()],
        "backtest": ev,
        "fonte": "API pública (não oficial) do Cartola FC, uso pessoal e local; contexto dos jogos: modelo futdados.",
    }


def players_frame(doc: dict) -> pd.DataFrame:
    df = pd.DataFrame([{k: v for k, v in p.items() if k not in ("contexto", "fatores")} for p in doc["atletas"]])
    return df.assign(atleta_id=df["id"])


def register(repo: Repository, cfg: dict, doc: dict) -> str | None:
    """Grava as previsões e os times sugeridos antes do fechamento. Fora do prazo, não grava."""
    if not doc["mercado_aberto"] or not doc["fechamento_utc"] or utc_now() >= doc["fechamento_utc"]:
        return None
    pf = players_frame(doc)
    times = {}
    for b in cfg["cartola"]["registro_orcamentos"]:
        res = best_team(pf, float(b), doc["esquemas"], doc["multiplicador_capitao"], reserves=cfg["cartola"]["reservas"])
        if res["ok"]:
            t, rv = res["time"], res["reservas"]
            times[str(b)] = {"esquema": res["esquema"],
                             "esperado": res.get("pontos_esperados_com_reservas", res["pontos_esperados"]),
                             "custo": res["custo"], "atletas": t.id.astype(int).tolist(),
                             "capitao": int(t[t.capitao].id.iloc[0]),
                             "posicoes": dict(zip(t.id.astype(int).astype(str), t.posicao, strict=True)),
                             "reservas": {r.posicao: int(r.id) for r in rv.itertuples()} if len(rv) else {}}
    atletas = [{k: p[k] for k in ("id", "posicao", "status", "preco", "media_cartola", "esperado", "previsto_se_jogar", "p_jogar")}
               for p in doc["atletas"]]
    return repo.insert_cartola_prediction({"season": doc["temporada"], "rodada": doc["rodada"],
                                           "fechamento_utc": doc["fechamento_utc"], "model_version": doc["versao_modelo"],
                                           "atletas": atletas, "times": times})


def live_record(repo: Repository, cfg: dict, season: int, current_round: int) -> list[dict]:
    """Previsto x real de cada rodada registrada que já terminou (o placar ao vivo do modelo)."""
    reg = repo.cartola_predictions(season)
    if reg.empty:
        return []
    reg = reg[reg.created_at < reg.fechamento_utc].sort_values("id").groupby("rodada").tail(1)
    mult = cfg["cartola"]["captain_multiplier"]
    out = []
    for r in reg.itertuples():
        if r.rodada >= current_round:
            continue
        real = fetch_round_points(cartola_root(cfg), season, int(r.rodada)).set_index("atleta_id")
        pred = pd.DataFrame(json.loads(r.atletas)).set_index("id")
        joined = pred.join(real[["pontos", "jogou"]], how="left")
        joined["jogou"] = joined.jogou.fillna(False).astype(bool)
        played = joined[joined.jogou]
        prov = joined[joined.status == "provavel"]
        times = {}
        for b, t in json.loads(r.times).items():
            total = team_real_points(t, real, mult)
            times[b] = {"esperado": round(t["esperado"], 1), "real": round(total, 1), "esquema": t["esquema"]}
        out.append({
            "rodada": int(r.rodada), "gravado_em": r.created_at, "hash": r.hash[:12],
            "atletas_avaliados": int(len(played)),
            "erro_modelo": round(float((played.previsto_se_jogar - played.pontos).abs().mean()), 3),
            "erro_media_cartola": round(float((played.media_cartola - played.pontos).abs().mean()), 3),
            "provaveis_que_jogaram": round(float(prov.jogou.mean()), 3) if len(prov) else None,
            "times": times,
        })
    return out


def team_real_points(t: dict, real: pd.DataFrame, mult: float) -> float:
    """Pontos reais do time sugerido com a regra do banco: o reserva da posição entra se algum
    titular dela não jogou (e o reserva jogou). Capitão que não jogou não multiplica nada."""
    def played(aid: int) -> bool:
        return aid in real.index and bool(real.jogou.get(aid, False))

    def pts(aid: int) -> float:
        return float(real.pontos.get(aid, 0.0)) if played(aid) else 0.0

    total = sum(pts(a) for a in t["atletas"]) + (mult - 1) * pts(t["capitao"])
    for pos, rid in (t.get("reservas") or {}).items():
        starters = [int(a) for a, p in (t.get("posicoes") or {}).items() if p == pos]
        if any(not played(a) for a in starters) and played(rid):
            total += pts(rid)
    return round(float(total), 1)


def write_site_json(doc: dict, path: str | Path) -> Path:
    from ..site_export import clean_json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean_json(doc), ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return path


def cartola_report(ev: dict, live: list[dict]) -> str:
    """Relatório agregado (sem nomes nem dados de atletas: pode ser versionado)."""
    pp = ev["por_posicao"]
    lines = ["# Cartola FC: quanto o modelo erra (estudo de caso)", "",
             "## Backtest da temporada", "",
             "Walk-forward: cada rodada prevista só com rodadas anteriores; o modelo de jogos usado no contexto foi ajustado "
             "só até a temporada anterior. Avaliado em atletas que entraram em campo. Baseline: a média do próprio Cartola.", "",
             "| Métrica | Modelo | Média do Cartola |", "|---|---|---|",
             f"| Erro absoluto médio (pontos) | {ev['mae_modelo']:.3f} | {ev['mae_media']:.3f} |".replace(".", ","),
             f"| Correlação de ordem na posição (Spearman) | {ev['spearman_modelo']:.3f} | {ev['spearman_media']:.3f} |".replace(".", ","),
             f"| Rodadas em que o modelo erra menos | {ev['rodadas_modelo_melhor']} de {ev['rodadas']} | — |", "",
             "| Posição | Erro do modelo | Erro da média | Atletas-rodada |", "|---|---|---|---|"]
    for pos, v in pp.items():
        lines.append(f"| {pos} | {v['mae_modelo']:.3f} | {v['mae_media']:.3f} | {v['n']} |".replace(".", ","))
    lines += ["", "## Ao vivo (previsões gravadas antes do fechamento do mercado)", ""]
    if not live:
        lines.append("Ainda não há rodada registrada e encerrada.")
    else:
        budgets = sorted({b for x in live for b in x["times"]}, key=float)
        lines += ["| Rodada | Erro do modelo | Erro da média | Prováveis que jogaram | " + " | ".join(f"Time C$ {b}: esperado → real" for b in budgets) + " |",
                  "|---" * (4 + len(budgets)) + "|"]
        for x in live:
            cells = [f"{x['times'][b]['esperado']:.1f} → {x['times'][b]['real']:.1f}" if b in x["times"] else "—" for b in budgets]
            pj = "—" if x["provaveis_que_jogaram"] is None else f"{x['provaveis_que_jogaram']:.0%}"
            lines.append(f"| {x['rodada']} | {x['erro_modelo']:.2f} | {x['erro_media_cartola']:.2f} | {pj} | " + " | ".join(cells) + " |")
    lines += ["", "Ganho real, mas modesto: a pontuação do Cartola tem muito acaso e o modelo não sabe a escalação.", ""]
    return "\n".join(lines).replace("→", "→")


def describe_team(res: dict) -> str:
    if not res["ok"]:
        return res["motivo"]
    lines = [f"Esquema {res['esquema']} · custo C$ {res['custo']:.2f} de {res['orcamento']:.2f} · "
             f"pontuação esperada {res['pontos_esperados']:.1f}"]
    for r in res["time"].itertuples():
        cap = " (C)" if r.capitao else ""
        lines.append(f"  {r.posicao.upper():<4} {r.apelido:<22}{cap:<4} {r.time_nome:<14} C$ {r.preco:>6.2f}  esperado {r.esperado:>5.2f}")
    rv = res.get("reservas")
    if rv is not None and len(rv):
        lines.append(f"  Banco (+{res['valor_reservas']:.2f} de pontuação esperada com os reservas):")
        for r in rv.itertuples():
            lines.append(f"  {r.posicao.upper():<4} {r.apelido:<26} {r.time_nome:<14} C$ {r.preco:>6.2f}  "
                         f"entra em {r.chance_de_entrar:.0%} dos casos, esperado {r.esperado:.2f}")
    return "\n".join(lines)


_ = np
