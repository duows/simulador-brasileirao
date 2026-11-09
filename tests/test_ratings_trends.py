import numpy as np
import pandas as pd
import pytest

from futdados.ratings.elo import EloParams, calibrate, empirical_home, fit_ordinal, ordinal_probs, outcome, run_elo
from futdados.simulate.schedule import round_robin
from futdados.trends import analyze, change_point, eras


def _league(seasons=(2030, 2031, 2032), seed=2):
    rng = np.random.default_rng(seed)
    teams = [f"t{i:02d}" for i in range(8)]
    strength = dict(zip(teams, np.linspace(-0.5, 0.5, 8)))
    rows = []
    for s in seasons:
        for r, games in enumerate(round_robin(teams), start=1):
            for h, a in games:
                lh, la = np.exp(0.3 + strength[h] - strength[a]), np.exp(strength[a] - strength[h])
                rows.append(dict(season=s, round=r, home_id=h, away_id=a, status="FINISHED",
                                 home_goals=int(rng.poisson(lh)), away_goals=int(rng.poisson(la)),
                                 kickoff_utc=pd.Timestamp(f"{s}-04-01", tz="UTC") + pd.Timedelta(days=7 * r)))
    return pd.DataFrame(rows), strength


def test_elo_is_zero_sum_and_ranks_strength():
    m, strength = _league()
    r = run_elo(m, EloParams(k=20, home=60, regression=0.0, promoted=0))
    gain = (r.elo_h_depois - r.elo_h_antes) + (r.elo_a_depois - r.elo_a_antes)
    assert np.allclose(gain, 0)
    last = pd.concat([r[["home_id", "elo_h_depois"]].set_axis(["t", "elo"], axis=1),
                      r[["away_id", "elo_a_depois"]].set_axis(["t", "elo"], axis=1)]).groupby("t").elo.last()
    corr = np.corrcoef([strength[t] for t in last.index], last.to_numpy())[0, 1]
    assert corr > 0.8 and last.idxmin() in ("t00", "t01")


def test_ordinal_probabilities_valid_and_monotone():
    m, _ = _league()
    r = run_elo(m, EloParams())
    theta = fit_ordinal(r.elo_diff.to_numpy(), outcome(r.home_goals, r.away_goals))
    p = ordinal_probs(np.array([-200, 0, 200]), theta)
    assert np.allclose(p.sum(axis=1), 1) and (p > 0).all()
    assert p[0, 0] < p[1, 0] < p[2, 0]


def test_calibration_runs_and_home_from_data():
    m, _ = _league()
    assert 0 < empirical_home(m, [2031]) < 300
    best, table = calibrate(m, [2031, 2032], {"k": [10, 20], "regression": [0, 0.3], "promoted": [0]})
    assert len(table) == 4 and best.k in (10, 20)


def test_trend_labels_need_signal():
    years = list(range(2006, 2026))
    rising = analyze(years, [50 + 1.5 * i for i in range(20)])
    assert rising["rotulo"] == "em alta" and rising["theil_sen"]["inclinacao"] == pytest.approx(1.5)
    rng = np.random.default_rng(0)
    noise = analyze(years, list(rng.normal(60, 5, 20)))
    assert noise["rotulo"] == "sem tendência clara"
    assert "frágeis" in noise["aviso"]


def test_change_point_and_eras():
    y = np.array([10.0] * 8 + [20.0] * 8)
    assert change_point(y) == 8
    assert change_point(np.full(12, 5.0)) is None
    e = eras(list(range(2006, 2027)), [1.0] * 7 + [1.0] * 7 + [5.0] * 7)
    assert e["diferenca_clara"]
