// Formatação em português do Brasil.
const pctFmt = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });
const numFmt = (d) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });

/** Percentual com 1 casa; abaixo de 0,1% mostra "<0,1%" para não sugerir impossível. */
export function pct(x) {
  if (x == null || Number.isNaN(x)) return "—";
  if (x > 0 && x < 0.001) return "<0,1%";
  if (x < 1 && x > 0.999) return ">99,9%";
  return pctFmt.format(x);
}

export function num(x, d = 1) {
  if (x == null || Number.isNaN(x)) return "—";
  return numFmt(d).format(x);
}

export function signed(x, d = 2) {
  if (x == null) return "—";
  const s = numFmt(d).format(Math.abs(x));
  if (Math.abs(x) < 0.5 * 10 ** -d) return numFmt(d).format(0);
  return (x > 0 ? "+" : "−") + s;
}

export function dateTimeBR(iso) {
  return new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });
}

/** Valores financeiros vêm em R$ mil; exibimos em milhões. */
export function brlMi(milReais) {
  if (milReais == null) return "—";
  return `R$ ${numFmt(1).format(milReais / 1000)} mi`;
}
