import { RangeBar } from "../../components/ProjectionTable";
import { load } from "../../lib/data";
import { outcomeProbs, scoreMatrix } from "../../lib/simulate.mjs";
import { brlMi, dateTimeBR, num, pct } from "../../lib/format";

export const metadata = { title: "São Paulo · futdados" };

const FIELDS = [
  ["receita_operacional", "Receita operacional"],
  ["divida_total", "Dívida / endividamento"],
  ["resultado", "Resultado do ano"],
  ["passivo_a_descoberto", "Passivo a descoberto"],
  ["venda_atletas", "Venda de atletas"],
  ["despesa_futebol_profissional", "Despesa do futebol profissional"],
  ["fidc", "FIDC (cotas do clube)"],
  ["divida_empresarios", "Dívida com empresários"],
  ["receita_estadio", "Receita do estádio (Morumbis)"],
];
const YEARS = ["2023", "2024", "2025"];
const STATUS = {
  confirmado: ["ok", "confirmado no PDF"], conflito: ["conf", "fontes divergem"],
  nao_confirmado: ["pend", "não confirmado"], lacuna: ["pend", "lacuna"], nao_aplicavel: ["pend", "não se aplica"],
};
const CLUBS = [["palmeiras", "Palmeiras"], ["corinthians", "Corinthians"], ["flamengo", "Flamengo"], ["santos", "Santos"]];

/** Posição atual pela tabela real (pontos, vitórias, saldo, gols pró). */
function currentPosition(sim, idx) {
  const a = sim.atual;
  const order = sim.times.map((_, i) => i).sort((x, y) =>
    a.pts[y] - a.pts[x] || a.v[y] - a.v[x] || (a.gp[y] - a.gc[y]) - (a.gp[x] - a.gc[x]) || a.gp[y] - a.gp[x]);
  return order.indexOf(idx) + 1;
}

function Source({ r }) {
  if (!r.fonte_url) return <span className="muted">{r.tipo_fonte === "pista_usuario" ? "pista a confirmar" : "—"}</span>;
  const host = new URL(r.fonte_url).hostname.replace(/^www\./, "");
  return (
    <a href={r.fonte_url} target="_blank" rel="noopener noreferrer">
      {r.tipo_fonte === "pdf_oficial" ? "PDF oficial" : "imprensa"} ({host}){r.pagina_pdf ? `, p. ${r.pagina_pdf}` : ""}
    </a>
  );
}

function Cell({ rows }) {
  if (!rows.length) return <span className="muted">—</span>;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {rows.map((r, i) => {
        const [cls, label] = STATUS[r.status] || ["pend", r.status];
        return (
          <div key={i}>
            <div><strong>{r.valor_mil_reais == null ? "—" : brlMi(r.valor_mil_reais)}</strong>{" "}
              <span className={`badge ${cls}`}>{label}</span></div>
            <div className="small muted">{r.definicao || r.observacao}</div>
            <div className="small"><Source r={r} /></div>
          </div>
        );
      })}
    </div>
  );
}

