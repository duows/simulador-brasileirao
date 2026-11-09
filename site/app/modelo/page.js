import { load } from "../../lib/data";
import { num, pct, signed } from "../../lib/format";

export const metadata = { title: "Modelo · futdados" };

const NAMES = {
  conjunto: "Conjunto (média ponderada)", conjunto_calibrado: "Conjunto calibrado",
  forcas_map: "Forças por time (MAP)", base_elo: "Baseline: Elo puro", ordinal: "Logística ordinal com fatores",
  poisson: "Poisson de 7 fatores", dixon_coles: "Poisson + Dixon-Coles", boosting: "Gradient boosting",
  base_freq: "Baseline: frequência histórica", base_mandante: "Baseline: sempre mandante",
};
const EXPLAIN = {
  base_elo: "Cada time tem uma nota que sobe quando ganha e cai quando perde, mais quando o adversário é forte. A diferença de notas vira probabilidade.",
  forcas_map: "Estima ataque e defesa de cada time com os jogos anteriores (os recentes pesam mais), puxando para a média quando há pouco dado.",
  poisson: "Gols esperados de cada time a partir de 7 fatores com peso explícito (força de longo prazo, mando, forma, descanso...).",
  ordinal: "Liga diretamente os fatores (diferença de Elo, ataque, defesa, forma) à chance de vitória, empate e derrota.",
  conjunto: "Média ponderada dos melhores modelos, com pesos escolhidos nas temporadas anteriores.",
  boosting: "Árvores de decisão combinadas. Mais flexível e menos transparente: só entraria se ganhasse com folga.",
};

