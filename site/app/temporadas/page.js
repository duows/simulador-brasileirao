import { load } from "../../lib/data";
import { num, pct } from "../../lib/format";

export const metadata = { title: "Temporadas · futdados" };

export default function Temporadas() {
  const d = load("temporadas").temporadas;
  const anos = Object.keys(d).map(Number).sort((a, b) => b - a);
  return (
    <>
      <p className="eyebrow">Pontos corridos com 20 clubes</p>
      <h1>Temporadas 2006–{anos[0]}</h1>
      <p className="lead">Campeão, pontos do campeão e do primeiro rebaixado, gols por jogo e empates de cada edição. Clique no ano para ver a temporada completa.</p>
      <div className="table-scroll">
        <table>
          <thead><tr><th className="l">Ano</th><th className="l">Campeão</th><th>Pts do campeão</th><th>Vice</th><th>Pts do 17º</th><th>Gols por jogo</th><th>Empates</th><th>Vitórias do mandante</th><th className="l">Rebaixados</th></tr></thead>
          <tbody>
            {anos.map((a) => {
              const s = d[a];
              const camp = s.tabela[0];
              const reb = s.tabela.slice(-4).map((x) => x.nome).join(", ");
              return (
                <tr key={a}>
                  <td className="l"><a href={`/temporadas/${a}/`}><strong>{a}</strong></a>{!s.encerrada && <span className="tag">em andamento</span>}</td>
                  <td className="l team"><a href={`/times/${camp.time}/`}>{s.encerrada ? camp.nome : `${camp.nome} (líder)`}</a></td>
                  <td>{s.liga.pts_campeao}</td><td>{s.liga.pts_vice}</td><td>{s.liga.pts_17}</td>
                  <td>{num(s.liga.gols_por_jogo, 2)}</td><td>{pct(s.liga.empates_pct)}</td><td>{pct(s.liga.vitorias_mandante_pct)}</td>
                  <td className="l small">{s.encerrada ? reb : "—"}</td>
                </tr>
              );
            })}
          </tbody>
          <caption>Posições pela ordem pontos, vitórias, saldo e gols pró. Fontes: footballcsv (2006–2023, domínio público) e football-data.org (2024 em diante).</caption>
        </table>
      </div>
    </>
  );
}
