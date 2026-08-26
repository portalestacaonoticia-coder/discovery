// Formatacao de data/numero do painel inteiro, sempre no fuso editorial.
const FUSO = "America/Sao_Paulo";

export function dataHora(iso) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: FUSO, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

// Datas de cotacao chegam como 'AAAA-MM-DD'; fatiar a string evita o fuso
// empurrar o dia para o anterior, que e' o erro classico com new Date(data).
export function dataCurta(isoData) {
  if (!isoData) return "—";
  const [, mes, dia] = String(isoData).split("-");
  return `${dia}/${mes}`;
}

export function dataLonga(isoData) {
  if (!isoData) return "—";
  const [ano, mes, dia] = String(isoData).split("-");
  return `${dia}/${mes}/${ano}`;
}

export function moeda(valor) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL",
    minimumFractionDigits: 4, maximumFractionDigits: 4,
  }).format(Number(valor));
}

export function pct(valor) {
  const n = Number(valor);
  return `${n > 0 ? "+" : ""}${n.toFixed(2).replace(".", ",")}%`;
}

export function tempoRelativo(iso) {
  if (!iso) return "—";
  const seg = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seg < 60) return "agora mesmo";
  const min = Math.round(seg / 60);
  if (min < 60) return `há ${min} min`;
  const horas = Math.round(min / 60);
  if (horas < 48) return `há ${horas} h`;
  return `há ${Math.round(horas / 24)} dias`;
}

export function duracao(inicio, fim) {
  if (!inicio || !fim) return "—";
  const seg = Math.max(0, Math.round((new Date(fim) - new Date(inicio)) / 1000));
  if (seg < 60) return `${seg} s`;
  return `${Math.floor(seg / 60)} min ${seg % 60} s`;
}
