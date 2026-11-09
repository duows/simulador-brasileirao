import { load } from "../../lib/data";
import { pct } from "../../lib/format";
import { Monogram } from "../../lib/teams";

export const metadata = { title: "Times · futdados" };

export default function Times() {
  const t = load("tabela");
  const rows = [...t.linhas].sort((a, b) => a.posicao_atual - b.posicao_atual);
  return (
    <>
      <p className="eyebrow">Brasileirão {t.temporada} · ordem da tabela atual</p>
      <h1>Times</h1>
      <p className="lead">Os 20 clubes da Série A. Cada página traz a posição, as chances, a distribuição da posição final, os próximos jogos e, quando houver, as finanças com fonte.</p>
      <div className="team-grid">
        {rows.map((l) => (
          <a key={l.time.id} className="team-card" href={`/times/${l.time.id}/`}>
            <Monogram id={l.time.id} nome={l.time.nome} />
            <div>
              <div><strong>{l.posicao_atual}º · {l.time.nome}</strong></div>
              <div className="meta">
                {l.pontos_atuais} pts em {l.jogos} jogos{l.adiados ? ` (${l.adiados} adiado)` : ""} · fim: {l.faixa_posicao.p10}º–{l.faixa_posicao.p90}º
              </div>
              <div className="meta">
                {l.chance_titulo > 0 && <>título {pct(l.chance_titulo)} · </>}
                G4 {pct(l.chance_g4)} · rebaixamento {pct(l.chance_rebaixamento)}
              </div>
            </div>
          </a>
        ))}
      </div>
    </>
  );
}
