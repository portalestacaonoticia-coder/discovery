// Tela Discovery: lê e edita o config/sites.yaml do repo discovery direto no
// GitHub — a fonte da verdade dos termos (classificador por hub) e das
// consultas (buscas do Google News). Salvar aqui = commit na main; o cron do
// Actions usa o arquivo novo na rodada seguinte, sem deploy nem código.
//
// AUTÔNOMO de propósito: import relativo sem extensão quebra o runtime ESM da
// Vercel (mesma lição do tick-radar.ts) — nada de módulo compartilhado.
// A edição usa o pacote `yaml` só para LOCALIZAR os nós (offsets em `range`) e
// emenda o texto original nesses trechos: reescrever o arquivo inteiro via
// toString() destruía CRLF, alinhamento de comentários e o estilo [a, b].
//
// Env (Vercel): DISCOVERY_GITHUB_TOKEN — PAT fine-grained com Contents
// read&write só no discovery (o RELOGIO_GITHUB_TOKEN é só Actions, não serve).
//
// GET  /api/discovery -> { sha, sites: [{ id, dominio, entidade, hubs, fontes }] }
// POST /api/discovery -> { sha, site, hubs?: [{id, termos}], fontes?: [{indice, consulta}] }
//                        edita o YAML e commita; 409 se o arquivo mudou no meio.

import { parseDocument, stringify } from "yaml";
import type { Node, YAMLMap, YAMLSeq } from "yaml";

interface Pedido {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
  query: Record<string, string | string[] | undefined>;
  body?: unknown;
}
interface Resposta {
  setHeader(nome: string, valor: string): void;
  status(codigo: number): Resposta;
  json(objeto: unknown): void;
}

const REPO = "portalestacaonoticia-coder/discovery";
const ARQUIVO = "config/sites.yaml";
const RAMO = "main";

// Sessão validada no Supabase do conteudo.tihee — mesmas contas do app.
const CONTEUDO_URL = process.env.VITE_SUPABASE_URL || "https://eprnygwxuysygloerbav.supabase.co";
const CONTEUDO_ANON = process.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwcm55Z3d4dXlzeWdsb2VyYmF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzOTgyODUsImV4cCI6MjA4OTk3NDI4NX0.hAXbTBbp2iWnb-vbKRCOTO15HkdCpwGOm_3R_xQGSn4";

async function sessaoValida(token: string): Promise<boolean> {
  if (process.env.RADAR_DEV_SEM_AUTH === "1") return true;
  if (!token) return false;
  const resposta = await fetch(`${CONTEUDO_URL}/auth/v1/user`, {
    headers: { apikey: CONTEUDO_ANON, Authorization: `Bearer ${token}` },
  });
  return resposta.ok;
}

function cabecalhosGitHub(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "radar-tihee-discovery",
  };
}

interface ArquivoNoRepo {
  texto: string;
  sha: string;
}

async function leArquivo(token: string): Promise<ArquivoNoRepo> {
  const resposta = await fetch(
    `https://api.github.com/repos/${REPO}/contents/${ARQUIVO}?ref=${RAMO}`,
    { headers: cabecalhosGitHub(token) },
  );
  if (!resposta.ok) {
    throw new Error(`GitHub devolveu HTTP ${resposta.status} ao ler ${ARQUIVO}`);
  }
  const corpo = (await resposta.json()) as { content: string; sha: string };
  return { texto: Buffer.from(corpo.content, "base64").toString("utf8"), sha: corpo.sha };
}

// -- leitura: YAML -> resumo para a tela -------------------------------------

interface HubDaTela {
  id: string;
  titulo: string;
  termos: string[];
}
interface FonteDaTela {
  indice: number;
  tipo: string;
  consulta: string | null;
  url: string | null;
}
interface SiteDaTela {
  id: string;
  dominio: string;
  entidade: string;
  hubs: HubDaTela[];
  fontes: FonteDaTela[];
}

export function resumeSites(texto: string): SiteDaTela[] {
  const bruto = parseDocument(texto).toJS() as {
    sites?: Record<string, {
      dominio?: string;
      entidade?: string;
      hubs?: { id?: string; titulo?: string; termos?: unknown[] }[];
      fontes?: { tipo?: string; consulta?: string; url?: string }[];
    }>;
  };
  return Object.entries(bruto.sites ?? {}).map(([id, site]) => ({
    id,
    dominio: site.dominio ?? "",
    entidade: site.entidade ?? "",
    hubs: (site.hubs ?? []).map((hub) => ({
      id: hub.id ?? "",
      titulo: hub.titulo ?? "",
      termos: (hub.termos ?? []).map(String),
    })),
    fontes: (site.fontes ?? []).map((fonte, indice) => ({
      indice,
      tipo: fonte.tipo ?? "",
      consulta: fonte.consulta ?? null,
      url: fonte.url ?? null,
    })),
  }));
}

