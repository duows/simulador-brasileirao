"use client";
// Probabilidade de cada time terminar em cada posição. Escala sequencial de uma cor (verde),
// do fundo ao acento; o percentual aparece dentro das células acima de 5% para não depender só de cor.
import { useMyTeam } from "./MyTeam";
import { pct } from "../lib/format";

function cellStyle(p) {
  if (p <= 0) return {};
  const k = Math.min(1, Math.sqrt(p / 0.6)); // raiz: diferencia melhor as probabilidades baixas
  return { background: `color-mix(in oklab, var(--accent) ${Math.round(k * 100)}%, var(--surface-2))` };
}

export default function Heatmap({ rows }) {
  const { team } = useMyTeam();
  const n = rows.length;
  return (
    <div className="table-scroll">
      <table className="heat">
        <thead>
          <tr>
            <th className="l">Time</th>
            {Array.from({ length: n }, (_, i) => <th key={i} className="c" scope="col">{i + 1}º</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className={r.id === team ? "focus" : undefined}>
              <td className="l team"><a href={`/times/${r.id}/`}>{r.nome}</a></td>
              {r.dist.map((p, i) => (
                <td key={i} className={`c ${p >= 0.2 ? "hi" : "lo"}`} style={cellStyle(p)}
                  title={`${r.nome} termina em ${i + 1}º: ${pct(p)}`}>
                  {p > 0.05 ? Math.round(p * 100) : ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <caption>Percentual de simulações em que o time termina em cada posição. Números aparecem nas células acima de 5%; passe o mouse para ver os demais.</caption>
      </table>
    </div>
  );
}
