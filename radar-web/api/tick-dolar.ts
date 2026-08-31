// Cron da Vercel (vercel.json): 14h16 e 15h20 de São Paulo, dias úteis —
// desperta o workflow do artigo do dólar + guias âncora (idempotente; a
// segunda tentativa cobre boletim PTAX atrasado). AUTÔNOMO como o tick-radar:
// import relativo sem extensão quebra o runtime ESM da Vercel.

interface Pedido {
  headers: Record<string, string | string[] | undefined>;
}
interface Resposta {
  status(codigo: number): Resposta;
  json(objeto: unknown): void;
}

const REPO = "portalestacaonoticia-coder/discovery";
const WORKFLOW = "dolar.yml";

export default async function handler(req: Pedido, res: Resposta) {
  const segredo = process.env.CRON_SECRET;
  if (segredo && req.headers.authorization !== `Bearer ${segredo}`) {
    return res.status(401).json({ erro: "não autorizado" });
  }
  const token = process.env.RELOGIO_GITHUB_TOKEN;
  if (!token) {
    return res.status(500).json({ erro: "falta RELOGIO_GITHUB_TOKEN nas variáveis da Vercel" });
  }
  const resposta = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "radar-tihee-despertador",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  if (resposta.status === 204) {
    return res.status(200).json({ ok: true, workflow: WORKFLOW, despertado: true });
  }
  return res.status(502).json({
    ok: false, workflow: WORKFLOW, github: resposta.status,
    detalhe: (await resposta.text()).slice(0, 300),
  });
}
