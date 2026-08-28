// Aba Radar: lê o Supabase do RADAR (repo discovery) com a service key, que
// vive SÓ aqui — variáveis de ambiente da Vercel, nunca no navegador (este app
// é 100% client-side; era proibido levar a chave para o bundle).
// Antes de responder, valida a sessão do conteudo.tihee: o token do usuário é
// conferido no Supabase do próprio app. Sem sessão válida, nada sai.
//
// A DECISAO de quais pautas soltar e' do radar (radar/selecao.py, no cron):
// aqui so' se exibe a selecao do dia e se editam os criterios/meta.
//
// GET  /api/radar            -> { sites }
// GET  /api/radar?site=doll  -> pautas, execucoes, artigos, contagens,
//                               resumoDia, selecaoDoDia e criterios
// POST /api/radar            -> { site, pautas_por_dia?, criterios? } salva config
//                            -> { pauta_id, status } veto/desfazer de uma pauta

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

// URL e chave publishable (anon) do Supabase do conteudo.tihee — públicas por
// design, as mesmas do front. O fallback literal cobre o caso de a Vercel não
// expor as VITE_* para funções.
const CONTEUDO_URL = process.env.VITE_SUPABASE_URL || "https://eprnygwxuysygloerbav.supabase.co";
const CONTEUDO_ANON = process.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwcm55Z3d4dXlzeWdsb2VyYmF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzOTgyODUsImV4cCI6MjA4OTk3NDI4NX0.hAXbTBbp2iWnb-vbKRCOTO15HkdCpwGOm_3R_xQGSn4";

// Supabase do RADAR (dados). Aceita os dois pares de nomes: RADAR_SUPABASE_*
// (padrao deste app) ou SUPABASE_* (os nomes do motor Python, que o projeto
// Vercel pode ter herdado do .env.example do repo).
const RADAR_URL = process.env.RADAR_SUPABASE_URL || process.env.SUPABASE_URL || "";
const RADAR_CHAVE = process.env.RADAR_SUPABASE_SERVICE_KEY ||
  process.env.SUPABASE_SERVICE_KEY || "";

const FUSO = "America/Sao_Paulo";

async function sessaoValida(token: string): Promise<boolean> {
  // RADAR_DEV_SEM_AUTH=1 só existe no runner local (scripts/radar-api-dev.mjs)
  if (process.env.RADAR_DEV_SEM_AUTH === "1") return true;
  if (!token) return false;
  const resposta = await fetch(`${CONTEUDO_URL}/auth/v1/user`, {
    headers: { apikey: CONTEUDO_ANON, Authorization: `Bearer ${token}` },
  });
  return resposta.ok;
}

interface Leitura {
  dados: unknown[] | null;
  total: number | null;
  erro: string | null;
}

function cabecalhosRadar(extra: Record<string, string> = {}): Record<string, string> {
  return { apikey: RADAR_CHAVE, Authorization: `Bearer ${RADAR_CHAVE}`, ...extra };
}

async function leRadar(recurso: string, query: string, contar = false): Promise<Leitura> {
  const url = `${RADAR_URL}/rest/v1/${recurso}?${query}`;
  try {
    const resposta = await fetch(url, {
      headers: cabecalhosRadar(contar ? { Prefer: "count=exact" } : {}),
    });
    if (!resposta.ok) return { dados: null, total: null, erro: `HTTP ${resposta.status}` };
    const dados = (await resposta.json()) as unknown[];
    let total: number | null = null;
    const faixa = resposta.headers.get("content-range");
    if (faixa && faixa.includes("/")) total = Number(faixa.split("/")[1]) || 0;
    return { dados, total, erro: null };
  } catch (erro) {
    return { dados: null, total: null, erro: String(erro) };
  }
}

/** 'AAAA-MM-DD' do dia atual no fuso editorial. */
function hojeEmSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(new Date());
}

/** Posts publicados hoje no WordPress do site (endpoint público; o WP compara
 *  `after` sem offset contra a data local do post, que já é o fuso do site). */
async function contaPostsDeHoje(wpUrl: string): Promise<number | null> {
  try {
    const base = wpUrl.replace(/\/+$/, "");
    const resposta = await fetch(`${base}/wp-json/wp/v2/posts?per_page=1&after=${hojeEmSaoPaulo()}T00:00:00`);
    if (!resposta.ok) return null;
    return Number(resposta.headers.get("x-wp-total")) || 0;
  } catch {
    return null;
  }
}

