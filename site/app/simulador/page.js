import Simulator from "../../components/Simulator";
import { load } from "../../lib/data";

export const metadata = { title: "Simulador “e se” · futdados" };

export default function SimuladorPage() {
  const data = load("simulador");
  const meta = load("meta");
  return (
    <>
      <h1>Simulador “e se”</h1>
      <p className="lead">
        Escolha o resultado de jogos que ainda não aconteceram e veja como mudam os pontos esperados, a faixa de posição
        e as chances de título, G4, G6 e rebaixamento. Tudo é recalculado no seu navegador, com os mesmos gols esperados
        do modelo; nenhum dado é enviado a lugar nenhum. Resultados reais até a rodada {data.rodada_base}.
      </p>
      <Simulator data={data} focus={meta.time_foco} />
    </>
  );
}
