import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import CartolaBuilder from "../../components/CartolaBuilder";
import { dateTimeBR, num } from "../../lib/format";

export const metadata = { title: "Cartola · futdados" };

const POS = { gol: "Goleiros", lat: "Laterais", zag: "Zagueiros", mei: "Meias", ata: "Atacantes", tec: "Técnicos" };

export default function Cartola() {
  // Dados do Cartola só existem localmente (API sem licença clara: fora do git e de qualquer publicação).
  const file = join(process.cwd(), "public", "data", "cartola.json");
  if (!existsSync(file)) {
    return (
      <>
        <h1>Cartola · estudo de caso</h1>
        <p className="lead">Os dados do Cartola ficam só no seu computador. Para gerar, rode <code>futdados cartola</code> e reconstrua o site.</p>
      </>
    );
  }
  const d = JSON.parse(readFileSync(file, "utf-8"));
  const bt = d.backtest;
  const f = d.fechamento;
  return (
    <>
      <p className="eyebrow">Estudo de caso pessoal · rodada {d.rodada} de {d.temporada}</p>
      <h1>Cartola: melhor time para o seu orçamento</h1>
      <p className="lead">
        Digite quantas cartoletas você tem e o sistema monta o time com a maior pontuação esperada pelo modelo, escolhendo
        esquema, atletas e capitão. O cálculo é exato e roda no seu navegador.
        {f && <> Mercado fecha em {String(f.dia).padStart(2, "0")}/{String(f.mes).padStart(2, "0")} às {String(f.hora).padStart(2, "0")}h{String(f.minuto).padStart(2, "0")}.</>}
      </p>
      {d.times_gravados && (
        <>
          <h2>Times gravados desta rodada</h2>
          <p className="lead">
            Estes são os times que ficaram registrados antes do fechamento (gravação de {String(d.times_gravados.gravado_em).slice(0, 16).replace("T", " ")} UTC)
            e que vão ser comparados com a pontuação real. Para o teste valer, escale exatamente um deles.
          </p>
          <div className="grid">
            {Object.entries(d.times_gravados.times).map(([b, t]) => (
              <section key={b} className="card">
                <h3>C$ {b} · {t.esquema} · esperado {num(t.esperado, 1)}</h3>
                <p className="small muted" style={{ margin: "0 0 6px" }}>custo C$ {num(t.custo, 2)}</p>
                <ul className="plain small">
                  {t.titulares.map((p) => (
                    <li key={p.id}><strong>{p.posicao.toUpperCase()}</strong> {p.apelido} <span className="muted">{p.time_nome}</span>{p.capitao && <span className="tag">capitão</span>}</li>
                  ))}
                </ul>
                <p className="small" style={{ margin: "6px 0 0" }}>
                  Banco: {t.banco.map((p) => `${p.posicao.toUpperCase()} ${p.apelido}${p.luxo ? " (luxo)" : ""}`).join(" · ")}
                </p>
              </section>
            ))}
          </div>
          <h2>Montar para outro orçamento</h2>
          <p className="small muted">Calculado agora com os dados mais recentes; pode diferir do time gravado se preços ou status mudaram.</p>
        </>
      )}
      <CartolaBuilder data={d} photos={process.env.CRESTS === "local"} />

      <h2>Ao vivo: previsto x real</h2>
      {d.ao_vivo && d.ao_vivo.length > 0 ? (
        <div className="table-scroll">
          <table>
            <thead><tr><th className="l">Rodada</th><th>Erro do modelo</th><th>Erro da média do Cartola</th><th>Prováveis que jogaram</th>
              {Object.keys(d.ao_vivo[d.ao_vivo.length - 1].times).map((b) => <th key={b}>Time C$ {b}: esperado → real</th>)}</tr></thead>
            <tbody>
              {d.ao_vivo.map((x) => (
                <tr key={x.rodada}>
                  <td className="l">{x.rodada}</td>
                  <td className={x.erro_modelo < x.erro_media_cartola ? "delta-pos" : "delta-neg"}>{num(x.erro_modelo, 2)}</td>
                  <td>{num(x.erro_media_cartola, 2)}</td>
                  <td>{x.provaveis_que_jogaram == null ? "—" : `${Math.round(x.provaveis_que_jogaram * 100)}%`}</td>
                  {Object.keys(d.ao_vivo[d.ao_vivo.length - 1].times).map((b) => (
                    <td key={b}>{x.times[b] ? `${num(x.times[b].esperado, 1)} → ${num(x.times[b].real, 1)}` : "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
            <caption>Previsões gravadas antes do fechamento do mercado (registro que não pode ser alterado) e comparadas depois com a pontuação oficial. Verde: o modelo errou menos que a média do Cartola naquela rodada.</caption>
          </table>
        </div>
      ) : (
        <p className="lead">
          Ainda nenhuma rodada registrada terminou. As previsões da rodada {d.rodada} já estão gravadas; depois que ela acabar,
          rode a atualização de novo e aqui aparece quanto o modelo errou e quantos pontos os times sugeridos fizeram de verdade.
        </p>
      )}

      <h2>Quanto o modelo erra (teste nas rodadas passadas)</h2>
      <p className="lead">
        Testado rodada a rodada nesta temporada, sempre só com as rodadas anteriores: erro médio de {num(bt.mae_modelo, 2)} pontos
        por atleta, contra {num(bt.mae_media, 2)} da média que o próprio Cartola mostra; errou menos em {bt.rodadas_modelo_melhor} de {bt.rodadas} rodadas.
        É um ganho real, mas pequeno: a pontuação do Cartola tem muito acaso, e o modelo não sabe a escalação nem quem vai ser poupado.
      </p>
      <ul className="plain small">
        <li>
          Chance de jogar pelo status do mercado: provável {Math.round(d.p_jogar.provavel * 100)}%, dúvida {Math.round(d.p_jogar.duvida * 100)}%.
          {d.p_jogar_estimativa && (d.p_jogar_estimativa.provavel?.casos ?? 0) > 0
            ? <> Estimada com o histórico guardado: {Object.entries(d.p_jogar_estimativa).map(([s, v]) => `${s === "duvida" ? "dúvida" : "provável"} ${v.jogaram} de ${v.casos} jogaram`).join(", ")} (puxado para o valor inicial enquanto há pouco histórico).</>
            : <> Ainda sem histórico: o sistema guarda o mercado de cada rodada e passa a estimar sozinho depois que ela termina.</>}
        </li>
        <li>Regularidade: fração dos últimos 5 jogos do time em que o atleta entrou em campo (titular de sempre pontua mais que quem entra no fim).</li>
        {d.finalizacoes_no_modelo && <li>Os gols esperados de cada time usam também as finalizações no alvo (scouts do Cartola), não só os gols.</li>}
        {d.jogos_fora_da_rodada.length > 0 && <li>Fora desta rodada do Cartola (não pontuam): {d.jogos_fora_da_rodada.join(", ")}.</li>}
        <li>Capitão pontua ×{num(d.multiplicador_capitao, 1)} (regra a confirmar no regulamento do Cartola).</li>
        <li>Dados: API pública do Cartola FC, para uso pessoal e local, gerados em {dateTimeBR(d.gerado_em)}.</li>
      </ul>

      <h2>Maiores pontuações esperadas por posição</h2>
      <div className="grid">
        {Object.entries(POS).map(([pos, label]) => (
          <section key={pos} className="card">
            <h3>{label}</h3>
            <div className="table-scroll">
              <table>
                <thead><tr><th className="l">Atleta</th><th>Preço</th><th>Esperado</th><th>Por C$</th></tr></thead>
                <tbody>
                  {d.atletas.filter((p) => p.posicao === pos).slice(0, 8).map((p) => (
                    <tr key={p.id}>
                      <td className="l">{p.apelido} <span className="muted small">{p.time_nome}</span></td>
                      <td>{num(p.preco, 2)}</td><td><strong>{num(p.esperado, 2)}</strong></td><td>{num(p.esperado / p.preco, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
