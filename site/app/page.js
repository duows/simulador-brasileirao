import EvolutionChart from "../components/EvolutionChart";
import Heatmap from "../components/Heatmap";
import HomeTable from "../components/HomeTable";
import MyTeamCards from "../components/MyTeamCards";
import Races from "../components/Races";
import { load } from "../lib/data";
import { num, pct } from "../lib/format";

export default function Home() {
  const t = load("tabela");
  const hist = load("historico");
  const rows = t.linhas.map((l, i) => ({
    id: l.time.id, nome: l.time.nome, jogos: l.jogos, pontos_atuais: l.pontos_atuais,
    pontos_esperados: l.pontos_esperados, p10: l.faixa_posicao.p10, p90: l.faixa_posicao.p90,
    titulo: l.chance_titulo, g4: l.chance_g4, g6: l.chance_g6, rebaixamento: l.chance_rebaixamento,
    posicao_atual: l.posicao_atual, posicao_proj: i + 1, v: l.v, e: l.e, d: l.d, gp: l.gp, gc: l.gc,
    ultimos5: l.ultimos5, adiados: l.adiados, dist: l.distribuicao_posicao,
  }));
  const names = Object.fromEntries(rows.map((r) => [r.id, r.nome]));
  return (
    <>
      <p className="eyebrow">Brasileirão {t.temporada} · resultados reais até a rodada {t.rodada_base}</p>
      <h1>Tabela projetada · fim do campeonato</h1>
      <p className="lead">
        O restante do campeonato foi simulado {num(t.simulacoes, 0)} vezes a partir das probabilidades estimadas pelo
        modelo para cada jogo{t.incerteza_parametros ? ", sorteando também a força de cada time dentro da margem de erro dela" : ""}. A ordem segue os pontos esperados, não o resultado mais provável de cada jogo (isso
        ignoraria os empates).
      </p>
      <Races rows={rows} />
      <MyTeamCards rows={rows} />
      <HomeTable rows={rows} />
      <p className="small muted">
        Desempate: pontos, vitórias, saldo, gols pró e confronto direto (só entre dois clubes); cartões não estão nos
        dados e viram sorteio. Ordem a confirmar no regulamento da CBF. 0% e 100% significam que aconteceu em nenhuma
        ou em todas as simulações, não que é impossível ou certo.
      </p>

      {t.pontos_necessarios && (
        <>
          <h2>Quantos pontos bastam</h2>
          <p className="lead">
            Nas simulações, quem terminou com pelo menos estes pontos alcançou o objetivo em {Math.round(t.pontos_necessarios.nivel * 100)}% dos casos ou mais.
          </p>
          <div className="tiles">
            {[["Título", "titulo"], ["G4", "g4"], ["G6", "g6"], ["Permanência", "permanencia"]].map(([l, k]) => (
              <div key={k} className="card tile"><div className="label">{l}</div>
                <div className="value">{t.pontos_necessarios[k] ?? "—"}</div><div className="sub">pontos no fim</div></div>
            ))}
          </div>
        </>
      )}

      {t.jogos_decisivos?.length > 0 && (
        <>
          <h2>Jogos que mais mexem nas chances</h2>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Rodada</th><th className="l">Jogo</th><th className="l">Quem mais depende</th><th>Se o mandante vencer</th><th>Se empatar</th><th>Se o visitante vencer</th></tr></thead>
              <tbody>
                {t.jogos_decisivos.map((g) => (
                  <tr key={`${g.mandante}-${g.visitante}`}>
                    <td className="l">R{g.rodada}</td>
                    <td className="l">{g.mandante_nome} x {g.visitante_nome}</td>
                    <td className="l">{g.time_nome} · {{ titulo: "título", g4: "G4", rebaixamento: "rebaixamento" }[g.objetivo]}</td>
                    <td>{pct(g.se_mandante_vence)}</td><td>{g.se_empate == null ? "—" : pct(g.se_empate)}</td><td>{pct(g.se_visitante_vence)}</td>
                  </tr>
                ))}
              </tbody>
              <caption>Chance do objetivo indicado para o time indicado, separando as simulações pelo resultado daquele jogo.</caption>
            </table>
          </div>
        </>
      )}

      <h2>Onde cada time termina</h2>
      <Heatmap rows={rows} />

      <h2>Evolução das chances</h2>
      <div className="grid">
        <section className="card">
          <h3>Título</h3>
          <EvolutionChart hist={hist} metric="titulo" names={names} label="Chance de título" />
        </section>
        <section className="card">
          <h3>Rebaixamento</h3>
          <EvolutionChart hist={hist} metric="rebaixamento" names={names} label="Chance de rebaixamento" />
        </section>
      </div>
    </>
  );
}
