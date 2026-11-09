"""Linha de comando do futdados. Use `futdados --help` para ver os subcomandos."""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .db import Repository


def _repo(cfg) -> Repository:
    return Repository(cfg["paths"]["db"])


def cmd_ingest_historical(args, cfg) -> None:
    from .ingest.historical import ingest_historical

    counts = ingest_historical(_repo(cfg), cfg)
    print(f"Histórico carregado: {sum(counts.values())} jogos em {len(counts)} temporadas.")


def cmd_ingest_api(args, cfg) -> None:
    from .ingest.football_data import ingest_api

    res = ingest_api(_repo(cfg), cfg, args.season)
    print(f"API: {res['matches']} jogos, {res['standings']} linhas de classificação.")
    for tid, coach in res["coach_changes"]:
        print(f"  Troca de técnico detectada: {tid} -> {coach}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="futdados", description=__doc__)
    p.add_argument("--config", help="caminho do model.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest-historical", help="carrega 2003-2025 do dataset adaoduque")
    s = sub.add_parser("ingest-api", help="baixa a temporada do football-data.org")
    s.add_argument("--season", type=int, required=True)
    return p


COMMANDS = {
    "ingest-historical": cmd_ingest_historical,
    "ingest-api": cmd_ingest_api,
}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    COMMANDS[args.command](args, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
