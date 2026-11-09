"""Geração dos relatórios em Markdown (reports/)."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from .model.features import FEATURES
from .model.poisson import Weights

# Para cada fator: (variação típica usada no exemplo, frase do exemplo, nome amigável)
FACTOR_TEXT = {
    "ataque": (math.log(1.2), "um ataque 20% melhor que a média da liga", "Força de ataque (longo prazo)"),
    "defesa_adversario": (math.log(1.2), "um adversário que sofre 20% mais gols que a média",
                          "Fragilidade da defesa adversária (longo prazo)"),
    "mando": (1.0, "jogar em casa", "Mando de campo"),
    "forma": (1.0, "ter 1 ponto por jogo a mais que o adversário nos últimos 5 jogos",
              "Forma recente (últimos 5)"),
    "descanso": (3.0, "ter 3 dias a mais de descanso que o adversário", "Descanso"),
    "meio_de_semana": (1.0, "jogo de terça a quinta (vale para os dois times)", "Jogo no meio da semana"),
    "tecnico_novo": (1.0, "estar nos 5 primeiros jogos de um técnico novo (e o adversário não)",
                     "Troca recente de técnico"),
}


def pct(x: float) -> str:
    return f"{x:+.1%}".replace(".", ",")


def num(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def weights_markdown(w: Weights, tune: pd.DataFrame | None = None) -> str:
    lines = [
        "# Pesos do modelo",
        "",
        f"- Versão do modelo: `{w.model_version}`",
        f"- Ajustado em: {w.fitted_at}",
        f"- Temporadas de treino: {w.train_seasons[0]}–{w.train_seasons[-1]} ({w.n_matches} jogos)",
        f"- Meia-vida da força de longo prazo: {w.half_life_days:.0f} dias",
        f"- Intercepto: {num(w.intercept)} (gols esperados base = média da liga × {num(math.exp(w.intercept))})",
        f"- Ajuste de placares baixos (Dixon-Coles, rho): {num(w.rho, 4)}",
        "",
        "Fórmula: `log(gols esperados) = log(média da liga) + intercepto + Σ peso × fator`.",
        "O intervalo é de 95%, por bootstrap de jogos. Quando ele cruza o zero, os dados",
        "não permitem afirmar que o fator tem efeito.",
        "",
        "| Fator | Peso | Intervalo 95% | O que significa |",
        "|---|---|---|---|",
    ]
    for f in FEATURES:
        step, phrase, label = FACTOR_TEXT[f]
        b = w.coef[f]
        lo, hi = w.ci_low.get(f, float("nan")), w.ci_high.get(f, float("nan"))
        eff = math.exp(b * step) - 1
        clear = not (lo <= 0 <= hi)
        meaning = f"{phrase.capitalize()} muda os gols esperados em {pct(eff)}."
        if not clear:
            meaning += " Efeito não distinguível de zero."
        lines.append(f"| {label} | {num(b)} | [{num(lo)}; {num(hi)}] | {meaning} |")
    lines += [
        "",
        "## Como ler",
        "",
        "- **Ataque e defesa** são taxas de gols com decaimento: um jogo de "
        f"{w.half_life_days:.0f} dias atrás vale metade de um jogo de hoje. Os gols são ajustados "
        "pela força do adversário, e um time sem histórico recente na Série A começa 15% abaixo "
        "da média (5 jogos fictícios, configurável).",
        "- Pesos de ataque e defesa menores que 1 significam que a diferença observada entre os "
        "times é em parte ruído: o modelo puxa as forças em direção à média.",
        "- **Forma** é medida além da força de longo prazo. Peso pequeno quer dizer que a "
        "sequência recente acrescenta pouco ao que o histórico com decaimento já captura.",
        "- **Descanso** só conta jogos da Série A (copas não estão nos dados). Ver limitações no README.",
        "- **Técnico novo** só tem dados por jogo a partir de 2014.",
    ]
    if tune is not None and not tune.empty:
        lines += ["", "## Escolha da meia-vida (walk-forward nas temporadas de ajuste)", "",
                  "| Meia-vida (dias) | Brier | Log loss | Jogos |", "|---|---|---|---|"]
        for r in tune.itertuples():
            lines.append(f"| {r.meia_vida_dias:.0f} | {num(r.brier, 4)} | {num(r.log_loss, 4)} | {r.n} |")
    return "\n".join(lines) + "\n"


def write(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
