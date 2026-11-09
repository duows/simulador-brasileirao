// Leitura, durante o build estático, dos JSONs gerados por `futdados export-site` em site/public/data.
import { readFileSync } from "node:fs";
import { join } from "node:path";

export function load(name) {
  return JSON.parse(readFileSync(join(process.cwd(), "public", "data", `${name}.json`), "utf-8"));
}
