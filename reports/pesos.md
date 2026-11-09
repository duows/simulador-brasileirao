# Pesos do modelo

- Versão do modelo: `futdados-0.1.0+dbe414fa`
- Ajustado em: 2026-11-09T01:15:16Z
- Temporadas de treino: 2006–2025 (7599 jogos)
- Meia-vida da força de longo prazo: 365 dias
- Intercepto: -0,248 (gols esperados base = média da liga × 0,780)
- Ajuste de placares baixos (Dixon-Coles, rho): 0,0000

Fórmula: `log(gols esperados) = log(média da liga) + intercepto + Σ peso × fator`.
O intervalo é de 95%, por bootstrap de jogos. Quando ele cruza o zero, os dados
não permitem afirmar que o fator tem efeito.

| Fator | Peso | Intervalo 95% | O que significa |
|---|---|---|---|
| Força de ataque (longo prazo) | 0,743 | [0,647; 0,851] | Um ataque 20% melhor que a média da liga muda os gols esperados em +14,5%. |
| Fragilidade da defesa adversária (longo prazo) | 0,705 | [0,601; 0,799] | Um adversário que sofre 20% mais gols que a média muda os gols esperados em +13,7%. |
| Mando de campo | 0,410 | [0,382; 0,433] | Jogar em casa muda os gols esperados em +50,7%. |
| Forma recente (últimos 5) | 0,034 | [0,016; 0,051] | Ter 1 ponto por jogo a mais que o adversário nos últimos 5 jogos muda os gols esperados em +3,4%. |
| Descanso | 0,000 | [-0,010; 0,009] | Ter 3 dias a mais de descanso que o adversário muda os gols esperados em +0,1%. Efeito não distinguível de zero. |
| Jogo no meio da semana | 0,044 | [0,008; 0,073] | Jogo de terça a quinta (vale para os dois times) muda os gols esperados em +4,5%. |
| Troca recente de técnico | -0,019 | [-0,050; 0,007] | Estar nos 5 primeiros jogos de um técnico novo (e o adversário não) muda os gols esperados em -1,9%. Efeito não distinguível de zero. |

## Como ler

- **Ataque e defesa** são taxas de gols com decaimento: um jogo de 365 dias atrás vale metade de um jogo de hoje. Os gols são ajustados pela força do adversário, e um time sem histórico recente na Série A começa 15% abaixo da média (5 jogos fictícios, configurável).
- Pesos de ataque e defesa menores que 1 significam que a diferença observada entre os times é em parte ruído: o modelo puxa as forças em direção à média.
- **Forma** é medida além da força de longo prazo. Peso pequeno quer dizer que a sequência recente acrescenta pouco ao que o histórico com decaimento já captura.
- **Descanso** só conta jogos da Série A (copas não estão nos dados). Ver limitações no README.
- **Técnico novo** só tem dados por jogo a partir de 2014.

## Escolha da meia-vida (walk-forward nas temporadas de ajuste)

| Meia-vida (dias) | Brier | Log loss | Jogos |
|---|---|---|---|
| 60 | 0,6233 | 1,0366 | 1900 |
| 90 | 0,6224 | 1,0352 | 1900 |
| 180 | 0,6206 | 1,0329 | 1900 |
| 365 | 0,6198 | 1,0320 | 1900 |
| 730 | 0,6201 | 1,0324 | 1900 |
| 1460 | 0,6208 | 1,0335 | 1900 |
