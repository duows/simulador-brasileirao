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
from .pipeline import (LINGUAGEM, SOURCES, last_complete_round, load_weights,
                       season_features)
from .simulate.montecarlo import round_plan
from .reports import FACTOR_TEXT
from .simulate.montecarlo import simulate_season, split_remaining
from .teams import display_name


def _base(cfg, w, generated_at: str) -> dict:
    return {"aviso": cfg["output"]["aviso"], "atribuicao": cfg["output"]["atribuicao"],
            "gerado_em": generated_at, "versao_modelo": w.model_version}


def _write(out_dir: Path, name: str, doc: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=float),
                                          encoding="utf-8")


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
    _write(out, "modelo", {**base, **model_data(cfg, w)})
    _write(out, "financas", {**base, **finance_data(cfg)})
    return out
