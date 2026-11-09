"""Normalização de nomes de times entre as fontes (dataset histórico e football-data.org)."""

from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .config import ROOT

TEAMS_CSV = ROOT / "config" / "teams.csv"


class UnknownTeamError(KeyError):
    """Nome de time sem correspondência em config/teams.csv."""


def normalize_key(name: str) -> str:
    """Chave de comparação: sem acento, minúsculas, sem pontuação e espaços extras.

    O dataset histórico traz espaços não separáveis (\xa0) e acentos
    inconsistentes, por isso a comparação é feita sobre esta chave.
    """
    text = unicodedata.normalize("NFKD", name.replace("\xa0", " "))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\- ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[dict[str, str], dict[str, str]]:
    alias_to_id: dict[str, str] = {}
    display: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tid = row["team_id"].strip()
            display[tid] = row["display_name"].strip()
            names = [row["display_name"], tid, *row["aliases"].split("|")]
            for alias in names:
                key = normalize_key(alias)
                if not key:
                    continue
                if key in alias_to_id and alias_to_id[key] != tid:
                    raise ValueError(f"Alias ambíguo '{alias}': {alias_to_id[key]} e {tid}")
                alias_to_id[key] = tid
    return alias_to_id, display


def team_id(name: str, path: str | Path = TEAMS_CSV) -> str:
    """Converte qualquer grafia conhecida no identificador canônico (ex.: 'sao-paulo')."""
    aliases, _ = _load(str(path))
    key = normalize_key(name)
    if key not in aliases:
        raise UnknownTeamError(
            f"Time desconhecido: {name!r} (chave {key!r}). Adicione o alias em config/teams.csv."
        )
    return aliases[key]


def try_team_id(*names: str | None, path: str | Path = TEAMS_CSV) -> str | None:
    """Tenta várias grafias (nome, nome curto, sigla) e devolve a primeira reconhecida."""
    for n in names:
        if not n:
            continue
        try:
            return team_id(n, path)
        except UnknownTeamError:
            continue
    return None


def display_name(tid: str, path: str | Path = TEAMS_CSV) -> str:
    _, display = _load(str(path))
    return display.get(tid, tid)
