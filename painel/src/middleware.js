import { NextResponse } from "next/server";

// Protecao de acesso do painel inteiro: uma senha unica via Basic Auth.
// E' o suficiente aqui porque o painel e' interno e so' LE dados; a escrita
// continua exclusiva dos crons com service key. Sem PAINEL_SENHA definida
// (dev local), abre livre.
export function middleware(pedido) {
  const senha = process.env.PAINEL_SENHA;
  if (!senha) return NextResponse.next();

  const cabecalho = pedido.headers.get("authorization") || "";
  const [tipo, codificado] = cabecalho.split(" ");
  if (tipo === "Basic" && codificado) {
    try {
      const decodificado = atob(codificado);
      const informada = decodificado.slice(decodificado.indexOf(":") + 1);
      if (informada === senha) return NextResponse.next();
    } catch {
      // cabecalho malformado cai no 401 abaixo
    }
  }

  return new NextResponse("Autenticação necessária", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Painel do radar"' },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
