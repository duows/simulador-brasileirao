"""Validação walk-forward por temporada, métricas e baselines.

Para prever a temporada S, os pesos são ajustados só com temporadas < S. Os fatores
de cada jogo de S usam só o que aconteceu antes daquele jogo (ver features.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model.features import build_features
from ..model.poisson import expected_goals, fit, outcome_probs

OUTCOMES = ["mandante", "empate", "visitante"]


def outcome_index(hg, ag) -> np.ndarray:
    hg, ag = np.asarray(hg, float), np.asarray(ag, float)
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    """Brier multiclasse: soma dos erros quadráticos nas 3 classes (0 = perfeito, 2 = pior)."""
    onehot = np.eye(3)[y]
    return float(np.mean(np.sum((p - onehot) ** 2, axis=1)))


def log_loss(p: np.ndarray, y: np.ndarray, eps: float = 1e-15) -> float:
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], eps, 1))))


def accuracy(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(p.argmax(axis=1) == y))


def calibration_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Para cada resultado: probabilidade média estimada x frequência observada, por faixa."""
    rows = []
    edges = np.linspace(0, 1, bins + 1)
    for k, name in enumerate(OUTCOMES):
        pk, hit = p[:, k], (y == k).astype(float)
        idx = np.clip(np.digitize(pk, edges) - 1, 0, bins - 1)
        for b in range(bins):
            sel = idx == b
            if sel.sum() == 0:
                continue
            rows.append({"resultado": name, "faixa": f"{edges[b]:.0%}-{edges[b + 1]:.0%}",
                         "n": int(sel.sum()), "estimado": float(pk[sel].mean()),
                         "observado": float(hit[sel].mean())})
    return pd.DataFrame(rows)


def baseline_home(n: int) -> np.ndarray:
    """'Sempre mandante': 100% para a vitória do mandante."""
    return np.tile([1.0, 0.0, 0.0], (n, 1))


def baseline_freq(train_y: np.ndarray, n: int) -> np.ndarray:
    """Frequência histórica de vitória do mandante, empate e vitória do visitante."""
    freq = np.bincount(train_y, minlength=3) / len(train_y)
    return np.tile(freq, (n, 1))


def walk_forward(matches: pd.DataFrame, cfg: dict, seasons: list[int], half_life: float,
                 feat: pd.DataFrame | None = None) -> pd.DataFrame:
    """Previsões fora da amostra para cada jogo das temporadas pedidas."""
    mcfg = cfg["model"]
    if feat is None:
        feat = build_features(matches, mcfg, half_life_days=half_life)
    done = feat[(feat.status == "FINISHED") & feat.home_goals.notna()]
    first = int(mcfg["train_first_season"])
    out = []
    for s in seasons:
        train = done[(done.season >= first) & (done.season < s)]
        test = done[done.season == s].copy()
        if train.empty or test.empty:
            continue
        w = fit(train, mcfg, half_life, bootstrap=0)
        lh, la = expected_goals(test, w)
        p = outcome_probs(lh, la, w.rho, mcfg["max_goals"])
        ytr = outcome_index(train.home_goals, train.away_goals)
        pf = baseline_freq(ytr, len(test))
        test["lambda_h"], test["lambda_a"] = lh, la
        test[["p_h", "p_d", "p_a"]] = p
        test[["f_h", "f_d", "f_a"]] = pf
        out.append(test)
    return pd.concat(out, ignore_index=True)


def score(pred: pd.DataFrame) -> dict[str, dict[str, float]]:
    y = outcome_index(pred.home_goals, pred.away_goals)
    p = pred[["p_h", "p_d", "p_a"]].to_numpy()
    f = pred[["f_h", "f_d", "f_a"]].to_numpy()
    h = baseline_home(len(pred))
    return {
        "modelo": {"brier": brier(p, y), "log_loss": log_loss(p, y), "acerto": accuracy(p, y)},
        "frequencia_historica": {"brier": brier(f, y), "log_loss": log_loss(f, y),
                                 "acerto": accuracy(f, y)},
        "sempre_mandante": {"brier": brier(h, y), "log_loss": log_loss(h, y),
                            "acerto": accuracy(h, y)},
    }


def tune_half_life(matches: pd.DataFrame, cfg: dict) -> tuple[float, pd.DataFrame]:
    """Escolhe a meia-vida pelo menor log loss nas temporadas de ajuste (anteriores ao teste)."""
    rows = []
    for hl in cfg["model"]["half_life_grid"]:
        pred = walk_forward(matches, cfg, cfg["backtest"]["tune_seasons"], hl)
        sc = score(pred)["modelo"]
        rows.append({"meia_vida_dias": hl, **sc, "n": len(pred)})
    table = pd.DataFrame(rows)
    best = float(table.sort_values("log_loss").iloc[0]["meia_vida_dias"])
    return best, table
