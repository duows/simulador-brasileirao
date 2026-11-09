# Backtest walk-forward

Temporadas de teste: 2015–2026 (4518 jogos). Para prever a temporada S, os pesos foram ajustados só com temporadas anteriores a S, e os fatores de cada jogo usam só resultados anteriores àquele jogo. A meia-vida (180 dias) foi escolhida em temporadas anteriores ao período de teste.

## Resultado

O modelo **supera os dois baselines** no Brier e no log loss. A vantagem sobre a frequência histórica é de 3,3% no Brier e 2,9% no log loss: real, mas pequena. Futebol tem muito acaso e um modelo sem escalação e sem xG não vai muito além disso.

| Método | Brier (menor é melhor) | Log loss (menor é melhor) | Acerto do resultado mais provável |
|---|---|---|---|
| Modelo | 0,6122 | 1,0210 | 49,5% |
| Frequência histórica (mandante/empate/visitante) | 0,6332 | 1,0511 | 48,3% |
| Sempre mandante (100% vitória do mandante) | 1,0341 | 17,86* | 48,3% |

\* "Sempre mandante" dá probabilidade zero a empates e derrotas, então o log loss é enorme (limitado numericamente). Ele serve de referência de acerto, não de probabilidade.

Brier multiclasse: soma dos erros quadráticos nas três classes (0 = perfeito, 2 = pior possível; chutar 1/3 para tudo dá 0,667).

## Por temporada

| Temporada | Jogos | Brier modelo | Brier frequência | Log loss modelo | Log loss frequência |
|---|---|---|---|---|---|
| 2015 | 380 | 0,6007 | 0,6129 | 1,0057 | 1,0230 |
| 2016 | 379 | 0,5979 | 0,6082 | 0,9993 | 1,0161 |
| 2017 | 380 | 0,6540 | 0,6570 | 1,0816 | 1,0846 |
| 2018 | 380 | 0,5806 | 0,6077 | 0,9759 | 1,0144 |
| 2019 | 380 | 0,5900 | 0,6334 | 0,9888 | 1,0517 |
| 2020 | 380 | 0,6344 | 0,6496 | 1,0510 | 1,0738 |
| 2021 | 380 | 0,6268 | 0,6442 | 1,0406 | 1,0658 |
| 2022 | 380 | 0,6237 | 0,6525 | 1,0397 | 1,0781 |
| 2023 | 380 | 0,6232 | 0,6406 | 1,0382 | 1,0619 |
| 2024 | 380 | 0,6153 | 0,6375 | 1,0256 | 1,0572 |
| 2025 | 380 | 0,5959 | 0,6239 | 0,9972 | 1,0380 |
| 2026 | 339 | 0,6028 | 0,6311 | 1,0068 | 1,0480 |

## Calibração

Se o modelo diz 40%, o evento deveria acontecer perto de 40% das vezes.
Empates: o modelo estimou em média 26,6% e aconteceram 26,9%.

| Resultado | Faixa estimada | Jogos | Estimado (média) | Observado |
|---|---|---|---|---|
| mandante | 20%-30% | 74 | 27,2% | 18,9% |
| mandante | 30%-40% | 740 | 36,3% | 31,6% |
| mandante | 40%-50% | 1847 | 45,4% | 44,8% |
| mandante | 50%-60% | 1436 | 54,4% | 57,5% |
| mandante | 60%-70% | 393 | 63,4% | 65,9% |
| mandante | 70%-80% | 25 | 72,3% | 80,0% |
| empate | 10%-20% | 69 | 18,6% | 18,8% |
| empate | 20%-30% | 4144 | 26,4% | 26,4% |
| empate | 30%-40% | 305 | 31,0% | 35,4% |
| visitante | 10%-20% | 1052 | 16,8% | 14,7% |
| visitante | 20%-30% | 2379 | 24,8% | 23,5% |
| visitante | 30%-40% | 954 | 33,7% | 36,8% |
| visitante | 40%-50% | 114 | 43,1% | 45,6% |

Faixas com menos de 20 jogos foram omitidas.
