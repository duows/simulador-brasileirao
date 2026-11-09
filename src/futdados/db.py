"""Acesso a dados isolado em um repositório.

Todo SQL do projeto fica aqui. Para migrar para Postgres basta reimplementar
esta classe (mesmos métodos) com outro driver; o resto do código só conversa
com `Repository`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    season      INTEGER NOT NULL,
    home_id     TEXT    NOT NULL,
    away_id     TEXT    NOT NULL,
    round       INTEGER,
    kickoff_utc TEXT,               -- ISO 8601; no histórico é a data local às 00:00
    home_goals  INTEGER,
    away_goals  INTEGER,
    status      TEXT    NOT NULL,   -- FINISHED, SCHEDULED, TIMED, POSTPONED...
    home_coach  TEXT,
    away_coach  TEXT,
    source      TEXT    NOT NULL,   -- 'footballcsv', 'football-data' ou 'calendario-gerado'
    ext_id      TEXT,
    updated_at  TEXT    NOT NULL,
    PRIMARY KEY (season, home_id, away_id)  -- em pontos corridos cada mando ocorre 1 vez
);

CREATE TABLE IF NOT EXISTS standings (
    season     INTEGER NOT NULL,
    fetched_at TEXT    NOT NULL,
    position   INTEGER,
    team_id    TEXT    NOT NULL,
    played INTEGER, won INTEGER, draw INTEGER, lost INTEGER,
    points INTEGER, goals_for INTEGER, goals_against INTEGER,
    PRIMARY KEY (season, fetched_at, team_id)
);

CREATE TABLE IF NOT EXISTS coach_snapshots (
    team_id    TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    coach      TEXT,
    PRIMARY KEY (team_id, fetched_at)
);

-- Registro imutável de previsões (gravado antes do jogo).
CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    season        INTEGER NOT NULL,
    round         INTEGER,
    home_id       TEXT NOT NULL,
    away_id       TEXT NOT NULL,
    kickoff_utc   TEXT NOT NULL,
    model_version TEXT NOT NULL,
    lambda_home   REAL NOT NULL,
    lambda_away   REAL NOT NULL,
    p_home        REAL NOT NULL,
    p_draw        REAL NOT NULL,
    p_away        REAL NOT NULL,
    payload       TEXT NOT NULL,
    prev_hash     TEXT NOT NULL,
    hash          TEXT NOT NULL UNIQUE,
    CHECK (created_at < kickoff_utc)
);
CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions
BEGIN SELECT RAISE(ABORT, 'registro de previsões é imutável'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions
BEGIN SELECT RAISE(ABORT, 'registro de previsões é imutável'); END;

-- Projeções da tabela, também só de inserção.
CREATE TABLE IF NOT EXISTS projections (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    season         INTEGER NOT NULL,
    based_on_round INTEGER NOT NULL,   -- últimos resultados reais considerados
    target_round   INTEGER NOT NULL,   -- "tabela depois da rodada X"
    model_version  TEXT NOT NULL,
    team_id        TEXT NOT NULL,
    exp_points     REAL, pos_p10 REAL, pos_p50 REAL, pos_p90 REAL,
    p_titulo REAL, p_g4 REAL, p_g6 REAL, p_rebaixamento REAL
);
CREATE TRIGGER IF NOT EXISTS projections_no_update BEFORE UPDATE ON projections
BEGIN SELECT RAISE(ABORT, 'registro de projeções é imutável'); END;
CREATE TRIGGER IF NOT EXISTS projections_no_delete BEFORE DELETE ON projections
BEGIN SELECT RAISE(ABORT, 'registro de projeções é imutável'); END;
"""

