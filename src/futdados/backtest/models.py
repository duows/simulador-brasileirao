"""Placar entre modelos em validação walk-forward por temporada (sem vazamento).

Para prever a temporada S, cada modelo só usa jogos de temporadas < S para estimar parâmetros;
fatores e ratings de cada jogo usam só o que aconteceu antes dele. O conjunto e a calibração usam
só previsões fora da amostra de temporadas anteriores a S (validação aninhada).

Modelos:
- base_freq, base_mandante, base_elo: os três baselines.
- poisson: modelo transparente atual (7 fatores, ridge, meia-vida).
- dixon_coles: poisson + ajuste de placares baixos (rho estimado no treino).
- forcas_map: ataque e defesa por time com prior gaussiano (MAP), decaimento temporal e mando
  comum, reajustado a cada rodada; incerteza por aproximação de Laplace.
- ordinal: logística ordinal V/E/D com diferença de Elo, de ataque e de defesa, forma, mando
  implícito, descanso e meio de semana.
- boosting: HistGradientBoosting nos mesmos fatores (só entra se ganhar de forma consistente).
- conjunto: média ponderada (pesos por RPS nas 5 temporadas anteriores).
- conjunto_calibrado: conjunto + temperatura estimada nas temporadas anteriores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, softmax
from scipy.stats import poisson as poisson_dist

from ..model.features import FEATURES, build_features
from ..model.poisson import expected_goals, fit, outcome_probs
from ..ratings.elo import EloParams, fit_ordinal, ordinal_probs, run_elo
from .walkforward import brier, log_loss, outcome_index, rps

KEYS = ["season", "home_id", "away_id"]


# ------------------------------------------------------------ métricas
def metrics(p: np.ndarray, y: np.ndarray) -> dict:
    return {"rps": rps(p, y), "log_loss": log_loss(p, y), "brier": brier(p, y),
            "acerto": float(np.mean(p.argmax(1) == y))}


def season_bootstrap_diff(df: pd.DataFrame, a: str, b: str, n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Diferença média de RPS (a - b) e IC 90% reamostrando TEMPORADAS inteiras."""
    per = df.groupby("season").apply(lambda g: pd.Series({"a": g[f"rps_{a}"].mean(), "b": g[f"rps_{b}"].mean(),
                                                           "n": len(g)}), include_groups=False)
    rng = np.random.default_rng(seed)
    s = per.index.to_numpy()
    diffs = []
    for _ in range(n):
        pick = per.loc[rng.choice(s, len(s))]
        diffs.append(np.average(pick.a - pick.b, weights=pick.n))
    point = float(np.average(per.a - per.b, weights=per.n))
    lo, hi = np.percentile(diffs, [5, 95])
    return point, float(lo), float(hi)


