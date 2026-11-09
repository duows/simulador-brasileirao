# futdados

Sistema de dados do canal: probabilidades estimadas pelo modelo para cada jogo do
Brasileirão Série A, projeção da tabela depois da rodada X e JSONs prontos para os
vídeos em Remotion. Foco no São Paulo FC, cobrindo a Série A inteira.

> **Como o canal fala:** o sistema descreve o que é provável com base em dados
> históricos e no desempenho recente. Ele não prevê o que vai acontecer. Usamos
> "probabilidade estimada pelo modelo" e "projeção". Nada de aposta: o projeto não
> coleta, não compara e não exibe odds de casa nenhuma. Todo JSON de saída traz o campo
> `"aviso": "Projeção estatística baseada em dados históricos. Não é recomendação de aposta."`

Football data provided by the Football-Data.org API.

## Como usar (o jeito simples)

1. Uma vez só, no PowerShell, salve a sua chave do football-data.org (feche e abra o terminal depois):
   `setx FOOTBALL_DATA_TOKEN "sua-chave"`
2. Para **não precisar rodar nada**: dê duplo clique uma vez em `scripts/agendar_atualizacao.bat`. Ele cria uma
   tarefa do Windows que atualiza tudo sozinha todo dia às 10h e às 17h (com o PC ligado). Depois, para ver,
   use **`ABRIR_SITE.bat`** (só abre, na hora). Se preferir na mão, **`ATUALIZAR_E_ABRIR.bat`** atualiza e abre.
   No Cartola, a previsão é gravada uma vez por rodada: a página mostra os times gravados para você escalar
   exatamente o que vai ser comparado.
3. (Antigo passo 2) A cada rodada, dê **duplo clique em `ATUALIZAR_E_ABRIR.bat`**. Ele baixa os jogos, reestima o
   modelo, recalcula métricas e Elo, grava as previsões da rodada (antes dos jogos), roda o Cartola
   e abre o site em http://localhost:3001, com escudos e fotos (modo local).
3. No site: **Tabela** (projeção até o fim), **Rodada**, **Times**, **Temporadas**, **Histórico**,
   **Simulador** ("e se") e **Cartola** (digite as cartoletas e o time sai na hora).

Por baixo, o atalho chama `futdados atualizar` (a mesma rotina pelo terminal).

## O modelo erra, e mostramos quanto

Backtest walk-forward 2015–2024 (3.671 jogos; 2024 só até setembro, ver Limitações),
com pesos estimados só com temporadas anteriores a cada uma. Detalhes e calibração em [reports/backtest.md](reports/backtest.md).

| Método | Brier | Log loss | Acerto do resultado mais provável |
|---|---|---|---|
| **Modelo** | **0,6143** | **1,0242** | **49,4%** |
| Frequência histórica (mandante/empate/visitante) | 0,6337 | 1,0518 | 48,2% |
| Sempre mandante | 1,0357 | — (infinito) | 48,2% |
| Chute de 1/3 para tudo | 0,6667 | 1,0986 | — |

O que isso quer dizer, sem enfeite:

- O modelo supera os dois baselines **em todas as 10 temporadas** de teste, mas a
  vantagem é pequena: 3,1% no Brier e 2,6% no log loss sobre a frequência histórica.
  Em 2017 a diferença quase some (0,654 contra 0,657).
- O resultado mais provável segundo o modelo acontece em cerca de **metade** dos jogos.
  Em 1 de cada 2 jogos o resultado é outro. É por isso que falamos em probabilidade.
- Calibração boa: o modelo estimou empate em 26,8% dos jogos e houve 26,9% de empates.
- Cada rodada nova gera um Brier próprio no comando `post-round`, publicado junto com o vídeo.

## Fatores e pesos

Sete fatores, com peso explícito e intervalo de incerteza em [reports/pesos.md](reports/pesos.md):
força de ataque e fragilidade da defesa adversária (longo prazo, com decaimento de
meia-vida de 180 dias), mando de campo, forma recente (5 jogos), dias de descanso, jogo
no meio da semana e troca recente de técnico. Mando (+49% nos gols esperados) e as
forças de longo prazo dominam. Forma pesa pouco. Descanso não tem efeito distinguível de
zero. **Técnico novo está desligado na prática**: a fonte histórica não traz técnicos, então
o peso não é estimável e fica 0.

