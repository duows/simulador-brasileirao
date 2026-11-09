import numpy as np
import pandas as pd

from futdados.config import load_config
from futdados.model.features import FEATURES
from futdados.model.poisson import Weights
from futdados.simulate.montecarlo import rank, simulate_season

CFG = load_config()
CRIT = CFG["simulation"]["tiebreakers"]


def _stats(pts, w, gd, gf):
    return {"pts": np.array([pts], float), "w": np.array([w], float),
            "gd": np.array([gd], float), "gf": np.array([gf], float)}


def test_rank_order_points_wins_gd_gf():
    st = _stats([10, 10, 10, 12], [3, 3, 2, 3], [5, 2, 9, 0], [8, 8, 9, 1])
    h2h = np.zeros((1, 4, 4))
    pos = rank(st, h2h, CRIT, np.random.default_rng(0))[0]
    # time 3 (12 pts) lidera; entre 0,1 (3 vitórias) o saldo decide; time 2 tem menos vitórias
    assert list(pos) == [2, 3, 4, 1]


def test_head_to_head_only_for_two_teams():
    st = _stats([10, 10], [3, 3], [2, 2], [5, 5])
    h2h = np.zeros((1, 2, 2))
    h2h[0, 1, 0] = 3  # time 1 venceu o confronto direto
    for seed in range(5):
        assert list(rank(st, h2h, CRIT, np.random.default_rng(seed))[0]) == [2, 1]
    # com três empatados o confronto direto não se aplica: vira sorteio
    st3 = _stats([10, 10, 10], [3, 3, 3], [2, 2, 2], [5, 5, 5])
    h3 = np.zeros((1, 3, 3))
    h3[0, 1, 0] = 3
    firsts = {tuple(rank(st3, h3, CRIT, np.random.default_rng(s))[0]) for s in range(30)}
    assert len(firsts) > 1


def _season(played_all=False):
    teams = ["a", "b", "c", "d"]
    rows, day, rnd = [], pd.Timestamp("2026-04-01", tz="UTC"), 0
    for h in teams:
        for a in teams:
            if h != a:
                rnd += 1
                day += pd.Timedelta(days=3)
                fin = played_all or rnd <= 6
                rows.append({"season": 2026, "round": (rnd + 1) // 2, "kickoff_utc": day,
                             "status": "FINISHED" if fin else "SCHEDULED", "home_id": h, "away_id": a,
                             "home_goals": 1 if fin else np.nan, "away_goals": 0 if fin else np.nan,
                             "mu": 1.25, **{f"{c}_h": 0.0 for c in FEATURES},
                             **{f"{c}_a": 0.0 for c in FEATURES}})
    df = pd.DataFrame(rows)
    df["mando_h"] = 1
    return df


W = Weights(intercept=-0.2, coef=dict(zip(FEATURES, [0.7, 0.7, 0.4, 0.03, 0.0, 0.04, -0.02])))


def test_simulation_finished_season_is_deterministic():
    tab = simulate_season(_season(True), W, CFG, target_round=6, n_sims=200)
    assert np.allclose(tab.exp_points, tab.pontos_atuais)
    assert np.isclose(tab.p_titulo.sum(), 1.0)


def test_simulation_probabilities_are_consistent():
    tab = simulate_season(_season(False), W, CFG, target_round=6, n_sims=2000, seed=1)
    assert np.isclose(tab.p_titulo.sum(), 1.0)
    assert (tab.p_g4 >= tab.p_titulo - 1e-12).all()
    assert (tab.pos_p10 <= tab.pos_p90).all()
    # pontos esperados entre o mínimo (atuais) e o máximo possível (3 por jogo restante)
    assert (tab.exp_points >= tab.pontos_atuais).all()
    assert (tab.exp_points <= tab.pontos_atuais + 3 * (6 - tab.jogos)).all()
    # cada jogo restante distribui entre 2 e 3 pontos
    remaining = 6
    total = tab.exp_points.sum() - tab.pontos_atuais.sum()
    assert 2 * remaining <= total <= 3 * remaining


def test_round_plan_skips_rounds_with_a_postponed_game():
    from futdados.simulate.montecarlo import round_plan

    df = pd.DataFrame({"round": [1, 1, 2, 2, 3, 3],
                       "status": ["FINISHED", "TIMED", "FINISHED", "FINISHED", "TIMED", "POSTPONED"]})
    nxt, postponed = round_plan(df)
    assert nxt == 3
    assert list(postponed) == [False, True, False, False, False, True]


def test_points_needed_and_decisive_games():
    from futdados.simulate.montecarlo import decisive_games, points_needed

    rng = np.random.default_rng(0)
    pts = rng.integers(30, 90, size=(2000, 20))
    pos = np.argsort(np.argsort(-pts, axis=1), axis=1) + 1  # posição pela pontuação
    zones = {"titulo": [1, 1], "g4": [1, 4], "g6": [1, 6], "rebaixamento": [17, 20]}
    need = points_needed(pts.astype(float), pos, zones)
    assert need["g4"] is not None and need["g4"] >= need["g6"] >= need["permanencia"]
    assert need["titulo"] is None or need["titulo"] >= need["g4"]  # None = nenhuma pontuação garantiu 90%
    # um jogo em que o vencedor sempre termina em 1º: diferença máxima para o título
    todo = pd.DataFrame({"round": [38], "home_id": ["a"], "away_id": ["b"]})
    outcomes = rng.integers(0, 3, size=(2000, 1)).astype(np.int8)
    p2 = np.full((2000, 2), 2)
    p2[outcomes[:, 0] == 0, 0] = 1
    p2[outcomes[:, 0] == 2, 1] = 1
    res = decisive_games(todo, outcomes, p2, {"a": 0, "b": 1}, zones)
    assert res and abs(res[0]["diferenca"]) == 1.0
