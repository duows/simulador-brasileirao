"""Cliente da API v4 do football-data.org (competição BSA).

- O token vem SEMPRE da variável de ambiente FOOTBALL_DATA_TOKEN.
- Respeita o limite do plano grátis (10 requisições por minuto) com janela deslizante.
- Cada resposta é gravada em data/raw/<data>/<endpoint>.json antes de ir para o banco.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from ..teams import try_team_id

TOKEN_ENV = "FOOTBALL_DATA_TOKEN"


class MissingTokenError(RuntimeError):
    pass


class RateLimiter:
    """Janela deslizante: no máximo `per_minute` chamadas em qualquer intervalo de 60 s."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.per_minute = per_minute
        self.clock, self.sleep = clock, sleep
        self.calls: deque[float] = deque()

    def wait(self) -> None:
        now = self.clock()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= self.per_minute:
            self.sleep(60 - (now - self.calls[0]) + 0.05)
            return self.wait()
        self.calls.append(self.clock())


class FootballDataClient:
    def __init__(self, base_url: str, raw_dir: str | Path, per_minute: int = 10,
                 token: str | None = None, session: requests.Session | None = None,
                 limiter: RateLimiter | None = None):
        token = token or os.environ.get(TOKEN_ENV)
        if not token:
            raise MissingTokenError(
                f"Defina a variável de ambiente {TOKEN_ENV} com sua chave do football-data.org.")
        self.base_url = base_url.rstrip("/")
        self.raw_dir = Path(raw_dir)
        self.session = session or requests.Session()
        self.session.headers.update({"X-Auth-Token": token})
        self.limiter = limiter or RateLimiter(per_minute)

    def get(self, path: str, params: dict[str, Any] | None = None, raw_name: str | None = None) -> dict:
        for attempt in range(3):
            self.limiter.wait()
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=30)
            if resp.status_code == 429:  # estourou o limite mesmo assim: espera o que a API pedir
                time.sleep(int(resp.headers.get("Retry-After", 60)))
                continue
            resp.raise_for_status()
            data = resp.json()
            self._save_raw(raw_name or path.strip("/").replace("/", "_"), params, data)
            return data
        raise RuntimeError(f"Falha após 3 tentativas: {path}")

    def _save_raw(self, name: str, params: dict | None, data: dict) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = "_".join(f"{k}-{v}" for k, v in sorted((params or {}).items()))
        out = self.raw_dir / stamp[:8] / f"{name}{'_' + suffix if suffix else ''}_{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return out

    # ------------------------------------------------------------ endpoints
    def matches(self, competition: str, season: int) -> dict:
        return self.get(f"/competitions/{competition}/matches", {"season": season})

    def standings(self, competition: str, season: int) -> dict:
        return self.get(f"/competitions/{competition}/standings", {"season": season})

    def teams(self, competition: str, season: int) -> dict:
        return self.get(f"/competitions/{competition}/teams", {"season": season})


def _tid(team: dict) -> str:
    tid = try_team_id(team.get("name"), team.get("shortName"), team.get("tla"))
    if tid is None:
        raise KeyError(f"Time da API sem alias em config/teams.csv: {team}")
    return tid


def parse_matches(payload: dict, season: int) -> list[dict]:
    rows = []
    for m in payload.get("matches", []):
        ft = (m.get("score") or {}).get("fullTime") or {}
        finished = m.get("status") == "FINISHED"
        utc = m["utcDate"].replace(".000", "")
        if not utc.endswith("Z"):
            utc = utc + "Z"
        rows.append({
            "season": season,
            "home_id": _tid(m["homeTeam"]),
            "away_id": _tid(m["awayTeam"]),
            "round": m.get("matchday"),
            "kickoff_utc": utc,
            "home_goals": ft.get("home") if finished else None,
            "away_goals": ft.get("away") if finished else None,
            "status": m.get("status", "SCHEDULED"),
            "home_coach": None,
            "away_coach": None,
            "source": "football-data",
            "ext_id": f"fd:{m['id']}",
        })
    return rows


def parse_standings(payload: dict) -> list[dict]:
    total = next((s for s in payload.get("standings", []) if s.get("type") == "TOTAL"), None)
    if not total:
        return []
    return [{
        "position": r["position"], "team_id": _tid(r["team"]), "played": r["playedGames"],
        "won": r["won"], "draw": r["draw"], "lost": r["lost"], "points": r["points"],
        "goals_for": r["goalsFor"], "goals_against": r["goalsAgainst"],
    } for r in total["table"]]


def ingest_api(repo, cfg: dict, season: int, client: FootballDataClient | None = None) -> dict:
    """Baixa jogos, classificação e técnicos da temporada e grava no banco (3 requisições)."""
    api = cfg["api"]
    client = client or FootballDataClient(api["base_url"], cfg["paths"]["raw"], api["requests_per_minute"])
    match_rows = parse_matches(client.matches(api["competition"], season), season)
    repo.upsert_matches(match_rows)
    standing_rows = parse_standings(client.standings(api["competition"], season))
    if standing_rows:
        repo.insert_standings(season, standing_rows)
    changed = []
    for team in client.teams(api["competition"], season).get("teams", []):
        coach = (team.get("coach") or {}).get("name")
        tid = _tid(team)
        if repo.record_coach(tid, coach):
            changed.append((tid, coach))
    return {"matches": len(match_rows), "standings": len(standing_rows), "coach_changes": changed}
