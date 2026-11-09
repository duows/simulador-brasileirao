// Evolução de uma chance (título, rebaixamento...) ao longo das rodadas, a partir das projeções
// gravadas ao vivo a cada atualização. Uma linha por time, cores categóricas em ordem fixa
// (paleta de referência, versão escura), legenda sempre visível e rótulo direto no último ponto.
import { pct } from "../lib/format";

const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];

export default function EvolutionChart({ hist, metric, names, teams = null, max = 6, label }) {
  const rounds = hist.rodadas || [];
  if (!rounds.length) {
    return <p className="muted small">Ainda não há projeções salvas para mostrar a evolução.</p>;
  }
  let ids = teams || Object.keys(hist.times)
    .filter((id) => Math.max(...hist.times[id][metric].map((v) => v ?? 0)) >= 0.01)
    .sort((a, b) => (hist.times[b][metric].at(-1) ?? 0) - (hist.times[a][metric].at(-1) ?? 0));
  ids = ids.slice(0, max);
  if (!ids.length) return <p className="muted small">Nenhum time passou de 1% nas projeções salvas.</p>;

  const W = 640, H = 240, L = 40, R = 110, T = 12, B = 28;
  const x = (i) => (rounds.length === 1 ? L + (W - L - R) / 2 : L + (i * (W - L - R)) / (rounds.length - 1));
  const y = (v) => T + (1 - v) * (H - T - B);
  // rótulos finais afastados verticalmente (mínimo 13px) para não se sobreporem
  const ends = ids.map((id) => {
    const vals = hist.times[id][metric];
    let i = vals.length - 1;
    while (i >= 0 && vals[i] == null) i -= 1;
    return { id, x: i >= 0 ? x(i) : null, y: i >= 0 ? y(vals[i]) : null };
  }).filter((e) => e.x != null).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 13);
  const labelY = Object.fromEntries(ends.map((e) => [e.id, e.y]));
  return (
    <figure style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label} por rodada`}>
        <g className="grid">
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
              <text x={L - 6} y={y(v) + 4} textAnchor="end">{Math.round(v * 100)}%</text>
            </g>
          ))}
        </g>
        {rounds.map((r, i) => (
          <text key={r} x={x(i)} y={H - 8} textAnchor="middle">R{r}</text>
        ))}
        {ids.map((id, s) => {
          const vals = hist.times[id][metric];
          const pts = vals.map((v, i) => (v == null ? null : [x(i), y(v)])).filter(Boolean);
          const color = SERIES[s % SERIES.length];
          const last = pts.at(-1);
          return (
            <g key={id}>
              {pts.length > 1 && <polyline fill="none" stroke={color} strokeWidth="2" points={pts.map((p) => p.join(",")).join(" ")} />}
              {vals.map((v, i) => v == null ? null : (
                <circle key={i} cx={x(i)} cy={y(v)} r="4" fill={color} stroke="var(--surface)" strokeWidth="2">
                  <title>{`${names[id] || id} · rodada ${rounds[i]}: ${pct(v)}`}</title>
                </circle>
              ))}
              {last && <text x={last[0] + 8} y={labelY[id] + 4} style={{ fill: "var(--text-2)" }}>{names[id] || id}</text>}
            </g>
          );
        })}
      </svg>
      <figcaption>
        <div className="series-legend">
          {ids.map((id, s) => <span key={id}><i style={{ background: SERIES[s % SERIES.length] }} />{names[id] || id} {pct(hist.times[id][metric].at(-1) ?? 0)}</span>)}
        </div>
        {rounds.length === 1 && (
          <p className="small muted" style={{ margin: "6px 0 0" }}>
            O histórico começou a ser salvo na rodada {rounds[0]}. Cada atualização acrescenta um ponto; o passado não é
            recalculado, porque os pesos atuais já viram os resultados seguintes.
          </p>
        )}
      </figcaption>
    </figure>
  );
}
