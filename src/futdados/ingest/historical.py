"""Ingestão do histórico a partir da organização footballcsv (domínio público, CC0 1.0).

Fonte: github.com/footballcsv/cache.wfb, arquivo <temporada>/br.1.csv (Série A).
O repositório pedido, github.com/footballcsv/world, só tem a Série A de 2019 (completa)
e de 2020 (177 jogos sem placar), por isso usamos o irmão cache.wfb, da mesma
organização e com a mesma licença (ver docs/DECISIONS.md D14).

Colunas reais conferidas (commit 399cc1f, set/2024):
Round, Date, Time, Timezone, Team 1, FT, HT, Team 2, [Comments], UTC
- FT é "gols1-gols2"; jogos cancelados trazem outro texto (ex.: "(*)" em 2016).
- UTC é o horário de início em UTC (ex.: 2015-05-09T21:30Z).
- Não há técnico nem cartões.
- 2024 está incompleta (o cache parou em setembro de 2024, 252 de 380 jogos).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd

from ..teams import team_id

SCORE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def ensure_repo(repo_dir: str | Path, repo_url: str) -> Path:
    """Clona (raso) o repositório se ainda não existir localmente."""
    repo_dir = Path(repo_dir)
    if not (repo_dir / "LICENSE.md").exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)], check=True)
    return repo_dir


def _utc(row) -> str:
    if isinstance(row.get("UTC"), str) and row["UTC"]:
        ts = pd.Timestamp(row["UTC"])
    else:  # sem horário: usa a data às 00:00 de Brasília
        ts = pd.Timestamp(row["Date"]) + pd.Timedelta(hours=3)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def load_season(repo_dir: str | Path, season: int) -> tuple[list[dict], int]:
    """Jogos com placar de uma temporada. Devolve (linhas, jogos ignorados sem placar)."""
    df = pd.read_csv(Path(repo_dir) / str(season) / "br.1.csv", dtype=str)
    rows, skipped = [], 0
    for r in df.to_dict("records"):
        m = SCORE.match(str(r.get("FT") or ""))
        if not m:
            skipped += 1  # cancelado ou ainda sem placar no cache
            continue
        rows.append({
            "season": season,
            "home_id": team_id(r["Team 1"]),
            "away_id": team_id(r["Team 2"]),
            "round": int(r["Round"]),
            "kickoff_utc": _utc(r),
            "home_goals": int(m.group(1)),
            "away_goals": int(m.group(2)),
            "status": "FINISHED",
            "home_coach": None,
            "away_coach": None,
            "source": "footballcsv",
            "ext_id": f"wfb:{season}:{r['Round']}:{r['Team 1']}",
        })
    return rows, skipped


def ingest_historical(repo, cfg: dict) -> dict[int, int]:
    """Carrega as temporadas configuradas no banco. Devolve jogos por temporada."""
    hcfg = cfg["historical"]
    repo_dir = ensure_repo(cfg["paths"]["historical_repo"], hcfg["repo_url"])
    counts: dict[int, int] = {}
    # prioridade de fontes (ver ingest/reconcile.py): não sobrescreve temporada que já veio da API
    api = repo.matches()
    api_keys = set(zip(api[api.source == "football-data"].season, api[api.source == "football-data"].home_id,
                       api[api.source == "football-data"].away_id))
    for season in range(hcfg["first_season"], hcfg["last_season"] + 1):
        rows, _ = load_season(repo_dir, season)
        rows = [r for r in rows if (r["season"], r["home_id"], r["away_id"]) not in api_keys]
        repo.upsert_matches(rows)
        counts[season] = len(rows)
    return counts
