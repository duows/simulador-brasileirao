"use client";
import { useMyTeam } from "./MyTeam";
import { num, pct } from "../lib/format";

/** Régua 1..N com a faixa p10-p90 da posição final. */
export function RangeBar({ p10, p90, n }) {
  const left = ((p10 - 1) / (n - 1)) * 100;
  const width = Math.max(((p90 - p10) / (n - 1)) * 100, 4);
  return (
    <span className="range" title={`Posição final entre ${p10}º e ${p90}º em 80% das simulações`}>
      <span className="bar" style={{ left: `${left}%`, width: `${width}%` }} />
    </span>
  );
}

function Delta({ v }) {
  if (v == null || Math.abs(v) < 0.0005) return null;
  return (
    <span className={`small ${v > 0 ? "delta-pos" : "delta-neg"}`}>
      {" "}({v > 0 ? "+" : "−"}{num(Math.abs(v) * 100, 1)} p.p.)
    </span>
  );
}

/**
 * rows: [{ id, nome, jogos, pontos_atuais, pontos_esperados, p10, p90, titulo, g4, g6, rebaixamento, delta? }]
 * delta (opcional): variação das chances em relação à projeção sem escolhas.
 */
export default function ProjectionTable({ rows, caption }) {
  const { team: focus } = useMyTeam();
  const n = rows.length;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th className="l">#</th>
            <th className="l">Time</th>
            <th title="Jogos disputados">J</th>
            <th>Pontos atuais</th>
            <th>Pontos esperados</th>
            <th className="l">Posição final (p10–p90)</th>
            <th>Título</th>
            <th>G4</th>
            <th>G6</th>
            <th>Rebaixamento</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id} className={r.id === focus ? "focus" : undefined}>
              <td className="l">{i + 1}</td>
              <td className="l">{r.nome}</td>
              <td>{r.jogos}</td>
              <td>{r.pontos_atuais}</td>
              <td>{num(r.pontos_esperados, 1)}</td>
              <td className="l">
                <span className="range-label">{r.p10 === r.p90 ? `${r.p10}º` : `${r.p10}º–${r.p90}º`}</span>
                <RangeBar p10={r.p10} p90={r.p90} n={n} />
              </td>
              <td>{pct(r.titulo)}<Delta v={r.delta?.titulo} /></td>
              <td>{pct(r.g4)}<Delta v={r.delta?.g4} /></td>
              <td>{pct(r.g6)}<Delta v={r.delta?.g6} /></td>
              <td>{pct(r.rebaixamento)}<Delta v={r.delta?.rebaixamento} /></td>
            </tr>
          ))}
        </tbody>
        {caption && <caption>{caption}</caption>}
      </table>
    </div>
  );
}
