"""Carregamento da configuração (config/model.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "model.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Lê o YAML e resolve os caminhos relativos à raiz do projeto."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["paths"] = {k: str((ROOT / v).resolve()) for k, v in cfg["paths"].items()}
    return cfg
