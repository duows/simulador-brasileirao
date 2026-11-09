import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { outcomeProbs, rankTeams, scoreMatrix, simulate } from "./simulate.mjs";

const CRIT = ["points", "wins", "goal_difference", "goals_for", "head_to_head", "red_cards", "yellow_cards", "draw_lots"];

test("matriz de placares soma 1 e favorece quem tem mais gols esperados", () => {
  const m = scoreMatrix(1.6, 0.9);
  assert.ok(Math.abs(m.reduce((a, b) => a + b, 0) - 1) < 1e-9);
  const [h, d, a] = outcomeProbs(m);
  assert.ok(h > a && Math.abs(h + d + a - 1) < 1e-9);
});

test("confronto direto só vale para exatamente dois empatados", () => {
  const st = { pts: [10, 10], v: [3, 3], sg: [2, 2], gp: [5, 5] };
  const h2h = [[0, 0], [3, 0]];
  assert.deepEqual(rankTeams(st, h2h, CRIT, [0.1, 0.9]), [2, 1]);
  const st3 = { pts: [10, 10, 10], v: [3, 3, 3], sg: [2, 2, 2], gp: [5, 5, 5] };
  const h3 = [[0, 0, 0], [3, 0, 0], [0, 0, 0]];
  assert.deepEqual(rankTeams(st3, h3, CRIT, [0.1, 0.5, 0.9]), [1, 2, 3]); // sorteio
});

const tiny = {
  times: [{ id: "a", nome: "A" }, { id: "b", nome: "B" }],
  atual: { pts: [0, 0], j: [0, 0], v: [0, 0], gp: [0, 0], gc: [0, 0] },
  confronto_direto_pontos: [[0, 0], [0, 0]],
  restantes: [{ id: 0, rodada: 1, mandante: 0, visitante: 1, gols_esperados: [1.4, 1.1] }],
  rho: 0, max_gols: 10, zonas: { titulo: [1, 1], rebaixamento: [2, 2] }, criterios_desempate: CRIT,
};

test("resultado escolhido é respeitado em todas as simulações", () => {
  const res = simulate(tiny, { 0: "visitante" }, 500, 1);
  const b = res.find((r) => r.time.id === "b");
  assert.equal(b.pontos_esperados, 3);
  assert.equal(b.chance.titulo, 1);
  const tie = simulate(tiny, { 0: "empate" }, 500, 1);
  assert.ok(tie.every((r) => r.pontos_esperados === 1));
});

test("chances somam 1 por zona e a faixa é coerente", () => {
  const res = simulate(tiny, {}, 1000, 2);
  const title = res.reduce((s, r) => s + r.chance.titulo, 0);
  assert.ok(Math.abs(title - 1) < 1e-9);
  assert.ok(res.every((r) => r.p10 <= r.p90));
});

const dataFile = new URL("../public/data/simulador.json", import.meta.url);
const tableFile = new URL("../public/data/tabela.json", import.meta.url);
test("sem escolhas, bate com a projeção do Python (pontos esperados)", { skip: !existsSync(dataFile) }, () => {
  const data = JSON.parse(readFileSync(dataFile, "utf-8"));
  const py = JSON.parse(readFileSync(tableFile, "utf-8"));
  const res = simulate(data, {}, 3000, 7);
  for (const row of py.linhas) {
    const js = res.find((r) => r.time.id === row.time.id);
    assert.ok(Math.abs(js.pontos_esperados - row.pontos_esperados) < 0.6,
      `${row.time.id}: js ${js.pontos_esperados.toFixed(2)} x py ${row.pontos_esperados}`);
  }
});