export default function SPFC() {
  const meta = load("meta");
  const t = load("tabela");
  const sim = load("simulador");
  const fin = load("financas");
  const focus = meta.time_foco;
  const rank = t.linhas.findIndex((l) => l.time.id === focus);
  const me = t.linhas[rank];
  const idx = sim.times.findIndex((x) => x.id === focus);
  const games = sim.restantes.filter((g) => g.mandante === idx || g.visitante === idx)
    .sort((a, b) => a.inicio_utc.localeCompare(b.inicio_utc));
  const spfc = fin.linhas.filter((r) => r.clube === "sao-paulo");
  const get = (rows, campo, ano) => rows.filter((r) => r.campo === campo && r.ano === ano);

  return (
    <>
      <h1>São Paulo · Brasileirão {t.temporada}</h1>
      {me && (
        <>
          <p className="lead">Resultados reais até a rodada {t.rodada_base}; o restante foi simulado {num(t.simulacoes, 0)} vezes.</p>
          <div className="tiles">
            <div className="card tile"><div className="label">Posição hoje</div>
              <div className="value">{currentPosition(sim, idx)}º</div>
              <div className="sub">{me.pontos_atuais} pontos em {me.jogos} jogos · saldo {me.saldo_atual}</div></div>
            <div className="card tile"><div className="label">Posição projetada (pontos esperados)</div>
              <div className="value">{rank + 1}º</div><div className="sub">{num(me.pontos_esperados, 1)} pontos esperados no fim</div></div>
            <div className="card tile"><div className="label">Faixa de posição final</div>
              <div className="value">{me.faixa_posicao.p10}º a {me.faixa_posicao.p90}º</div>
              <div className="sub"><RangeBar p10={me.faixa_posicao.p10} p90={me.faixa_posicao.p90} n={t.linhas.length} /> 80% das simulações</div></div>
          </div>
          <div className="tiles">
            {[["Chance de título", me.chance_titulo], ["Chance de G4", me.chance_g4], ["Chance de G6", me.chance_g6], ["Chance de rebaixamento", me.chance_rebaixamento]].map(([l, v]) => (
              <div key={l} className="card tile"><div className="label">{l}</div>
                <div className="value">{pct(v)}</div></div>
            ))}
          </div>
          <p className="small muted">0% = não aconteceu em nenhuma das simulações; não quer dizer impossível.</p>

          {games.length > 0 && (
            <>
              <h2>Jogos que faltam</h2>
              <div className="table-scroll">
                <table>
                  <thead><tr><th className="l">Rodada</th><th className="l">Data</th><th className="l">Jogo</th><th>Vitória SPFC</th><th>Empate</th><th>Derrota SPFC</th></tr></thead>
                  <tbody>
                    {games.map((g) => {
                      const [h, d, a] = outcomeProbs(scoreMatrix(g.gols_esperados[0], g.gols_esperados[1], sim.rho, sim.max_gols), sim.max_gols);
                      const home = g.mandante === idx;
                      return (
                        <tr key={g.id}>
                          <td className="l">{g.rodada}</td><td className="l">{dateTimeBR(g.inicio_utc)}</td>
                          <td className="l">{sim.times[g.mandante].nome} x {sim.times[g.visitante].nome}</td>
                          <td>{pct(home ? h : a)}</td><td>{pct(d)}</td><td>{pct(home ? a : h)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <caption>Probabilidade estimada pelo modelo, do ponto de vista do São Paulo.</caption>
                </table>
              </div>
            </>
          )}
        </>
      )}

      <h2>Finanças do São Paulo (2023–2025)</h2>
      <p className="lead">
        Cada número tem fonte (PDF oficial do balanço com página, ou imprensa) e data de consulta. Quando duas fontes
        divergem, as duas aparecem lado a lado, marcadas como “fontes divergem”. Valores em milhões de reais.
      </p>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Ressalvas</h3>
        <ul className="plain">
          <li>O parecer do auditor sobre 2025 tem <strong>ressalva</strong>: saques em conta sem comprovação suficiente. Há ênfase sobre investigações em andamento.</li>
          <li>2024 foi <strong>reapresentado</strong> no balanço de 2025 (desconsolidação do FIDC): receita e despesa do futebol de 2024 têm dois valores.</li>
          <li>O superávit de 2025 depende da venda de atletas (R$ 283,8 mi).</li>
          <li>“Dívida” é a definição do próprio clube (obrigações menos direitos a receber) e não é comparável direto com a de outros clubes.</li>
          <li>Duas pistas iniciais não bateram com os PDFs: dívida de 2023 de R$ 856 mi e despesa do futebol de 2024 de R$ 625,4 mi.</li>
        </ul>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Item</th>{YEARS.map((y) => <th key={y} className="l">{y}</th>)}</tr></thead>
          <tbody>
            {FIELDS.map(([campo, label]) => (
              <tr key={campo}>
                <td className="l" style={{ verticalAlign: "top" }}><strong>{label}</strong></td>
                {YEARS.map((y) => (
                  <td key={y} className="l wrap-cell" style={{ verticalAlign: "top" }}><Cell rows={get(spfc, campo, y)} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Comparação com rivais (2025)</h2>
      <p className="lead">Cobertura desigual: Palmeiras e Santos vêm do PDF oficial; Flamengo e Corinthians, por enquanto, só da imprensa.</p>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Item</th><th className="l">São Paulo</th>{CLUBS.map(([, n]) => <th key={n} className="l">{n}</th>)}</tr></thead>
          <tbody>
            {[["receita_operacional", "Receita operacional"], ["resultado", "Resultado do ano"],
              ["passivo_a_descoberto", "Passivo a descoberto"], ["venda_atletas", "Venda de atletas"],
              ["divida_total", "Dívida (definição de cada fonte)"]].map(([campo, label]) => (
              <tr key={campo}>
                <td className="l" style={{ verticalAlign: "top" }}><strong>{label}</strong></td>
                <td className="l wrap-cell" style={{ verticalAlign: "top" }}><Cell rows={get(spfc, campo, "2025").filter((r) => r.tipo_fonte !== "pista_usuario")} /></td>
                {CLUBS.map(([id]) => (
                  <td key={id} className="l wrap-cell" style={{ verticalAlign: "top" }}>
                    <Cell rows={get(fin.linhas.filter((r) => r.clube === id), campo, "2025")} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
