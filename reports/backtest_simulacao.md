# Backtest da simulação de campeonato

Temporadas 2015–2025. Em cada uma, a projeção foi refeita como se estivéssemos nas rodadas 10, 20 e 30, escondendo os resultados seguintes, e comparada com a classificação final. Brier: erro quadrático médio das chances (menor é melhor). Baseline: todo time com a mesma chance (a taxa da zona).

| Rodada de corte | Brier título (base) | Brier G4 (base) | Brier rebaixamento (base) | Posição final dentro da faixa p10–p90 |
|---|---|---|---|---|
| 10 | 0,037 (0,047) | 0,091 (0,160) | 0,120 (0,160) | 87% |
| 20 | 0,025 (0,047) | 0,061 (0,160) | 0,083 (0,160) | 86% |
| 30 | 0,016 (0,047) | 0,030 (0,160) | 0,057 (0,160) | 93% |

No total, a posição final caiu dentro da faixa p10–p90 em 89% dos casos (o esperado para uma faixa de 80% bem calibrada é perto de 80%).

## Calibração

**titulo**

| Faixa estimada | Times | Estimado | Observado |
|---|---|---|---|
| 0%-5% | 538 | 0% | 0% |
| 5%-20% | 71 | 10% | 13% |
| 20%-40% | 30 | 29% | 27% |

**g4**

| Faixa estimada | Times | Estimado | Observado |
|---|---|---|---|
| 0%-5% | 345 | 1% | 0% |
| 5%-20% | 118 | 11% | 6% |
| 20%-40% | 60 | 29% | 33% |
| 40%-60% | 44 | 48% | 52% |
| 60%-80% | 39 | 71% | 79% |
| 80%-95% | 24 | 87% | 96% |
| 95%-100% | 30 | 99% | 93% |

**rebaixamento**

| Faixa estimada | Times | Estimado | Observado |
|---|---|---|---|
| 0%-5% | 321 | 1% | 1% |
| 5%-20% | 123 | 11% | 15% |
| 20%-40% | 83 | 29% | 27% |
| 40%-60% | 54 | 50% | 37% |
| 60%-80% | 35 | 69% | 71% |
| 80%-95% | 23 | 87% | 96% |
| 95%-100% | 21 | 99% | 100% |
