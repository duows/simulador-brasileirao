from pathlib import Path

import pytest

from futdados.config import ROOT
from futdados.finance import FIELDS, read, validate

FILES = [ROOT / "data" / "finance" / "spfc.csv", ROOT / "data" / "finance" / "comparativo_clubes.csv"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_finance_csv_is_valid(path):
    assert not validate(read(path))


def test_spfc_covers_all_fields_and_years():
    rows = read(FILES[0])
    have = {(r["ano"], r["campo"]) for r in rows}
    for year in ("2023", "2024", "2025"):
        for field in FIELDS:
            assert (year, field) in have, f"falta {field} {year} (registre como lacuna se não houver)"


def test_validator_catches_problems():
    base = dict(clube="x", ano="2025", campo="resultado", valor_mil_reais="10", definicao="",
                tipo_fonte="pdf_oficial", fonte_url="", pagina_pdf="", data_consulta="",
                status="conflito", observacao="")
    errs = validate([base])
    assert any("URL" in e for e in errs) and any("página" in e for e in errs)
    assert any("uma fonte só" in e for e in errs)
    pista = {**base, "tipo_fonte": "pista_usuario", "status": "confirmado"}
    assert any("pista" in e for e in validate([pista]))