def per_match_rps(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    onehot = np.eye(3)[y]
    cp, co = np.cumsum(p, axis=1)[:, :2], np.cumsum(onehot, axis=1)[:, :2]
    return np.sum((cp - co) ** 2, axis=1) / 2


# ------------------------------------------------------------ modelos
def _ordinal_multi_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Logística ordinal com vários fatores (ridge leve). Parâmetros: betas, c1, log(c2-c1)."""
    p = X.shape[1]

    def nll(theta):
        b, c1, gap = theta[:p], theta[p], theta[p + 1]
        c2 = c1 + np.exp(gap)
        eta = X @ b
        pa, pl = expit(c1 - eta), expit(c2 - eta)
        probs = np.stack([1 - pl, pl - pa, pa], 1)
        return -np.sum(np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1))) + alpha * np.sum(b**2)

    res = minimize(nll, np.concatenate([np.zeros(p), [-1.0, 0.0]]), method="L-BFGS-B")
    return res.x


def _ordinal_multi_probs(X: np.ndarray, theta: np.ndarray) -> np.ndarray:
    p = X.shape[1]
    b, c1, c2 = theta[:p], theta[p], theta[p] + np.exp(theta[p + 1])
    eta = X @ b
    pa, pl = expit(c1 - eta), expit(c2 - eta)
    return np.stack([1 - pl, pl - pa, pa], 1)


ORD_COLS = ["elo_diff", "atk_diff", "def_diff", "forma_h", "descanso_h", "meio_de_semana_h"]


def design(feat: pd.DataFrame) -> np.ndarray:
    X = pd.DataFrame({
        "elo_diff": feat.elo_diff / 100, "atk_diff": feat.ataque_h - feat.ataque_a,
        "def_diff": feat.defesa_adversario_h - feat.defesa_adversario_a, "forma_h": feat.forma_h,
        "descanso_h": feat.descanso_h / 3, "meio_de_semana_h": feat.meio_de_semana_h,
    })
    return X[ORD_COLS].to_numpy(float)


def forcas_map_season(matches: pd.DataFrame, season: int, half_life: float = 365, prior_sd: float = 0.3) -> pd.DataFrame:
    """Para cada rodada da temporada, ajusta ataque/defesa por time com jogos anteriores (MAP) e prevê."""
    hist = matches[(matches.status == "FINISHED") & matches.home_goals.notna()].copy()
    hist["kickoff_utc"] = pd.to_datetime(hist.kickoff_utc, utc=True)
    target = hist[hist.season == season]
    out = []
    for _rnd, games in target.groupby("round"):
        start = games.kickoff_utc.min()
        train = hist[(hist.kickoff_utc < start) & (hist.season >= season - 3)]
        teams = sorted(set(train.home_id) | set(train.away_id) | set(games.home_id) | set(games.away_id))
        ix = {t: i for i, t in enumerate(teams)}
        T = len(teams)
        hi, ai = train.home_id.map(ix).to_numpy(), train.away_id.map(ix).to_numpy()
        hg, ag = train.home_goals.to_numpy(float), train.away_goals.to_numpy(float)
        age = (start - train.kickoff_utc).dt.total_seconds().to_numpy() / 86400
        wt = 0.5 ** (age / half_life)

        def nll(theta):
            atk, dfn, mu, home = theta[:T], theta[T:2 * T], theta[2 * T], theta[2 * T + 1]
            lh = np.exp(mu + home + atk[hi] + dfn[ai])
            la = np.exp(mu + atk[ai] + dfn[hi])
            ll = np.sum(wt * (hg * np.log(lh) - lh + ag * np.log(la) - la))
            return -ll + 0.5 * np.sum(atk**2 + dfn**2) / prior_sd**2

        res = minimize(nll, np.zeros(2 * T + 2), method="L-BFGS-B")
        th = res.x
        atk, dfn, mu, home = th[:T], th[T:2 * T], th[2 * T], th[2 * T + 1]
        gh, ga_ = games.home_id.map(ix).to_numpy(), games.away_id.map(ix).to_numpy()
        lh = np.exp(mu + home + atk[gh] + dfn[ga_])
        la = np.exp(mu + atk[ga_] + dfn[gh])
        p = outcome_probs(lh, la)
        out.append(pd.DataFrame({"season": season, "home_id": games.home_id.to_numpy(), "away_id": games.away_id.to_numpy(),
                                 "p_h": p[:, 0], "p_d": p[:, 1], "p_a": p[:, 2], "lh": lh, "la": la}))
    return pd.concat(out, ignore_index=True)


def all_oos(matches: pd.DataFrame, cfg: dict, seasons: list[int], elo_params: EloParams,
            half_life: float, first_train: int) -> pd.DataFrame:
    """Previsões fora da amostra de todos os modelos (uma linha por jogo)."""
    mcfg = cfg["model"]
    feat = build_features(matches, mcfg, half_life_days=half_life)
    elo = run_elo(matches, elo_params)[KEYS + ["elo_diff"]]
    feat = feat.merge(elo, on=KEYS, how="left")
    done = feat[(feat.status == "FINISHED") & feat.home_goals.notna()].copy()
    done["y"] = outcome_index(done.home_goals, done.away_goals)
    rows = []
    for s in seasons:
        train = done[(done.season >= first_train) & (done.season < s)]
        test = done[done.season == s].copy()
        if train.empty or test.empty:
            continue
        ytr = train.y.to_numpy()
        # baselines
        freq = np.bincount(ytr, minlength=3) / len(ytr)
        test[["base_freq_h", "base_freq_d", "base_freq_a"]] = np.tile(freq, (len(test), 1))
        test[["base_mandante_h", "base_mandante_d", "base_mandante_a"]] = np.tile([1.0, 0, 0], (len(test), 1))
        th = fit_ordinal(train.elo_diff.to_numpy(), ytr)
        test[["base_elo_h", "base_elo_d", "base_elo_a"]] = ordinal_probs(test.elo_diff.to_numpy(), th)
        # Poisson e Dixon-Coles
        w = fit(train, {**mcfg, "dixon_coles": True}, half_life, bootstrap=0)
        lh, la = expected_goals(test, w)
        test[["poisson_h", "poisson_d", "poisson_a"]] = outcome_probs(lh, la, 0.0)
        test[["dixon_coles_h", "dixon_coles_d", "dixon_coles_a"]] = outcome_probs(lh, la, w.rho)
        test["lh_poisson"], test["la_poisson"], test["rho"] = lh, la, w.rho
        # ordinal com fatores
        Xtr, Xte = design(train), design(test)
        theta = _ordinal_multi_fit(Xtr, ytr)
        test[["ordinal_h", "ordinal_d", "ordinal_a"]] = _ordinal_multi_probs(Xte, theta)
        # boosting
        from sklearn.ensemble import HistGradientBoostingClassifier

        gb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3, l2_regularization=1.0,
                                            random_state=0)
        gb.fit(Xtr, ytr)
        test[["boosting_h", "boosting_d", "boosting_a"]] = gb.predict_proba(Xte)
        # forças por time (MAP), reajustado a cada rodada
        fm = forcas_map_season(matches, s)
        test = test.merge(fm.rename(columns={"p_h": "forcas_map_h", "p_d": "forcas_map_d", "p_a": "forcas_map_a",
                                             "lh": "lh_forcas", "la": "la_forcas"}), on=KEYS, how="left")
        rows.append(test)
    return pd.concat(rows, ignore_index=True)


BASE_MODELS = ["base_freq", "base_mandante", "base_elo", "poisson", "dixon_coles", "forcas_map", "ordinal", "boosting"]
ENSEMBLE_PARTS = ["poisson", "base_elo", "ordinal", "forcas_map"]


def probs(df: pd.DataFrame, model: str) -> np.ndarray:
    return df[[f"{model}_h", f"{model}_d", f"{model}_a"]].to_numpy(float)


def add_ensemble(df: pd.DataFrame, lookback: int = 5) -> tuple[pd.DataFrame, dict]:
    """Conjunto com pesos estimados em temporadas anteriores (simplex via softmax) e temperatura."""
    out, info = [], {}
    seasons = sorted(df.season.unique())
    for s in seasons:
        prev = df[(df.season < s) & (df.season >= s - lookback)]
        cur = df[df.season == s].copy()
        if len(prev) < 300:
            wts = np.ones(len(ENSEMBLE_PARTS)) / len(ENSEMBLE_PARTS)
            temp = 1.0
        else:
            yp = prev.y.to_numpy()
            P = np.stack([probs(prev, m) for m in ENSEMBLE_PARTS])

            def obj(z):
                return rps(np.tensordot(softmax(z), P, axes=1), yp)

            wts = softmax(minimize(obj, np.zeros(len(ENSEMBLE_PARTS)), method="Nelder-Mead").x)
            pe = np.tensordot(wts, P, axes=1)

            def tobj(lt):
                q = pe ** (1 / np.exp(lt))
                return log_loss(q / q.sum(1, keepdims=True), yp)

            temp = float(np.exp(minimize(tobj, [0.0], method="Nelder-Mead").x[0]))
        Pc = np.stack([probs(cur, m) for m in ENSEMBLE_PARTS])
        pe = np.tensordot(wts, Pc, axes=1)
        cur[["conjunto_h", "conjunto_d", "conjunto_a"]] = pe
        q = pe ** (1 / temp)
        cur[["conjunto_calibrado_h", "conjunto_calibrado_d", "conjunto_calibrado_a"]] = q / q.sum(1, keepdims=True)
        info[int(s)] = {"pesos": dict(zip(ENSEMBLE_PARTS, map(float, wts))), "temperatura": temp}
        out.append(cur)
    return pd.concat(out, ignore_index=True), info


ALL_MODELS = BASE_MODELS + ["conjunto", "conjunto_calibrado"]


def scoreboard(df: pd.DataFrame, eval_seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = df[df.season.isin(eval_seasons)].copy()
    y = d.y.to_numpy()
    rows, per = [], []
    for m in ALL_MODELS:
        p = probs(d, m)
        d[f"rps_{m}"] = per_match_rps(p, y)
        rows.append({"modelo": m, **metrics(p, y)})
        for s, g in d.groupby("season"):
            per.append({"modelo": m, "season": int(s), "rps": float(g[f"rps_{m}"].mean())})
    table = pd.DataFrame(rows).sort_values("rps").reset_index(drop=True)
    per = pd.DataFrame(per)
    return table, per, d


def goal_mae(d: pd.DataFrame) -> dict:
    out = {}
    for name, (h, a) in {"poisson": ("lh_poisson", "la_poisson"), "forcas_map": ("lh_forcas", "la_forcas")}.items():
        out[name] = float(np.mean(np.abs(d[h] - d.home_goals) + np.abs(d[a] - d.away_goals)) / 2)
    return out


def overdispersion(d: pd.DataFrame) -> dict:
    """Razão variância/média dos gols condicionada ao modelo (≈1 = Poisson basta; >1 = Binomial Negativa)."""
    y = np.concatenate([d.home_goals, d.away_goals]).astype(float)
    lam = np.concatenate([d.lh_poisson, d.la_poisson])
    pearson = float(np.mean((y - lam) ** 2 / lam))
    # probabilidade de 0 gols: observada x Poisson
    p0_obs = float(np.mean(y == 0))
    p0_mod = float(np.mean(poisson_dist.pmf(0, lam)))
    return {"dispersao_pearson": pearson, "zero_gols_observado": p0_obs, "zero_gols_poisson": p0_mod}


def ablation(matches: pd.DataFrame, cfg: dict, seasons: list[int], half_life: float, first_train: int) -> pd.DataFrame:
    """Para cada fator do Poisson: RPS fora da amostra com e sem ele (IC 90% por temporadas)."""
    mcfg = cfg["model"]
    feat = build_features(matches, mcfg, half_life_days=half_life)
    done = feat[(feat.status == "FINISHED") & feat.home_goals.notna()].copy()
    y_all = outcome_index(done.home_goals, done.away_goals)
    done["y"] = y_all

    def run(drop: str | None) -> pd.Series:
        res = []
        for s in seasons:
            train = done[(done.season >= first_train) & (done.season < s)].copy()
            test = done[done.season == s].copy()
            if drop:
                for side in ("h", "a"):
                    train[f"{drop}_{side}"] = 0.0
                    test[f"{drop}_{side}"] = 0.0
            w = fit(train, mcfg, half_life, bootstrap=0)
            lh, la = expected_goals(test, w)
            res.append(pd.Series(per_match_rps(outcome_probs(lh, la), test.y.to_numpy()), index=test.index))
        return pd.concat(res)

    full = run(None)
    rows = []
    for f in FEATURES:
        if np.concatenate([done[f"{f}_h"], done[f"{f}_a"]]).std() == 0:
            rows.append({"fator": f, "delta_rps": np.nan, "ic90": [np.nan, np.nan], "decisao": "sem dados (fator constante)"})
            continue
        without = run(f)
        diff = (without - full)
        per = diff.groupby(done.loc[diff.index, "season"]).mean()
        rng = np.random.default_rng(0)
        boots = [rng.choice(per.to_numpy(), len(per)).mean() for _ in range(2000)]
        lo, hi = np.percentile(boots, [5, 95])
        rows.append({"fator": f, "delta_rps": float(diff.mean()), "ic90": [float(lo), float(hi)],
                     "decisao": "mantém (ajuda)" if lo > 0 else ("neutro" if hi >= 0 else "piora")})
    return pd.DataFrame(rows)