// -- escrita: valida o pedido, edita os nós, commita --------------------------

interface PedidoDeEdicao {
  sha: string;
  site: string;
  hubs?: { id: string; termos: string[] }[];
  fontes?: { indice: number; consulta: string }[];
}

/** Valida e normaliza o corpo; devolve mensagem de erro ou o pedido limpo. */
function saneiaEdicao(corpo: unknown): { erro: string } | { pedido: PedidoDeEdicao } {
  const b = (corpo ?? {}) as Record<string, unknown>;
  if (typeof b.sha !== "string" || !/^[0-9a-f]{20,64}$/.test(b.sha)) {
    return { erro: "sha do arquivo é obrigatório (venha do GET)" };
  }
  if (typeof b.site !== "string" || !/^[a-z0-9_-]{1,40}$/.test(b.site)) {
    return { erro: "site é obrigatório" };
  }
  const pedido: PedidoDeEdicao = { sha: b.sha, site: b.site };

  if (b.hubs !== undefined) {
    if (!Array.isArray(b.hubs)) return { erro: "hubs precisa ser lista de {id, termos}" };
    pedido.hubs = [];
    for (const item of b.hubs as unknown[]) {
      const h = (item ?? {}) as { id?: unknown; termos?: unknown };
      if (typeof h.id !== "string" || !/^[a-z0-9_-]{1,40}$/.test(h.id)) {
        return { erro: "cada hub precisa de um id válido" };
      }
      if (!Array.isArray(h.termos)) return { erro: `hub ${h.id}: termos precisa ser lista` };
      const termos = (h.termos as unknown[])
        .map((t) => String(t).trim())
        .filter(Boolean);
      if (termos.length === 0) return { erro: `hub ${h.id}: informe ao menos um termo` };
      if (termos.length > 40) return { erro: `hub ${h.id}: no máximo 40 termos` };
      const grande = termos.find((t) => t.length > 60);
      if (grande) return { erro: `hub ${h.id}: termo longo demais ("${grande.slice(0, 20)}…")` };
      if (pedido.hubs.some((outro) => outro.id === h.id)) {
        return { erro: `hub ${h.id} veio duplicado no pedido` };
      }
      pedido.hubs.push({ id: h.id, termos });
    }
  }

  if (b.fontes !== undefined) {
    if (!Array.isArray(b.fontes)) return { erro: "fontes precisa ser lista de {indice, consulta}" };
    pedido.fontes = [];
    for (const item of b.fontes as unknown[]) {
      const f = (item ?? {}) as { indice?: unknown; consulta?: unknown };
      const indice = Number(f.indice);
      if (!Number.isInteger(indice) || indice < 0 || indice > 50) {
        return { erro: "cada fonte precisa do indice dela na lista" };
      }
      const consulta = typeof f.consulta === "string" ? f.consulta.trim() : "";
      if (!consulta || consulta.length > 120) {
        return { erro: `fonte ${indice}: consulta precisa ter de 1 a 120 caracteres` };
      }
      if (pedido.fontes.some((outra) => outra.indice === indice)) {
        return { erro: `fonte ${indice} veio duplicada no pedido` };
      }
      pedido.fontes.push({ indice, consulta });
    }
  }

  if (!pedido.hubs?.length && !pedido.fontes?.length) {
    return { erro: "nada para salvar: mande hubs e/ou fontes" };
  }
  return { pedido };
}

/** Um trecho do texto original a substituir (offsets do `range` dos nós). */
interface Remendo {
  inicio: number;
  fim: number;
  texto: string;
}

/** Escalar YAML numa linha só, sem a quebra final do stringify. */
function escalarYaml(valor: string, aspas: boolean): string {
  return stringify(valor, aspas ? { defaultStringType: "QUOTE_DOUBLE", defaultKeyType: "PLAIN" } : {}).trim();
}

/** Aplica a edição emendando só os trechos tocados; comentários, quebras de
 *  linha e o resto do arquivo ficam byte a byte como estavam. */
