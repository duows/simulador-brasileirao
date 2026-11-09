"""Pontuação esperada de cada atleta do Cartola FC, explicável por fatores.

Para cada posição, uma regressão linear (ridge leve) da pontuação de um atleta numa rodada:

    pontos ≈ a + b1·média_ajustada + b2·P(SG) + b3·gols_esperados_time + b4·mando + b5·P(vitória)

- média_ajustada: média do atleta nas rodadas ANTERIORES, puxada para a média da posição com
  `shrink` jogos fictícios (pouca amostra = mais perto da média da posição).
- P(SG): chance do time não sofrer gol, exp(-gols esperados do adversário), do nosso modelo.
- gols_esperados_time, P(vitória): do nosso modelo de jogos, com fatores que só usam o passado.
- mando: 1 se o time joga em casa.

Validação walk-forward dentro da temporada: para a rodada r, coeficientes ajustados só com
rodadas < r e médias calculadas só com rodadas < r. Baseline: a média do atleta (o que o
próprio Cartola mostra).

Pontuação esperada final = P(jogar) × pontos previstos, com P(jogar) pelo status do mercado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = ["media_ajustada", "p_sg", "gols_time", "mando", "p_vitoria"]
LABELS = {"base": "Base da posição", "media_ajustada": "Média do atleta (ajustada)", "p_sg": "Chance de não sofrer gol",
          "gols_time": "Gols esperados do time", "mando": "Jogar em casa", "p_vitoria": "Chance de vitória"}


def match_context(partidas: pd.DataFrame, feat: pd.DataFrame, weights) -> pd.DataFrame:
    """Contexto de cada time em cada rodada do Cartola: gols esperados, P(SG), P(vitória), mando."""
    from ..model.poisson import expected_goals, outcome_probs

    f = feat.copy()
    lh, la = expected_goals(f, weights)
    p = outcome_probs(lh, la, weights.rho)
    f["lh"], f["la"], f["ph"], f["pa"] = lh, la, p[:, 0], p[:, 2]
    m = partidas.merge(f[["home_id", "away_id", "lh", "la", "ph", "pa"]], on=["home_id", "away_id"], how="left")
    home = pd.DataFrame({"rodada": m.rodada, "team_id": m.home_id, "adversario": m.away_id, "valida": m.valida,
                         "gols_time": m.lh, "gols_adv": m.la, "p_vitoria": m.ph, "mando": 1})
    away = pd.DataFrame({"rodada": m.rodada, "team_id": m.away_id, "adversario": m.home_id, "valida": m.valida,
                         "gols_time": m.la, "gols_adv": m.lh, "p_vitoria": m.pa, "mando": 0})
    ctx = pd.concat([home, away], ignore_index=True)
    ctx["p_sg"] = np.exp(-ctx.gols_adv)
    return ctx


def add_prior_means(pontos: pd.DataFrame, shrink: float) -> pd.DataFrame:
    """Média de cada atleta nas rodadas anteriores (sem vazamento), puxada para a média da posição."""
    df = pontos[pontos.jogou].sort_values(["atleta_id", "rodada"]).copy()
    g = df.groupby("atleta_id").pontos
    df["soma_prev"] = g.cumsum() - df.pontos
    df["n_prev"] = g.cumcount()
    pos_mean = {}
    for r in sorted(df.rodada.unique()):  # média da posição só com rodadas anteriores
        prev = df[df.rodada < r]
        pos_mean[r] = prev.groupby("posicao").pontos.mean().to_dict() if len(prev) else {}
    overall = df.groupby("posicao").pontos.mean().to_dict()
    df["media_pos"] = [pos_mean[r].get(p, overall[p]) for r, p in zip(df.rodada, df.posicao)]
    df["media_previa"] = np.where(df.n_prev > 0, df.soma_prev / df.n_prev.clip(lower=1), np.nan)
    df["media_ajustada"] = (df.soma_prev + shrink * df.media_pos) / (df.n_prev + shrink)
    return df


def _fit(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    Xb = np.hstack([np.ones((len(X), 1)), X])
    pen = alpha * np.eye(Xb.shape[1])
    pen[0, 0] = 0
    return np.linalg.solve(Xb.T @ Xb + pen, Xb.T @ y)


def fit_position_models(rows: pd.DataFrame, alpha: float = 1.0) -> dict[str, np.ndarray]:
    return {pos: _fit(g[FEATURES].to_numpy(float), g.pontos.to_numpy(float), alpha) for pos, g in rows.groupby("posicao")}


def predict(rows: pd.DataFrame, coefs: dict[str, np.ndarray]) -> np.ndarray:
    out = np.full(len(rows), np.nan)
    for pos, c in coefs.items():
        sel = (rows.posicao == pos).to_numpy()
        if sel.any():
            out[sel] = c[0] + rows.loc[sel, FEATURES].to_numpy(float) @ c[1:]
    return out


def decompose(row: pd.Series, coef: np.ndarray) -> dict[str, float]:
    """Contribuição de cada fator em pontos (soma = pontos previstos)."""
    out = {"base": float(coef[0])}
    for i, f in enumerate(FEATURES):
        out[f] = float(coef[i + 1] * row[f])
    return out


def training_table(pontos: pd.DataFrame, ctx: pd.DataFrame, shrink: float) -> pd.DataFrame:
    df = add_prior_means(pontos, shrink)
    return df.merge(ctx, on=["rodada", "team_id"], how="inner").dropna(subset=FEATURES)


def walk_forward(table: pd.DataFrame, first_round: int, alpha: float) -> pd.DataFrame:
    """Previsão fora da amostra de cada rodada >= first_round."""
    out = []
    for r in sorted(table.rodada.unique()):
        if r < first_round:
            continue
        train, test = table[table.rodada < r], table[table.rodada == r].copy()
        coefs = fit_position_models(train, alpha)
        test["previsto"] = predict(test, coefs)
        out.append(test)
    return pd.concat(out, ignore_index=True)


def evaluate(pred: pd.DataFrame) -> dict:
    """Erro absoluto médio e correlação de ordem (por rodada e posição) contra a média do Cartola."""
    from scipy.stats import spearmanr

    d = pred.dropna(subset=["media_previa"]).copy()  # baseline precisa de pelo menos 1 jogo anterior
    res = {"n": len(d), "mae_modelo": float((d.previsto - d.pontos).abs().mean()),
           "mae_media": float((d.media_previa - d.pontos).abs().mean())}
    rho_m, rho_b = [], []
    for _, g in d.groupby(["rodada", "posicao"]):
        if len(g) >= 8:
            rho_m.append(spearmanr(g.previsto, g.pontos).statistic)
            rho_b.append(spearmanr(g.media_previa, g.pontos).statistic)
    res["spearman_modelo"], res["spearman_media"] = float(np.nanmean(rho_m)), float(np.nanmean(rho_b))
    # por rodada: o modelo ganha da média em quantas rodadas (MAE)?
    by = d.groupby("rodada").apply(lambda g: pd.Series({"m": (g.previsto - g.pontos).abs().mean(),
                                                         "b": (g.media_previa - g.pontos).abs().mean()}),
                                   include_groups=False)
    res["rodadas_modelo_melhor"] = int((by.m < by.b).sum())
    res["rodadas"] = len(by)
    res["por_posicao"] = d.groupby("posicao").apply(
        lambda g: {"mae_modelo": float((g.previsto - g.pontos).abs().mean()),
                   "mae_media": float((g.media_previa - g.pontos).abs().mean()), "n": len(g)},
        include_groups=False).to_dict()
    return res
