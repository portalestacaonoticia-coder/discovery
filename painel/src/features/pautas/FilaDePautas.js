import Selo from "@/components/Selo";
import { contagemPorStatus, filaDePautas } from "@/lib/consultas";
import { tempoRelativo } from "@/lib/formata";

export default async function FilaDePautas({ site }) {
  const [chips, pautas] = await Promise.all([contagemPorStatus(site), filaDePautas(site)]);

  return (
    <section className="cartao">
      <h2>Fila de pautas</h2>
      {chips.length > 0 && (
        <div className="chips">
          {chips.map((c) => (
            <span key={c.status} className="chip">
              {c.status} <b>{c.total}</b>
            </span>
          ))}
        </div>
      )}
      {pautas.length === 0 && (
        <p className="aviso">Nenhuma pauta ainda — elas surgem quando o radar coleta algo relevante.</p>
      )}
      {pautas.length > 0 && (
        <div className="tabela-envelope">
          <table>
            <thead>
              <tr>
                <th>Pauta sugerida</th>
                <th>Ângulo</th>
                <th>Hub</th>
                <th>Status</th>
                <th>Quando</th>
              </tr>
            </thead>
            <tbody>
              {pautas.map((p) => (
                <tr key={p.id}>
                  <td className="quebra">
                    {p.titulo_sug || p.itens?.titulo || "—"}
                    {p.dado_proprio && <div className="mudo">dado próprio: {p.dado_proprio}</div>}
                    {p.itens?.url && (
                      <div className="mudo">
                        origem:{" "}
                        <a href={p.itens.url} target="_blank" rel="noreferrer">
                          {p.itens.veiculo || "link"}
                        </a>
                      </div>
                    )}
                  </td>
                  <td className="discreto">{p.angulo}</td>
                  <td className="discreto">{p.hub || "—"}</td>
                  <td><Selo status={p.status} /></td>
                  <td className="discreto">{tempoRelativo(p.criado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
