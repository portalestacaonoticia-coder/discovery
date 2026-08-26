import GraficoCotacoes from "./GraficoCotacoes";
import { serieCotacoes } from "@/lib/consultas";
import { dataCurta, dataLonga, moeda, pct } from "@/lib/formata";

export default async function CartaoCotacao({ site }) {
  const serie = await serieCotacoes(site, 30);
  if (serie.length === 0) return null; // site sem base de cotacoes (ex.: ferrugem)

  const atual = serie[serie.length - 1];
  const anterior = serie.length > 1 ? serie[serie.length - 2] : null;
  const delta = anterior
    ? (Number(atual.ptax_venda) / Number(anterior.ptax_venda) - 1) * 100
    : null;

  const recentes = [...serie].reverse().slice(0, 10);

  return (
    <section className="cartao">
      <h2>PTAX de venda — últimos {serie.length} pregões</h2>

      <div className="cotacao-heroi">
        <span className="valor">{moeda(atual.ptax_venda)}</span>
        {/* delta em tinta neutra de proposito: dolar subir nao e' "bom" nem "ruim" */}
        {delta !== null && (
          <span className="delta">
            {delta >= 0 ? "▲" : "▼"} {pct(delta)} ante o pregão anterior
          </span>
        )}
        <span className="quando">cotação de {dataLonga(atual.data)}</span>
      </div>

      <GraficoCotacoes pontos={serie} />

      <div className="tabela-envelope" style={{ marginTop: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th className="num">Compra</th>
              <th className="num">Venda</th>
              <th className="num">Variação</th>
            </tr>
          </thead>
          <tbody>
            {recentes.map((c, i) => {
              const ant = recentes[i + 1];
              const v = ant ? (Number(c.ptax_venda) / Number(ant.ptax_venda) - 1) * 100 : null;
              return (
                <tr key={c.data}>
                  <td className="discreto">{dataCurta(c.data)}</td>
                  <td className="num">{moeda(c.ptax_compra)}</td>
                  <td className="num">{moeda(c.ptax_venda)}</td>
                  <td className="num discreto">{v === null ? "—" : pct(v)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
