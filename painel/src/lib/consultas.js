// Todas as leituras do painel. O painel so LE — quem escreve sao os crons.
import { supabase } from "./supabase";

// Sites conhecidos = uniao do que ja apareceu nas tabelas. Data-driven de
// proposito: site novo no sites.yaml aparece aqui sozinho, sem tocar no painel.
export async function sitesConhecidos() {
  const sb = supabase();
  const tabelas = ["pautas", "cotacoes", "artigos", "execucoes"];
  const nomes = new Set();
  await Promise.all(
    tabelas.map(async (tabela) => {
      const { data, error } = await sb.from(tabela).select("site").limit(2000);
      if (!error) for (const linha of data || []) if (linha.site) nomes.add(linha.site);
    }),
  );
  return [...nomes].sort();
}

export async function resumoDoSite(site) {
  const sb = supabase();
  const [pautasNovas, pautasTotal, artigos, cotacao, execucao] = await Promise.all([
    sb.from("pautas").select("id", { count: "exact", head: true }).eq("site", site).eq("status", "nova"),
    sb.from("pautas").select("id", { count: "exact", head: true }).eq("site", site),
    sb.from("artigos").select("id", { count: "exact", head: true }).eq("site", site),
    sb.from("cotacoes").select("data, ptax_venda").eq("site", site).order("data", { ascending: false }).limit(1),
    sb.from("execucoes").select("fluxo, status, fim").eq("site", site).order("fim", { ascending: false }).limit(1),
  ]);
  return {
    site,
    pautasNovas: pautasNovas.count ?? 0,
    pautasTotal: pautasTotal.count ?? 0,
    artigos: artigos.count ?? 0,
    ultimaCotacao: cotacao.data?.[0] ?? null,
    ultimaExecucao: execucao.error ? null : (execucao.data?.[0] ?? null),
  };
}

export async function filaDePautas(site, limite = 30) {
  const { data } = await supabase()
    .from("pautas")
    .select("*, itens(titulo, url, veiculo, publicado_em)")
    .eq("site", site)
    .order("criado_em", { ascending: false })
    .limit(limite);
  return data ?? [];
}

export async function contagemPorStatus(site) {
  // O PostgREST nao agrega por grupo; contamos os status conhecidos em paralelo.
  const status = ["nova", "aprovada", "rascunho", "publicada", "descartada"];
  const sb = supabase();
  const contagens = await Promise.all(
    status.map((s) =>
      sb.from("pautas").select("id", { count: "exact", head: true }).eq("site", site).eq("status", s),
    ),
  );
  return status
    .map((s, i) => ({ status: s, total: contagens[i].count ?? 0 }))
    .filter((c) => c.total > 0);
}

export async function serieCotacoes(site, dias = 30) {
  const { data } = await supabase()
    .from("cotacoes")
    .select("data, ptax_compra, ptax_venda")
    .eq("site", site)
    .eq("moeda", "USD")
    .order("data", { ascending: false })
    .limit(dias);
  return (data ?? []).reverse(); // ordem crescente de data, como o grafico espera
}

export async function listaArtigos(site, limite = 10) {
  const { data } = await supabase()
    .from("artigos")
    .select("id, tipo, hub, referencia, titulo, status, motivo_portao, url_publicada, criado_em")
    .eq("site", site)
    .order("criado_em", { ascending: false })
    .limit(limite);
  return data ?? [];
}

// Devolve null quando a tabela execucoes ainda nao existe no Supabase —
// o painel usa isso para mostrar a instrucao de rodar o schema.sql.
export async function ultimasExecucoes(site, limite = 10) {
  const { data, error } = await supabase()
    .from("execucoes")
    .select("*")
    .eq("site", site)
    .order("fim", { ascending: false })
    .limit(limite);
  if (error) return null;
  return data ?? [];
}
