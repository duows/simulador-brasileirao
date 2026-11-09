// Gráfico de linhas em SVG (sem biblioteca). Uma escala Y, cores categóricas em ordem fixa
// (paleta de referência, versão escura), legenda sempre visível, rótulo direto no fim da linha
// (afastado para não colidir) e tooltip nativo em cada ponto. Opcional: faixa de incerteza.
const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9", "#e66767", "#008300"];

export default function LineChart({
  x, series, yMin, yMax, invert = false, band = null, height = 260, format = (v) => v, label = "Gráfico",
  highlight = null, yTicks = 5, ticks = null, legend = true,
}) {
  const W = 680, H = height, L = 46, R = 120, T = 12, B = 28;
  const n = x.length;
  const vals = series.flatMap((s) => s.values.filter((v) => v != null));
  const lo = yMin ?? Math.min(...vals, ...(band ? band[0] : []));
  const hi = yMax ?? Math.max(...vals, ...(band ? band[1] : []));
  const span = hi - lo || 1;
  const px = (i) => (n === 1 ? L + (W - L - R) / 2 : L + (i * (W - L - R)) / (n - 1));
  const py = (v) => (invert ? T + ((v - lo) / span) * (H - T - B) : T + (1 - (v - lo) / span) * (H - T - B));
  const tickVals = ticks || niceTicks(lo, hi, yTicks);
  const step = Math.max(1, Math.ceil(n / 12));
  const ends = series.map((s, i) => {
    let j = s.values.length - 1;
    while (j >= 0 && s.values[j] == null) j -= 1;
    return { i, y: j >= 0 ? py(s.values[j]) : null, x: j >= 0 ? px(j) : null };
  }).filter((e) => e.y != null).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 12);
  const endY = Object.fromEntries(ends.map((e) => [e.i, e.y]));
  const color = (s, i) => s.color || SERIES[i % SERIES.length];

  return (
    <figure style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        <g className="grid">
          {tickVals.map((v) => (
            <g key={v}><line x1={L} x2={W - R} y1={py(v)} y2={py(v)} />
              <text x={L - 6} y={py(v) + 4} textAnchor="end">{format(v)}</text></g>
          ))}
        </g>
        {x.map((xv, i) => ((i % step === 0 && n - 1 - i >= step) || i === n - 1) && <text key={i} x={px(i)} y={H - 8} textAnchor="middle">{xv}</text>)}
        {band && (
          <polygon fill="var(--accent)" opacity="0.12"
            points={[...band[1].map((v, i) => `${px(i)},${py(v)}`), ...band[0].map((v, i) => `${px(i)},${py(v)}`).reverse()].join(" ")} />
        )}
        {series.map((s, si) => {
          const pts = s.values.map((v, i) => (v == null ? null : [px(i), py(v)]));
          const segs = [];
          let cur = [];
          pts.forEach((p) => { if (p) cur.push(p); else if (cur.length) { segs.push(cur); cur = []; } });
          if (cur.length) segs.push(cur);
          const dim = highlight && s.id !== highlight;
          const c = color(s, si);
          return (
            <g key={s.id || si} opacity={dim ? 0.25 : 1}>
              {segs.map((seg, k) => seg.length > 1 && (
                <polyline key={k} fill="none" stroke={c} strokeWidth={s.id === highlight ? 3 : 2} strokeDasharray={s.dashed ? "5 4" : undefined}
                  points={seg.map((p) => p.join(",")).join(" ")} />
              ))}
              {!s.noDots && s.values.map((v, i) => v == null ? null : (
                <circle key={i} cx={px(i)} cy={py(v)} r={n > 25 ? 2.5 : 3.5} fill={c} stroke="var(--surface)" strokeWidth="1.5">
                  <title>{`${s.label} · ${x[i]}: ${format(v)}`}</title>
                </circle>
              ))}
              {endY[si] != null && !dim && (
                <text x={ends.find((e) => e.i === si).x + 8} y={endY[si] + 4} style={{ fill: "var(--text-2)" }}>{s.label}</text>
              )}
            </g>
          );
        })}
      </svg>
      {legend && (
        <figcaption className="series-legend">
          {series.map((s, si) => <span key={s.id || si}><i style={{ background: color(s, si) }} />{s.label}</span>)}
        </figcaption>
      )}
    </figure>
  );
}

/** Marcações "redondas" (1, 2, 5 × 10^k) dentro do intervalo. */
function niceTicks(lo, hi, count) {
  const raw = (hi - lo) / Math.max(count - 1, 1);
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((x) => x >= raw) || raw;
  const start = Math.ceil(lo / step) * step;
  const out = [];
  for (let v = start; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}
