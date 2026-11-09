"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import ProjectionTable from "./ProjectionTable";
import { useMyTeam } from "./MyTeam";
import { outcomeProbs, scoreMatrix, simulate } from "../lib/simulate.mjs";
import { dateTimeBR, pct } from "../lib/format";

const SIMS = [2000, 5000, 10000];

function toRows(res) {
  return res.map((r) => ({
    id: r.time.id, nome: r.time.nome, jogos: r.jogos, pontos_atuais: r.pontos_atuais,
    pontos_esperados: r.pontos_esperados, p10: r.p10, p90: r.p90,
    titulo: r.chance.titulo, g4: r.chance.g4, g6: r.chance.g6, rebaixamento: r.chance.rebaixamento,
  }));
}

export default function Simulator({ data }) {
  const { team: focus } = useMyTeam();
  const [choices, setChoices] = useState({});
  const [nSims, setNSims] = useState(data.simulacoes_padrao);
  const [round, setRound] = useState(null); // começa mostrando todas as rodadas
  const [onlyFocus, setOnlyFocus] = useState(false);
  const [result, setResult] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  const names = data.times.map((t) => t.nome);
  const focusIdx = data.times.findIndex((t) => t.id === focus);
  const rounds = useMemo(() => [...new Set(data.restantes.map((g) => g.rodada))].sort((x, y) => x - y), [data]);
  const probs = useMemo(() => Object.fromEntries(data.restantes.map((g) => [
    g.id, outcomeProbs(scoreMatrix(g.gols_esperados[0], g.gols_esperados[1], data.rho, data.max_gols), data.max_gols),
  ])), [data]);

  // recalcula com um pequeno atraso para não travar enquanto a pessoa escolhe vários jogos
  useEffect(() => {
    setBusy(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setResult(simulate(data, choices, nSims));
      setBusy(false);
    }, 120);
    return () => clearTimeout(timer.current);
  }, [data, choices, nSims]);

  useEffect(() => { // linha de base sem escolhas, com o mesmo número de simulações
    setBaseline(simulate(data, {}, nSims));
  }, [data, nSims]);

  const rows = useMemo(() => {
    if (!result) return [];
    const base = Object.fromEntries((baseline || []).map((r) => [r.time.id, r.chance]));
    const hasChoices = Object.keys(choices).length > 0;
    return toRows(result).map((r) => ({
      ...r,
      delta: hasChoices && base[r.id] ? {
        titulo: r.titulo - base[r.id].titulo, g4: r.g4 - base[r.id].g4,
        g6: r.g6 - base[r.id].g6, rebaixamento: r.rebaixamento - base[r.id].rebaixamento,
      } : undefined,
    }));
  }, [result, baseline, choices]);

  const games = data.restantes.filter((g) => (round == null || g.rodada === round)
    && (!onlyFocus || focusIdx < 0 || g.mandante === focusIdx || g.visitante === focusIdx));
  const nChosen = Object.keys(choices).length;

  function pick(id, value) {
    setChoices((c) => {
      const next = { ...c };
      if (!value) delete next[id]; else next[id] = value;
      return next;
    });
  }

  if (!data.restantes.length) return <p className="lead">Não há jogos restantes para simular.</p>;

  return (
    <>
      <div className="controls">
        <label>Rodada{" "}
          <select value={round ?? ""} onChange={(e) => setRound(e.target.value === "" ? null : Number(e.target.value))}>
            <option value="">Todas</option>
            {rounds.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        {focusIdx >= 0 && <label><input type="checkbox" checked={onlyFocus} onChange={(e) => setOnlyFocus(e.target.checked)} /> só jogos do {names[focusIdx]}</label>}
        <label>Simulações{" "}
          <select value={nSims} onChange={(e) => setNSims(Number(e.target.value))}>
            {SIMS.map((n) => <option key={n} value={n}>{n.toLocaleString("pt-BR")}</option>)}
          </select>
        </label>
        <button onClick={() => setChoices({})} disabled={!nChosen}>Limpar escolhas ({nChosen})</button>
        <span className="small muted" aria-live="polite">{busy ? "Recalculando…" : "Tabela atualizada"}</span>
      </div>

      <div className="picks">
        {games.map((g) => {
          const p = probs[g.id];
          const v = choices[g.id] || "";
          return (
            <div key={g.id} className={`pick${v ? " chosen" : ""}`}>
              <div className="names">
                <div><strong>{names[g.mandante]}</strong> x <strong>{names[g.visitante]}</strong></div>
                <div className="small muted">R{g.rodada} · {dateTimeBR(g.inicio_utc)} · modelo: mandante {pct(p[0])}, empate {pct(p[1])}, visitante {pct(p[2])}</div>
              </div>
              <select aria-label={`Resultado de ${names[g.mandante]} x ${names[g.visitante]}`}
                value={v} onChange={(e) => pick(g.id, e.target.value)}>
                <option value="">Modelo decide</option>
                <option value="mandante">Vitória {names[g.mandante]}</option>
                <option value="empate">Empate</option>
                <option value="visitante">Vitória {names[g.visitante]}</option>
              </select>
            </div>
          );
        })}
        {!games.length && <p className="muted">Nenhum jogo com esse filtro.</p>}
      </div>

      <h2>Tabela projetada com as suas escolhas</h2>
      <p className="small muted">
        Os jogos escolhidos são sorteados só entre placares compatíveis com o resultado escolhido (o saldo de gols
        continua realista); os demais seguem a probabilidade estimada pelo modelo. Entre parênteses, a variação em pontos
        percentuais em relação à projeção sem escolhas.
      </p>
      {result && <ProjectionTable rows={rows}
        caption={`${nSims.toLocaleString("pt-BR")} simulações feitas no seu navegador. Faixa: percentis 10 e 90 da posição final.`} />}
    </>
  );
}
