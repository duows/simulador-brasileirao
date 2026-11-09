# Cobertura de dados 2006-2026

Jogos esperados contra existentes no banco, por temporada, com a fonte usada e a licença.
Regra de fonte: football-data.org > footballcsv > adaoduque (este só local, nunca no banco).

| Temporada | Esperados | No banco | Encerrados | Adiados | Remarcados | Portões fechados | Fonte | Licença |
|---|---|---|---|---|---|---|---|---|
| 2006 | 380 | 380 | 380 | 0 | 2 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2007 | 380 | 380 | 380 | 0 | 8 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2008 | 380 | 380 | 380 | 0 | 0 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2009 | 380 | 380 | 380 | 0 | 3 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2010 | 380 | 380 | 380 | 0 | 2 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2011 | 380 | 380 | 380 | 0 | 5 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2012 | 380 | 380 | 380 | 0 | 2 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2013 | 380 | 380 | 380 | 0 | 9 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2014 | 380 | 380 | 380 | 0 | 4 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2015 | 380 | 380 | 380 | 0 | 0 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2016 | 379 | 379 | 379 | 0 | 2 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2017 | 380 | 380 | 380 | 0 | 3 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2018 | 380 | 380 | 380 | 0 | 6 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2019 | 380 | 380 | 380 | 0 | 4 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2020 | 380 | 380 | 380 | 0 | 19 | 380 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2021 | 380 | 380 | 380 | 0 | 20 | 214 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2022 | 380 | 380 | 380 | 0 | 5 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2023 | 380 | 380 | 380 | 0 | 8 | 0 | footballcsv/cache.wfb | CC0 1.0 (procedência: cache do worldfootball.net, ver D14) |
| 2024 | 380 | 380 | 380 | 0 | 16 | 0 | football-data.org API v4 | plano grátis; atribuição obrigatória (D02, D15) |
| 2025 | 380 | 380 | 380 | 0 | 19 | 0 | football-data.org API v4 | plano grátis; atribuição obrigatória (D02, D15) |
| 2026 | 380 | 380 | 339 | 1 | 8 | 0 | football-data.org API v4 | plano grátis; atribuição obrigatória (D02, D15) |

## Notas por temporada

- **2016**: Chapecoense x Atlético-MG (38ª rodada) não foi disputado após o acidente aéreo da Chapecoense; o resultado não entrou na tabela.
- **2020**: Temporada disputada de agosto de 2020 a fevereiro de 2021, sem público (pandemia).
- **2021**: Público voltou aos poucos a partir de outubro de 2021, com regras diferentes por estado (TODO: datas por jogo).
- **2026**: Ordem de desempate pela imprensa sobre o Art. 15 do Regulamento Específico 2026; houve divergência pública na leitura do § 2º.

## Checagens de qualidade

- Nenhum problema: sem duplicados, placares válidos, sem time com dois jogos na mesma rodada, turno e returno simétricos, 38 jogos por time e soma de pontos consistente nas temporadas encerradas.

Flags: adiado = não disputado numa rodada que já teve jogos; remarcado = disputado a 7+ dias da data mediana da rodada; portões fechados = período definido em config/seasons.yaml. Campo neutro: sem fonte (TODO).