export function aplicaEdicao(texto: string, pedido: PedidoDeEdicao): { novoTexto?: string; erro?: string } {
  const doc = parseDocument(texto);
  const site = doc.getIn(["sites", pedido.site]);
  if (!site) return { erro: `site ${pedido.site} não existe no sites.yaml` };
  const remendos: Remendo[] = [];

  for (const edicaoHub of pedido.hubs ?? []) {
    const hubs = doc.getIn(["sites", pedido.site, "hubs"]) as YAMLSeq | undefined;
    const alvo = (hubs?.items ?? []).find(
      (item) => (item as YAMLMap).get?.("id") === edicaoHub.id,
    ) as YAMLMap | undefined;
    if (!alvo) return { erro: `hub ${edicaoHub.id} não existe em ${pedido.site}` };
    const no = alvo.get("termos", true) as Node | null;
    if (!no?.range) return { erro: `hub ${edicaoHub.id}: campo termos não encontrado no YAML` };
    // termos são palavras simples: estilo plano, como o arquivo já usa
    const itens = edicaoHub.termos.map((t) => escalarYaml(t, false)).join(", ");
    remendos.push({ inicio: no.range[0], fim: no.range[1], texto: `[${itens}]` });
  }

  for (const edicaoFonte of pedido.fontes ?? []) {
    const fontes = doc.getIn(["sites", pedido.site, "fontes"]) as YAMLSeq | undefined;
    const alvo = fontes?.items?.[edicaoFonte.indice] as YAMLMap | undefined;
    if (!alvo) return { erro: `fonte ${edicaoFonte.indice} não existe em ${pedido.site}` };
    if (alvo.get("tipo") !== "google_news") {
      return { erro: `fonte ${edicaoFonte.indice} não é google_news — edite no repo` };
    }
    const no = alvo.get("consulta", true) as Node | null;
    if (!no?.range) return { erro: `fonte ${edicaoFonte.indice}: campo consulta não encontrado no YAML` };
    // consultas ficam entre aspas no arquivo: mantém o estilo
    remendos.push({ inicio: no.range[0], fim: no.range[1], texto: escalarYaml(edicaoFonte.consulta, true) });
  }

  // do fim para o começo, para um remendo não deslocar os offsets dos demais
  remendos.sort((a, b) => b.inicio - a.inicio);
  let novoTexto = texto;
  for (const remendo of remendos) {
    novoTexto = novoTexto.slice(0, remendo.inicio) + remendo.texto + novoTexto.slice(remendo.fim);
  }
  return { novoTexto };
}

async function commita(token: string, pedido: PedidoDeEdicao, novoTexto: string) {
  return fetch(`https://api.github.com/repos/${REPO}/contents/${ARQUIVO}`, {
    method: "PUT",
    headers: { ...cabecalhosGitHub(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      message: `Discovery: termos/consultas de ${pedido.site} via radar-web`,
      content: Buffer.from(novoTexto, "utf8").toString("base64"),
      sha: pedido.sha,
      branch: RAMO,
    }),
  });
}

export default async function handler(req: Pedido, res: Resposta) {
  const autorizacao = typeof req.headers.authorization === "string" ? req.headers.authorization : "";
  const token = autorizacao.replace(/^Bearer\s+/i, "");
  if (!(await sessaoValida(token))) {
    res.status(401).json({ erro: "sessão inválida — entre de novo no conteudo.tihee" });
    return;
  }

  const tokenGitHub = process.env.DISCOVERY_GITHUB_TOKEN || "";
  if (!tokenGitHub) {
    res.status(500).json({
      erro: "falta DISCOVERY_GITHUB_TOKEN na Vercel (PAT com Contents read&write no discovery)",
    });
    return;
  }

  try {
    if (req.method === "GET") {
      const arquivo = await leArquivo(tokenGitHub);
      res.status(200).json({ sha: arquivo.sha, sites: resumeSites(arquivo.texto) });
      return;
    }

    if (req.method !== "POST") {
      res.status(405).json({ erro: "método não permitido" });
      return;
    }

    const saneado = saneiaEdicao(req.body);
    if ("erro" in saneado) {
      res.status(400).json({ erro: saneado.erro });
      return;
    }
    const { pedido } = saneado;

    const arquivo = await leArquivo(tokenGitHub);
    if (arquivo.sha !== pedido.sha) {
      res.status(409).json({ erro: "o sites.yaml mudou no repositório — recarregue e edite de novo" });
      return;
    }
    const edicao = aplicaEdicao(arquivo.texto, pedido);
    if (edicao.erro || !edicao.novoTexto) {
      res.status(400).json({ erro: edicao.erro ?? "não consegui aplicar a edição" });
      return;
    }
    const resposta = await commita(tokenGitHub, pedido, edicao.novoTexto);
    if (resposta.status === 409) {
      res.status(409).json({ erro: "o sites.yaml mudou no repositório — recarregue e edite de novo" });
      return;
    }
    if (!resposta.ok) {
      res.status(502).json({ erro: `GitHub recusou o commit (HTTP ${resposta.status})` });
      return;
    }
    const corpo = (await resposta.json()) as { content?: { sha?: string }; commit?: { sha?: string } };
    res.status(200).json({ ok: true, site: pedido.site, sha: corpo.content?.sha ?? null, commit: corpo.commit?.sha ?? null });
  } catch (erro) {
    res.status(502).json({ erro: String(erro) });
  }
}
