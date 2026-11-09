"""Pontuação esperada de cada atleta do Cartola FC, explicável por fatores.

Para cada posição, uma regressão linear (ridge leve) da pontuação de um atleta numa rodada:

    pontos ≈ a + b1·média_ajustada + b2·regularidade + b3·P(SG) + b4·gols_esperados_time
             + b5·mando + b6·P(vitória)

- média_ajustada: média do atleta nas rodadas ANTERIORES, puxada para a média da posição com
  `shrink` jogos fictícios (pouca amostra = mais perto da média da posição).
- P(SG): chance do time não sofrer gol, exp(-gols esperados do adversário), do nosso modelo.
- gols_esperados_time, P(vitória): do nosso modelo de jogos, com fatores que só usam o passado.
- mando: 1 se o time joga em casa.
- regularidade: fração dos últimos 5 jogos do time em que o atleta entrou em campo.

Validação walk-forward dentro da temporada: para a rodada r, coeficientes ajustados só com
rodadas < r e médias calculadas só com rodadas < r. Baseline: a média do atleta (o que o
próprio Cartola mostra).

Pontuação esperada final = P(jogar) × pontos previstos, com P(jogar) pelo status do mercado,
estimada com o histórico de status guardado (ver project.estimate_p_jogar).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = ["media_ajustada", "regularidade", "p_sg", "gols_time", "mando", "p_vitoria"]
REG_WINDOW = 5
LABELS = {"soma_time_11": "Soma esperada do time ÷ 11",
          "base": "Base da posição", "media_ajustada": "Média do atleta (ajustada)",
          "regularidade": "Regularidade (jogou nos últimos 5 jogos do time)", "p_sg": "Chance de não sofrer gol",
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


def season_means(pontos: pd.DataFrame, min_games: int = 5) -> dict[int, float]:
    """Média de cada atleta numa temporada (só quem jogou pelo menos `min_games`)."""
    g = pontos[pontos.jogou].groupby("atleta_id").pontos.agg(["mean", "count"])
    return g[g["count"] >= min_games]["mean"].to_dict()


def add_prior_means(pontos: pd.DataFrame, shrink: float, prev_means: dict[int, float] | None = None) -> pd.DataFrame:
    """Média de cada atleta nas rodadas anteriores (sem vazamento), puxada para um valor a priori:
    a média dele na temporada anterior, se houver (5+ jogos), senão a média da posição."""
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
    prior = df.atleta_id.map(prev_means or {}).fillna(df.media_pos)
    df["media_ajustada"] = (df.soma_prev + shrink * prior) / (df.n_prev + shrink)
    return df


def add_regularity(rows: pd.DataFrame, pontos: pd.DataFrame, window: int = REG_WINDOW) -> pd.DataFrame:
    """Fração dos últimos `window` jogos do time (antes da rodada) em que o atleta entrou em campo.

    Separa o titular de sempre do reserva que entra no fim: quem joga pouco pontua menos quando
    entra. Sem jogo anterior do time, 0,5.
    """
    pl = pontos[pontos.jogou]
    team_rounds = {t: np.sort(s.unique()) for t, s in pl.groupby("team_id").rodada}
    played = set(zip(pl.atleta_id, pl.rodada, strict=True))

    def reg(a, t, r):
        rs = team_rounds.get(t)
        rs = rs[rs < r][-window:] if rs is not None else []
        return float(np.mean([(a, x) in played for x in rs])) if len(rs) else 0.5

    out = rows.copy()
    out["regularidade"] = [reg(a, t, r) for a, t, r in zip(out.atleta_id, out.team_id, out.rodada, strict=True)]
    return out


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


def training_table(pontos: pd.DataFrame, ctx: pd.DataFrame, shrink: float,
                   prev_means: dict[int, float] | None = None) -> pd.DataFrame:
    df = add_regularity(add_prior_means(pontos, shrink, prev_means), pontos)
    return df.merge(ctx, on=["rodada", "team_id"], how="inner").dropna(subset=FEATURES)


def walk_forward(table: pd.DataFrame, first_round: int, alpha: float, sums: pd.DataFrame | None = None,
                 ctx: pd.DataFrame | None = None) -> pd.DataFrame:
    """Previsão fora da amostra de cada rodada >= first_round."""
    out = []
    for r in sorted(table.rodada.unique()):
        if r < first_round:
            continue
        train, test = table[table.rodada < r], table[table.rodada == r].copy()
        coefs = fit_position_models(train, alpha)
        test["previsto"] = predict(test, coefs)
        if sums is not None and ctx is not None and (test.posicao == "tec").any():
            tc = fit_team_sum(sums[sums.rodada < r], ctx, alpha)
            sel = test.posicao == "tec"
            test.loc[sel, "previsto"] = coach_prediction(test[sel], tc)
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


def production_context(partidas: pd.DataFrame, matches: pd.DataFrame, season: int, half_life: float = 365,
                       shots: pd.DataFrame | None = None, peso_gols: float = 1.0) -> pd.DataFrame:
    """Contexto por time e rodada com o motor de produção (forças por time), reajustado antes de
    cada rodada com os jogos anteriores a ela: sem vazamento, igual para treino e previsão."""
    from ..model.poisson import outcome_probs
    from ..model.production import fit_strengths, lambdas

    rows = []
    season_m = matches[matches.season == season]
    for rnd, g in partidas.dropna(subset=["home_id", "away_id"]).groupby("rodada"):
        keys = g.merge(season_m[["home_id", "away_id", "kickoff_utc"]], on=["home_id", "away_id"], how="left")
        start = pd.to_datetime(keys.kickoff_utc, utc=True).min()
        if pd.isna(start):
            start = pd.Timestamp(g.data.min(), tz="America/Sao_Paulo").tz_convert("UTC")
        s = fit_strengths(matches, start, half_life=half_life, shots=shots, peso_gols=peso_gols)
        lh, la = lambdas(s, g.home_id, g.away_id)
        p = outcome_probs(lh, la)
        for (h, a, v), x, y, ph, pa in zip(g[["home_id", "away_id", "valida"]].itertuples(index=False), lh, la,
                                           p[:, 0], p[:, 2], strict=True):
            rows.append({"rodada": rnd, "team_id": h, "adversario": a, "valida": v, "gols_time": x, "gols_adv": y,
                         "p_vitoria": ph, "mando": 1})
            rows.append({"rodada": rnd, "team_id": a, "adversario": h, "valida": v, "gols_time": y, "gols_adv": x,
                         "p_vitoria": pa, "mando": 0})
    ctx = pd.DataFrame(rows)
    ctx["p_sg"] = np.exp(-ctx.gols_adv)
    return ctx


# ----------------------------------------------------------------- técnico
# Regra conferida nos dados de 2026 (95% exato em 642 pontuações): técnico = soma dos pontos dos
# jogadores do time dele que entraram em campo / 11 + 1 ponto se o time vencer (scout V).
TEAM_FEATURES = ["gols_time", "p_sg", "mando"]


def team_sums(pontos: pd.DataFrame) -> pd.DataFrame:
    pl = pontos[(pontos.posicao != "tec") & pontos.jogou]
    return pl.groupby(["rodada", "team_id"]).pontos.sum().rename("soma_time").reset_index()


def fit_team_sum(sums: pd.DataFrame, ctx: pd.DataFrame, alpha: float = 1.0) -> np.ndarray:
    d = sums.merge(ctx, on=["rodada", "team_id"]).dropna(subset=TEAM_FEATURES)
    return _fit(d[TEAM_FEATURES].to_numpy(float), d.soma_time.to_numpy(float), alpha)


def coach_prediction(rows: pd.DataFrame, coef: np.ndarray) -> np.ndarray:
    """Pontuação prevista do técnico = soma esperada do time / 11 + chance de vitória."""
    soma = coef[0] + rows[TEAM_FEATURES].to_numpy(float) @ coef[1:]
    return soma / 11 + rows.p_vitoria.to_numpy(float)


def coach_decompose(row: pd.Series, coef: np.ndarray) -> dict[str, float]:
    soma = coef[0] + sum(coef[i + 1] * row[f] for i, f in enumerate(TEAM_FEATURES))
    return {"soma_time_11": float(soma / 11), "p_vitoria": float(row["p_vitoria"])}
