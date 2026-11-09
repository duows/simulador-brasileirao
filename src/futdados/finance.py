"""Dataset financeiro: esquema e validação dos CSVs em data/finance.

Regras (ver docs/DECISIONS.md D13):
- valores em R$ mil, na convenção de sinal do balanço (déficit e passivo a descoberto negativos);
- todo número guarda URL da fonte, data de consulta e página do PDF (índice da página no arquivo,
  que pode diferir do número impresso no rodapé);
- fontes divergentes viram duas linhas com status "conflito"; nunca escolhemos em silêncio;
- pistas do usuário entram com tipo_fonte "pista_usuario" e nunca como "confirmado".
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["receita_operacional", "divida_total", "resultado", "passivo_a_descoberto", "venda_atletas",
          "despesa_futebol_profissional", "fidc", "divida_empresarios"]
EXTRA_FIELDS = ["receita_estadio", "obrigacoes_totais", "passivo_total", "patrimonio_liquido"]
COLUMNS = ["clube", "ano", "campo", "valor_mil_reais", "definicao", "tipo_fonte", "fonte_url",
           "pagina_pdf", "data_consulta", "status", "observacao"]
STATUS = {"confirmado", "conflito", "nao_confirmado", "lacuna", "nao_aplicavel"}
SOURCE_TYPES = {"pdf_oficial", "imprensa", "pista_usuario", ""}


def read(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write(path: str | Path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def validate(rows: list[dict]) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = ok)."""
    errors = []
    by_key: dict[tuple, list[dict]] = {}
    for i, r in enumerate(rows, start=2):
        r = {k: ("" if v is None else str(v)) for k, v in r.items()}
        if r["campo"] not in FIELDS + EXTRA_FIELDS:
            errors.append(f"linha {i}: campo desconhecido {r['campo']}")
        if r["status"] not in STATUS:
            errors.append(f"linha {i}: status inválido {r['status']}")
        if r["tipo_fonte"] not in SOURCE_TYPES:
            errors.append(f"linha {i}: tipo_fonte inválido {r['tipo_fonte']}")
        has_value = r["valor_mil_reais"] != ""
        if r["tipo_fonte"] == "pista_usuario" and r["status"] == "confirmado":
            errors.append(f"linha {i}: pista do usuário não pode ser 'confirmado'")
        if has_value and r["tipo_fonte"] != "pista_usuario":
            if not r["fonte_url"].startswith("http"):
                errors.append(f"linha {i}: número sem URL de fonte")
            if not r["data_consulta"]:
                errors.append(f"linha {i}: número sem data de consulta")
            if r["tipo_fonte"] == "pdf_oficial" and not r["pagina_pdf"]:
                errors.append(f"linha {i}: número de PDF sem página")
        if r["status"] == "lacuna" and has_value:
            errors.append(f"linha {i}: lacuna com valor preenchido")
        by_key.setdefault((r["clube"], r["ano"], r["campo"]), []).append(r)
    for key, group in by_key.items():
        conflicts = [g for g in group if g["status"] == "conflito"]
        if conflicts and len(group) < 2:
            errors.append(f"{key}: conflito marcado com uma fonte só")
    return errors
