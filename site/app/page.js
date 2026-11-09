import EvolutionChart from "../components/EvolutionChart";
import Heatmap from "../components/Heatmap";
import HomeTable from "../components/HomeTable";
import MyTeamCards from "../components/MyTeamCards";
import Races from "../components/Races";
import { load } from "../lib/data";
import { num } from "../lib/format";

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
        modelo para cada jogo. A ordem segue os pontos esperados, não o resultado mais provável de cada jogo (isso
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
