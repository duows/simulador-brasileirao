import math

import numpy as np
import pandas as pd
import pytest

from futdados.config import load_config
from futdados.model.features import FEATURES, build_features
from futdados.model.poisson import Weights, decompose, fit, outcome_probs, score_matrix

MCFG = load_config()["model"]


def synthetic_matches(n_seasons=4, seed=1):
    """Liga fictícia de 10 times com forças fixas conhecidas."""
    rng = np.random.default_rng(seed)
    teams = [f"t{i}" for i in range(10)]
    strength = dict(zip(teams, np.linspace(-0.3, 0.3, 10)))
    rows, day = [], pd.Timestamp("2010-01-01", tz="UTC")
    for s in range(n_seasons):
        rnd = 0
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                rnd += 1
                day += pd.Timedelta(days=1)
                lh = math.exp(0.1 + 0.3 + strength[h] - strength[a])
                la = math.exp(0.1 + strength[a] - strength[h])
                rows.append(dict(season=2010 + s, round=rnd // 5 + 1, kickoff_utc=day, status="FINISHED",
                                 home_id=h, away_id=a, home_goals=rng.poisson(lh),
                                 away_goals=rng.poisson(la), home_coach=None, away_coach=None))
    return pd.DataFrame(rows)


def test_features_do_not_leak_future():
    m = synthetic_matches(2)
    f1 = build_features(m, MCFG, half_life_days=180)
    m2 = m.copy()
    cut = m2.kickoff_utc.iloc[100]
    m2.loc[m2.kickoff_utc > cut, ["home_goals", "away_goals"]] = 9  # muda o futuro
    f2 = build_features(m2, MCFG, half_life_days=180)
    cols = [f"{c}_h" for c in FEATURES] + [f"{c}_a" for c in FEATURES]
    upto = f1.kickoff_utc <= cut + pd.Timedelta(days=1)  # inclui o jogo seguinte ao corte
    pd.testing.assert_frame_equal(f1.loc[upto, cols], f2.loc[upto, cols])


def test_fit_recovers_home_advantage():
    feat = build_features(synthetic_matches(6), MCFG, half_life_days=365)
    w = fit(feat[feat.season >= 2011], {**MCFG, "dixon_coles": False}, 365, bootstrap=0)
    assert w.coef["mando"] == pytest.approx(0.3, abs=0.08)
    assert w.coef["ataque"] > 0.3 and w.coef["defesa_adversario"] > 0.3


def test_score_matrix_and_probs_sum_to_one():
    m = score_matrix(1.6, 0.9, rho=-0.05)
    assert m.sum() == pytest.approx(1.0)
    p = outcome_probs([1.6, 0.5], [0.9, 2.0])
    assert np.allclose(p.sum(axis=1), 1.0)
    assert p[0, 0] > p[0, 2] and p[1, 2] > p[1, 0]


def test_decomposition_sums_to_total():
    w = Weights(intercept=-0.2, coef=dict(zip(FEATURES, [0.7, 0.7, 0.4, 0.03, 0.0, 0.04, -0.02])))
    x = np.array([0.15, -0.1, 1, 0.8, -2, 1, 1])
    base = 1.25 * math.exp(w.intercept)
    dec = decompose(x, base, w)
    total = base * math.exp(float(w.beta() @ x))
    assert sum(d["gols"] for d in dec.values()) == pytest.approx(total - base, abs=1e-9)
    assert dec["mando"]["gols"] > 0 and dec["defesa_adversario"]["gols"] < 0
    # caso degenerado: todos os fatores zerados
    dec0 = decompose(np.zeros(7), base, w)
    assert all(d["gols"] == 0 for d in dec0.values())


def test_new_coach_flag_first_n_matches():
    m = synthetic_matches(1)
    m["home_coach"], m["away_coach"] = "A", "A"
    t0 = m[(m.home_id == "t0") | (m.away_id == "t0")].index
    t0[5]
    for i in t0[5:]:
        col = "home_coach" if m.at[i, "home_id"] == "t0" else "away_coach"
        m.at[i, col] = "B"
    f = build_features(m, MCFG)
    rows = f[(f.home_id == "t0") | (f.away_id == "t0")].reset_index(drop=True)
    flag = np.where(rows.home_id == "t0", rows.raw_newcoach_h, rows.raw_newcoach_a)
    n = MCFG["new_coach_matches"]
    assert list(flag[:5]) == [0] * 5
    assert list(flag[5:5 + n]) == [1] * n
    assert flag[5 + n] == 0


def test_blend_shots_mixes_goals_and_shots():
    import pandas as pd

    from futdados.model.production import blend_shots

    n = 40
    train = pd.DataFrame({"season": [2026] * n, "home_id": [f"h{i}" for i in range(n)], "away_id": [f"a{i}" for i in range(n)],
                          "home_goals": [2] * n, "away_goals": [0] * n})
    shots = pd.DataFrame({"season": [2026] * n, "home_id": train.home_id, "away_id": train.away_id,
                          "sot_h": [4.0] * (n - 1) + [8.0], "sot_a": [2.0] * n})
    out = blend_shots(train, shots, 0.5)
    conv_h = 2 * n / (4.0 * (n - 1) + 8.0)
    assert out.home_goals.iloc[-1] == pytest.approx(0.5 * 2 + 0.5 * conv_h * 8)
    assert out.away_goals.sum() == pytest.approx(0)   # conversão zero quando ninguém fez gol fora
    assert blend_shots(train, shots, 1.0) is train and blend_shots(train, None, 0.5) is train
