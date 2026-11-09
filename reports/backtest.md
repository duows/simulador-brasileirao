# Backtest walk-forward

Temporadas de teste: 2015–2025 (4179 jogos). Para prever a temporada S, os pesos foram ajustados só com temporadas anteriores a S, e os fatores de cada jogo usam só resultados anteriores àquele jogo. A meia-vida (365 dias) foi escolhida em temporadas anteriores ao período de teste.

## Resultado

O modelo **supera os dois baselines** no Brier e no log loss. A vantagem sobre a frequência histórica é de 3,4% no Brier e 2,9% no log loss: real, mas pequena. Futebol tem muito acaso e um modelo sem escalação e sem xG não vai muito além disso.

| Método | Brier (menor é melhor) | Log loss (menor é melhor) | Acerto do resultado mais provável |
|---|---|---|---|
| Modelo | 0,6121 | 1,0208 | 49,6% |
| Frequência histórica (mandante/empate/visitante) | 0,6335 | 1,0515 | 48,3% |
| Sempre mandante (100% vitória do mandante) | 1,0347 | 17,87* | 48,3% |

\* "Sempre mandante" dá probabilidade zero a empates e derrotas, então o log loss é enorme (limitado numericamente). Ele serve de referência de acerto, não de probabilidade.

Brier multiclasse: soma dos erros quadráticos nas três classes (0 = perfeito, 2 = pior possível; chutar 1/3 para tudo dá 0,667).

## Por temporada

| Temporada | Jogos | Brier modelo | Brier frequência | Log loss modelo | Log loss frequência |
|---|---|---|---|---|---|
| 2015 | 380 | 0,6035 | 0,6122 | 1,0089 | 1,0222 |
| 2016 | 379 | 0,6008 | 0,6078 | 1,0034 | 1,0155 |
| 2017 | 380 | 0,6504 | 0,6575 | 1,0764 | 1,0856 |
| 2018 | 380 | 0,5819 | 0,6065 | 0,9771 | 1,0124 |
| 2019 | 380 | 0,5898 | 0,6336 | 0,9885 | 1,0521 |
| 2020 | 380 | 0,6315 | 0,6502 | 1,0467 | 1,0746 |
| 2021 | 380 | 0,6246 | 0,6447 | 1,0373 | 1,0664 |
| 2022 | 380 | 0,6232 | 0,6534 | 1,0390 | 1,0793 |
| 2023 | 380 | 0,6195 | 0,6411 | 1,0333 | 1,0627 |
| 2024 | 380 | 0,6148 | 0,6378 | 1,0249 | 1,0577 |
| 2025 | 380 | 0,5933 | 0,6236 | 0,9931 | 1,0376 |

## Calibração

Se o modelo diz 40%, o evento deveria acontecer perto de 40% das vezes.
Empates: o modelo estimou em média 26,9% e aconteceram 26,9%.

| Resultado | Faixa estimada | Jogos | Estimado (média) | Observado |
|---|---|---|---|---|
| mandante | 20%-30% | 81 | 27,0% | 16,0% |
| mandante | 30%-40% | 746 | 36,3% | 34,2% |
| mandante | 40%-50% | 1655 | 45,3% | 44,4% |
| mandante | 50%-60% | 1310 | 54,4% | 57,9% |
| mandante | 60%-70% | 359 | 63,2% | 65,7% |
| mandante | 70%-80% | 28 | 72,4% | 71,4% |
| empate | 10%-20% | 55 | 18,5% | 16,4% |
| empate | 20%-30% | 3770 | 26,7% | 26,2% |
| empate | 30%-40% | 354 | 30,9% | 35,9% |
| visitante | 10%-20% | 1029 | 16,8% | 14,5% |
| visitante | 20%-30% | 2124 | 24,8% | 24,2% |
| visitante | 30%-40% | 904 | 33,8% | 35,6% |
| visitante | 40%-50% | 103 | 43,4% | 47,6% |

Faixas com menos de 20 jogos foram omitidas.
