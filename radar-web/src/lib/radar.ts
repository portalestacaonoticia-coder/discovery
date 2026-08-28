// Tipos, leitura e formatação da aba Radar (dados do radar de pautas, via
// /api/radar — a service key fica na função serverless, nunca aqui).

export interface RadarExecucao {
  id: number;
  fluxo: string;
  site: string | null;
  status: string;
  resumo: string | null;
  inicio: string;
  fim: string;
}

export interface RadarPauta {
  id: number;
  item_id: number | null;
  angulo: string;
  hub: string | null;
  status: string;
  titulo_sug: string | null;
  dado_proprio: string | null;
  criado_em: string;
  pontuacao: number | null;
  motivo_selecao: string | null;
  selecionada_em: string | null;
  horario_sugerido: string | null;
  itens: { titulo: string; url: string; veiculo: string | null; publicado_em?: string | null } | null;
}

export interface RadarCriterios {
  dado_proprio?: number;
  minimo?: number;
  quente_ate_horas?: number;
  angulos?: Record<string, number>;
  frescor?: Record<string, number>;
  janela?: Record<string, number>;
}

export interface RadarArtigo {
  id: number;
  titulo: string;
  tipo: string;
  status: string;
  motivo_portao: string | null;
  url_publicada: string | null;
  criado_em: string;
}

export interface RadarResumoDia {
  pautasPorDia: number | null;
  sairam: number | null; // posts publicados hoje no WP do site; null sem WP
  selecionadas: number; // pautas que o radar aprovou sozinho hoje
  wpConfigurado: boolean;
}

export interface RadarDoSite {
  execucoes: RadarExecucao[];
  pautas: RadarPauta[];
  artigos: RadarArtigo[];
  contagens: Record<string, number>;
  resumoDia: RadarResumoDia;
  selecaoDoDia: RadarPauta[];
  criterios: RadarCriterios | null;
  avisos: string[];
}

export async function consultaRadar<T>(caminho: string, token: string): Promise<T> {
  const resposta = await fetch(`/api/radar${caminho}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    throw new Error((corpo as { erro?: string }).erro || `HTTP ${resposta.status}`);
  }
  return corpo as T;
}

export interface RadarConfig {
  pautasPorDia?: number;
  criterios?: RadarCriterios;
}

export async function salvaConfigRadar(site: string, config: RadarConfig, token: string): Promise<void> {
  const resposta = await fetch("/api/radar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      site,
      ...(config.pautasPorDia !== undefined ? { pautas_por_dia: config.pautasPorDia } : {}),
      ...(config.criterios !== undefined ? { criterios: config.criterios } : {}),
    }),
  });
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error((corpo as { erro?: string }).erro || `HTTP ${resposta.status}`);
  }
}

export type StatusTriagem = "aprovada" | "descartada" | "nova";

export async function mudaStatusPautaRadar(pautaId: number, status: StatusTriagem, token: string): Promise<void> {
  const resposta = await fetch("/api/radar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ pauta_id: pautaId, status }),
  });
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error((corpo as { erro?: string }).erro || `HTTP ${resposta.status}`);
  }
}

// -- regras e formatação (puras, testáveis) ---------------------------------

const FUSO = "America/Sao_Paulo";

/** Quantas ainda vão sair hoje: meta - saíram, nunca negativo. */
export function restanteDoDia(meta: number | null, sairam: number | null): number | null {
  if (meta === null || sairam === null) return null;
  return Math.max(0, meta - sairam);
}

/** Timestamp ISO -> 'HH:mm' no fuso editorial (horário sugerido do dia). */
export function horaRadar(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: FUSO,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/** Timestamp ISO -> 'DD/MM HH:mm' no fuso editorial. */
export function quandoRadar(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: FUSO,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function duracaoRadar(inicio: string | null, fim: string | null): string {
  if (!inicio || !fim) return "—";
  const seg = Math.max(0, Math.round((new Date(fim).getTime() - new Date(inicio).getTime()) / 1000));
  if (seg < 60) return `${seg} s`;
  return `${Math.floor(seg / 60)} min ${seg % 60} s`;
}
