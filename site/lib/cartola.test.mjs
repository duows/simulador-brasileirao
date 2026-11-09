import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { bestTeam } from "./cartola.mjs";

const SCHEMES = { "4-3-3": { gol: 1, lat: 2, zag: 2, mei: 3, ata: 3, tec: 1 }, "3-5-2": { gol: 1, lat: 0, zag: 3, mei: 5, ata: 2, tec: 1 } };

function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = Math.imul(a ^ (a >>> 15), a | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function randomPlayers(seed, perPos = 5) {
  const r = rng(seed);
  const out = [];
  let id = 0;
  for (const pos of ["gol", "lat", "zag", "mei", "ata", "tec"]) {
    for (let i = 0; i < perPos; i++) {
      const preco = Math.round((2 + r() * 15) * 100) / 100;
      out.push({ id: id++, posicao: pos, preco, esperado: Math.round((0.5 + preco * 0.4 + r() * 3) * 100) / 100 });
    }
  }
  return out;
}

/** Força bruta: todas as combinações por posição (instância pequena), capitão = melhor não técnico. */
function brute(players, budget, schemes, mult) {
  const comb = (arr, k) => (k === 0 ? [[]] : arr.flatMap((x, i) => comb(arr.slice(i + 1), k - 1).map((c) => [x, ...c])));
  let best = -Infinity;
  for (const s of Object.values(schemes)) {
    const lists = Object.entries(s).map(([pos, k]) => comb(players.filter((p) => p.posicao === pos), k));
    const rec = (i, chosen, cost) => {
      if (cost > budget + 1e-9) return;
      if (i === lists.length) {
        const cap = Math.max(...chosen.filter((p) => p.posicao !== "tec").map((p) => p.esperado));
        const v = chosen.reduce((a, p) => a + p.esperado, 0) + (mult - 1) * cap;
        if (v > best) best = v;
        return;
      }
      for (const c of lists[i]) rec(i + 1, chosen.concat(c), cost + c.reduce((a, p) => a + Math.ceil(p.preco * 10 - 1e-9) / 10, 0));
    };
    rec(0, [], 0);
  }
  return best;
}

test("igual à força bruta em instâncias pequenas", () => {
  for (const seed of [1, 2, 3]) {
    const players = randomPlayers(seed, 4);
    for (const budget of [70, 90, 120]) {
      const res = bestTeam(players, budget, SCHEMES, 1.5);
      const bf = brute(players, budget, SCHEMES, 1.5);
      if (bf === -Infinity) { assert.equal(res.ok, false); continue; }
      assert.ok(res.ok);
      assert.ok(Math.abs(res.pontos_esperados - bf) < 1e-6, `seed ${seed} budget ${budget}: ${res.pontos_esperados} x ${bf}`);
      assert.ok(res.custo <= budget + 1e-9);
      assert.equal(res.time.length, 12);
      assert.equal(res.time.filter((p) => p.capitao).length, 1);
      assert.ok(!res.time.find((p) => p.capitao && p.posicao === "tec"));
    }
  }
});

test("orçamento insuficiente devolve motivo", () => {
  const res = bestTeam(randomPlayers(4, 4), 5, SCHEMES, 1.5);
  assert.equal(res.ok, false);
  assert.match(res.motivo, /insuficiente/);
});

const real = new URL("../public/data/cartola.json", import.meta.url);
test("com os dados locais da rodada: time válido e rápido", { skip: !existsSync(real) }, () => {
  const d = JSON.parse(readFileSync(real, "utf-8"));
  const t0 = Date.now();
  const res = bestTeam(d.atletas, 100, d.esquemas, d.multiplicador_capitao);
  const ms = Date.now() - t0;
  assert.ok(res.ok && res.custo <= 100 && res.time.length === 12);
  assert.ok(ms < 8000, `demorou ${ms} ms`);
});
