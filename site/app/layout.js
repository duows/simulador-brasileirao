import "./globals.css";
import { IBM_Plex_Sans, Saira_Condensed } from "next/font/google";
import Nav from "../components/Nav";
import { MyTeamProvider, MyTeamSelect } from "../components/MyTeam";
import { load } from "../lib/data";
import { dateTimeBR } from "../lib/format";

// Fontes baixadas no build e servidas pelo próprio site (nenhuma chamada externa por visitante).
const saira = Saira_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-saira", display: "swap" });
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-plex", display: "swap" });

const meta = load("meta");
const teams = load("tabela").linhas.map((l) => l.time).sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

export const metadata = {
  title: "futdados · Brasileirão",
  description: "Probabilidades estimadas pelo modelo e projeções do Brasileirão Série A.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" className={`${saira.variable} ${plex.variable}`}>
      <body>
        <MyTeamProvider>
        <header className="top">
          <div className="wrap">
            <a className="brand" href="/">futdados</a>
            <Nav />
            <MyTeamSelect teams={teams} />
          </div>
        </header>
        {/* aviso obrigatório em todas as páginas */}
        <div className="notice" role="note">
          <div className="wrap">
            <strong>{meta.aviso}</strong>
            {meta.demonstracao && <> {meta.nota_demonstracao}</>}
          </div>
        </div>
        <main><div className="wrap">{children}</div></main>
        <footer className="bottom">
          <div className="wrap">
            <span><strong>{meta.aviso}</strong></span>
            <span>{meta.atribuicao}. Histórico: footballcsv (domínio público, CC0).</span>
            <span>Última atualização: {dateTimeBR(meta.gerado_em)} (horário de Brasília) · modelo {meta.versao_modelo}</span>
            <span className="muted">{meta.linguagem}</span>
          </div>
        </footer>
        </MyTeamProvider>
      </body>
    </html>
  );
}
