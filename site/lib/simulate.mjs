// Simulação Monte Carlo no navegador, espelho de src/futdados/simulate/montecarlo.py.
// Cada jogo restante é sorteado da matriz de placares de Poisson (gols esperados vindos
// do modelo). Jogos com resultado escolhido pela pessoa são sorteados só entre os
// placares compatíveis com aquele resultado, para o saldo de gols continuar realista.

/** Gerador pseudoaleatório com semente (mulberry32): mesma escolha, mesmo resultado. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function poissonPmf(lambda, max) {
  const out = new Array(max + 1);
  let p = Math.exp(-lambda);
  for (let k = 0; k <= max; k++) {
    out[k] = p;
    p = (p * lambda) / (k + 1);
  }
  return out;
}

function dcTau(x, y, lh, la, rho) {
  if (!rho) return 1;
  if (x === 0 && y === 0) return 1 - lh * la * rho;
  if (x === 0 && y === 1) return 1 + lh * rho;
  if (x === 1 && y === 0) return 1 + la * rho;
  if (x === 1 && y === 1) return 1 - rho;
  return 1;
}

/** Matriz achatada P[gm * (max+1) + gv], normalizada. */
export function scoreMatrix(lh, la, rho = 0, max = 10) {
  const ph = poissonPmf(lh, max);
  const pa = poissonPmf(la, max);
  const n = max + 1;
  const m = new Float64Array(n * n);
  let s = 0;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const v = ph[i] * pa[j] * dcTau(i, j, lh, la, rho);
      m[i * n + j] = v;
      s += v;
    }
  }
  for (let k = 0; k < m.length; k++) m[k] /= s;
  return m;
}

export function outcomeProbs(m, max = 10) {
  const n = max + 1;
  let h = 0, d = 0, a = 0;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const v = m[i * n + j];
    if (i > j) h += v; else if (i === j) d += v; else a += v;
  }
  return [h, d, a];
}

const OUTCOME = { mandante: 0, empate: 1, visitante: 2 };

/** Placares acumulados por resultado: [todos, só vitória mandante, só empate, só visitante]. */
function samplers(m, max) {
  const n = max + 1;
  const build = (keep) => {
    const idx = [], cum = [];
    let s = 0;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      if (!keep(i, j)) continue;
      s += m[i * n + j];
      idx.push(i * n + j);
      cum.push(s);
    }
    return { idx, cum, total: s };
  };
  return [
    build(() => true),
    build((i, j) => i > j),
    build((i, j) => i === j),
    build((i, j) => i < j),
  ];
}

function draw(sampler, u) {
  const target = u * sampler.total;
  const { cum } = sampler;
  let lo = 0, hi = cum.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (cum[mid] < target) lo = mid + 1; else hi = mid;
  }
  return sampler.idx[lo];
}

/**
 * Ordena os times de uma simulação. Critérios antes de "head_to_head" entram direto;
 * o confronto direto só desempata grupos de exatamente dois; cartões não existem nos
 * dados e caem no sorteio (chave aleatória), como no Python.
 */
export function rankTeams(st, h2h, criteria, rand) {
  const T = st.pts.length;
  const keyMap = { points: "pts", wins: "v", goal_difference: "sg", goals_for: "gp" };
  const cut = criteria.indexOf("head_to_head");
  const before = (cut >= 0 ? criteria.slice(0, cut) : criteria).map((c) => keyMap[c]).filter(Boolean);
  const order = Array.from({ length: T }, (_, i) => i);
  const tieKey = rand;
  order.sort((x, y) => {
    for (const k of before) if (st[k][x] !== st[k][y]) return st[k][y] - st[k][x];
    return tieKey[x] - tieKey[y];
  });
  if (cut >= 0) {
    const same = (x, y) => before.every((k) => st[k][x] === st[k][y]);
    for (let p = 0; p < T - 1; p++) {
      const a = order[p], b = order[p + 1];
      if (!same(a, b)) continue;
      const prevTie = p > 0 && same(order[p - 1], a);
      const nextTie = p + 2 < T && same(b, order[p + 2]);
      if (!prevTie && !nextTie && h2h[b][a] > h2h[a][b]) {
        order[p] = b;
        order[p + 1] = a;
      }
    }
  }
  const pos = new Array(T);
  order.forEach((team, i) => { pos[team] = i + 1; });
  return pos;
}