Cada jogo no JSON traz `"fatores"`: quanto cada um somou ou tirou dos gols esperados de
cada time (a soma bate com o total) e o multiplicador correspondente.

## Limitações

- **Sem xG**: o modelo usa só gols, que são poucos e têm muito acaso.
- **Sem escalação**: não sabe de desfalques, poupados, lesões nem suspensões.
- **Só Série A**: jogos de Copa do Brasil, Libertadores e Sul-Americana não entram no
  descanso nem na forma. Um time que jogou no meio da semana pela copa aparece como descansado.
- **Buraco nos dados**: o footballcsv para em setembro de 2024 (252 de 380 jogos) e não
  tem 2025. Até rodar `ingest-api --season 2024` e `--season 2025` (se o plano grátis
  liberar temporadas passadas), as forças de 2026 partem de dados de 2024. O
  `simulate-season` mostra um alerta quando isso acontece.
- **Técnico novo**: sem técnico por jogo no histórico, o peso fica 0. As trocas da
  temporada corrente continuam sendo registradas (API e `config/coach_changes.csv`) para
  quando houver histórico com técnicos.
- **Promovidos** partem do desempenho médio histórico de promovidos no primeiro ano
  (cerca de 12% menos gols marcados e 11% mais sofridos que a média), estimado só com
  temporadas anteriores.
- **Projeção**: as forças não se atualizam dentro da simulação, e forma/técnico novo só
  valem para a próxima rodada. Mudanças grandes no elenco (janela de transferências) não
  são vistas até aparecerem nos resultados.
- **Desempate**: ordem baseada na imprensa sobre o regulamento de 2026, a confirmar no
  PDF oficial da CBF. Cartões não estão disponíveis e viram sorteio.
- **Pré-temporada**: não enxerga contratações nem vendas da janela; a força vem só dos
  resultados. A faixa de posição é larga de propósito: antes da 1ª rodada a incerteza é grande.

