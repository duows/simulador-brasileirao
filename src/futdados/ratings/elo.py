"""Elo adaptado ao futebol, com parâmetros calibrados por validação (não fixados no olho).

Atualização depois de cada jogo:
    E = 1 / (1 + 10^(-(R_mandante + mando - R_visitante) / 400))
    R_mandante += K * G(saldo) * (S - E)        (S = 1, 0,5 ou 0)
    G(saldo) = 1 (saldo 0 ou 1), 1,5 (saldo 2), (11 + saldo) / 8 (saldo 3+)
Entre temporadas cada rating volta parte do caminho até a média (regressão), e um time que não
estava na temporada anterior entra com média + deslocamento de promovido.

Probabilidade de V/E/D a partir da diferença de rating: regressão logística ordinal
(um coeficiente e dois cortes), ajustada só com temporadas anteriores à avaliada.
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

BASE = 1500.0


@dataclass
class EloParams:
    k: float = 20.0
    home: float = 60.0
    regression: float = 0.25
    promoted: float = -100.0


def _gmult(gd: int) -> float:
    gd = abs(gd)
    return 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)


def run_elo(matches: pd.DataFrame, p: EloParams) -> pd.DataFrame:
    """Percorre os jogos disputados em ordem e devolve os ratings antes/depois de cada jogo."""
    done = matches[(matches.status == "FINISHED") & matches.home_goals.notna()].copy()
    done["kickoff_utc"] = pd.to_datetime(done.kickoff_utc, utc=True)
    done = done.sort_values(["kickoff_utc", "home_id"]).reset_index(drop=True)
    members = {int(s): set(g.home_id) | set(g.away_id) for s, g in matches.groupby("season")}
    rating: dict[str, float] = {}
    season_now = None
    out = np.zeros((len(done), 4))
    seasons, hs, as_, hg, ag = (done.season.to_numpy(), done.home_id.to_numpy(), done.away_id.to_numpy(),
                                done.home_goals.to_numpy(int), done.away_goals.to_numpy(int))
    for i in range(len(done)):
        s = int(seasons[i])
        if s != season_now:  # virada de temporada: regressão e entrada de promovidos
            if rating:
                mean = float(np.mean([rating[t] for t in members.get(season_now, rating.keys()) if t in rating]))
                rating = {t: mean + (1 - p.regression) * (r - mean) for t, r in rating.items()}
            prev = members.get(s - 1)
            ref = float(np.mean(list(rating.values()))) if rating else BASE
            for t in members.get(s, ()):
                promoted = prev is not None and t not in prev
                if t not in rating:
                    rating[t] = ref + p.promoted
                elif promoted:  # voltou depois de rebaixado: rating antigo, limitado ao de promovido
                    rating[t] = min(rating[t], ref + p.promoted)
            season_now = s
        h, a = hs[i], as_[i]
        rh, ra = rating[h], rating[a]
        e = 1 / (1 + 10 ** (-(rh + p.home - ra) / 400))
        sres = 1.0 if hg[i] > ag[i] else (0.5 if hg[i] == ag[i] else 0.0)
        delta = p.k * _gmult(hg[i] - ag[i]) * (sres - e)
        out[i] = (rh, ra, rh + delta, ra - delta)
        rating[h], rating[a] = rh + delta, ra - delta
    done[["elo_h_antes", "elo_a_antes", "elo_h_depois", "elo_a_depois"]] = out
    done["elo_diff"] = done.elo_h_antes + p.home - done.elo_a_antes
    return done


def outcome(hg, ag) -> np.ndarray:
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def fit_ordinal(diff: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ajusta (b, c1, c2): P(visitante)=σ(c1 - b·d), P(visitante ou empate)=σ(c2 - b·d)."""
    d = diff / 100.0

    def nll(theta):
        b, c1, gap = theta
        c2 = c1 + np.exp(gap)
        p_away = expit(c1 - b * d)
        p_le_draw = expit(c2 - b * d)
        p = np.stack([1 - p_le_draw, p_le_draw - p_away, p_away], axis=1)
        return -np.sum(np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1)))

    res = minimize(nll, np.array([0.5, -1.0, 0.0]), method="L-BFGS-B")
    b, c1, gap = res.x
    return np.array([b, c1, c1 + np.exp(gap)])


def ordinal_probs(diff: np.ndarray, theta: np.ndarray) -> np.ndarray:
    b, c1, c2 = theta
    d = np.asarray(diff) / 100.0
    p_away = expit(c1 - b * d)
    p_le_draw = expit(c2 - b * d)
    return np.stack([1 - p_le_draw, p_le_draw - p_away, p_away], axis=1)


def _rps(p, y):
    onehot = np.eye(3)[y]
    cp, co = np.cumsum(p, axis=1)[:, :2], np.cumsum(onehot, axis=1)[:, :2]
    return float(np.mean(np.sum((cp - co) ** 2, axis=1) / 2))


def empirical_home(matches: pd.DataFrame, seasons: list[int]) -> float:
    """Mando em pontos de Elo que faz E (ratings iguais) = pontuação média do mandante no período."""
    d = matches[matches.season.isin(seasons) & (matches.status == "FINISHED")]
    score = float(((d.home_goals > d.away_goals) + 0.5 * (d.home_goals == d.away_goals)).mean())
    return float(-400 * np.log10(1 / score - 1))


def calibrate(matches: pd.DataFrame, tune_seasons: list[int], grid: dict | None = None) -> tuple[EloParams, pd.DataFrame]:
    """K, regressão e deslocamento de promovidos pelo menor RPS nas temporadas de ajuste.

    O mando é estimado direto dos dados (`empirical_home`): calibrado por RPS ele cresce sem
    parar com ganho desprezível, porque a regressão ordinal já absorve o efeito médio do mando.
    """
    home = empirical_home(matches, tune_seasons)
    grid = grid or {"k": [5, 10, 15, 20, 30], "regression": [0.0, 0.1, 0.2, 0.3, 0.4, 0.6],
                    "promoted": [0, -25, -50, -100, -150]}
    rows = []
    for k, reg, prom in itertools.product(grid["k"], grid["regression"], grid["promoted"]):
        p = EloParams(k, home, reg, prom)
        r = run_elo(matches[matches.season <= max(tune_seasons)], p)
        sel = r[r.season.isin(tune_seasons)]
        y = outcome(sel.home_goals.to_numpy(), sel.away_goals.to_numpy())
        theta = fit_ordinal(sel.elo_diff.to_numpy(), y)
        rows.append({**asdict(p), "rps": _rps(ordinal_probs(sel.elo_diff.to_numpy(), theta), y)})
    table = pd.DataFrame(rows).sort_values("rps").reset_index(drop=True)
    best = table.iloc[0]
    return EloParams(float(best.k), home, float(best.regression), float(best.promoted)), table


def ratings_table(r: pd.DataFrame) -> pd.DataFrame:
    """Formato longo para o banco: rating de cada time depois de cada jogo."""
    h = pd.DataFrame({"season": r.season, "round": r["round"], "kickoff_utc": r.kickoff_utc.astype(str),
                      "team_id": r.home_id, "opp_id": r.away_id, "elo_antes": r.elo_h_antes, "elo": r.elo_h_depois})
    a = pd.DataFrame({"season": r.season, "round": r["round"], "kickoff_utc": r.kickoff_utc.astype(str),
                      "team_id": r.away_id, "opp_id": r.home_id, "elo_antes": r.elo_a_antes, "elo": r.elo_a_depois})
    return pd.concat([h, a]).sort_values(["kickoff_utc", "team_id"]).reset_index(drop=True)
