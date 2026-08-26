// Selo de status: cor + rotulo sempre juntos — cor sozinha nunca carrega o
// significado (regra de acessibilidade da skill de dataviz).
const VARIANTES = {
  ok: { classe: "selo-bom", rotulo: "✓ ok" },
  publicada: { classe: "selo-bom", rotulo: "✓ publicada" },
  aprovada: { classe: "selo-bom", rotulo: "✓ aprovada" },
  auto: { classe: "selo-bom", rotulo: "✓ auto" },
  rascunho: { classe: "selo-alerta", rotulo: "◐ rascunho" },
  erro: { classe: "selo-critico", rotulo: "✕ erro" },
  sem_cotacao: { classe: "selo-neutro", rotulo: "— sem cotação" },
  nova: { classe: "selo-info", rotulo: "● nova" },
  descartada: { classe: "selo-neutro", rotulo: "descartada" },
};

export default function Selo({ status }) {
  const v = VARIANTES[status] ?? { classe: "selo-neutro", rotulo: status };
  return <span className={`selo ${v.classe}`}>{v.rotulo}</span>;
}
