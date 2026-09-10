// Tipos e leitura da tela Discovery (config editorial do sites.yaml, via
// /api/discovery — o token do GitHub fica na função serverless, nunca aqui).

export interface DiscoveryHub {
  id: string;
  titulo: string;
  termos: string[];
}

export interface DiscoveryFonte {
  indice: number;
  tipo: string;
  consulta: string | null;
  url: string | null;
}

export interface DiscoverySite {
  id: string;
  dominio: string;
  entidade: string;
  hubs: DiscoveryHub[];
  fontes: DiscoveryFonte[];
}

export interface DiscoveryConfig {
  sha: string;
  sites: DiscoverySite[];
}

export interface DiscoveryEdicao {
  sha: string;
  site: string;
  hubs?: { id: string; termos: string[] }[];
  fontes?: { indice: number; consulta: string }[];
}

export async function consultaDiscovery(token: string): Promise<DiscoveryConfig> {
  const resposta = await fetch("/api/discovery", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    throw new Error((corpo as { erro?: string }).erro || `HTTP ${resposta.status}`);
  }
  return corpo as DiscoveryConfig;
}

export async function salvaDiscovery(edicao: DiscoveryEdicao, token: string): Promise<void> {
  const resposta = await fetch("/api/discovery", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(edicao),
  });
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error((corpo as { erro?: string }).erro || `HTTP ${resposta.status}`);
  }
}

// -- regras puras da tela (testáveis) ----------------------------------------

/** Lista de termos -> texto editável no campo. */
export function termosParaTexto(termos: string[]): string {
  return termos.join(", ");
}

/** Texto do campo -> lista de termos limpa (vírgula separa; vazio some). */
export function textoParaTermos(texto: string): string[] {
  return texto
    .split(",")
    .map((termo) => termo.trim())
    .filter(Boolean);
}

/** Duas listas de termos dizem a mesma coisa? (ordem importa: é config). */
export function termosIguais(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((termo, i) => termo === b[i]);
}
