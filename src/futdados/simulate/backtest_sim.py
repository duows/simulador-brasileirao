"""Backtest da simulação de campeonato: as chances de título, G4 e rebaixamento eram confiáveis?

Para cada temporada encerrada e rodada de corte (10, 20, 30), refaz a projeção escondendo os
resultados seguintes (forças e Elo só com jogos anteriores ao corte) e compara as chances com o
que aconteceu: Brier de cada objetivo, contra o baseline "todo time tem a mesma chance", e
calibração (quando o modelo dava 30%, aconteceu perto de 30%?).

Ressalva: os pesos do conjunto vêm do backtest de jogos (usam temporadas posteriores para
escolher só dois números); o resto é sem vazamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..pipeline import load_weights, season_features
from .montecarlo import simulate_season

GOALS = {"titulo": "p_titulo", "g4": "p_g4", "rebaixamento": "p_rebaixamento"}


def run(repo, cfg, seasons: list[int], cuts: list[int], n_sims: int = 5000) -> pd.DataFrame:
    w = load_weights(cfg)
    tss = repo.table("team_season_stats")
    zones = cfg["simulation"]["zones"]
    rows = []
    for s in seasons:
        final = tss[tss.season == s].set_index("team_id").posicao.astype(int)
        for cut in cuts:
            feat = season_features(repo, cfg, w, s, as_of_round=cut)
            tab = simulate_season(feat, w, cfg, int(feat["round"].max()), n_sims=n_sims, seed=s * 100 + cut)
            for r in tab.itertuples():
                pos = int(final.get(r.team_id, 99))
                rows.append({"temporada": s, "corte": cut, "team_id": r.team_id, "posicao_final": pos,
                             "pos_p10": r.pos_p10, "pos_p90": r.pos_p90,
                             "p_titulo": r.p_titulo, "p_g4": r.p_g4, "p_rebaixamento": r.p_rebaixamento,
                             "y_titulo": int(pos <= zones["titulo"][1]), "y_g4": int(pos <= zones["g4"][1]),
                             "y_rebaixamento": int(pos >= zones["rebaixamento"][0])})
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> dict:
    out = {"por_corte": [], "calibracao": {}, "faixa_p10_p90": None}
    for cut, g in df.groupby("corte"):
        row = {"corte": int(cut), "n": len(g)}
        for name, col in GOALS.items():
            y = g[f"y_{name}"].to_numpy(float)
            p = g[col].to_numpy(float)
            base = np.full_like(y, y.mean())  # mesma chance para todos (taxa da zona)
            row[f"brier_{name}"] = float(np.mean((p - y) ** 2))
            row[f"brier_base_{name}"] = float(np.mean((base - y) ** 2))
        rows_in = (g.posicao_final >= g.pos_p10) & (g.posicao_final <= g.pos_p90)
        row["dentro_da_faixa"] = float(rows_in.mean())
        out["por_corte"].append(row)
    out["faixa_p10_p90"] = float(((df.posicao_final >= df.pos_p10) & (df.posicao_final <= df.pos_p90)).mean())
    bins = [0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0001]
    for name, col in GOALS.items():
        cal = []
        idx = np.digitize(df[col], bins) - 1
        for b in range(len(bins) - 1):
            sel = idx == b
            if sel.sum() >= 10:
                cal.append({"faixa": f"{bins[b]:.0%}-{min(bins[b + 1], 1):.0%}", "n": int(sel.sum()),
                            "estimado": float(df[col][sel].mean()), "observado": float(df[f"y_{name}"][sel].mean())})
        out["calibracao"][name] = cal
    return out


def markdown(summ: dict, seasons: list[int]) -> str:
    def f(x, d=3):
        return f"{x:.{d}f}".replace(".", ",")

    lines = ["# Backtest da simulação de campeonato", "",
             f"Temporadas {seasons[0]}–{seasons[-1]}. Em cada uma, a projeção foi refeita como se estivéssemos nas rodadas "
             "10, 20 e 30, escondendo os resultados seguintes, e comparada com a classificação final. Brier: erro "
             "quadrático médio das chances (menor é melhor). Baseline: todo time com a mesma chance (a taxa da zona).", "",
             "| Rodada de corte | Brier título (base) | Brier G4 (base) | Brier rebaixamento (base) | Posição final dentro da faixa p10–p90 |",
             "|---|---|---|---|---|"]
    for r in summ["por_corte"]:
        lines.append(f"| {r['corte']} | {f(r['brier_titulo'])} ({f(r['brier_base_titulo'])}) | {f(r['brier_g4'])} ({f(r['brier_base_g4'])}) | "
                     f"{f(r['brier_rebaixamento'])} ({f(r['brier_base_rebaixamento'])}) | {r['dentro_da_faixa']:.0%} |")
    lines += ["", f"No total, a posição final caiu dentro da faixa p10–p90 em {summ['faixa_p10_p90']:.0%} dos casos "
              "(o esperado para uma faixa de 80% bem calibrada é perto de 80%).", "", "## Calibração", ""]
    for name, cal in summ["calibracao"].items():
        lines += [f"**{name}**", "", "| Faixa estimada | Times | Estimado | Observado |", "|---|---|---|---|"]
        lines += [f"| {c['faixa']} | {c['n']} | {c['estimado']:.0%} | {c['observado']:.0%} |" for c in cal]
        lines.append("")
    return "\n".join(lines)