## Instalação

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```

A chave do football-data.org vai só na variável de ambiente (nunca no código):

```bash
export FOOTBALL_DATA_TOKEN="sua-chave"
```

## Comandos

```bash
futdados ingest-historical
```

```bash
futdados update --season 2026
```

```bash
futdados predict-round --season 2026
```

```bash
futdados project --season 2026 --round 30
```

```bash
futdados post-round --season 2026 --round 30
```

```bash
futdados simulate-season --season 2026
```

| Comando | O que faz |
|---|---|
| `ingest-historical` | Baixa (git clone raso) e carrega 2010-2024 do footballcsv (CC0) |
| `ingest-api --season S` | Jogos, classificação e técnicos da temporada pela API (3 requisições) |
| `fit [--half-life D]` | Escolhe a meia-vida no walk-forward, estima os pesos, gera `reports/pesos.md` |
| `update --season S` | `ingest-api` + `fit` |
| `backtest` | Walk-forward por temporada, gera `reports/backtest.md` |
| `predict-round --season S [--round N] [--repetir]` | Estima a primeira rodada sem jogos disputados e, à parte, os jogos adiados; grava no registro imutável (sem duplicar) e gera `out/videos/rodada-S-rNN-estimativas.json` |
| `project --season S [--round X]` | Tabela projetada depois da rodada X (padrão: fim do campeonato) |
| `post-round --season S --round N` | Estimado x real, Brier da rodada, variação das chances do SPFC, tabela atualizada |
| `verify-registry` | Confere a cadeia de hashes do registro de previsões |
| `simulate-season --season S [--teams a,b,...]` | Pré-temporada: simula o campeonato inteiro (10 mil vezes) com o calendário da API ou uma tabela balanceada gerada a partir de `--teams` |

Rotina de uma rodada: `update` → `predict-round` (antes do primeiro jogo) → jogos →
`update` → `post-round`.

### Registro imutável

As previsões ficam na tabela `predictions` do SQLite. Triggers impedem UPDATE e DELETE,
uma restrição recusa previsões gravadas depois do início do jogo, e cada linha guarda o
hash da anterior (cadeia SHA-256). O `post-round` usa a última previsão gravada antes de
cada jogo. Para auditoria pública, vale publicar o hash da última linha junto com o vídeo.

## Site (dashboard)

Site estático em Next.js (pasta `site/`), escuro, em português, que lê só os arquivos de
`site/public/data` gerados pelo pipeline. Nenhuma chamada à API por visitante, sem escudos,
fotos ou odds. Páginas: Tabela projetada, Rodada (com adiados à parte), Simulador “e se”
(recalcula no navegador), Modelo (pesos, backtest, limitações) e São Paulo (posição, chances,
jogos que faltam e finanças com fonte). Todas mostram o aviso, a atribuição e a data da última
atualização.

```bash
futdados export-site --season 2026
```

```bash
cd site && npm install && npm run dev
```

Abra http://localhost:3000. Para gerar o HTML estático: `npm run build` (sai em `site/out/`),
e `npm start` serve essa pasta em http://localhost:4173.

## Cartola (estudo de caso pessoal, só local)

`futdados cartola --budget 120` baixa os dados da rodada (API pública e não oficial do Cartola),
calcula a pontuação esperada de cada atleta (média ajustada + contexto do jogo vindo do modelo)
e monta o melhor time para o orçamento (esquema, atletas e capitão, solução exata). A página
`/cartola` do site faz o mesmo no navegador: você digita as cartoletas e o time aparece, com os
fatores de cada atleta. Nada do Cartola vai para o git (ver D24). Backtest em
[reports/cartola.md](reports/cartola.md): erro 2,84 contra 2,95 da média do Cartola.

## Saídas para vídeo

Exemplos reais em [docs/exemplos](docs/exemplos). Todo JSON tem `tipo`, `gerado_em`,
`versao_modelo`, `aviso`, `atribuicao` ("Football data provided by the Football-Data.org API"),
`linguagem` e `fontes`.

- `rodada-<temporada>-r<NN>-estimativas.json`: gols esperados, probabilidade estimada de
  vitória do mandante, empate e vitória do visitante (da matriz de placares), placar mais
  provável e fatores de cada jogo.
- `tabela-projetada-<temporada>-apos-r<X>-base-r<N>.json`: pontos esperados, faixa de
  posição (p10-p90), chance de título, G4, G6 e rebaixamento.
- `pos-rodada-<temporada>-r<NN>.json`: comparação estimado x real e Brier da rodada.
- `pre-temporada-<temporada>.json`: força inicial de cada time, pontos esperados, faixa de
  posição final (p10-p90) e chances de título, G4, G6 e rebaixamento.

## Estrutura

```
src/futdados/   ingest/ model/ simulate/ backtest/ cli.py db.py pipeline.py reports.py
config/         model.yaml (todos os pesos e parâmetros), teams.csv, coach_changes.csv
data/           futdados.sqlite, raw/ (JSON bruto da API), finance/, model/weights.json
reports/        pesos.md, backtest.md, spfc_financas.md
docs/           DECISIONS.md (termos de uso, licenças e escolhas), exemplos/
```

O acesso a dados fica todo em `src/futdados/db.py` (`Repository`), para migrar para
Postgres depois sem mexer no resto.

## Finanças

`data/finance/spfc.csv` e `data/finance/comparativo_clubes.csv` trazem receita, dívida,
resultado, passivo a descoberto, venda de atletas, despesa do futebol, FIDC e dívida com
empresários (2023-2025), cada número com URL, página do PDF e data de consulta. Fontes que
divergem ficam registradas lado a lado como conflito. Resumo, lacunas e perguntas em aberto em
[reports/spfc_financas.md](reports/spfc_financas.md).

## Fontes

- Temporada corrente: [football-data.org](https://www.football-data.org), plano grátis (ver D02 em DECISIONS.md).
  **Football data provided by the Football-Data.org API.**
- Histórico 2010-2024: [footballcsv/cache.wfb](https://github.com/footballcsv/cache.wfb), domínio
  público (CC0 1.0). O [footballcsv/world](https://github.com/footballcsv/world) só tem 2019-2020
  da Série A (ver D14).

## Testes

```bash
.venv/Scripts/python -m pytest -q
```
