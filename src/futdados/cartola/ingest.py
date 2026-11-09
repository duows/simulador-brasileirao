"""Ingestão da API pública (não oficial) do Cartola FC, só para estudo local.

Endpoints usados (host api.cartola.globo.com, conferidos em 2026-11-09):
- /mercado/status: rodada atual, status do mercado, cartoletas iniciais.
- /atletas/mercado: atletas com preço, status (7 provável, 2 dúvida, 3 suspenso, 5 contundido,
  6 nulo), média e scouts acumulados.
- /atletas/pontuados/{rodada}: pontuação e scouts de cada atleta naquela rodada.
- /partidas/{rodada}: jogos da rodada (ids dos clubes, data, placar).
- /clubes, /posicoes, /esquemas.

Sem licença nem termos públicos claros: tudo fica em data/cartola (gitignored) e nunca entra
em arquivo versionado nem em export público (ver docs/DECISIONS.md D24).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

from ..teams import try_team_id

BASE = "https://api.cartola.globo.com"
POS = {1: "gol", 2: "lat", 3: "zag", 4: "mei", 5: "ata", 6: "tec"}
STATUS = {2: "duvida", 3: "suspenso", 5: "contundido", 6: "nulo", 7: "provavel"}


class CartolaClient:
    def __init__(self, cache_dir: str | Path, pause: float = 1.0, session: requests.Session | None = None):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pause = pause
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "futdados-estudo-local"})

    def get(self, path: str, cache_name: str | None = None, refresh: bool = True) -> dict | list:
        """Busca com pausa entre chamadas (educado com o servidor) e guarda a resposta bruta."""
        f = self.cache / f"{cache_name or path.strip('/').replace('/', '_')}.json"
        if f.exists() and not refresh:
            return json.loads(f.read_text(encoding="utf-8"))
        time.sleep(self.pause)
        r = self.session.get(f"{BASE}{path}", timeout=30)
        r.raise_for_status()
        data = r.json()
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data


def club_map(clubes: dict) -> dict[int, str]:
    """id do clube no Cartola -> id do time no futdados.

    O Cartola identifica os clubes pela sigla (FLA, SAO, CAP...), que é a mesma de short_name em
    config/teams.csv; os aliases ficam de reserva.
    """
    import csv

    from ..teams import TEAMS_CSV

    by_short = {r["short_name"]: r["team_id"] for r in csv.DictReader(open(TEAMS_CSV, encoding="utf-8"))}
    out = {}
    for cid, c in clubes.items():
        tid = by_short.get((c.get("abreviacao") or "").upper()) or try_team_id(
            c.get("nome_fantasia"), c.get("slug"), c.get("nome"), c.get("apelido"))
        if tid:
            out[int(cid)] = tid
    return out


def ingest(cache_dir: str | Path, season: int, refresh_past: bool = False) -> dict[str, pd.DataFrame]:
    """Baixa mercado, partidas e pontuações já disputadas. Rodadas passadas ficam em cache."""
    cli = CartolaClient(cache_dir)
    status = cli.get("/mercado/status")
    if status.get("temporada") != season:
        raise ValueError(f"A API está na temporada {status.get('temporada')}, não em {season}.")
    rodada = int(status["rodada_atual"])
    mercado = cli.get("/atletas/mercado")
    clubes = cli.get("/clubes")
    cmap = club_map(clubes)
    missing = sorted({a["clube_id"] for a in mercado["atletas"]} - set(cmap) - {1})
    if missing:
        raise KeyError(f"Clubes do Cartola sem alias em config/teams.csv: {[clubes[str(i)]['nome'] for i in missing]}")
    atletas = pd.DataFrame([{
        "atleta_id": a["atleta_id"], "apelido": a["apelido"], "clube_id": a["clube_id"],
        "team_id": cmap.get(a["clube_id"]), "posicao": POS[a["posicao_id"]], "status": STATUS.get(a["status_id"], "outro"),
        "preco": float(a["preco_num"]), "media": float(a["media_num"]), "jogos": int(a["jogos_num"]),
    } for a in mercado["atletas"]])

    pts, partidas = [], []
    for r in range(1, rodada + 1):
        past = r < rodada
        if past:
            pr = cli.get(f"/atletas/pontuados/{r}", refresh=refresh_past)
            for aid, a in (pr.get("atletas") or {}).items():
                pts.append({"rodada": r, "atleta_id": int(aid), "clube_id": a["clube_id"], "team_id": cmap.get(a["clube_id"]),
                            "posicao": POS[a["posicao_id"]], "pontos": float(a["pontuacao"]),
                            "jogou": bool(a.get("entrou_em_campo")), **{f"s_{k}": v for k, v in (a.get("scout") or {}).items()}})
        pa = cli.get(f"/partidas/{r}", refresh=refresh_past or not past)
        for p in pa["partidas"]:
            partidas.append({"rodada": r, "home_id": cmap.get(p["clube_casa_id"]), "away_id": cmap.get(p["clube_visitante_id"]),
                             "data": p["partida_data"], "valida": bool(p.get("valida", True)),
                             "placar_casa": p.get("placar_oficial_mandante"), "placar_fora": p.get("placar_oficial_visitante")})
    pontos = pd.DataFrame(pts).fillna({c: 0 for c in pd.DataFrame(pts).columns if c.startswith("s_")})
    esquemas = cli.get("/esquemas")
    return {"atletas": atletas, "pontos": pontos, "partidas": pd.DataFrame(partidas),
            "status": status, "esquemas": esquemas}
