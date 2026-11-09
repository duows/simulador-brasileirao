import EvolutionChart from "../../../components/EvolutionChart";
import LineChart from "../../../components/LineChart";
import FinanceTable from "../../../components/Finance";
import MatchCard from "../../../components/MatchCard";
import { RangeBar } from "../../../components/ProjectionTable";
import { load } from "../../../lib/data";
import { dateTimeBR, num, pct } from "../../../lib/format";
import { Monogram } from "../../../lib/teams";

export const dynamicParams = false;

export function generateStaticParams() {
  return load("tabela").linhas.map((l) => ({ slug: l.time.id }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const l = load("tabela").linhas.find((x) => x.time.id === slug);
  return { title: `${l ? l.time.nome : slug} · futdados` };
}

const zoneClass = (p) => (p <= 4 ? "" : p <= 6 ? "g6" : p <= 16 ? "mid" : "reb");

function Meter({ label, value, invert = false, note }) {
  // 1,0 = média da liga; escala log de 0,5x a 2x. "invert": abaixo de 1 é melhor (defesa).
  const pos = Math.max(0, Math.min(1, (Math.log(value) / Math.log(2) + 1) / 2));
  const good = invert ? value < 1 : value > 1;
  const left = Math.min(pos, 0.5) * 100, width = Math.abs(pos - 0.5) * 100;
  return (
    <div className="meter" title={note}>
      <span>{label}</span>
      <span className="track"><span className="mid" />
        <span className="fill" style={{ left: `${left}%`, width: `${width}%`, background: good ? "var(--accent)" : "var(--alert)" }} />
      </span>
      <span style={{ textAlign: "right" }}><strong>{num(value, 2)}</strong>×</span>
    </div>
  );
}

const SPFC_NOTES = [
  "O parecer do auditor sobre 2025 tem ressalva: saques em conta sem comprovação suficiente, e ênfase sobre investigações em andamento.",
  "2024 foi reapresentado no balanço de 2025 (desconsolidação do FIDC): receita e despesa do futebol de 2024 têm dois valores.",
  "O superávit de 2025 depende da venda de atletas (R$ 283,8 mi).",
  "Duas pistas iniciais não bateram com os PDFs: dívida de 2023 de R$ 856 mi e despesa do futebol de 2024 de R$ 625,4 mi.",
];

export default async function TeamPage({ params }) {
  const { slug } = await params;
  const tab = load("tabela");
  const tm = load("times").times[slug];
  const hist = load("historico");
  const fin = load("financas").linhas.filter((r) => r.clube === slug);
  const rank = tab.linhas.findIndex((l) => l.time.id === slug);
  const l = tab.linhas[rank];
  const n = tab.linhas.length;
  const dist = l.distribuicao_posicao;
  const maxP = Math.max(...dist);
  const h = hist.times[slug];
  const teamHist = h ? {
    rodadas: hist.rodadas,
    times: { titulo: { v: h.titulo }, g4: { v: h.g4 }, g6: { v: h.g6 }, rebaixamento: { v: h.rebaixamento } },
  } : { rodadas: [], times: {} };
  const ppg = (s) => (s.j ? s.pts / s.j : 0);
  const past = load("temporadas").times_historico[slug];
  const closedHist = past ? past.temporadas.filter((t) => t.j >= 38) : [];
  const best = closedHist.length ? closedHist.reduce((a, b) => (b.pts > a.pts ? b : a)) : (past?.temporadas[0] || {});
  const worst = closedHist.length ? closedHist.reduce((a, b) => (b.pts < a.pts ? b : a)) : (past?.temporadas[0] || {});
  const trend = past?.tendencia;
  const adiados = tm.proximos.filter((j) => j.adiado);
  const proximos = tm.proximos.filter((j) => !j.adiado);

  return (
    <>
      <p className="eyebrow">Brasileirão {tab.temporada} · resultados reais até a rodada {tab.rodada_base}</p>
      <div className="team-head">
        <Monogram id={slug} nome={tm.nome} large />
        <h1 style={{ margin: 0 }}>{tm.nome}</h1>
      </div>

      <div className="tiles">
        <div className="card tile"><div className="label">Posição hoje</div><div className="value">{tm.posicao_atual}º</div>
          <div className="sub">{tm.pts} pontos · {tm.v}V {tm.e}E {tm.d}D · saldo {tm.gp - tm.gc}</div></div>
        <div className="card tile"><div className="label">Jogos</div><div className="value">{tm.j}</div>
          <div className="sub">{tm.adiados ? `${tm.adiados} jogo adiado a disputar` : `de ${2 * (n - 1)}`}</div></div>
        <div className="card tile"><div className="label">Pontos esperados no fim</div><div className="value">{num(l.pontos_esperados, 1)}</div>
          <div className="sub">posição projetada: {rank + 1}º</div></div>
        <div className="card tile"><div className="label">Faixa de posição final</div>
          <div className="value">{l.faixa_posicao.p10}º–{l.faixa_posicao.p90}º</div>
          <div className="sub"><RangeBar p10={l.faixa_posicao.p10} p90={l.faixa_posicao.p90} n={n} /> 80% das simulações</div></div>
      </div>
      <div className="tiles">
        {[["Título", l.chance_titulo], ["G4", l.chance_g4], ["G6", l.chance_g6], ["Rebaixamento", l.chance_rebaixamento]].map(([k, v]) => (
          <div key={k} className="card tile"><div className="label">Chance · {k}</div>
            <div className="value" style={k === "Rebaixamento" && v > 0 ? { color: "var(--alert)" } : undefined}>{pct(v)}</div></div>
        ))}
      </div>

      <h2>Distribuição da posição final</h2>
      <section className="card">
        <div className="distbars" role="img" aria-label={dist.map((p, i) => `${i + 1}º: ${pct(p)}`).join("; ")}>
          {dist.map((p, i) => (
            <div key={i} className={zoneClass(i + 1)} style={{ height: `${maxP ? (p / maxP) * 100 : 0}%` }} title={`${i + 1}º: ${pct(p)}`}>
              {p >= 0.05 && <span className="small" style={{ position: "absolute", top: -18, left: 0, right: 0, textAlign: "center", color: "var(--text-2)" }}>{Math.round(p * 100)}</span>}
            </div>
          ))}
        </div>
        <div className="distaxis">{dist.map((_, i) => <span key={i}>{i + 1}</span>)}</div>
        <p className="small muted" style={{ margin: "8px 0 0" }}>Percentual das simulações em que o time termina em cada posição (verde: G4, azul: G6, vermelho: rebaixamento).</p>
      </section>

      <h2>Próximos jogos</h2>
      {proximos.length ? <div className="grid">{proximos.map((j) => <MatchCard key={`${j.mandante.id}-${j.visitante.id}`} j={j} collapsible />)}</div>
        : <p className="muted">Sem jogos restantes.</p>}
      {adiados.length > 0 && (
        <>
          <h3 style={{ marginTop: 20 }}>Jogo adiado</h3>
          <div className="grid">{adiados.map((j) => <MatchCard key={`${j.mandante.id}-${j.visitante.id}`} j={j} collapsible />)}</div>
        </>
      )}

      <h2>Ataque, defesa e forma</h2>
      <div className="grid">
        <section className="card">
          <h3>Força relativa à média da liga</h3>
          <Meter label="Ataque" value={tm.forca.ataque} note="Gols marcados por jogo (com decaimento) em relação à média da liga" />
          <Meter label="Defesa" value={tm.forca.defesa} invert note="Gols sofridos por jogo em relação à média: abaixo de 1 é melhor" />
          <p className="small muted">1,00× = média da liga. Ataque acima de 1 marca mais; defesa abaixo de 1 sofre menos. Inclui o histórico recente com decaimento.</p>
          <h3 style={{ marginTop: 14 }}>Forma recente</h3>
          <p style={{ margin: 0 }}>
            <span className="form">{tm.ultimos5.map((x, i) => <b key={i} className={x}>{x}</b>)}</span>{" "}
            <span className="muted small">{num(tm.forca.pontos_por_jogo_ultimos5, 2)} pontos por jogo nos últimos 5</span>
          </p>
        </section>
        <section className="card">
          <h3>Casa e fora</h3>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Local</th><th>J</th><th>Pts</th><th>Pts/jogo</th><th>GP</th><th>GC</th></tr></thead>
              <tbody>
                {[["Em casa", tm.casa], ["Fora", tm.fora]].map(([k, s]) => (
                  <tr key={k}><td className="l">{k}</td><td>{s.j}</td><td>{s.pts}</td><td>{num(ppg(s), 2)}</td><td>{s.gp}</td><td>{s.gc}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 style={{ marginTop: 14 }}>Últimos resultados</h3>
          <div className="table-scroll">
            <table>
              <tbody>
                {tm.resultados.slice(0, 8).map((r) => (
                  <tr key={r.rodada + r.adversario}>
                    <td className="l">R{r.rodada}</td>
                    <td className="l">{r.local === "casa" ? "x" : "@"} <a href={`/times/${r.adversario}/`}>{r.adversario_nome}</a></td>
                    <td>{r.gols_pro}–{r.gols_contra}</td>
                    <td><span className="form"><b className={r.resultado}>{r.resultado}</b></span></td>
                    <td className="muted small">{dateTimeBR(r.data_utc).split(" ")[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <h2>Evolução das chances</h2>
      <section className="card">
        <EvolutionChart hist={teamHist} metric="v" teams={["titulo", "g4", "g6", "rebaixamento"]
          .filter((k) => teamHist.times[k] && Math.max(...teamHist.times[k].v.map((x) => x ?? 0)) > 0)}
          names={{ titulo: "Título", g4: "G4", g6: "G6", rebaixamento: "Rebaixamento" }} label={`Chances de ${tm.nome}`} />
      </section>

      {past && (
        <>
          <h2>Histórico desde 2006</h2>
          <p className="lead">
            {past.temporadas.length} temporadas na Série A desde 2006. Melhor campanha: {best.temporada} ({best.pos}º, {best.pts} pts).
            Pior: {worst.temporada} ({worst.pos}º, {worst.pts} pts).
            {trend && <> Tendência de pontos por temporada: <strong>{trend.pontos.rotulo}</strong>; da posição: <strong>{trend.posicao.rotulo}</strong>.</>}
          </p>
          <div className="grid">
            <section className="card"><h3>Posição final por temporada</h3>
              <LineChart x={past.temporadas.map((t) => t.temporada)} series={[{ id: "pos", label: "posição", values: past.temporadas.map((t) => t.pos) }]}
                yMin={1} yMax={20} invert ticks={[1, 4, 6, 10, 17, 20]} format={(v) => `${v}º`} legend={false} height={220} label={`Posição final de ${tm.nome} por temporada`} />
              <p className="small muted">Só as temporadas em que o time estava na Série A. A temporada em andamento entra com a posição atual.</p></section>
            <section className="card"><h3>Força (Elo) no fim de cada temporada</h3>
              <LineChart x={past.temporadas.map((t) => t.temporada)} series={[{ id: "elo", label: "Elo", values: past.temporadas.map((t) => t.elo_fim) }]}
                format={(v) => num(v, 0)} legend={false} height={220} label={`Elo de ${tm.nome}`} />
              <p className="small muted">1.500 ≈ média histórica. Cada vitória sobre um adversário forte rende mais pontos de Elo.</p></section>
          </div>
        </>
      )}

      <h2>Finanças</h2>
      {fin.length ? (
        <>
          {slug === "sao-paulo" && (
            <section className="card" style={{ marginBottom: 12 }}>
              <h3>Ressalvas</h3>
              <ul className="plain">{SPFC_NOTES.map((t) => <li key={t}>{t}</li>)}</ul>
            </section>
          )}
          <p className="small muted">Quando duas fontes divergem, as duas aparecem lado a lado, marcadas como “fontes divergem”. A definição de dívida varia entre clubes e não é comparável direto.</p>
          <FinanceTable rows={fin} />
        </>
      ) : <p className="muted">Ainda não há dados financeiros deste clube no projeto.</p>}
    </>
  );
}