export default function Modelo() {
  const m = load("modelo");
  const bt = m.backtest;
  const elo = bt?.elo;
  return (
    <>
      <p className="eyebrow">Laboratório do modelo</p>
      <h1>Como os modelos funcionam e quanto eles erram</h1>
      <p className="lead">
        Vários modelos foram testados do mesmo jeito: para prever cada temporada, cada um só usou as temporadas anteriores
        (walk-forward, sem vazamento). A métrica principal é o RPS (ranked probability score): mede a distância entre a
        probabilidade estimada e o que aconteceu, respeitando que empate fica entre vitória e derrota. Quanto menor, melhor.
      </p>

      {bt && (
        <>
          <h2>Placar entre modelos</h2>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Modelo</th><th>RPS</th><th>Log loss</th><th>Acerto</th><th>Diferença para o Elo (IC 90%)</th><th>Temporadas melhor que o Elo</th></tr></thead>
              <tbody>
                {bt.placar.map((r) => {
                  const d = bt.diferenca_vs_elo[r.modelo];
                  return (
                    <tr key={r.modelo} className={r.modelo === bt.placar[0].modelo ? "focus" : undefined}>
                      <td className="l" title={EXPLAIN[r.modelo] || ""}>{NAMES[r.modelo] || r.modelo}</td>
                      <td>{num(r.rps, 4)}</td>
                      <td>{r.log_loss > 5 ? "infinito" : num(r.log_loss, 4)}</td>
                      <td>{pct(r.acerto)}</td>
                      <td>{d ? `${signed(d[0], 4)} (${signed(d[1], 4)} a ${signed(d[2], 4)})` : "—"}</td>
                      <td>{bt.temporadas_melhor_que_elo[r.modelo] || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
              <caption>
                {bt.temporadas[0]}–{bt.temporadas[bt.temporadas.length - 1]}, {num(bt.n, 0)} jogos. Diferença negativa = erra menos que o
                Elo. Intervalo por bootstrap de temporadas inteiras.
              </caption>
            </table>
          </div>

          <h2>O que o placar diz, sem enfeite</h2>
          <ul className="plain">
            <li>O melhor modelo (<strong>{NAMES[bt.placar[0].modelo]}</strong>) ganha do Elo puro por uma margem minúscula, e o intervalo cruza o zero: não dá para afirmar que é melhor.</li>
            <li>O <strong>Poisson de 7 fatores</strong> perde do Elo puro em todas as temporadas. Ele continua bem melhor que a frequência histórica.</li>
            <li>Todos ganham com folga da frequência histórica, cerca de 5% no RPS. O resultado mais provável acontece em metade dos jogos.</li>
            <li>Dixon-Coles, gradient boosting e calibração extra não melhoraram e ficam desligados.</li>
          </ul>

          <h2>Como cada modelo funciona</h2>
          <div className="grid">
            {Object.entries(EXPLAIN).map(([k, v]) => (
              <section key={k} className="card"><h3>{NAMES[k]}</h3><p className="small" style={{ margin: 0 }}>{v}</p></section>
            ))}
          </div>
          {elo && (
            <p className="small muted">
              Elo calibrado nas temporadas {elo.temporadas_ajuste[0]}–{elo.temporadas_ajuste[elo.temporadas_ajuste.length - 1]}:
              K = {num(elo.k, 0)}, mando = {num(elo.home, 0)} pontos, regressão de {pct(elo.regression)} à média entre temporadas,
              promovidos {num(elo.promoted, 0)} pontos em relação à média.
            </p>
          )}

          <h2>Por fase da temporada (RPS)</h2>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Fase</th>{Object.keys(bt.por_fase[0]).filter((k) => k !== "fase").map((k) => <th key={k}>{NAMES[k]}</th>)}</tr></thead>
              <tbody>
                {bt.por_fase.map((r) => (
                  <tr key={r.fase}><td className="l">{r.fase}</td>
                    {Object.entries(r).filter(([k]) => k !== "fase").map(([k, v]) => <td key={k}>{num(v, 4)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Calibração do conjunto</h2>
          <p className="lead">Quando o modelo diz 40%, o evento deveria acontecer perto de 40% das vezes.</p>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Resultado</th><th className="l">Faixa estimada</th><th>Jogos</th><th>Estimado</th><th>Observado</th></tr></thead>
              <tbody>
                {bt.calibracao.filter((c) => c.n >= 30).map((c) => (
                  <tr key={`${c.resultado}-${c.faixa}`}><td className="l">{c.resultado}</td><td className="l">{c.faixa}</td><td>{c.n}</td>
                    <td>{pct(c.estimado)}</td><td>{pct(c.observado)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Ablação dos fatores do Poisson</h2>
          <p className="lead">Quanto o RPS piora sem cada fator (positivo = o fator ajuda). Fator sem ganho fica desligado e documentado.</p>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Fator</th><th>Δ RPS sem o fator</th><th>IC 90%</th><th className="l">Decisão</th></tr></thead>
              <tbody>
                {bt.ablacao.map((a) => (
                  <tr key={a.fator}><td className="l">{a.fator}</td>
                    <td>{a.delta_rps == null ? "—" : signed(a.delta_rps, 5)}</td>
                    <td>{a.ic90?.[0] == null ? "—" : `${signed(a.ic90[0], 5)} a ${signed(a.ic90[1], 5)}`}</td>
                    <td className="l">{a.decisao}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {m.backtest_simulacao && (
        <>
          <h2>A simulação do campeonato acerta?</h2>
          <p className="lead">
            Para cada temporada de 2015 a 2025, a projeção foi refeita como se estivéssemos nas rodadas 10, 20 e 30 e comparada
            com a classificação final. Brier menor é melhor; entre parênteses, o de dar a mesma chance para todos os times.
            A posição final caiu dentro da faixa p10–p90 em {pct(m.backtest_simulacao.faixa_p10_p90)} dos casos (o ideal seria perto de 80%: a faixa é um pouco conservadora).
          </p>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Rodada de corte</th><th>Título</th><th>G4</th><th>Rebaixamento</th><th>Dentro da faixa</th></tr></thead>
              <tbody>
                {m.backtest_simulacao.por_corte.map((r) => (
                  <tr key={r.corte}><td className="l">{r.corte}</td>
                    <td>{num(r.brier_titulo, 3)} ({num(r.brier_base_titulo, 3)})</td>
                    <td>{num(r.brier_g4, 3)} ({num(r.brier_base_g4, 3)})</td>
                    <td>{num(r.brier_rebaixamento, 3)} ({num(r.brier_base_rebaixamento, 3)})</td>
                    <td>{pct(r.dentro_da_faixa)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>Pesos do Poisson de 7 fatores</h2>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Fator</th><th>Peso</th><th>Intervalo 95%</th><th className="l">Exemplo</th></tr></thead>
          <tbody>
            {m.fatores.map((f) => (
              <tr key={f.fator}>
                <td className="l">{f.rotulo}</td><td>{num(f.peso, 3)}</td>
                <td>{f.estimavel ? `${num(f.ic95[0], 3)} a ${num(f.ic95[1], 3)}` : "—"}</td>
                <td className="l wrap-cell">{f.estimavel ? `${f.exemplo}: ${signed(f.efeito_exemplo * 100, 1)}% nos gols esperados` : "sem dados no histórico"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Limitações</h2>
      <ul className="plain">
        <li><strong>Sem xG e sem escalação.</strong> Os modelos só veem gols: não sabem de desfalques, poupados, lesões ou suspensões.</li>
        <li><strong>Só Série A.</strong> Jogos de copas não entram no descanso nem na forma.</li>
        <li><strong>Troca de técnico sem efeito.</strong> As fontes abertas não trazem técnico por jogo.</li>
        <li><strong>Fontes:</strong> 2006 a 2023 do footballcsv (domínio público); de 2024 em diante, da API do football-data.org.</li>
        <li><strong>O resultado mais provável acontece em cerca de metade dos jogos.</strong> Por isso falamos em probabilidade, nunca em certeza.</li>
      </ul>
    </>
  );
}
