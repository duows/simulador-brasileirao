"""Ingestão do histórico 2003-2025 do repositório adaoduque/Brasileirao_Dataset.

Colunas reais conferidas em campeonato-brasileiro-full.csv (commit 15f027c, fev/2026):
ID, rodata (sic, é a rodada), data (dd/mm/aaaa), hora, mandante, visitante,
formacao_*, tecnico_* (só a partir de 2014), vencedor, arena, mandante_Placar,
visitante_Placar, mandante_Estado, visitante_Estado.

O CSV não tem coluna de temporada. A temporada 2020 terminou em fevereiro de 2021,
então o ano da data não serve. A temporada é deduzida pela ordem do ID: cada vez que a
rodada volta de ~38 para 1 começa uma temporada nova (verificado: 22 temporadas).

2025 só existe em data/brasileirao-2025.json (chaves = rodada; datas às vezes sem ano).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..teams import team_id

BRT_OFFSET = timedelta(hours=3)  # horário de Brasília -> UTC (horário de verão ignorado)


def ensure_repo(repo_dir: str | Path, repo_url: str) -> Path:
    """Clona (raso) o repositório se ainda não existir localmente."""
    repo_dir = Path(repo_dir)
    if not (repo_dir / "campeonato-brasileiro-full.csv").exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)], check=True)
    return repo_dir


def _to_utc_iso(day: datetime, hour: str | None) -> str:
    h, m = 0, 0
    if hour and ":" in hour:
        try:
            h, m = (int(x) for x in hour.strip().split(":")[:2])
        except ValueError:
            h, m = 0, 0
    local = day.replace(hour=h, minute=m)
    return (local + BRT_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")


def assign_seasons(ids: pd.Series, rounds: pd.Series, first_season: int) -> np.ndarray:
    """Temporada pela quebra de rodada (38 -> 1) na ordem dos IDs."""
    order = np.argsort(ids.to_numpy(), kind="stable")
    r = rounds.to_numpy()[order]
    breaks = np.concatenate([[0], (np.diff(r) < -20).astype(int)])
    season_sorted = first_season + np.cumsum(breaks)
    out = np.empty_like(season_sorted)
    out[order] = season_sorted
    return out


def _clean_coach(x) -> str | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    x = str(x).strip()
    return x or None


def load_csv(repo_dir: str | Path, first_season: int = 2003) -> list[dict]:
    df = pd.read_csv(Path(repo_dir) / "campeonato-brasileiro-full.csv", dtype=str)
    df["ID"] = df["ID"].astype(int)
    df["rodata"] = df["rodata"].astype(int)
    df["season"] = assign_seasons(df["ID"], df["rodata"], first_season)
    rows = []
    for r in df.itertuples(index=False):
        day = datetime.strptime(r.data.strip(), "%d/%m/%Y")
        rows.append({
            "season": int(r.season),
            "home_id": team_id(r.mandante),
            "away_id": team_id(r.visitante),
            "round": int(r.rodata),
            "kickoff_utc": _to_utc_iso(day, r.hora),
            "home_goals": int(r.mandante_Placar),
            "away_goals": int(r.visitante_Placar),
            "status": "FINISHED",
            "home_coach": _clean_coach(r.tecnico_mandante),
            "away_coach": _clean_coach(r.tecnico_visitante),
            "source": "adaoduque",
            "ext_id": f"csv:{r.ID}",
        })
    return rows


def _parse_json_date(text: str, season: int) -> datetime:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    # Sem ano (ex.: "06/12"): assume o ano da temporada; jan-fev pertencem ao ano seguinte.
    d, m = (int(x) for x in text.split("/")[:2])
    return datetime(season + (1 if m <= 2 else 0), m, d)


def load_season_json(repo_dir: str | Path, season: int) -> list[dict]:
    path = Path(repo_dir) / "data" / f"brasileirao-{season}.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = []
    for round_key, matches in data.items():
        rnd = int("".join(c for c in round_key if c.isdigit()))
        for i, m in enumerate(matches):
            hg, ag = m["goals"]["home"], m["goals"]["away"]
            played = str(hg).strip().isdigit() and str(ag).strip().isdigit()
            day = _parse_json_date(m["date"], season)
            rows.append({
                "season": season,
                "home_id": team_id(m["clubs"]["home"]),
                "away_id": team_id(m["clubs"]["away"]),
                "round": rnd,
                "kickoff_utc": _to_utc_iso(day, m.get("hour")),
                "home_goals": int(hg) if played else None,
                "away_goals": int(ag) if played else None,
                "status": "FINISHED" if played else "SCHEDULED",
                "home_coach": _clean_coach(m.get("coach", {}).get("home")),
                "away_coach": _clean_coach(m.get("coach", {}).get("away")),
                "source": "adaoduque",
                "ext_id": f"json:{season}:{rnd}:{i}",
            })
    return rows


def ingest_historical(repo, cfg: dict) -> dict[int, int]:
    """Carrega CSV (2003-2024) + JSONs configurados no banco. Devolve jogos por temporada."""
    hcfg = cfg["historical"]
    repo_dir = ensure_repo(cfg["paths"]["historical_repo"], hcfg["repo_url"])
    rows = [r for r in load_csv(repo_dir, hcfg["first_season"]) if r["season"] <= hcfg["last_season_csv"]]
    for season in hcfg.get("json_seasons", []):
        rows += load_season_json(repo_dir, season)
    repo.upsert_matches(rows)
    counts: dict[int, int] = {}
    for r in rows:
        counts[r["season"]] = counts.get(r["season"], 0) + 1
    return counts
