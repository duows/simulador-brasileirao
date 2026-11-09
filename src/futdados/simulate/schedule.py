"""Tabela de rodadas balanceada (turno e returno) para quando a API ainda não publicou o calendário.

Método do círculo: um time fica fixo e os outros giram. O returno espelha o turno com o
mando invertido. Cada time joga uma vez por rodada, enfrenta todos duas vezes (uma em casa,
uma fora) e tem 19 jogos em casa numa liga de 20.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def round_robin(teams: list[str]) -> list[list[tuple[str, str]]]:
    """Rodadas do turno e do returno: lista de rodadas, cada uma com pares (mandante, visitante)."""
    teams = list(teams)
    if len(teams) % 2:
        raise ValueError("Número ímpar de times: a Série A tem número par.")
    n = len(teams)
    fixed, rot = teams[0], teams[1:]
    first = []
    for r in range(n - 1):
        lineup = [fixed] + rot
        games = []
        for i in range(n // 2):
            a, b = lineup[i], lineup[n - 1 - i]
            # mando pela posição no círculo: como os times giram de posição, cada um alterna
            # casa e fora (no máximo 2 seguidos) e tem 9 ou 10 jogos em casa no turno
            home_first = (r % 2 == 0) if i == 0 else (i % 2 == 1)
            games.append((a, b) if home_first else (b, a))
        first.append(games)
        rot = rot[-1:] + rot[:-1]
    second = [[(b, a) for a, b in games] for games in first]
    return first + second


def generate_schedule(teams: list[str], season: int, start_mmdd: str = "04-11",
                      kickoff_hour_utc: int = 22) -> list[dict]:
    """Jogos com datas fictícias: uma rodada por semana, aos sábados, a partir de `start_mmdd`."""
    month, day = (int(x) for x in start_mmdd.split("-"))
    start = datetime(season, month, day, kickoff_hour_utc, tzinfo=timezone.utc)
    start += timedelta(days=(5 - start.weekday()) % 7)  # próximo sábado
    rows = []
    for r, games in enumerate(round_robin(sorted(teams)), start=1):
        when = (start + timedelta(weeks=r - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for h, a in games:
            rows.append({"season": season, "home_id": h, "away_id": a, "round": r,
                         "kickoff_utc": when, "home_goals": None, "away_goals": None,
                         "status": "SCHEDULED", "home_coach": None, "away_coach": None,
                         "source": "calendario-gerado", "ext_id": None})
    return rows
