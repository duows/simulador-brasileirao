import numpy as np
import pandas as pd
import pytest

from futdados.metrics import _current, _longest, build_all, fit_pythagorean, gini, team_games
from futdados.simulate.schedule import round_robin


def _league(seasons=(2030, 2031), seed=0):
    rng = np.random.default_rng(seed)
    teams = [f"t{i:02d}" for i in range(20)]
    rows = []
    for s in seasons:
        for r, games in enumerate(round_robin(teams), start=1):
            for h, a in games:
                rows.append(dict(season=s, round=r, home_id=h, away_id=a, status="FINISHED",
                                 home_goals=int(rng.poisson(1.5)), away_goals=int(rng.poisson(1.1)),
                                 kickoff_utc=pd.Timestamp(f"{s}-04-01", tz="UTC") + pd.Timedelta(days=7 * r),
                                 source="teste"))
    return pd.DataFrame(rows)


def test_streak_helpers():
    flags = [True, True, False, True, True, True]
    assert _longest(flags) == 3 and _current(flags) == 3
    assert _current([True, False]) == 0


def test_gini_bounds():
    assert gini(np.array([10, 10, 10])) == pytest.approx(0)
    assert gini(np.array([0, 0, 30])) > 0.6


def test_round_and_season_tables_are_consistent():
    m = _league()
    out = build_all(m)
    trs, tss, lss = out["team_round_stats"], out["team_season_stats"], out["league_season_stats"]
    last = trs[trs["round"] == 38].set_index(["season", "team_id"])
    full = tss.set_index(["season", "team_id"])
    assert (last.loc[full.index, "pts"] == full.pts).all()
    assert (full.j == 38).all() and (full.v + full.e + full.d == 38).all()
    # pontos totais = 3 por vitória + 1 por empate (2 por jogo empatado)
    g = team_games(m)
    assert tss.pts.sum() == g.pts.sum()
    assert sorted(trs[(trs.season == 2030) & (trs["round"] == 10)].posicao) == list(range(1, 21))
    assert (lss.pts_campeao >= lss.pts_vice).all() and len(lss) == 2
    leader = trs[trs.posicao == 1]
    assert (leader.dist_lider == 0).all()


def test_pythagorean_fit_recovers_relation():
    rng = np.random.default_rng(1)
    gp = rng.integers(30, 70, 200).astype(float)
    gc = rng.integers(30, 70, 200).astype(float)
    k = 1.5
    ppg = 0.1 + 2.5 * gp**k / (gp**k + gc**k)
    df = pd.DataFrame({"gp": gp, "gc": gc, "pts": ppg * 38, "j": 38})
    kk, a, b = fit_pythagorean(df)
    assert kk == pytest.approx(1.5, abs=0.05) and a == pytest.approx(0.1, abs=0.05)
