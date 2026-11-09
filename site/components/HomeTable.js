"use client";
// Tabela da home: alternância Atual x Projetada, ordenação por coluna, faixa de zona,
// chances como barras com o número ao lado, últimos 5 resultados e jogos adiados.
import { useMemo, useState } from "react";
import { useMyTeam } from "./MyTeam";
import { RangeBar } from "./ProjectionTable";
import { num, pct } from "../lib/format";

const ZONES = [
  ["z-g4", "G4 (1º–4º)", (p) => p <= 4],
  ["z-g6", "G6 (5º–6º)", (p) => p <= 6],
  ["z-mid", "Meio", (p) => p <= 16],
  ["z-reb", "Rebaixamento (17º–20º)", () => true],
];
const zoneOf = (p) => ZONES.find(([, , f]) => f(p))[0];

function PBar({ v, kind = "" }) {
  return (
    <span className={`pbar ${kind}${v === 0 ? " zero" : ""}`} title={pct(v)}>
      <span className="track"><span className="fill" style={{ width: `${Math.max(v * 100, v > 0 ? 2 : 0)}%` }} /></span>
      <span className="v">{pct(v)}</span>
    </span>
  );
}

function Form({ list }) {
  const label = { V: "vitória", E: "empate", D: "derrota" };
  return (
    <span className="form" aria-label={`Últimos resultados: ${list.map((x) => label[x]).join(", ")}`}>
      {list.map((x, i) => <b key={i} className={x} title={label[x]}>{x}</b>)}
    </span>
  );
}

function Delta({ from, to }) {
  const d = from - to; // positivo = sobe na tabela
  if (d === 0) return <span className="delta same" title="Mesma posição">=</span>;
  return (
    <span className={`delta ${d > 0 ? "up" : "down"}`} title={`Posição projetada ${to}º, hoje ${from}º`}>
      {d > 0 ? "▲" : "▼"}{Math.abs(d)}
    </span>
  );
}

const COLS = {
  atual: [
    ["posicao_atual", "#", (r) => r.posicao_atual, 1],
    ["nome", "Time", (r) => r.nome, 1],
    ["pontos_atuais", "Pts", (r) => r.pontos_atuais, -1],
    ["jogos", "J", (r) => r.jogos, -1],
    ["v", "V", (r) => r.v, -1],
    ["e", "E", (r) => r.e, -1],
    ["d", "D", (r) => r.d, -1],
    ["sg", "SG", (r) => r.gp - r.gc, -1],
    ["gp", "GP", (r) => r.gp, -1],
    ["ultimos5", "Últimos 5", null, 0],
  ],
  projetada: [
    ["posicao_proj", "#", (r) => r.posicao_proj, 1],
    ["nome", "Time", (r) => r.nome, 1],
    ["pontos_esperados", "Pts esperados", (r) => r.pontos_esperados, -1],
    ["delta", "vs hoje", (r) => r.posicao_atual - r.posicao_proj, -1],
    ["faixa", "Faixa (p10–p90)", (r) => r.p10 + r.p90 / 100, 1],
    ["titulo", "Título", (r) => r.titulo, -1],
    ["g4", "G4", (r) => r.g4, -1],
    ["g6", "G6", (r) => r.g6, -1],
    ["rebaixamento", "Rebaixamento", (r) => r.rebaixamento, -1],
  ],
};

