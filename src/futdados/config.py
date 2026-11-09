"""Carregamento da configuração (config/model.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "model.yaml"


def load_dotenv(path: str | Path | None = None) -> list[str]:
    """Lê o arquivo .env da raiz (fora do git) e preenche as variáveis que ainda não existem no
    ambiente. Formato: NOME=valor por linha; # comenta. Devolve os nomes carregados (nunca os valores)."""
    import os

    f = Path(path) if path else ROOT / ".env"
    if not f.exists():
        return []
    loaded = []
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip().removeprefix("export ").strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
            loaded.append(key)
    return loaded


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Lê o YAML, carrega o .env (se houver) e resolve os caminhos relativos à raiz do projeto."""
    load_dotenv()
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["paths"] = {k: str((ROOT / v).resolve()) for k, v in cfg["paths"].items()}
    return cfg
