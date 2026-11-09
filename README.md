# futdados

Sistema de dados do canal: probabilidades estimadas pelo modelo para cada jogo do
Brasileirão Série A, projeção da tabela depois da rodada X e JSONs prontos para os
vídeos em Remotion. Foco no São Paulo FC, cobrindo a Série A inteira.

> **Como o canal fala:** o sistema descreve o que é provável com base em dados
> históricos e no desempenho recente. Ele não prevê o que vai acontecer. Usamos
> "probabilidade estimada pelo modelo" e "projeção". Nada de aposta: o projeto não
> coleta, não compara e não exibe odds de casa nenhuma. Todo JSON de saída traz o campo
> `"aviso": "Projeção estatística baseada em dados históricos. Não é recomendação de aposta."`

## O modelo erra, e mostramos quanto

Backtest walk-forward 2015–2025 (4.179 jogos, pesos estimados só com temporadas
anteriores a cada uma). Detalhes e calibração em [reports/backtest.md](reports/backtest.md).

| Método | Brier | Log loss | Acerto do resultado mais provável |
|---|---|---|---|
| **Modelo** | **0,6121** | **1,0208** | **49,6%** |
| Frequência histórica (mandante/empate/visitante) | 0,6335 | 1,0515 | 48,3% |
| Sempre mandante | 1,0347 | — (infinito) | 48,3% |
| Chute de 1/3 para tudo | 0,6667 | 1,0986 | — |

O que isso quer dizer, sem enfeite:

- O modelo supera os dois baselines **em todas as 11 temporadas** de teste, mas a
  vantagem é pequena: 3,4% no Brier e 2,9% no log loss sobre a frequência histórica.
- O resultado mais provável segundo o modelo acontece em cerca de **metade** dos jogos.
  Em 1 de cada 2 jogos o resultado é outro. É por isso que falamos em probabilidade.
- Calibração boa: o modelo estimou empate em 26,9% dos jogos e houve 26,9% de empates.
  Nas faixas mais extremas do mandante (20%-30%) o modelo exagerou a chance do mandante.
- Cada rodada nova gera um Brier próprio no comando `post-round`, publicado junto com o vídeo.

## Fatores e pesos

Sete fatores, com peso explícito e intervalo de incerteza em [reports/pesos.md](reports/pesos.md):
força de ataque e fragilidade da defesa adversária (longo prazo, com decaimento de
meia-vida de 365 dias), mando de campo, forma recente (5 jogos), dias de descanso, jogo
no meio da semana e troca recente de técnico. Mando (+51% nos gols esperados) e as
forças de longo prazo dominam. Forma pesa pouco. Descanso e técnico novo não têm efeito
distinguível de zero nos dados; ficaram no modelo porque faziam parte do desenho
inicial, e o peso perto de zero faz com que quase não mexam nos números.

Cada jogo no JSON traz `"fatores"`: quanto cada um somou ou tirou dos gols esperados de
cada time (a soma bate com o total) e o multiplicador correspondente.

## Limitações

- **Sem xG**: o modelo usa só gols, que são poucos e têm muito acaso.
- **Sem escalação**: não sabe de desfalques, poupados, lesões nem suspensões.
- **Só Série A**: jogos de Copa do Brasil, Libertadores e Sul-Americana não entram no
  descanso nem na forma. Um time que jogou no meio da semana pela copa aparece como descansado.
- **Técnico novo**: só há técnico por jogo no histórico a partir de 2014; na temporada
  corrente a troca é detectada pelos dados da API ou registrada à mão em
  `config/coach_changes.csv`. Interinos e grafias diferentes contam como troca.
- **Promovidos** começam com força a priori 15% pior que a média (valor fixo, não estimado).
- **Projeção**: as forças não se atualizam dentro da simulação, e forma/técnico novo só
  valem para a próxima rodada. Mudanças grandes no elenco (janela de transferências) não
  são vistas até aparecerem nos resultados.
- **Desempate**: ordem baseada na imprensa sobre o regulamento de 2026, a confirmar no
  PDF oficial da CBF. Cartões não estão disponíveis e viram sorteio.
- **Horário**: o histórico usa horário de Brasília convertido com +3 h.

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

| Comando | O que faz |
|---|---|
| `ingest-historical` | Baixa (git clone raso) e carrega 2003-2025 do dataset histórico |
| `ingest-api --season S` | Jogos, classificação e técnicos da temporada pela API (3 requisições) |
| `fit [--half-life D]` | Escolhe a meia-vida no walk-forward, estima os pesos, gera `reports/pesos.md` |
| `update --season S` | `ingest-api` + `fit` |
| `backtest` | Walk-forward por temporada, gera `reports/backtest.md` |
| `predict-round --season S [--round N]` | Estima a rodada, grava no registro imutável e gera `out/videos/rodada-S-rNN-estimativas.json` |
| `project --season S [--round X]` | Tabela projetada depois da rodada X (padrão: fim do campeonato) |
| `post-round --season S --round N` | Estimado x real, Brier da rodada, variação das chances do SPFC, tabela atualizada |
| `verify-registry` | Confere a cadeia de hashes do registro de previsões |

Rotina de uma rodada: `update` → `predict-round` (antes do primeiro jogo) → jogos →
`update` → `post-round`.

### Registro imutável

As previsões ficam na tabela `predictions` do SQLite. Triggers impedem UPDATE e DELETE,
uma restrição recusa previsões gravadas depois do início do jogo, e cada linha guarda o
hash da anterior (cadeia SHA-256). O `post-round` usa a última previsão gravada antes de
cada jogo. Para auditoria pública, vale publicar o hash da última linha junto com o vídeo.

## Saídas para vídeo

Exemplos reais em [docs/exemplos](docs/exemplos). Todo JSON tem `tipo`, `gerado_em`,
`versao_modelo`, `aviso`, `linguagem` e `fontes`.

- `rodada-<temporada>-r<NN>-estimativas.json`: gols esperados, probabilidade estimada de
  vitória do mandante, empate e vitória do visitante (da matriz de placares), placar mais
  provável e fatores de cada jogo.
- `tabela-projetada-<temporada>-apos-r<X>-base-r<N>.json`: pontos esperados, faixa de
  posição (p10-p90), chance de título, G4, G6 e rebaixamento.
- `pos-rodada-<temporada>-r<NN>.json`: comparação estimado x real e Brier da rodada.

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

## Fontes

- Temporada corrente: [football-data.org](https://www.football-data.org), plano grátis (ver D02 em DECISIONS.md).
- Histórico 2003-2025: [Brasileirao_Dataset](https://github.com/adaoduque/Brasileirao_Dataset),
  de Adão Duque. O repositório não declara licença; não redistribuímos o dataset (ver D03).

## Testes

```bash
.venv/Scripts/python -m pytest -q
```