export default function HomeTable({ rows }) {
  const { team } = useMyTeam();
  const [view, setView] = useState("projetada");
  const [sort, setSort] = useState({ key: null, dir: 1 });
  const cols = COLS[view];
  const n = rows.length;

  const sorted = useMemo(() => {
    const def = view === "atual" ? "posicao_atual" : "posicao_proj";
    const key = sort.key && cols.some(([k]) => k === sort.key) ? sort.key : def;
    const col = cols.find(([k]) => k === key);
    const dir = sort.key === key ? sort.dir : col[3] || 1;
    const get = col[2];
    return [...rows].sort((a, b) => {
      const x = get(a), y = get(b);
      const c = typeof x === "string" ? x.localeCompare(y, "pt-BR") : x - y;
      return c * dir || a.posicao_proj - b.posicao_proj;
    });
  }, [rows, view, sort, cols]);

  function clickSort(key, natural) {
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: natural || 1 }));
  }

  const posKey = view === "atual" ? "posicao_atual" : "posicao_proj";
  return (
    <>
      <div className="controls">
        <div className="seg" role="group" aria-label="Visão da tabela">
          <button aria-pressed={view === "projetada"} onClick={() => { setView("projetada"); setSort({ key: null, dir: 1 }); }}>Projetada (fim)</button>
          <button aria-pressed={view === "atual"} onClick={() => { setView("atual"); setSort({ key: null, dir: 1 }); }}>Atual</button>
        </div>
        <span className="small muted">Clique no título de uma coluna para ordenar.</span>
      </div>
      <div className="table-scroll tall">
        <table>
          <thead>
            <tr>
              <th aria-label="Zona" />
              {cols.map(([key, label, get, natural]) => (
                <th key={key} className={key === "nome" || key === "faixa" || key === "ultimos5" ? "l" : undefined}
                  aria-sort={sort.key === key ? (sort.dir * (natural || 1) > 0 ? "ascending" : "descending") : undefined}>
                  {get ? (
                    <button className="sort" data-active={sort.key === key} onClick={() => clickSort(key, natural)}>
                      {label}{sort.key === key ? (sort.dir === (natural || 1) ? " ↓" : " ↑") : ""}
                    </button>
                  ) : label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} className={r.id === team ? "focus" : undefined}>
                <td className="zone"><span className={zoneOf(r[posKey])} title={`${r[posKey]}º`} /></td>
                {cols.map(([key]) => <Cell key={key} k={key} r={r} n={n} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="zone-legend">
        {ZONES.filter(([c]) => c !== "z-mid").map(([c, label]) => <span key={c}><i className={c} />{label}</span>)}
        <span>A faixa de cor segue a posição {view === "atual" ? "atual" : "projetada"}.</span>
      </div>
    </>
  );
}

function Cell({ k, r, n }) {
  switch (k) {
    case "posicao_atual": return <td>{r.posicao_atual}</td>;
    case "posicao_proj": return <td>{r.posicao_proj}</td>;
    case "nome":
      return (
        <td className="l team">
          <a href={`/times/${r.id}/`}>{r.nome}</a>
          {r.adiados > 0 && <span className="tag" title={`${r.adiados} jogo adiado ainda por disputar: por isso tem ${r.jogos} jogos`}>{r.adiados} adiado{r.adiados > 1 ? "s" : ""}</span>}
        </td>
      );
    case "sg": { const sg = r.gp - r.gc; return <td>{sg > 0 ? `+${sg}` : sg}</td>; }
    case "ultimos5": return <td className="l"><Form list={r.ultimos5} /></td>;
    case "pontos_esperados": return <td><strong>{num(r.pontos_esperados, 1)}</strong></td>;
    case "delta": return <td><Delta from={r.posicao_atual} to={r.posicao_proj} /></td>;
    case "faixa":
      return (
        <td className="l">
          <span className="range-label">{r.p10 === r.p90 ? `${r.p10}º` : `${r.p10}º–${r.p90}º`}</span>
          <RangeBar p10={r.p10} p90={r.p90} n={n} />
        </td>
      );
    case "titulo": return <td><PBar v={r.titulo} /></td>;
    case "g4": return <td><PBar v={r.g4} /></td>;
    case "g6": return <td><PBar v={r.g6} kind="g6" /></td>;
    case "rebaixamento": return <td><PBar v={r.rebaixamento} kind="alert" /></td>;
    default: return <td>{r[k]}</td>;
  }
}
