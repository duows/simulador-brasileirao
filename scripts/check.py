"""CI local: `python scripts/check.py` (ou `make check`).

Roda, em ordem: ruff, pytest, checagem de qualidade dos dados, testes e build do site, e uma
varredura de segredos, odds, escudos e vocabulário proibido nos arquivos versionados e nos
dados exportados. Para no primeiro erro.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
BIN = Path(PY).parent
NPM = "npm.cmd" if sys.platform == "win32" else "npm"

# Vocabulário proibido (a frase obrigatória do aviso é removida antes de procurar "aposta").
FORBIDDEN = re.compile(r"\b(palpites?|apostas?|apostar|favoritos?|favorita|dicas?|odds|tips?)\b", re.I)
AVISO = "Não é recomendação de aposta"
SECRET = re.compile(r"(X-Auth-Token\s*[:=]\s*['\"][0-9a-f]{20,}|FOOTBALL_DATA_TOKEN\s*=\s*['\"]?[0-9a-f]{20,})", re.I)
CREST = re.compile(r"crests?\.football-data\.org|crestUrl\"\s*:\s*\"http", re.I)
# Arquivos de documentação que DISCUTEM as regras (citam as palavras para proibi-las).
VOCAB_EXEMPT = {"docs/DECISIONS.md", "scripts/check.py", "tests/test_pipeline.py", "README.md"}


def run(label: str, cmd: list[str], cwd: Path = ROOT) -> None:
    print(f"\n==> {label}: {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"FALHOU: {label}")
        sys.exit(res.returncode)


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / f for f in out.splitlines()]


def scan() -> None:
    print("\n==> varredura: segredos, escudos e vocabulário", flush=True)
    problems = []
    files = tracked_files() + list((ROOT / "site" / "public" / "data").glob("*.json"))
    for f in files:
        if not f.exists() or f.suffix in {".png", ".jpg", ".pdf", ".sqlite", ".woff2"} or "package-lock" in f.name:
            continue
        rel = f.relative_to(ROOT).as_posix()
        text = f.read_text(encoding="utf-8", errors="ignore")
        if SECRET.search(text):
            problems.append(f"{rel}: possível token")
        if CREST.search(text):
            problems.append(f"{rel}: URL de escudo")
        if rel not in VOCAB_EXEMPT and rel.endswith((".json", ".js", ".md", ".py", ".csv")):
            m = FORBIDDEN.search(text.replace(AVISO, ""))
            if m:
                problems.append(f"{rel}: vocabulário proibido '{m.group(0)}'")
    if problems:
        print("\n".join(problems))
        print("FALHOU: varredura")
        sys.exit(1)
    print(f"ok ({len(files)} arquivos)")


def main() -> None:
    run("lint", [str(BIN / "ruff"), "check", "src", "tests", "scripts"])
    run("testes Python", [PY, "-m", "pytest", "-q"])
    run("qualidade dos dados", [str(BIN / "futdados"), "coverage", "--strict", "--no-write"])
    run("testes do site", [NPM, "test"], cwd=ROOT / "site")
    run("build do site", [NPM, "run", "build"], cwd=ROOT / "site")
    scan()
    print("\nTudo certo.")


if __name__ == "__main__":
    main()
