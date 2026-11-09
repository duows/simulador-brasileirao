from pathlib import Path

import pytest

from futdados.config import ROOT
from futdados.teams import UnknownTeamError, display_name, normalize_key, team_id, try_team_id

REPO = ROOT / "data" / "external" / "Brasileirao_Dataset"


def test_normalize_strips_accents_and_nbsp():
    assert normalize_key("\xa0São  Paulo\xa0\xa0") == "sao paulo"
    assert normalize_key("Grêmio FBPA") == "gremio fbpa"


@pytest.mark.parametrize("historical, api, expected", [
    ("Sao Paulo", "São Paulo FC", "sao-paulo"),
    ("Palmeiras", "SE Palmeiras", "palmeiras"),
    ("Corinthians", "SC Corinthians Paulista", "corinthians"),
    ("Flamengo", "CR Flamengo", "flamengo"),
    ("Santos", "Santos FC", "santos"),
    ("Athletico-PR", "CA Paranaense", "athletico-pr"),
    ("Atletico-MG", "CA Mineiro", "atletico-mg"),
    ("Bragantino", "Red Bull Bragantino", "bragantino"),
    ("Botafogo-RJ", "Botafogo FR", "botafogo"),
    ("Vasco", "CR Vasco da Gama", "vasco"),
    ("Gremio", "Grêmio FBPA", "gremio"),
    ("Sport Recife", "Sport Club do Recife", "sport"),
])
def test_both_sources_map_to_same_id(historical, api, expected):
    assert team_id(historical) == team_id(api) == expected


def test_athletico_and_atletico_are_different():
    assert team_id("Athletico Paranaense") != team_id("Atlético Mineiro")
    assert team_id("Atletico-GO") == "atletico-go"


def test_unknown_team_raises():
    with pytest.raises(UnknownTeamError):
        team_id("Real Madrid")
    assert try_team_id(None, "XYZ", "SAO") is None
    assert try_team_id("Desconhecido", "São Paulo") == "sao-paulo"


def test_display_name():
    assert display_name("sao-paulo") == "São Paulo"


@pytest.mark.skipif(not (REPO / "campeonato-brasileiro-full.csv").exists(),
                    reason="dataset histórico não baixado")
def test_all_historical_names_resolve():
    import json

    import pandas as pd

    df = pd.read_csv(REPO / "campeonato-brasileiro-full.csv", dtype=str)
    for name in set(df.mandante) | set(df.visitante):
        team_id(name)
    for path in (REPO / "data").glob("brasileirao-*.json"):
        for matches in json.loads(path.read_text(encoding="utf-8")).values():
            for m in matches:
                team_id(m["clubs"]["home"])
                team_id(m["clubs"]["away"])
