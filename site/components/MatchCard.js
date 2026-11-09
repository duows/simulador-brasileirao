// Card de um jogo: probabilidade estimada (V/E/D), gols esperados, placar mais provável e
// decomposição dos fatores. Usado na Rodada e nas páginas de time.
import { dateTimeBR, num, pct, signed } from "../lib/format";

function ProbBar({ p, home, away }) {
  const parts = [
    ["mandante", `Vitória ${home}`, "var(--s-home)", p.mandante],
    ["empate", "Empate", "var(--s-draw)", p.empate],
    ["visitante", `Vitória ${away}`, "var(--s-away)", p.visitante],
  ];
  return (
    <>
      <div className="probbar" role="img"
        aria-label={parts.map(([, l, , v]) => `${l}: ${pct(v)}`).join("; ")}>
        {parts.map(([k, label, color, v]) => (
          <span key={k} style={{ flexBasis: `${v * 100}%`, background: color }} title={`${label}: ${pct(v)}`}>
            {v >= 0.12 ? pct(v) : ""}
          </span>
        ))}
      </div>
      <div className="legend">
        {parts.map(([k, label, color, v]) => (
          <span key={k}><i style={{ background: color }} />{label} {pct(v)}</span>
        ))}
      </div>
    </>
  );
}

/** Barra divergente: efeito em gols (positivo à direita, em azul; negativo à esquerda, em vermelho). */
function Effect({ v, scale }) {
  const w = Math.min(Math.abs(v) / scale, 1) * 50;
  const style = v >= 0 ? { left: "50%", width: `${w}%`, background: "var(--pos)" }
    : { right: "50%", width: `${w}%`, background: "var(--neg)" };
  return (
    <span className="effect" title={`${signed(v, 3)} gol esperado`}>
      <span>{signed(v, 2)}</span>
      <span className="track">{Math.abs(v) >= 0.005 && <span className="fill" style={style} />}</span>
    </span>
  );
}

export default function MatchCard({ j, collapsible = false }) {
  const scale = Math.max(0.3, ...j.fatores.flatMap((f) => [Math.abs(f.mandante.efeito_gols), Math.abs(f.visitante.efeito_gols)]));
  const ge = j.gols_esperados;
  return (
    <article className="card">
      <div className="match-head">
        <div className="teams">{j.mandante.nome} x {j.visitante.nome}</div>
        <div className="small muted">
          {j.adiado && <><span className="badge pend">adiado · rodada {j.rodada}</span>{" "}</>}
          {dateTimeBR(j.inicio_utc)}
        </div>
      </div>
      <ProbBar p={j.probabilidade_estimada} home={j.mandante.nome} away={j.visitante.nome} />
      <div className="kv" style={{ marginTop: 8 }}>
        <span>Gols esperados: <strong>{num(ge.mandante, 2)}</strong> x <strong>{num(ge.visitante, 2)}</strong></span>
        <span>Placar mais provável: {j.placar_mais_provavel.mandante}–{j.placar_mais_provavel.visitante} ({pct(j.placar_mais_provavel.probabilidade)})</span>
      </div>
      <Factors j={j} ge={ge} scale={scale} collapsible={collapsible} />
      <RegistryNote j={j} />
    </article>
  );
}

function Factors({ j, ge, scale, collapsible }) {
  const body = (
    <>
      <h3 style={{ marginTop: 14 }}>Por que esses números</h3>
      <p className="small muted" style={{ margin: "0 0 6px" }}>
        Ponto de partida: {num(j.gols_base, 2)} gol para cada time. Cada linha mostra quanto o fator somou ou tirou dos gols esperados.
      </p>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Fator</th><th>{j.mandante.nome}</th><th>{j.visitante.nome}</th></tr></thead>
          <tbody>
            {j.fatores.map((f) => (
              <tr key={f.fator}>
                <td className="l">{f.rotulo}</td>
                <td><Effect v={f.mandante.efeito_gols} scale={scale} /></td>
                <td><Effect v={f.visitante.efeito_gols} scale={scale} /></td>
              </tr>
            ))}
            <tr>
              <td className="l"><strong>Gols esperados</strong></td>
              <td><strong>{num(ge.mandante, 2)}</strong></td>
              <td><strong>{num(ge.visitante, 2)}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
  return collapsible ? <details style={{ marginTop: 10 }}><summary className="small">Ver os fatores do modelo</summary>{body}</details> : body;
}

function RegistryNote({ j }) {
  return (
      <p className="small muted" style={{ margin: "8px 0 0" }}>
        {j.registro
          ? <>Registrado antes do jogo em {dateTimeBR(j.registro.gravado_em)} · hash {j.registro.hash.slice(0, 12)}…</>
          : <>Ainda não gravado no registro imutável (rode <code>futdados predict-round</code> antes do jogo).</>}
      </p>
  );
}

