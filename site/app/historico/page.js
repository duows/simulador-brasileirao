import LineChart from "../../components/LineChart";
import { load } from "../../lib/data";
import { num, pct, signed } from "../../lib/format";

export const metadata = { title: "Histórico e tendências · futdados" };

const GROUPS = [
  ["Disputa", ["pts_campeao", "pts_vice", "pts_g4", "pts_17"], false],
  ["Jogo", ["gols_por_jogo", "empates_pct", "vitorias_mandante_pct", "vantagem_mando_gols"], false],
  ["Equilíbrio", ["gini_pontos", "desvio_pontos", "times_na_briga_5_rodadas_antes"], false],
];
const PCT = new Set(["empates_pct", "vitorias_mandante_pct"]);
const WHAT = {
  pts_campeao: "Quanto o campeão precisou somar. Alto = campeão dominante ou liga desequilibrada.",
  pts_vice: "Pontos do segundo colocado.",
  pts_g4: "Pontos do 4º: o corte aproximado para a Libertadores direta.",
  pts_17: "Pontos do 17º, o primeiro rebaixado: a linha da queda.",
  gols_por_jogo: "Média de gols por partida no campeonato.",
  empates_pct: "Fração de jogos que terminaram empatados.",
  vitorias_mandante_pct: "Fração de vitórias de quem joga em casa.",
  vantagem_mando_gols: "Quantos gols a mais o mandante marca, em média, por jogo.",
  gini_pontos: "Desigualdade na distribuição de pontos (0 = todos iguais).",
  desvio_pontos: "Dispersão dos pontos entre os 20 clubes.",
  times_na_briga_5_rodadas_antes: "Quantos times ainda podiam alcançar o líder a 5 rodadas do fim.",
};

function Series({ k, v }) {
  const fmt = (x) => (PCT.has(k) ? pct(x) : num(x, k.startsWith("pts") || k.startsWith("times") ? 0 : 2));
  const ts = v.theil_sen;
  const trendLine = v.anos.map((a) => ts.intercepto + ts.inclinacao * a);
  return (
    <section className="card">
      <h3>{v.nome} <span className="tag">{v.rotulo}</span></h3>
      <p className="small muted" style={{ margin: "0 0 6px" }}>{WHAT[k]}</p>
      <LineChart x={v.anos} band={v.faixa90} format={fmt} height={220} label={v.nome}
        series={[{ id: "v", label: "valor", values: v.valores }, { id: "l", label: "LOESS", values: v.loess, noDots: true },
          { id: "t", label: "Theil-Sen", values: trendLine, noDots: true, dashed: true }]} />
      <p className="small" style={{ margin: "6px 0 0" }}>
        Inclinação robusta: {signed(PCT.has(k) ? ts.inclinacao * 100 : ts.inclinacao, 3)}{PCT.has(k) ? " p.p." : ""} por ano
        (IC 90%: {signed(PCT.has(k) ? ts.ic90[0] * 100 : ts.ic90[0], 3)} a {signed(PCT.has(k) ? ts.ic90[1] * 100 : ts.ic90[1], 3)}).
        {v.mudanca && <> Mudança de média em {v.mudanca.ano}: {fmt(v.mudanca.media_antes)} → {fmt(v.mudanca.media_depois)}.</>}
        {" "}Eras: {Object.entries(v.eras.medias).map(([e, x]) => `${e} ${fmt(x)}`).join(" · ")}
        {v.eras.diferenca_clara ? " (diferença clara)" : " (sem diferença clara entre eras)"}.
      </p>
      <p className="small muted" style={{ margin: "4px 0 0" }}>{v.aviso}</p>
    </section>
  );
}

export default function Historico() {
  const t = load("tendencias").liga;
  return (
    <>
      <p className="eyebrow">2006 em diante · temporadas encerradas</p>
      <h1>Histórico e tendências</h1>
      <p className="lead">
        Como o Brasileirão mudou desde o início dos pontos corridos com 20 clubes. Cada gráfico mostra o valor de cada ano,
        uma curva suavizada (LOESS) com faixa de incerteza e a tendência robusta (Theil-Sen). O rótulo só diz “em alta” ou
        “em queda” quando o teste estatístico tem sinal; com 20 temporadas, a maioria das séries não tem.
      </p>
      {GROUPS.map(([g, keys]) => (
        <div key={g}>
          <h2>{g}</h2>
          <div className="grid">{keys.filter((k) => t[k]).map((k) => <Series key={k} k={k} v={t[k]} />)}</div>
        </div>
      ))}
    </>
  );
}
