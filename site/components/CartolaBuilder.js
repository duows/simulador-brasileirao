"use client";
// Monta o melhor time do Cartola para o orçamento digitado, no navegador.
import { useMemo, useState } from "react";
import { addReserves, bestTeam } from "../lib/cartola.mjs";
import { num, pct, signed } from "../lib/format";

const POS = { gol: "Goleiro", lat: "Lateral", zag: "Zagueiro", mei: "Meia", ata: "Atacante", tec: "Técnico" };
const FACTORS = ["base", "media_ajustada", "p_sg", "gols_time", "mando", "p_vitoria"];

function Factors({ p, labels }) {
  return (
    <div className="small" style={{ display: "grid", gap: 2, marginTop: 6 }}>
      {FACTORS.map((f) => (
        <div key={f} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span className="muted">{labels[f]}</span><span>{signed(p.fatores[f], 2)}</span>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span className="muted">Se jogar</span><strong>{num(p.previsto_se_jogar, 2)}</strong>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span className="muted">× chance de jogar ({p.status === "duvida" ? "dúvida" : "provável"})</span><strong>{pct(p.p_jogar)}</strong>
      </div>
    </div>
  );
}

export default function CartolaBuilder({ data }) {
  const [budget, setBudget] = useState(data.cartoletas_iniciais || 100);
  const [scheme, setScheme] = useState("");
  const [withDoubt, setWithDoubt] = useState(true);
  const [open, setOpen] = useState(null);
  const players = useMemo(() => data.atletas.filter((p) => withDoubt || p.status === "provavel"), [data, withDoubt]);
  const res = useMemo(() => {
    const b = Number(budget);
    if (!Number.isFinite(b) || b <= 0) return { ok: false, motivo: "Digite um orçamento válido." };
    const r = bestTeam(players, b, data.esquemas, data.multiplicador_capitao, scheme || null);
    if (!r.ok) return r;
    const bench = addReserves(r.time, players, data.reservas);
    return { ...r, reservas: bench.reservas, valor_reservas: bench.valor };
  }, [players, budget, scheme, data]);

  return (
    <>
      <div className="controls">
        <label>Orçamento (C$){" "}
          <input type="number" min="0" step="0.5" value={budget} onChange={(e) => setBudget(e.target.value)}
            style={{ width: 100, font: "inherit", color: "var(--text)", background: "var(--surface-2)", border: "1px solid var(--border-strong)", borderRadius: 8, padding: "6px 10px" }} />
        </label>
        <label>Esquema{" "}
          <select value={scheme} onChange={(e) => setScheme(e.target.value)}>
            <option value="">O melhor</option>
            {Object.keys(data.esquemas).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label><input type="checkbox" checked={withDoubt} onChange={(e) => setWithDoubt(e.target.checked)} /> incluir atletas em dúvida</label>
      </div>

      {!res.ok ? <p className="lead">{res.motivo}</p> : (
        <>
          <div className="tiles">
            <div className="card tile"><div className="label">Pontuação esperada</div><div className="value">{num(res.pontos_esperados + res.valor_reservas, 1)}</div>
              <div className="sub">titulares {num(res.pontos_esperados, 1)} + banco {num(res.valor_reservas, 1)} · capitão ×{num(data.multiplicador_capitao, 1)}</div></div>
            <div className="card tile"><div className="label">Custo</div><div className="value">C$ {num(res.custo, 2)}</div>
              <div className="sub">sobram C$ {num(Number(budget) - res.custo, 2)}</div></div>
            <div className="card tile"><div className="label">Esquema</div><div className="value">{res.esquema}</div><div className="sub">{scheme ? "escolhido por você" : "o que rende mais"}</div></div>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Posição</th><th className="l">Atleta</th><th className="l">Jogo</th><th>Preço</th><th>Média Cartola</th><th>Esperado</th><th className="l">Por quê</th></tr></thead>
              <tbody>
                {res.time.map((p) => (
                  <tr key={p.id}>
                    <td className="l">{POS[p.posicao]}</td>
                    <td className="l"><strong>{p.apelido}</strong>{p.capitao && <span className="tag">capitão</span>}{p.status === "duvida" && <span className="tag">dúvida</span>}
                      <div className="small muted">{p.time_nome}</div></td>
                    <td className="l small">{p.mando ? "x" : "@"} {p.adversario}<div className="muted">SG {pct(p.contexto.p_sg)} · vitória {pct(p.contexto.p_vitoria)}</div></td>
                    <td>C$ {num(p.preco, 2)}</td><td>{num(p.media_cartola, 2)}</td>
                    <td><strong>{num(p.esperado * (p.capitao ? data.multiplicador_capitao : 1), 2)}</strong></td>
                    <td className="l wrap-cell">
                      <button onClick={() => setOpen(open === p.id ? null : p.id)} style={{ padding: "2px 8px", fontSize: 12 }}>
                        {open === p.id ? "fechar" : "ver fatores"}</button>
                      {open === p.id && <Factors p={p} labels={data.rotulos_fatores} />}
                    </td>
                  </tr>
                ))}
              </tbody>
              <caption>Titulares. Pontuação esperada = chance de jogar × pontos previstos se jogar. Os pontos previstos somam a base da posição, a média do atleta (puxada para a média da posição quando há poucos jogos) e o contexto do jogo vindo do nosso modelo: chance de não sofrer gol, gols esperados do time, mando e chance de vitória.</caption>
            </table>
          </div>
          {res.reservas.length > 0 && (
            <>
              <h3 style={{ marginTop: 18 }}>Banco de reservas</h3>
              <div className="table-scroll">
                <table>
                  <thead><tr><th className="l">Posição</th><th className="l">Atleta</th><th className="l">Jogo</th><th>Preço</th><th>Esperado se entrar</th><th>Chance de entrar</th><th>Vale</th></tr></thead>
                  <tbody>
                    {res.reservas.map((p) => (
                      <tr key={p.id}>
                        <td className="l">{POS[p.posicao]}</td>
                        <td className="l"><strong>{p.apelido}</strong><div className="small muted">{p.time_nome}</div></td>
                        <td className="l small">{p.mando ? "x" : "@"} {p.adversario}</td>
                        <td>C$ {num(p.preco, 2)}</td><td>{num(p.esperado, 2)}</td><td>{pct(p.chance_de_entrar)}</td>
                        <td><strong>{num(p.valor_reserva, 2)}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                  <caption>O reserva entra no lugar de um titular da mesma posição que não jogar. Regra usada: não gasta cartoletas e custa no máximo o mesmo que o titular mais barato da posição (a confirmar no regulamento do Cartola). Técnico não tem reserva.</caption>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
