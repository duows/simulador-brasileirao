// Melhor time do Cartola para um orçamento, no navegador (exato, por programação dinâmica).
// Espelho de src/futdados/cartola/optimize.py (que usa programação linear inteira).
//
// Preços em décimos de cartoleta, arredondados PARA CIMA: o time encontrado sempre cabe no
// orçamento real. Para cada posição, uma tabela "melhor soma de pontos escolhendo k atletas com
// custo até c, com ou sem capitão"; depois as posições são combinadas para cada esquema.

const POSITIONS = ["gol", "lat", "zag", "mei", "ata", "tec"];
const NEG = -1e18;

function positionTable(players, K, C, mult, canCaptain) {
  // dp[j][cap][c] em arrays planos; keep[i][j][cap][c] para reconstruir
  const W = C + 1;
  const dp = Array.from({ length: K + 1 }, (_, j) => [0, 1].map((cap) => {
    const a = new Float64Array(W).fill(NEG);
    if (j === 0 && cap === 0) a.fill(0);
    return a;
  }));
  const keep = players.map(() => Array.from({ length: K + 1 }, () => [new Uint8Array(W), new Uint8Array(W)]));
  players.forEach((p, i) => {
    for (let j = K; j >= 1; j--) {
      for (let c = C; c >= p.u; c--) {
        const prev0 = dp[j - 1][0][c - p.u];
        const prev1 = dp[j - 1][1][c - p.u];
        // sem capitão
        if (prev0 > NEG / 2 && prev0 + p.e > dp[j][0][c]) { dp[j][0][c] = prev0 + p.e; keep[i][j][0][c] = 1; }
        // com capitão: ou ele mesmo é o capitão (vem de cap=0) ou o capitão já foi escolhido
        let best = dp[j][1][c], how = 0;
        if (prev1 > NEG / 2 && prev1 + p.e > best) { best = prev1 + p.e; how = 1; }
        if (canCaptain && prev0 > NEG / 2 && prev0 + p.e * mult > best) { best = prev0 + p.e * mult; how = 2; }
        if (how) { dp[j][1][c] = best; keep[i][j][1][c] = how; }
      }
    }
  });
  return { dp, keep };
}

function reconstruct(players, keep, k, cap, c) {
  const chosen = [];
  let j = k, cp = cap, cc = c;
  for (let i = players.length - 1; i >= 0 && j > 0; i--) {
    const how = keep[i][j][cp][cc];
    if (!how) continue;
    const isCap = cp === 1 && how === 2;
    chosen.push({ ...players[i].p, capitao: isCap });
    cc -= players[i].u;
    j -= 1;
    if (isCap) cp = 0;
  }
  return chosen;
}

/** Combina duas tabelas "até custo c": out[cap][c] = max A[a][c1] + B[b][c - c1], a + b = cap. */
function combine(A, B, C) {
  const out = [new Float64Array(C + 1).fill(NEG), new Float64Array(C + 1).fill(NEG)];
  const arg = [new Int32Array(C + 1), new Int32Array(C + 1)];
  const argA = [new Int8Array(C + 1), new Int8Array(C + 1)];
  for (let c = 0; c <= C; c++) {
    for (let c1 = 0; c1 <= c; c1++) {
      const c2 = c - c1;
      const a0 = A[0][c1], a1 = A[1][c1], b0 = B[0][c2], b1 = B[1][c2];
      if (a0 > NEG / 2 && b0 > NEG / 2 && a0 + b0 > out[0][c]) { out[0][c] = a0 + b0; arg[0][c] = c1; argA[0][c] = 0; }
      if (a1 > NEG / 2 && b0 > NEG / 2 && a1 + b0 > out[1][c]) { out[1][c] = a1 + b0; arg[1][c] = c1; argA[1][c] = 1; }
      if (a0 > NEG / 2 && b1 > NEG / 2 && a0 + b1 > out[1][c]) { out[1][c] = a0 + b1; arg[1][c] = c1; argA[1][c] = 0; }
    }
  }
  return { out, arg, argA };
}

/**
 * players: [{ id, posicao, preco, esperado, ... }]; schemes: { "4-3-3": { gol: 1, lat: 2, ... } }.
 * Devolve { ok, esquema, custo, pontos_esperados, time } ou { ok: false, motivo }.
 */
export function bestTeam(players, budget, schemes, mult = 1.5, onlyScheme = null) {
  const C = Math.floor(budget * 10 + 1e-9);
  const byPos = Object.fromEntries(POSITIONS.map((pos) => [pos, players
    .filter((p) => p.posicao === pos && p.esperado > 0)
    .map((p) => ({ p, e: p.esperado, u: Math.ceil(p.preco * 10 - 1e-9) }))]));
  const names = onlyScheme ? [onlyScheme] : Object.keys(schemes);
  const maxK = Object.fromEntries(POSITIONS.map((pos) => [pos, Math.max(...names.map((s) => schemes[s][pos] || 0))]));
  const tables = Object.fromEntries(POSITIONS.map((pos) =>
    [pos, positionTable(byPos[pos], maxK[pos], C, mult, pos !== "tec")]));
  let best = null;
  for (const s of names) {
    // começa com a primeira posição e combina as demais
    let acc = null;
    const steps = [];
    for (const pos of POSITIONS) {
      const k = schemes[s][pos] || 0;
      const T = [tables[pos].dp[k][0], tables[pos].dp[k][1]];
      if (!acc) { acc = T; steps.push({ pos, k, comb: null }); continue; }
      const comb = combine(acc, T, C);
      steps.push({ pos, k, comb });
      acc = comb.out;
    }
    const value = acc[1][C];
    if (value > NEG / 2 && (!best || value > best.value)) best = { value, s, steps };
  }
  if (!best) return { ok: false, motivo: "Orçamento insuficiente para montar um time completo com os atletas disponíveis." };
  // reconstrução de trás para frente
  let c = C, cap = 1;
  const team = [];
  for (let i = best.steps.length - 1; i >= 0; i--) {
    const st = best.steps[i];
    let cPos = c, capPos = cap;
    if (st.comb) {
      const c1 = st.comb.arg[cap][c];
      const capA = st.comb.argA[cap][c];
      cPos = c - c1;
      capPos = cap - capA;
      c = c1;
      cap = capA;
    }
    team.push(...reconstruct(byPos[st.pos], tables[st.pos].keep, st.k, capPos, cPos));
  }
  const order = Object.fromEntries(POSITIONS.map((p, i) => [p, i]));
  team.sort((a, b) => order[a.posicao] - order[b.posicao] || b.esperado - a.esperado);
  const custo = team.reduce((x, p) => x + p.preco, 0);
  return { ok: true, esquema: best.s, custo, pontos_esperados: best.value, time: team };
}
