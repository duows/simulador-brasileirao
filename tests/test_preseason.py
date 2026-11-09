import json
from collections import Counter

import pandas as pd
import pytest

from futdados.model.features import promoted_prior
from futdados.pipeline import preseason_json, simulate_preseason
from futdados.simulate.schedule import generate_schedule, round_robin

from test_pipeline import AVISO, FORBIDDEN, env  # noqa: F401  (reaproveita a liga fictícia)

ATTRIB = "Football data provided by the Football-Data.org API"


def test_round_robin_is_balanced():
    teams = [f"t{i:02d}" for i in range(20)]
    rounds = round_robin(teams)
    assert len(rounds) == 38
    for games in rounds:  # cada time joga uma vez por rodada
        played = [t for g in games for t in g]
        assert sorted(played) == sorted(teams)
    pairs = Counter((h, a) for games in rounds for h, a in games)
    assert len(pairs) == 380 and set(pairs.values()) == {1}  # cada mando uma vez
    home = Counter(h for games in rounds for h, _ in games)
    assert set(home.values()) == {19}
    first_half_home = Counter(h for games in rounds[:19] for h, _ in games)
    assert set(first_half_home.values()) <= {9, 10}


def test_generated_schedule_dates_are_weekly_saturdays():
    rows = generate_schedule([f"t{i}" for i in range(4)], 2026, "04-11", 22)
    days = sorted({pd.Timestamp(r["kickoff_utc"]) for r in rows})
    assert all(d.weekday() == 5 for d in days)
    assert all((b - a).days == 7 for a, b in zip(days, days[1:]))


def test_promoted_prior_uses_only_past_seasons():
    members = {2020: {"a", "b"}, 2021: {"a", "c"}, 2022: {"a", "d"}}
    stats = {2021: {"a": [30, 10, 10], "c": [10, 30, 10]},   # média da liga: 2 gols por time por jogo
             2022: {"a": [10, 10, 10], "d": [99, 0, 10]}}
    att, dfn, n = promoted_prior(stats, members, 2022)
    assert n == 1  # só o promovido de 2021 (c); 2022 ainda não terminou
    assert att == pytest.approx(0.5) and dfn == pytest.approx(1.5)
    assert promoted_prior(stats, members, 2021) is None


def test_preseason_with_generated_calendar(env):  # noqa: F811
    repo, cfg = env
    teams = ["t0", "t1", "t2", "t3", "t4", "t5"]
    table, meta = simulate_preseason(repo, cfg, 2030, teams=teams, n_sims=300)
    assert meta["calendar"] == "gerado" and len(table) == 6
    assert table.p_titulo.sum() == pytest.approx(1.0)
    assert (table.pos_p10 <= table.pos_p90).all()
    assert (table.pontos_atuais == 0).all()
    path = preseason_json(cfg, table, meta)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["aviso"] == AVISO and doc["atribuicao"] == ATTRIB
    assert doc["alertas"]  # avisa que o calendário é gerado
    text = path.read_text(encoding="utf-8").lower()
    assert not any(w in text for w in FORBIDDEN)


def test_preseason_ignores_results_of_the_season(env):  # noqa: F811
    repo, cfg = env
    table, meta = simulate_preseason(repo, cfg, 2022, n_sims=200)
    assert meta["calendar"].startswith("api")
    assert (table.pontos_atuais == 0).all() and (table.jogos == 0).all()


def test_preseason_requires_calendar_or_teams(env):  # noqa: F811
    repo, cfg = env
    with pytest.raises(ValueError):
        simulate_preseason(repo, cfg, 2031)
