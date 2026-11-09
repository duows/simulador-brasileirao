import LineChart from "../../../components/LineChart";
import { load } from "../../../lib/data";
import { num, pct, signed } from "../../../lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(load("temporadas").temporadas).map((ano) => ({ ano }));
}

export async function generateMetadata({ params }) {
  const { ano } = await params;
  return { title: `Brasileirão ${ano} · futdados` };
}

const zone = (p) => (p <= 4 ? "z-g4" : p <= 6 ? "z-g6" : p >= 17 ? "z-reb" : "z-mid");

export default async function Temporada({ params }) {
  const { ano } = await params;
  const s = load("temporadas").temporadas[ano];
  const L = s.liga;
  const top = s.tabela.slice(0, 5);
  const race = top.map((t) => ({ id: t.time, label: t.nome, values: s.trajetorias[t.time].pts }));
  const intFmt = (v) => num(v, 0);
  const zoneColor = (p) => (p <= 4 ? "var(--zone-g4)" : p >= 17 ? "var(--zone-reb)" : "#4f5d57");
  const bump = s.tabela.map((t) => ({ id: t.time, label: t.nome, values: s.trajetorias[t.time].pos, noDots: true, color: zoneColor(t.pos) }));
  const byLuck = [...s.tabela].sort((a, b) => b.sorte - a.sorte);
  const atk = [...s.tabela].sort((a, b) => b.gp - a.gp).slice(0, 3);
  const def = [...s.tabela].sort((a, b) => a.gc - b.gc).slice(0, 3);
  return (
    <>
      <p className="eyebrow"><a href="/temporadas/">Temporadas</a> · {s.encerrada ? "encerrada" : "em andamento"}</p>
      <h1>Brasileirão {ano}</h1>
      <div className="tiles">
        <div className="card tile"><div className="label">{s.encerrada ? "Campeão" : "Líder"}</div><div className="value" style={{ fontSize: 26 }}>{s.tabela[0].nome}</div><div className="sub">{L.pts_campeao} pontos</div></div>
        <div className="card tile"><div className="label">Corte do G4 · do Z4</div><div className="value">{L.pts_g4} · {L.pts_17}</div><div className="sub">pontos do 4º e do 17º</div></div>
        <div className="card tile"><div className="label">Gols por jogo</div><div className="value">{num(L.gols_por_jogo, 2)}</div><div className="sub">empates {pct(L.empates_pct)}</div></div>
        <div className="card tile"><div className="label">Vitórias do mandante</div><div className="value">{pct(L.vitorias_mandante_pct)}</div><div className="sub">visitante {pct(L.vitorias_visitante_pct)}</div></div>
      </div>

      <h2>{s.encerrada ? "Tabela final" : "Tabela atual"}</h2>
      <div className="table-scroll tall">
        <table>
          <thead><tr><th aria-label="Zona" /><th>#</th><th className="l">Time</th><th>Pts</th><th>J</th><th>V</th><th>E</th><th>D</th><th>GP</th><th>GC</th><th>SG</th>
            <th title="Pontos que o saldo de gols sugere (Pitagórico)">Pts Pitagóricos</th><th title="Pontos reais menos Pitagóricos: positivo = mais pontos que o saldo sugere">Sorte</th></tr></thead>
          <tbody>
            {s.tabela.map((t) => (
              <tr key={t.time}>
                <td className="zone"><span className={zone(t.pos)} /></td>
                <td>{t.pos}</td><td className="l team"><a href={`/times/${t.time}/`}>{t.nome}</a></td>
                <td><strong>{t.pts}</strong></td><td>{t.j}</td><td>{t.v}</td><td>{t.e}</td><td>{t.d}</td><td>{t.gp}</td><td>{t.gc}</td>
                <td>{t.gp - t.gc > 0 ? `+${t.gp - t.gc}` : t.gp - t.gc}</td><td>{num(t.pts_pitagoricos, 1)}</td><td>{signed(t.sorte, 1)}</td>
              </tr>
            ))}
          </tbody>
          <caption>Pitagórico: pontos esperados a partir de gols pró e contra, com expoente ajustado ao histórico do Brasileirão. "Sorte" é a diferença; valores grandes costumam não se repetir.</caption>
        </table>
      </div>

      <h2>Corrida pelo título</h2>
      <section className="card">
        <LineChart x={s.rodadas.map((r) => `R${r}`)} series={race} yMin={0} format={intFmt} label={`Pontos acumulados dos 5 primeiros em ${ano}`} />
      </section>

      <h2>Posição rodada a rodada</h2>
      <section className="card">
        <LineChart x={s.rodadas.map((r) => `R${r}`)} series={bump} yMin={1} yMax={20} invert height={420}
          label={`Posição de cada time por rodada em ${ano}`} ticks={[1, 4, 6, 10, 17, 20]} legend={false} format={(v) => `${v}º`} />
        <p className="small muted">Cor pela posição final: verde = terminou no G4, vermelho = rebaixado, cinza = os demais. 1º no topo; passe o mouse nos pontos para ver o time.</p>
      </section>

      <h2>Destaques</h2>
      <div className="grid">
        <section className="card"><h3>Melhores ataques e defesas</h3>
          <p className="small">Ataque: {atk.map((t) => `${t.nome} (${t.gp})`).join(", ")}</p>
          <p className="small">Defesa: {def.map((t) => `${t.nome} (${t.gc})`).join(", ")}</p></section>
        <section className="card"><h3>Acima e abaixo do esperado</h3>
          <p className="small">Mais pontos que o saldo sugere: {byLuck.slice(0, 3).map((t) => `${t.nome} (${signed(t.sorte, 1)})`).join(", ")}</p>
          <p className="small">Menos pontos que o saldo sugere: {byLuck.slice(-3).reverse().map((t) => `${t.nome} (${signed(t.sorte, 1)})`).join(", ")}</p></section>
        <section className="card"><h3>Maiores goleadas</h3>
          <ul className="plain small">{s.maiores_goleadas.map((g, i) => <li key={i}>R{g.rodada}: {g.mandante} {g.placar} {g.visitante}</li>)}</ul></section>
      </div>
    </>
  );
}
