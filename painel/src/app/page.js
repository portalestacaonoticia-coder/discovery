import Link from "next/link";
import Selo from "@/components/Selo";
import { resumoDoSite, sitesConhecidos } from "@/lib/consultas";
import { dataCurta, moeda, tempoRelativo } from "@/lib/formata";

export const dynamic = "force-dynamic";

export default async function VisaoGeral() {
  const sites = await sitesConhecidos();
  const resumos = await Promise.all(sites.map(resumoDoSite));

  return (
    <>
      <div>
        <h1>Visão geral</h1>
        <p className="subtitulo">Um cartão por site — clique para abrir a fila, as cotações e as execuções.</p>
      </div>

      {resumos.length === 0 && (
        <div className="cartao aviso">
          Nenhum site apareceu no banco ainda. Assim que o radar rodar
          (<code>python -m radar.principal</code>) os sites surgem aqui sozinhos.
        </div>
      )}

      <div className="grade-cartoes">
        {resumos.map((r) => (
          <Link key={r.site} href={`/${r.site}`} className="cartao cartao-site">
            <span className="nome">{r.site}</span>
            <span className="metrica">
              <span className="numero">{r.pautasNovas}</span>
              <span className="rotulo">pautas novas na fila ({r.pautasTotal} no total)</span>
            </span>
            <span className="linha-meta">
              {r.ultimaExecucao ? (
                <>
                  <Selo status={r.ultimaExecucao.status} />
                  <span>
                    {r.ultimaExecucao.fluxo} {tempoRelativo(r.ultimaExecucao.fim)}
                  </span>
                </>
              ) : (
                <span>sem execução registrada</span>
              )}
            </span>
            <span className="linha-meta">
              {r.ultimaCotacao ? (
                <span>
                  PTAX {moeda(r.ultimaCotacao.ptax_venda)} em {dataCurta(r.ultimaCotacao.data)} · {r.artigos} artigos
                </span>
              ) : (
                <span>{r.artigos} artigos gerados</span>
              )}
            </span>
          </Link>
        ))}
      </div>
    </>
  );
}
