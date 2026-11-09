"use client";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "Tabela projetada"],
  ["/rodada/", "Rodada"],
  ["/simulador/", "Simulador “e se”"],
  ["/modelo/", "Modelo"],
  ["/spfc/", "São Paulo"],
];

export default function Nav() {
  const path = usePathname() || "/";
  const norm = path.endsWith("/") ? path : `${path}/`;
  return (
    <nav className="menu" aria-label="Seções">
      {LINKS.map(([href, label]) => (
        <a key={href} href={href} aria-current={norm === href ? "page" : undefined}>{label}</a>
      ))}
    </nav>
  );
}
