import "@/styles/tokens.css";
import "@/styles/painel.css";
import "@/styles/features/cotacoes.css";

export const metadata = {
  title: "Painel do radar",
  description: "Pautas, cotações, artigos e execuções do radar em um lugar só",
};

export default function Layout({ children }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="topo">
          <a href="/" className="marca">📡 Painel do radar</a>
        </header>
        <main className="conteudo">{children}</main>
      </body>
    </html>
  );
}
