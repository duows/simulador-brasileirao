from pathlib import Path

import pytest

from futdados.config import ROOT
from futdados.teams import UnknownTeamError, display_name, normalize_key, team_id, try_team_id

REPO = ROOT / "data" / "external" / "footballcsv-cache.wfb"


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


@pytest.mark.skipif(not (REPO / "2010" / "br.1.csv").exists(), reason="footballcsv não baixado")
def test_all_historical_names_resolve():
    import pandas as pd

    for season in range(2010, 2025):
        df = pd.read_csv(REPO / str(season) / "br.1.csv", dtype=str)
        for name in set(df["Team 1"]) | set(df["Team 2"]):
            team_id(name)


@pytest.mark.parametrize("name, expected", [
    ("Flamengo RJ", "flamengo"), ("Grêmio Porto Alegre", "gremio"), ("Atlético Goianiense", "atletico-go"),
    ("Athletico Paranaense", "athletico-pr"), ("Atlético Mineiro", "atletico-mg"), ("Vasco da Gama RJ", "vasco"),
])
def test_footballcsv_names(name, expected):
    assert team_id(name) == expected