function percentile(counts, total, q) {
  // counts[k] = vezes que o time terminou na posição k+1 (método "linear" não é
  // necessário aqui: devolvemos a menor posição cuja frequência acumulada atinge q)
  let acc = 0;
  for (let k = 0; k < counts.length; k++) {
    acc += counts[k];
    if (acc / total >= q) return k + 1;
  }
  return counts.length;
}

/**
 * data: o JSON simulador.json. choices: { [idJogo]: "mandante" | "empate" | "visitante" }.
 * Devolve uma linha por time com pontos esperados, faixa p10-p90 e chances por zona.
 */
export function simulate(data, choices = {}, nSims = 2000, seed = 20260101) {
  const T = data.times.length;
  const max = data.max_gols;
  const n = max + 1;
  const prepared = data.restantes.map((g) => {
    const m = scoreMatrix(g.gols_esperados[0], g.gols_esperados[1], data.rho, max);
    return { g, s: samplers(m, max) };
  });
  const r = rng(seed);
  const expPts = new Float64Array(T);
  const posCounts = Array.from({ length: T }, () => new Array(T).fill(0));
  const zones = Object.fromEntries(Object.keys(data.zonas).map((z) => [z, new Float64Array(T)]));
  const base = data.atual;

  for (let s = 0; s < nSims; s++) {
    const st = { pts: base.pts.slice(), v: base.v.slice(), gp: base.gp.slice(), gc: base.gc.slice() };
    const h2h = data.confronto_direto_pontos.map((row) => row.slice());
    for (const { g, s: smp } of prepared) {
      const choice = choices[g.id];
      const sampler = choice ? smp[1 + OUTCOME[choice]] : smp[0];
      const cell = draw(sampler, r());
      const hg = Math.floor(cell / n), ag = cell % n;
      const h = g.mandante, a = g.visitante;
      const hp = hg > ag ? 3 : hg === ag ? 1 : 0;
      const ap = ag > hg ? 3 : hg === ag ? 1 : 0;
      st.pts[h] += hp; st.pts[a] += ap;
      if (hp === 3) st.v[h] += 1;
      if (ap === 3) st.v[a] += 1;
      st.gp[h] += hg; st.gc[h] += ag; st.gp[a] += ag; st.gc[a] += hg;
      h2h[h][a] += hp; h2h[a][h] += ap;
    }
    st.sg = st.gp.map((gf, i) => gf - st.gc[i]);
    const rand = Array.from({ length: T }, () => r());
    const pos = rankTeams(st, h2h, data.criterios_desempate, rand);
    for (let t = 0; t < T; t++) {
      expPts[t] += st.pts[t];
      posCounts[t][pos[t] - 1] += 1;
      for (const [z, [lo, hi]] of Object.entries(data.zonas)) {
        if (pos[t] >= lo && pos[t] <= hi) zones[z][t] += 1;
      }
    }
  }
  return data.times.map((team, t) => ({
    time: team,
    indice: t,
    pontos_atuais: base.pts[t],
    jogos: base.j[t],
    pontos_esperados: expPts[t] / nSims,
    p10: percentile(posCounts[t], nSims, 0.1),
    p90: percentile(posCounts[t], nSims, 0.9),
    chance: Object.fromEntries(Object.entries(zones).map(([z, arr]) => [z, arr[t] / nSims])),
  })).sort((x, y) => y.pontos_esperados - x.pontos_esperados || y.pontos_atuais - x.pontos_atuais);
}
