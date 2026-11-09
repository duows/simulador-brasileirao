// Sobe o site em modo local COM escudos e fotos (CRESTS=local). Uso pessoal: não publique um
// build feito assim (escudos são marcas dos clubes e fotos têm direito de imagem).
import { spawn } from "node:child_process";

const port = process.env.PORT || "3001";
const child = spawn(process.platform === "win32" ? "npx.cmd" : "npx", ["next", "dev", "-p", port], {
  stdio: "inherit", shell: process.platform === "win32", env: { ...process.env, CRESTS: "local" },
});
child.on("exit", (code) => process.exit(code ?? 0));