MATCH_COLS = [
    "season", "home_id", "away_id", "round", "kickoff_utc", "home_goals", "away_goals",
    "status", "home_coach", "away_coach", "source", "ext_id",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Repository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ jogos
    def upsert_matches(self, rows: Iterable[dict[str, Any]]) -> int:
        """Insere ou atualiza jogos pela chave (temporada, mandante, visitante). Idempotente."""
        now = utc_now()
        cols = MATCH_COLS + ["updated_at"]
        sql = (
            f"INSERT INTO matches ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
            "ON CONFLICT(season, home_id, away_id) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("season", "home_id", "away_id"))
        )
        data = [tuple(r.get(c) for c in MATCH_COLS) + (now,) for r in rows]
        with self.conn:
            self.conn.executemany(sql, data)
        return len(data)

    def matches(self, season: int | None = None) -> pd.DataFrame:
        sql = "SELECT * FROM matches"
        params: tuple = ()
        if season is not None:
            sql += " WHERE season = ?"
            params = (season,)
        df = pd.read_sql_query(sql + " ORDER BY kickoff_utc, home_id", self.conn, params=params)
        df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
        return df

    def seasons(self) -> list[int]:
        return [r[0] for r in self.conn.execute("SELECT DISTINCT season FROM matches ORDER BY 1")]

    # -------------------------------------------------------------- tabela
    def insert_standings(self, season: int, rows: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO standings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(season, now, r["position"], r["team_id"], r["played"], r["won"], r["draw"],
                  r["lost"], r["points"], r["goals_for"], r["goals_against"]) for r in rows],
            )

    # ------------------------------------------------------------ técnicos
    def record_coach(self, team_id: str, coach: str | None) -> bool:
        """Grava o técnico atual. Devolve True se mudou em relação ao último registro."""
        last = self.conn.execute(
            "SELECT coach FROM coach_snapshots WHERE team_id=? ORDER BY fetched_at DESC LIMIT 1",
            (team_id,),
        ).fetchone()
        changed = last is not None and last[0] != coach
        if last is None or changed:
            with self.conn:
                self.conn.execute("INSERT OR REPLACE INTO coach_snapshots VALUES (?,?,?)",
                                  (team_id, utc_now(), coach))
        return changed

    def coach_snapshots(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM coach_snapshots ORDER BY fetched_at", self.conn)

    # ----------------------------------------------------------- previsões
    def _last_hash(self) -> str:
        row = self.conn.execute("SELECT hash FROM predictions ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else "genesis"

    def insert_prediction(self, rec: dict[str, Any], created_at: str | None = None) -> str:
        """Acrescenta uma previsão ao registro encadeado por hash.

        Recusa (CHECK no banco) previsões gravadas depois do início do jogo.
        """
        created_at = created_at or utc_now()
        prev = self._last_hash()
        payload = json.dumps(rec["payload"], ensure_ascii=False, sort_keys=True)
        base = json.dumps(
            [created_at, rec["season"], rec["home_id"], rec["away_id"], rec["kickoff_utc"],
             rec["model_version"], round(rec["p_home"], 6), round(rec["p_draw"], 6),
             round(rec["p_away"], 6), prev],
            ensure_ascii=False,
        )
        digest = hashlib.sha256((base + payload).encode("utf-8")).hexdigest()
        with self.conn:
            self.conn.execute(
                "INSERT INTO predictions (created_at, season, round, home_id, away_id, kickoff_utc,"
                " model_version, lambda_home, lambda_away, p_home, p_draw, p_away, payload,"
                " prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (created_at, rec["season"], rec["round"], rec["home_id"], rec["away_id"],
                 rec["kickoff_utc"], rec["model_version"], rec["lambda_home"], rec["lambda_away"],
                 rec["p_home"], rec["p_draw"], rec["p_away"], payload, prev, digest),
            )
        return digest

    def predictions(self, season: int, round_: int | None = None) -> pd.DataFrame:
        sql, params = "SELECT * FROM predictions WHERE season=?", [season]
        if round_ is not None:
            sql += " AND round=?"
            params.append(round_)
        return pd.read_sql_query(sql + " ORDER BY id", self.conn, params=params)

    def verify_prediction_chain(self) -> bool:
        prev = "genesis"
        for row in self.conn.execute("SELECT prev_hash, hash FROM predictions ORDER BY id"):
            if row[0] != prev:
                return False
            prev = row[1]
        return True

    # ----------------------------------------------------------- projeções
    def insert_projection(self, meta: dict[str, Any], table: pd.DataFrame) -> str:
        run_id = hashlib.sha1(f"{utc_now()}{meta}".encode()).hexdigest()[:12]
        now = utc_now()
        with self.conn:
            self.conn.executemany(
                "INSERT INTO projections (run_id, created_at, season, based_on_round, target_round,"
                " model_version, team_id, exp_points, pos_p10, pos_p50, pos_p90, p_titulo, p_g4,"
                " p_g6, p_rebaixamento) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(run_id, now, meta["season"], meta["based_on_round"], meta["target_round"],
                  meta["model_version"], r.team_id, r.exp_points, r.pos_p10, r.pos_p50, r.pos_p90,
                  r.p_titulo, r.p_g4, r.p_g6, r.p_rebaixamento) for r in table.itertuples()],
            )
        return run_id

    def projection(self, season: int, based_on_round: int, target_round: int) -> pd.DataFrame:
        """Última projeção gravada para (temporada, rodada-base, rodada-alvo)."""
        row = self.conn.execute(
            "SELECT run_id FROM projections WHERE season=? AND based_on_round=? AND target_round=?"
            " ORDER BY id DESC LIMIT 1", (season, based_on_round, target_round),
        ).fetchone()
        if not row:
            return pd.DataFrame()
        return pd.read_sql_query("SELECT * FROM projections WHERE run_id=?", self.conn,
                                 params=(row[0],))
