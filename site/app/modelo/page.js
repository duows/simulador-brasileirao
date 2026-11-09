import { load } from "../../lib/data";
import { num, pct, signed } from "../../lib/format";

export const metadata = { title: "Modelo · futdados" };

const METHODS = [
  ["modelo", "Modelo"],
  ["frequencia_historica", "Frequência histórica (mandante / empate / visitante)"],
  ["sempre_mandante", "Sempre mandante (100% para o mandante)"],
];

export default function Modelo() {
  const m = load("modelo");
  const bt = m.backtest;
  const gain = bt ? 1 - bt.metricas.modelo.brier / bt.metricas.frequencia_historica.brier : null;
  const worse = bt ? bt.por_temporada.filter((s) => s.brier_modelo >= s.brier_freq).map((s) => s.temporada) : [];
  return (
    <>
      <h1>Como o modelo funciona e quanto ele erra</h1>
      <p className="lead">
        Regressão de Poisson para os gols de cada time, com poucos fatores e peso explícito para cada um. Treino com
        {" "}{num(m.jogos_treino, 0)} jogos ({m.temporadas_treino[0]}–{m.temporadas_treino[1]}). A força de longo prazo usa
        decaimento com meia-vida de {num(m.meia_vida_dias, 0)} dias: um jogo desse tempo atrás vale metade de um jogo de hoje.
      </p>

      <h2>Pesos dos fatores</h2>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Fator</th><th>Peso</th><th>Intervalo 95%</th><th className="l">Exemplo</th><th className="l">Leitura</th></tr></thead>
          <tbody>
            {m.fatores.map((f) => (
              <tr key={f.fator}>
                <td className="l">{f.rotulo}</td>
                <td>{num(f.peso, 3)}</td>
                <td>{f.estimavel ? `${num(f.ic95[0], 3)} a ${num(f.ic95[1], 3)}` : "—"}</td>
                <td className="l wrap-cell">{f.estimavel ? `${f.exemplo}: ${signed(f.efeito_exemplo * 100, 1)}% nos gols esperados` : "sem dados no histórico"}</td>
                <td className="l">{!f.estimavel ? "não estimável (peso fixado em 0)" : f.distinguivel_de_zero ? "efeito detectado" : "não distinguível de zero"}</td>
              </tr>
            ))}
          </tbody>
          <caption>Intervalo de 95% por bootstrap de jogos. Quando ele cruza o zero, os dados não permitem afirmar que o fator tem efeito.</caption>
        </table>
      </div>

      {bt && (
        <>
          <h2>Backtest: o modelo contra referências simples</h2>
          <p className="lead">
            Validação walk-forward {bt.temporadas[0]}–{bt.temporadas[bt.temporadas.length - 1]} ({num(bt.n, 0)} jogos): para
            prever cada temporada, os pesos foram estimados só com as temporadas anteriores.
            {gain != null && <> O modelo erra {pct(gain)} menos que a frequência histórica no Brier. Ganha, mas por pouco.</>}
            {worse.length > 0 ? <> Não bateu a frequência histórica em: {worse.join(", ")}.</> : <> Bateu a frequência histórica em todas as temporadas de teste.</>}
          </p>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Método</th><th>Brier</th><th>Log loss</th><th>Acerto do resultado mais provável</th></tr></thead>
              <tbody>
                {METHODS.map(([k, label]) => (
                  <tr key={k} className={k === "modelo" ? "focus" : undefined}>
                    <td className="l">{label}</td>
                    <td>{num(bt.metricas[k].brier, 4)}</td>
                    <td>{k === "sempre_mandante" ? "infinito*" : num(bt.metricas[k].log_loss, 4)}</td>
                    <td>{pct(bt.metricas[k].acerto)}</td>
                  </tr>
                ))}
                <tr><td className="l">Chute de 1/3 para cada resultado</td><td>{num(2 / 3, 4)}</td><td>{num(Math.log(3), 4)}</td><td>—</td></tr>
              </tbody>
              <caption>Menor é melhor no Brier (0 a 2) e no log loss. *“Sempre mandante” dá probabilidade zero a empates e derrotas.</caption>
            </table>
          </div>

          <h2>Por temporada</h2>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Temporada</th><th>Jogos</th><th>Brier modelo</th><th>Brier frequência</th><th>Log loss modelo</th><th>Log loss frequência</th></tr></thead>
              <tbody>
                {bt.por_temporada.map((s) => (
                  <tr key={s.temporada}>
                    <td className="l">{s.temporada}</td><td>{s.n}</td>
                    <td>{num(s.brier_modelo, 4)}</td><td>{num(s.brier_freq, 4)}</td>
                    <td>{num(s.ll_modelo, 4)}</td><td>{num(s.ll_freq, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Calibração</h2>
          <p className="lead">
            Quando o modelo diz 40%, o evento deveria acontecer perto de 40% das vezes. Empates: estimados em
            {" "}{pct(bt.empate_estimado)} dos jogos, aconteceram em {pct(bt.empate_observado)}.
          </p>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Resultado</th><th className="l">Faixa estimada</th><th>Jogos</th><th>Estimado</th><th>Observado</th></tr></thead>
              <tbody>
                {bt.calibracao.filter((c) => c.n >= 20).map((c) => (
                  <tr key={`${c.resultado}-${c.faixa}`}>
                    <td className="l">{c.resultado}</td><td className="l">{c.faixa}</td><td>{c.n}</td>
                    <td>{pct(c.estimado)}</td><td>{pct(c.observado)}</td>
                  </tr>
                ))}
              </tbody>
              <caption>Faixas com menos de 20 jogos omitidas.</caption>
            </table>
          </div>
        </>
      )}

      <h2>Limitações</h2>
      <ul className="plain">
        <li><strong>Sem xG e sem escalação.</strong> O modelo só vê gols: não sabe de desfalques, poupados, lesões ou suspensões.</li>
        <li><strong>Só Série A.</strong> Jogos de copas não entram no descanso nem na forma.</li>
        <li><strong>Troca de técnico sem efeito.</strong> A fonte histórica não traz técnicos, então o peso não pode ser estimado e fica 0.</li>
        <li><strong>Duas fontes de dados.</strong> 2010 a 2023 vêm do footballcsv (domínio público); de 2024 em diante, da API do football-data.org.</li>
        <li><strong>Promovidos</strong> partem do desempenho médio histórico de promovidos no primeiro ano.</li>
        <li><strong>Projeção.</strong> As forças não se atualizam dentro da simulação; mudanças de elenco só aparecem quando viram resultado.</li>
        <li><strong>Desempate.</strong> Ordem baseada na imprensa sobre o regulamento, a confirmar no documento oficial da CBF; cartões viram sorteio.</li>
        <li><strong>O resultado mais provável acontece em cerca de metade dos jogos.</strong> Por isso falamos em probabilidade, nunca em certeza.</li>
      </ul>
    </>
  );
}