async function mudaStatusPauta(res: Resposta, corpo: unknown) {
  const { pauta_id, status } = (corpo ?? {}) as { pauta_id?: number; status?: string };
  const id = Number(pauta_id);
  // 'nova' permitido para desfazer uma aprovacao/descarte por engano
  if (!Number.isInteger(id) || !["aprovada", "descartada", "nova"].includes(status || "")) {
    res.status(400).json({ erro: "pauta_id e status (aprovada | descartada | nova) são obrigatórios" });
    return;
  }
  const resposta = await fetch(`${RADAR_URL}/rest/v1/pautas?id=eq.${id}`, {
    method: "PATCH",
    headers: cabecalhosRadar({ "Content-Type": "application/json", Prefer: "return=representation" }),
    body: JSON.stringify({ status }),
  });
  const linhas = resposta.ok ? ((await resposta.json()) as unknown[]) : [];
  if (!resposta.ok || linhas.length === 0) {
    res.status(resposta.ok ? 404 : 502).json({ erro: `não consegui atualizar a pauta ${id}` });
    return;
  }
  res.status(200).json({ ok: true, pauta_id: id, status });
}

/** Aceita só pesos numéricos (0 a 100) em chaves conhecidas ou simples. */
function saneiaCriterios(bruto: unknown): Record<string, unknown> | null {
  if (typeof bruto !== "object" || bruto === null) return null;
  const b = bruto as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" && isFinite(v) && v >= 0 && v <= 100 ? v : null);
  const saida: Record<string, unknown> = {};
  const dado = num(b.dado_proprio);
  if (dado !== null) saida.dado_proprio = dado;
  const minimo = num(b.minimo);
  if (minimo !== null) saida.minimo = minimo;
  const quente = num(b.quente_ate_horas);
  if (quente !== null) saida.quente_ate_horas = quente;
  for (const grupo of ["angulos", "frescor", "janela"] as const) {
    if (typeof b[grupo] === "object" && b[grupo] !== null) {
      const g: Record<string, number> = {};
      for (const [chave, valor] of Object.entries(b[grupo] as Record<string, unknown>)) {
        const n = num(valor);
        if (n !== null && /^[a-z0-9_]{1,30}$/.test(chave)) g[chave] = n;
      }
      if (Object.keys(g).length) saida[grupo] = g;
    }
  }
  return Object.keys(saida).length ? saida : null;
}

async function salvaMeta(res: Resposta, corpo: unknown) {
  const { site, pautas_por_dia, criterios } = (corpo ?? {}) as {
    site?: string;
    pautas_por_dia?: number;
    criterios?: unknown;
  };
  if (!site) {
    res.status(400).json({ erro: "site é obrigatório" });
    return;
  }

  const carga: Record<string, unknown> = { site, atualizado_em: new Date().toISOString() };
  if (pautas_por_dia !== undefined) {
    const quantidade = Number(pautas_por_dia);
    if (!Number.isInteger(quantidade) || quantidade < 0 || quantidade > 200) {
      res.status(400).json({ erro: "pautas_por_dia precisa ser inteiro de 0 a 200" });
      return;
    }
    carga.pautas_por_dia = quantidade;
  }
  if (criterios !== undefined) {
    const limpos = saneiaCriterios(criterios);
    if (!limpos) {
      res.status(400).json({ erro: "criterios precisa ter pesos numéricos de 0 a 100" });
      return;
    }
    // O jsonb e' substituido inteiro no banco: mescla com o que ja esta salvo
    // para editar um peso nao apagar os demais.
    const atual = await leRadar("metas", `site=eq.${encodeURIComponent(site)}&select=criterios&limit=1`);
    const base = ((atual.dados?.[0] as { criterios?: Record<string, unknown> } | undefined)?.criterios) ?? {};
    const mesclado: Record<string, unknown> = { ...base, ...limpos };
    for (const grupo of ["angulos", "frescor", "janela"] as const) {
      const doBanco = base[grupo];
      const doPedido = limpos[grupo];
      if (typeof doBanco === "object" || typeof doPedido === "object") {
        mesclado[grupo] = { ...((doBanco as object) ?? {}), ...((doPedido as object) ?? {}) };
      }
    }
    carga.criterios = mesclado;
  }
  if (carga.pautas_por_dia === undefined && carga.criterios === undefined) {
    res.status(400).json({ erro: "nada para salvar: mande pautas_por_dia e/ou criterios" });
    return;
  }

  // upsert por site; colunas fora da carga ficam como estão
  const resposta = await fetch(`${RADAR_URL}/rest/v1/metas?on_conflict=site`, {
    method: "POST",
    headers: cabecalhosRadar({
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates",
    }),
    body: JSON.stringify(carga),
  });
  if (!resposta.ok) {
    res.status(502).json({ erro: `não consegui salvar (HTTP ${resposta.status})` });
    return;
  }
  res.status(200).json({ ok: true, site });
}

