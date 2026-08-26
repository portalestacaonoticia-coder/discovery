import Selo from "@/components/Selo";
import { ultimasExecucoes } from "@/lib/consultas";
import { dataHora, duracao, tempoRelativo } from "@/lib/formata";

export default async function UltimasExecucoes({ site }) {
  const linhas = await ultimasExecucoes(site);

  return (
    <section className="cartao">
      <h2>Execuções dos crons</h2>
      {linhas === null && (
        <p className="aviso">
          A tabela <code>execucoes</code> ainda não existe no Supabase. Rode o{" "}
          <code>sql/schema.sql</code> de novo no SQL Editor (ele é idempotente) e
          cada rodada dos crons passa a aparecer aqui.
        </p>
      )}
      {linhas?.length === 0 && (
        <p className="aviso">Nenhuma execução registrada ainda — a próxima rodada dos crons aparece aqui.</p>
      )}
      {linhas?.length > 0 && (
        <div className="tabela-envelope">
          <table>
            <thead>
              <tr>
                <th>Fluxo</th>
                <th>Status</th>
                <th>Resumo</th>
                <th>Quando</th>
                <th className="num">Duração</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.id}>
                  <td>{l.fluxo}</td>
                  <td><Selo status={l.status} /></td>
                  <td className="discreto quebra">{l.resumo || "—"}</td>
                  <td className="discreto" title={dataHora(l.fim)}>{tempoRelativo(l.fim)}</td>
                  <td className="num discreto">{duracao(l.inicio, l.fim)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
