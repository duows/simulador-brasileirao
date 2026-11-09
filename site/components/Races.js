"use client";
// Três disputas no topo da home: título, vagas na Libertadores (G4 incerto) e permanência.
import { useMyTeam } from "./MyTeam";
import { pct } from "../lib/format";

function Race({ title, note, items, alert, empty, foot }) {
  const { team } = useMyTeam();
  return (
    <section className={`card race${alert ? " alert" : ""}`}>
      <h3>{title} <small>{note}</small></h3>
      {items.length === 0 ? <p className="empty">{empty}</p> : (
        <ol>
          {items.map((it) => (
            <li key={it.id} className={it.id === team ? "me" : undefined}>
              <a href={`/times/${it.id}/`} style={{ color: "inherit", textDecoration: "none" }}>{it.nome}</a>
              <span className="bar" aria-hidden="true"><span style={{ width: `${Math.max(it.v * 100, 1.5)}%` }} /></span>
              <span className="v">{pct(it.v)}</span>
            </li>
          ))}
        </ol>
      )}
      {foot && <p className="empty" style={{ margin: "8px 0 0" }}>{foot}</p>}
    </section>
  );
}

export default function Races({ rows }) {
  const title = rows.filter((r) => r.titulo > 0).sort((a, b) => b.titulo - a.titulo)
    .map((r) => ({ id: r.id, nome: r.nome, v: r.titulo }));
  const libert = rows.filter((r) => r.g4 >= 0.05 && r.g4 <= 0.95).sort((a, b) => b.g4 - a.g4)
    .map((r) => ({ id: r.id, nome: r.nome, v: r.g4 }));
  const riskAll = rows.filter((r) => r.rebaixamento > 0).sort((a, b) => b.rebaixamento - a.rebaixamento);
  const risk = riskAll.filter((r) => r.rebaixamento >= 0.005).slice(0, 8)
    .map((r) => ({ id: r.id, nome: r.nome, v: r.rebaixamento }));
  const riskRest = riskAll.length - risk.length;
  return (
    <div className="races">
      <Race title="Título" note="chance de terminar em 1º" items={title} empty="Nenhum time com chance nas simulações." />
      <Race title="Vagas na Libertadores" note="G4 entre 5% e 95%" items={libert}
        empty="Nenhuma vaga de G4 em aberto: todas acima de 95% ou abaixo de 5%." />
      <Race title="Permanência" note="risco de rebaixamento" items={risk} alert empty="Ninguém em risco nas simulações."
        foot={riskRest > 0 ? `Mais ${riskRest} time${riskRest > 1 ? "s" : ""} com risco abaixo de 0,5%.` : null} />
    </div>
  );
}
