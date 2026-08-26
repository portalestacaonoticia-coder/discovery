import Selo from "@/components/Selo";
import { listaArtigos } from "@/lib/consultas";
import { tempoRelativo } from "@/lib/formata";

export default async function ListaArtigos({ site }) {
  const artigos = await listaArtigos(site);
  if (artigos.length === 0) return null;

  return (
    <section className="cartao">
      <h2>Artigos gerados</h2>
      <div className="tabela-envelope">
        <table>
          <thead>
            <tr>
              <th>Título</th>
              <th>Tipo</th>
              <th>Status</th>
              <th>Portão</th>
              <th>Quando</th>
            </tr>
          </thead>
          <tbody>
            {artigos.map((a) => (
              <tr key={a.id}>
                <td className="quebra">
                  {a.url_publicada ? (
                    <a href={a.url_publicada} target="_blank" rel="noreferrer">{a.titulo}</a>
                  ) : (
                    a.titulo
                  )}
                </td>
                <td className="discreto">{a.tipo}</td>
                <td><Selo status={a.status} /></td>
                <td className="discreto quebra">{a.motivo_portao || "—"}</td>
                <td className="discreto">{tempoRelativo(a.criado_em)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
