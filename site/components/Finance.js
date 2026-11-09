// Finanças de um clube, com fonte e status de cada número (dataset curado em data/finance).
import { brlMi } from "../lib/format";

export const FIELDS = [
  ["receita_operacional", "Receita operacional"],
  ["divida_total", "Dívida / endividamento"],
  ["resultado", "Resultado do ano"],
  ["passivo_a_descoberto", "Passivo a descoberto"],
  ["patrimonio_liquido", "Patrimônio líquido"],
  ["venda_atletas", "Venda de atletas"],
  ["despesa_futebol_profissional", "Despesa do futebol profissional"],
  ["fidc", "FIDC (cotas do clube)"],
  ["divida_empresarios", "Dívida com empresários"],
  ["receita_estadio", "Receita do estádio"],
  ["obrigacoes_totais", "Obrigações totais"],
  ["passivo_total", "Passivo total"],
];
const STATUS = {
  confirmado: ["ok", "confirmado"], conflito: ["conf", "fontes divergem"],
  nao_confirmado: ["pend", "não confirmado"], lacuna: ["pend", "lacuna"], nao_aplicavel: ["pend", "não se aplica"],
};

function Source({ r }) {
  if (!r.fonte_url) return <span className="muted">{r.tipo_fonte === "pista_usuario" ? "pista a confirmar" : "—"}</span>;
  const host = new URL(r.fonte_url).hostname.replace(/^www\./, "");
  return (
    <a href={r.fonte_url} target="_blank" rel="noopener noreferrer">
      {r.tipo_fonte === "pdf_oficial" ? "PDF oficial" : "imprensa"} ({host}){r.pagina_pdf ? `, p. ${r.pagina_pdf}` : ""}
    </a>
  );
}

export function FinanceCell({ rows }) {
  if (!rows.length) return <span className="muted">—</span>;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {rows.map((r, i) => {
        const [cls, label] = STATUS[r.status] || ["pend", r.status];
        return (
          <div key={i}>
            <div><strong>{r.valor_mil_reais == null ? "—" : brlMi(r.valor_mil_reais)}</strong>{" "}
              <span className={`badge ${cls}`}>{label}</span></div>
            <div className="small muted">{r.definicao || r.observacao}</div>
            <div className="small"><Source r={r} /></div>
          </div>
        );
      })}
    </div>
  );
}

export default function FinanceTable({ rows }) {
  const years = [...new Set(rows.map((r) => r.ano))].sort();
  const fields = FIELDS.filter(([f]) => rows.some((r) => r.campo === f));
  return (
    <div className="table-scroll">
      <table>
        <thead><tr><th className="l">Item</th>{years.map((y) => <th key={y} className="l">{y}</th>)}</tr></thead>
        <tbody>
          {fields.map(([campo, label]) => (
            <tr key={campo}>
              <td className="l" style={{ verticalAlign: "top" }}><strong>{label}</strong></td>
              {years.map((y) => (
                <td key={y} className="l wrap-cell" style={{ verticalAlign: "top" }}>
                  <FinanceCell rows={rows.filter((r) => r.campo === campo && r.ano === y)} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <caption>Valores em milhões de reais. Cada número tem fonte (PDF oficial com página, ou imprensa) e data de consulta no dataset.</caption>
      </table>
    </div>
  );
}