export default async function handler(req: Pedido, res: Resposta) {
  const autorizacao = typeof req.headers.authorization === "string" ? req.headers.authorization : "";
  const token = autorizacao.replace(/^Bearer\s+/i, "");
  if (!(await sessaoValida(token))) {
    res.status(401).json({ erro: "sessão inválida — entre de novo no conteudo.tihee" });
    return;
  }

  if (!RADAR_URL || !RADAR_CHAVE) {
    res.status(500).json({
      erro: "faltam RADAR_SUPABASE_URL/SUPABASE_URL e a service key nas variáveis de ambiente da Vercel",
    });
    return;
  }

  if (req.method === "POST") {
    const corpo = (req.body ?? {}) as { pauta_id?: unknown };
    if (corpo.pauta_id !== undefined) {
      await mudaStatusPauta(res, req.body);
    } else {
      await salvaMeta(res, req.body);
    }
    return;
  }
  if (req.method !== "GET") {
    res.status(405).json({ erro: "método não permitido" });
    return;
  }

  res.setHeader("Cache-Control", "private, max-age=60");
  const site = typeof req.query.site === "string" ? req.query.site : "";

  if (!site) {
    // Sem ?site: lista os sites conhecidos — a união do que já apareceu nas
    // tabelas, para site novo do sites.yaml surgir aqui sozinho.
    const tabelas = ["pautas", "cotacoes", "artigos", "execucoes", "metas"];
    const nomes = new Set<string>();
    await Promise.all(
      tabelas.map(async (tabela) => {
        const r = await leRadar(tabela, "select=site&limit=2000");
        for (const linha of r.dados || []) {
          const s = (linha as { site?: string }).site;
          if (s) nomes.add(s);
        }
      }),
    );
    res.status(200).json({ sites: [...nomes].sort() });
    return;
  }

  const s = `site=eq.${encodeURIComponent(site)}`;
  const status = ["nova", "aprovada", "rascunho", "publicada", "descartada"];
  const colunasPauta = "id,item_id,angulo,hub,status,titulo_sug,dado_proprio,criado_em,pontuacao,motivo_selecao,selecionada_em,horario_sugerido,itens(titulo,url,veiculo,publicado_em)";
  // Sao Paulo e' UTC-3 fixo desde 2019
  const inicioDia = `${hojeEmSaoPaulo()}T00:00:00-03:00`;
  const [execucoes, pautas, selecao, artigos, meta, ...porStatus] = await Promise.all([
    leRadar("execucoes", `${s}&order=fim.desc&limit=10`),
    leRadar("pautas", `${s}&order=criado_em.desc&limit=20&select=${colunasPauta}`),
    // o que o radar decidiu soltar hoje (radar/selecao.py marca no cron),
    // na ordem do dia: quentes primeiro, fixas pelos slots da janela
    leRadar("pautas", `${s}&status=eq.aprovada&selecionada_em=gte.${encodeURIComponent(inicioDia)}&order=horario_sugerido.asc.nullslast,pontuacao.desc&select=${colunasPauta}`),
    leRadar("artigos", `${s}&order=criado_em.desc&limit=10&select=id,titulo,tipo,status,motivo_portao,url_publicada,criado_em`),
    leRadar("metas", `${s}&limit=1`),
    ...status.map((st) => leRadar("pautas", `${s}&status=eq.${st}&select=id&limit=1`, true)),
  ]);

  const contagens: Record<string, number> = {};
  status.forEach((st, i) => {
    const total = porStatus[i].total || 0;
    if (total > 0) contagens[st] = total;
  });

  const linhaMeta = (meta.dados?.[0] ?? null) as {
    pautas_por_dia?: number;
    wp_url?: string | null;
    criterios?: unknown;
  } | null;
  const wpUrl = linhaMeta?.wp_url || null;
  const sairam = wpUrl ? await contaPostsDeHoje(wpUrl) : null;
  const selecionadas = (selecao.dados || []).length;

  res.status(200).json({
    execucoes: execucoes.dados || [],
    pautas: pautas.dados || [],
    artigos: artigos.dados || [],
    contagens,
    resumoDia: {
      pautasPorDia: linhaMeta?.pautas_por_dia ?? null,
      sairam,
      selecionadas,
      wpConfigurado: !!wpUrl,
    },
    selecaoDoDia: selecao.dados || [],
    criterios: linhaMeta?.criterios ?? null,
    avisos: [execucoes.erro && `execucoes: ${execucoes.erro}`].filter(Boolean),
  });
}
