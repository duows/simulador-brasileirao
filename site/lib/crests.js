// Escudos e fotos SÓ no modo local (CRESTS=local). Os endereços vêm dos dados locais do Cartola
// (site/public/data/cartola.json, fora do git). Escudo é marca do clube e foto tem direito de
// imagem: um build feito com CRESTS=local não deve ser publicado. Sem a variável: monograma.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

let cache = null;

export function crestsEnabled() {
  return process.env.CRESTS === "local";
}

export function crestMap() {
  if (!crestsEnabled()) return {};
  if (cache) return cache;
  const file = join(process.cwd(), "public", "data", "cartola.json");
  cache = existsSync(file) ? JSON.parse(readFileSync(file, "utf-8")).escudos || {} : {};
  return cache;
}
