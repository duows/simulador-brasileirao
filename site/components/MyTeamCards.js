"use client";
import { useMyTeam } from "./MyTeam";
import { num, pct } from "../lib/format";

/** Cards do time escolhido em "Meu time". Sem escolha, não aparece nada. */
export default function MyTeamCards({ rows }) {
  const { team } = useMyTeam();
  const r = rows.find((x) => x.id === team);
  if (!r) return null;
  return (
    <div className="tiles">
      <div className="card tile"><div className="label">{r.nome} · pontos esperados</div>
        <div className="value">{num(r.pontos_esperados, 1)}</div>
        <div className="sub">hoje tem {r.pontos_atuais} em {r.jogos} jogos</div></div>
      <div className="card tile"><div className="label">{r.nome} · faixa de posição final</div>
        <div className="value">{r.p10}º a {r.p90}º</div><div className="sub">em 80% das simulações</div></div>
      <div className="card tile"><div className="label">{r.nome} · chance de G4</div>
        <div className="value">{pct(r.g4)}</div><div className="sub">G6: {pct(r.g6)} · título: {pct(r.titulo)}</div></div>
      <div className="card tile"><div className="label">{r.nome} · chance de rebaixamento</div>
        <div className="value">{pct(r.rebaixamento)}</div><div className="sub"><a href={`/times/${r.id}/`}>página do time</a></div></div>
    </div>
  );
}
