import ProjectionTable from "../components/ProjectionTable";
import { load } from "../lib/data";
import { num, pct } from "../lib/format";

export default function Home() {
  const meta = load("meta");
  const t = load("tabela");
  const rows = t.linhas.map((l) => ({
    id: l.time.id, nome: l.time.nome, jogos: l.jogos, pontos_atuais: l.pontos_atuais,
    pontos_esperados: l.pontos_esperados, p10: l.faixa_posicao.p10, p90: l.faixa_posicao.p90,
    titulo: l.chance_titulo, g4: l.chance_g4, g6: l.chance_g6, rebaixamento: l.chance_rebaixamento,
  }));
  const spfc = rows.find((r) => r.id === meta.time_foco);
  return (
    <>
      <h1>Tabela projetada · fim do Brasileirão {t.temporada}</h1>
      <p className="lead">
        Resultados reais até a rodada {t.rodada_base}. O restante do campeonato foi simulado {num(t.simulacoes, 0)} vezes
        a partir das probabilidades estimadas pelo modelo para cada jogo. A ordem segue os pontos esperados, não o
        resultado mais provável de cada jogo (isso ignoraria os empates).
      </p>
      {spfc && (
        <div className="tiles">
          <div className="card tile"><div className="label">São Paulo · pontos esperados</div>
            <div className="value">{num(spfc.pontos_esperados, 1)}</div>
            <div className="sub">hoje tem {spfc.pontos_atuais} em {spfc.jogos} jogos</div></div>
          <div className="card tile"><div className="label">São Paulo · faixa de posição final</div>
            <div className="value">{spfc.p10}º a {spfc.p90}º</div><div className="sub">em 80% das simulações</div></div>
          <div className="card tile"><div className="label">São Paulo · chance de G4</div>
            <div className="value">{pct(spfc.g4)}</div><div className="sub">G6: {pct(spfc.g6)}</div></div>
          <div className="card tile"><div className="label">São Paulo · chance de rebaixamento</div>
            <div className="value">{pct(spfc.rebaixamento)}</div><div className="sub">título: {pct(spfc.titulo)}</div></div>
        </div>
      )}
      <ProjectionTable rows={rows} focus={meta.time_foco}
        caption="Faixa de posição: do percentil 10 ao 90 das simulações (80% dos cenários caem dentro dela). G4 = 1º ao 4º, G6 = 1º ao 6º, rebaixamento = 17º ao 20º." />
      <p className="small muted">
        Critérios de desempate usados: pontos, vitórias, saldo, gols pró, confronto direto (só entre dois clubes);
        cartões não estão nos dados e viram sorteio. Ordem a confirmar no regulamento da CBF.
      </p>
    </>
  );
}
