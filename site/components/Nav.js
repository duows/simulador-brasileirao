"use client";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "Tabela"],
  ["/rodada/", "Rodada"],
  ["/times/", "Times"],
  ["/temporadas/", "Temporadas"],
  ["/historico/", "Histórico"],
  ["/simulador/", "Simulador"],
  ["/modelo/", "Modelo"],
];

export default function Nav() {
  const path = usePathname() || "/";
  const norm = path.endsWith("/") ? path : `${path}/`;
  return (
    <nav className="menu" aria-label="Seções">
      {LINKS.map(([href, label]) => (
        <a key={href} href={href} aria-current={(href === "/" ? norm === "/" : norm.startsWith(href)) ? "page" : undefined}>{label}</a>
      ))}
    </nav>
  );
}
