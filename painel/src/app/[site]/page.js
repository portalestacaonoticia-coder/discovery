import Link from "next/link";
import CartaoCotacao from "@/features/cotacoes/CartaoCotacao";
import FilaDePautas from "@/features/pautas/FilaDePautas";
import ListaArtigos from "@/features/artigos/ListaArtigos";
import UltimasExecucoes from "@/features/execucoes/UltimasExecucoes";

export const dynamic = "force-dynamic";

export default async function PaginaDoSite({ params }) {
  const { site } = await params;

  return (
    <>
      <div>
        <p className="subtitulo"><Link href="/">← visão geral</Link></p>
        <h1>{site}</h1>
      </div>

      <UltimasExecucoes site={site} />
      <CartaoCotacao site={site} />
      <FilaDePautas site={site} />
      <ListaArtigos site={site} />
    </>
  );
}
