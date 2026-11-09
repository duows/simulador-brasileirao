import { load } from "../../lib/data";

export const metadata = { title: "Times · futdados" };

export default function Times() {
  const t = load("tabela");
  const teams = t.linhas.map((l) => l.time).sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  return (
    <>
      <h1>Times · Brasileirão {t.temporada}</h1>
      <ul className="plain">
        {teams.map((x) => <li key={x.id}>{x.id === "sao-paulo" ? <a href="/spfc/">{x.nome}</a> : x.nome}</li>)}
      </ul>
    </>
  );
}
