import { load } from "../../lib/data";
import MatchCard from "../../components/MatchCard";

export const metadata = { title: "Rodada · futdados" };

export default function Rodada() {
  const r = load("rodada");
  const adiados = r.adiados || [];
  if (!r.rodada && !adiados.length) {
    return <><h1>Rodada</h1><p className="lead">Não há jogos pendentes nesta temporada.</p></>;
  }
  return (
    <>
      <h1>{r.rodada ? `Rodada ${r.rodada}` : "Jogos pendentes"} · Brasileirão {r.temporada}</h1>
      <p className="lead">
        Probabilidade estimada pelo modelo de vitória do mandante, empate e vitória do visitante, vinda da matriz de
        placares (Poisson). Cada jogo mostra quanto cada fator pesou nos gols esperados de cada time.
      </p>
      {r.rodada && (
        <div className="grid">
          {r.jogos.map((j) => <MatchCard key={`${j.mandante.id}-${j.visitante.id}`} j={j} />)}
        </div>
      )}
      {adiados.length > 0 && (
        <>
          <h2>Jogos adiados</h2>
          <p className="lead">
            Jogos de rodadas que já aconteceram e foram remarcados. Têm probabilidade estimada própria e entram na
            tabela projetada na data nova.
          </p>
          <div className="grid">
            {adiados.map((j) => <MatchCard key={`${j.mandante.id}-${j.visitante.id}`} j={j} />)}
          </div>
        </>
      )}
    </>
  );
}
