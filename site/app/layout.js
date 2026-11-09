import "./globals.css";
import Nav from "../components/Nav";
import { load } from "../lib/data";
import { dateTimeBR } from "../lib/format";

const meta = load("meta");

export const metadata = {
  title: "futdados · Brasileirão",
  description: "Probabilidades estimadas pelo modelo e projeções do Brasileirão Série A, com foco no São Paulo FC.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="top">
          <div className="wrap">
            <a className="brand" href="/">futdados</a>
            <Nav />
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
      </body>
    </html>
  );
}
