"""Regressão de Poisson regularizada (ridge) com pesos explícitos, e matriz de placares.

Gols esperados do time i contra j:
    log(gols_esperados) = log(média da liga) + intercepto + soma(peso_k * fator_k)

Cada peso é um número com significado direto: exp(peso) é o quanto os gols esperados
são multiplicados quando o fator aumenta uma unidade.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

from .. import __version__
from .features import FEATURES, long_format


@dataclass
class Weights:
    intercept: float
    coef: dict[str, float]
    ci_low: dict[str, float] = field(default_factory=dict)
    ci_high: dict[str, float] = field(default_factory=dict)
    feature_std: dict[str, float] = field(default_factory=dict)
    rho: float = 0.0                  # ajuste Dixon-Coles de placares baixos
    half_life_days: float = 180
    train_seasons: list[int] = field(default_factory=list)
    n_matches: int = 0
    fitted_at: str = ""
    model_version: str = ""

    def beta(self) -> np.ndarray:
        return np.array([self.coef[f] for f in FEATURES])

    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path) -> Weights:
        with open(path, encoding="utf-8") as fh:
            return cls(**json.load(fh))


def _fit_ridge(X, y, off, alpha, scale) -> np.ndarray:
    """Minimiza a deviance de Poisson + alpha/2 * soma((peso * desvio-padrão)^2).

    O intercepto não é penalizado. A penalidade em escala padronizada evita que fatores
    medidos em unidades diferentes (dias, pontos, log) sejam punidos de forma desigual.
    """
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    pen = np.concatenate([[0.0], scale**2]) * alpha

    def f(b):
        eta = off + Xb @ b
        mu = np.exp(eta)
        loss = np.sum(mu - y * eta) + 0.5 * np.sum(pen * b * b)
        grad = Xb.T @ (mu - y) + pen * b
        return loss, grad

    res = minimize(f, np.zeros(p + 1), jac=True, method="L-BFGS-B")
    return res.x


def dc_tau(x, y, lh, la, rho):
    """Fator de Dixon-Coles para 0-0, 1-0, 0-1 e 1-1 (corrige a frequência de empates)."""
    tau = np.ones(np.broadcast(x, y, lh).shape)
    tau = np.where((x == 0) & (y == 0), 1 - lh * la * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lh * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + la * rho, tau)
    tau = np.where((x == 1) & (y == 1), 1 - rho, tau)
    return tau


def fit_rho(lh, la, hg, ag) -> float:
    """Estima rho por máxima verossimilhança dados os gols esperados já ajustados."""
    hg, ag = hg.astype(int), ag.astype(int)

    def nll(rho):
        t = dc_tau(hg, ag, lh, la, rho)
        if np.any(t <= 0):
            return 1e12
        return -np.sum(np.log(t))

    return float(minimize_scalar(nll, bounds=(-0.3, 0.3), method="bounded").x)


def fit(feat, mcfg: dict, half_life_days: float, bootstrap: int | None = None,
        seed: int = 0) -> Weights:
    """Ajusta os pesos nos jogos disputados de `feat` (já filtrado para o treino)."""
    feat = feat[feat["status"] == "FINISHED"].dropna(subset=["home_goals"])
    X, y, off, gid = long_format(feat)
    raw_std = X.std(axis=0)
    scale = raw_std.copy()
    scale[scale == 0] = 1.0  # fator sem variação: peso fica 0 (não estimável)
    alpha = float(mcfg["ridge_alpha"])
    b = _fit_ridge(X, y, off, alpha, scale)

    lam = np.exp(off + b[0] + X @ b[1:])
    n = len(feat)
    rho = fit_rho(lam[:n], lam[n:], y[:n], y[n:]) if mcfg.get("dixon_coles", True) else 0.0

    lo, hi = {}, {}
    B = int(mcfg["bootstrap"] if bootstrap is None else bootstrap)
    if B > 0:
        rng = np.random.default_rng(seed)
        draws = []
        for _ in range(B):
            games = rng.integers(0, n, n)          # reamostra JOGOS (as duas linhas juntas)
            idx = np.concatenate([games, games + n])
            draws.append(_fit_ridge(X[idx], y[idx], off[idx], alpha, scale))
        draws = np.array(draws)
        q_lo, q_hi = np.percentile(draws, [2.5, 97.5], axis=0)
        lo = {f: float(q_lo[i + 1]) for i, f in enumerate(FEATURES)}
        hi = {f: float(q_hi[i + 1]) for i, f in enumerate(FEATURES)}
        lo["intercepto"], hi["intercepto"] = float(q_lo[0]), float(q_hi[0])

    w = Weights(
        intercept=float(b[0]),
        coef={f: float(b[i + 1]) for i, f in enumerate(FEATURES)},
        ci_low=lo, ci_high=hi,
        feature_std={f: float(raw_std[i]) for i, f in enumerate(FEATURES)},
        rho=rho, half_life_days=float(half_life_days),
        train_seasons=sorted(int(s) for s in feat["season"].unique()),
        n_matches=int(n),
        fitted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    digest = hashlib.sha1(json.dumps([w.intercept, w.coef, w.rho, w.half_life_days,
                                      w.train_seasons]).encode()).hexdigest()[:8]
    w.model_version = f"futdados-{__version__}+{digest}"
    return w


# ------------------------------------------------------------------ previsão
def expected_goals(feat, w: Weights) -> tuple[np.ndarray, np.ndarray]:
    beta = w.beta()
    xh = feat[[f"{c}_h" for c in FEATURES]].to_numpy(float)
    xa = feat[[f"{c}_a" for c in FEATURES]].to_numpy(float)
    base = np.log(feat["mu"].to_numpy(float)) + w.intercept
    return np.exp(base + xh @ beta), np.exp(base + xa @ beta)


def score_matrix(lh: float, la: float, rho: float = 0.0, max_goals: int = 10) -> np.ndarray:
    """Matriz P[gols_mandante, gols_visitante]. Soma 1 (renormalizada)."""
    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    if rho:
        xx, yy = np.meshgrid(g, g, indexing="ij")
        m = m * dc_tau(xx, yy, lh, la, rho)
    return m / m.sum()


def outcome_probs(lh, la, rho=0.0, max_goals=10) -> np.ndarray:
    """Vetorizado: devolve array (n, 3) com P(mandante), P(empate), P(visitante)."""
    lh, la = np.atleast_1d(lh), np.atleast_1d(la)
    out = np.empty((len(lh), 3))
    for i, (a, b) in enumerate(zip(lh, la)):
        m = score_matrix(a, b, rho, max_goals)
        out[i] = [np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()]
    return out


def decompose(x: np.ndarray, base: float, w: Weights) -> dict[str, dict[str, float]]:
    """Quanto cada fator somou ou tirou dos gols esperados (em gols).

    Usa a média logarítmica (decomposição LMDI): a soma das contribuições é exatamente
    gols_esperados - gols_base, e cada fator recebe a parte proporcional ao seu termo
    peso * fator na escala log.
    """
    beta = w.beta()
    terms = beta * x
    lam = base * math.exp(terms.sum())
    L = lam if abs(lam - base) < 1e-12 else (lam - base) / math.log(lam / base)
    return {f: {"valor": float(x[i]), "peso": float(beta[i]),
                "multiplicador": float(math.exp(terms[i])),
                "gols": float(terms[i] * L)}
            for i, f in enumerate(FEATURES)}
