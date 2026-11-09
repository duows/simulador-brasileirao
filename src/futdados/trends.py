"""Tendências e mudança estrutural em séries anuais curtas (21 pontos no máximo).

Para cada série: Theil-Sen (inclinação robusta com intervalo), teste de Mann-Kendall (via tau de
Kendall contra o tempo), LOESS com faixa de bootstrap, média móvel de 3 anos e ponto de mudança
na média (particionamento ótimo com penalidade tipo BIC). O rótulo em linguagem simples só sai
quando o teste tem sinal (p < 0,05); senão "sem tendência clara".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

ERAS = [("2006–2012", 2006, 2012), ("2013–2019", 2013, 2019), ("2020–2026", 2020, 2026)]


def mann_kendall(t: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    tau, p = stats.kendalltau(t, y)
    return float(tau), float(p)


def theil_sen(t: np.ndarray, y: np.ndarray) -> dict:
    slope, intercept, lo, hi = stats.theilslopes(y, t, alpha=0.90)
    return {"inclinacao": float(slope), "intercepto": float(intercept), "ic90": [float(lo), float(hi)]}


def loess_band(t: np.ndarray, y: np.ndarray, frac: float = 0.6, n_boot: int = 300, seed: int = 0) -> dict:
    """LOESS e faixa de 90% por bootstrap de resíduos (os anos ficam fixos; reamostra o ruído)."""
    fit = lowess(y, t, frac=frac, return_sorted=False)
    resid = y - fit
    rng = np.random.default_rng(seed)
    curves = [lowess(fit + rng.choice(resid, len(resid), replace=True), t, frac=frac, return_sorted=False)
              for _ in range(n_boot)]
    lo, hi = np.percentile(np.array(curves), [5, 95], axis=0)
    return {"loess": fit.tolist(), "faixa90": [lo.tolist(), hi.tolist()]}


def change_point(y: np.ndarray, min_size: int = 3) -> int | None:
    """Índice onde a média muda (um único corte), se reduzir o erro além da penalidade."""
    n = len(y)
    if n < 2 * min_size:
        return None
    sse0 = float(np.sum((y - y.mean()) ** 2))
    sigma2 = sse0 / max(n - 1, 1)
    best, best_cost = None, sse0
    for k in range(min_size, n - min_size + 1):
        a, b = y[:k], y[k:]
        cost = float(np.sum((a - a.mean()) ** 2) + np.sum((b - b.mean()) ** 2)) + 2 * sigma2 * np.log(n)
        if cost < best_cost:
            best, best_cost = k, cost
    return best


def label(tau: float, p: float, higher_is: str = "alta") -> str:
    if p >= 0.05 or np.isnan(p):
        return "sem tendência clara"
    return "em alta" if tau > 0 else "em queda"


def analyze(years: list[int], values: list[float]) -> dict:
    t = np.asarray(years, float)
    y = np.asarray(values, float)
    ok = ~np.isnan(y)
    t, y = t[ok], y[ok]
    if len(y) < 5:
        return {"anos": t.astype(int).tolist(), "valores": y.tolist(), "rotulo": "poucos dados", "n": len(y)}
    tau, p = mann_kendall(t, y)
    cp = change_point(y)
    out = {
        "anos": t.astype(int).tolist(), "valores": y.tolist(), "n": int(len(y)),
        "media_movel_3": pd.Series(y).rolling(3, center=True, min_periods=2).mean().tolist(),
        "theil_sen": theil_sen(t, y), "mann_kendall": {"tau": tau, "p": p},
        "rotulo": label(tau, p),
        "mudanca": None if cp is None else {"ano": int(t[cp]), "media_antes": float(y[:cp].mean()),
                                            "media_depois": float(y[cp:].mean())},
        **loess_band(t, y),
    }
    out["aviso"] = (f"São só {len(y)} temporadas: tendências curtas são frágeis. "
                    + ("O teste de Mann-Kendall não encontrou sinal (p ≥ 0,05)." if p >= 0.05
                       else f"Mann-Kendall p = {p:.3f}."))
    return out


def eras(years: list[int], values: list[float]) -> dict:
    groups = {name: [v for yr, v in zip(years, values) if a <= yr <= b and not np.isnan(v)] for name, a, b in ERAS}
    groups = {k: v for k, v in groups.items() if len(v) >= 3}
    p = float(stats.kruskal(*groups.values()).pvalue) if len(groups) >= 2 else float("nan")
    return {"medias": {k: float(np.mean(v)) for k, v in groups.items()}, "kruskal_p": p,
            "diferenca_clara": bool(p < 0.05)}


LEAGUE_SERIES = {
    "pts_campeao": "Pontos do campeão", "pts_vice": "Pontos do vice", "pts_g4": "Pontos do 4º colocado",
    "pts_g6": "Pontos do 6º colocado", "pts_17": "Pontos do 17º (1º do Z4)", "pts_16": "Pontos do 16º",
    "gols_por_jogo": "Gols por jogo", "empates_pct": "Empates", "vitorias_mandante_pct": "Vitórias do mandante",
    "vantagem_mando_gols": "Vantagem de mando (gols por jogo)", "gini_pontos": "Desigualdade de pontos (Gini)",
    "desvio_pontos": "Desvio padrão dos pontos", "times_na_briga_5_rodadas_antes": "Times na briga pelo título a 5 rodadas do fim",
}


def league_trends(lss: pd.DataFrame) -> dict:
    closed = lss[lss.encerrada.astype(bool)].sort_values("season")
    out = {}
    for col, name in LEAGUE_SERIES.items():
        yrs, vals = closed.season.tolist(), closed[col].astype(float).tolist()
        out[col] = {"nome": name, **analyze(yrs, vals), "eras": eras(yrs, vals)}
    return out


def team_trends(tss: pd.DataFrame, elo_end: pd.DataFrame, closed_seasons: list[int]) -> dict:
    out = {}
    for tid, g in tss[tss.season.isin(closed_seasons)].groupby("team_id"):
        g = g.sort_values("season")
        e = elo_end[elo_end.team_id == tid].sort_values("season")
        out[tid] = {
            "pontos": analyze(g.season.tolist(), g.pts.astype(float).tolist()),
            "posicao": analyze(g.season.tolist(), g.posicao.astype(float).tolist()),
            "elo_fim": analyze(e.season.tolist(), e.elo.astype(float).tolist()),
        }
        # posição: número menor é melhor, então "em alta" vira "subindo na tabela"
        rot = out[tid]["posicao"]["rotulo"]
        out[tid]["posicao"]["rotulo"] = {"em alta": "caindo na tabela", "em queda": "subindo na tabela"}.get(rot, rot)
    return out
