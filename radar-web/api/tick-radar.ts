// Cron da Vercel (vercel.json): a cada 30 min, todos os dias — desperta o
// workflow do radar (coleta, seleção, satélites e piso) via workflow_dispatch.
// O motor continua no GitHub Actions com os secrets de lá; daqui sai só o
// "acorda". AUTÔNOMO de propósito: import relativo sem extensão quebra o
// runtime ESM da Vercel (FUNCTION_INVOCATION_FAILED — mesma lição do runner
// local), então nada de módulo compartilhado aqui.
//
// Env (Vercel): RELOGIO_GITHUB_TOKEN (PAT fine-grained, Actions read&write só
// no discovery); CRON_SECRET opcional tranca a rota para além do cron.

interface Pedido {
  headers: Record<string, string | string[] | undefined>;
}
interface Resposta {
  status(codigo: number): Resposta;
  json(objeto: unknown): void;
}

const REPO = "portalestacaonoticia-coder/discovery";
const WORKFLOW = "radar.yml";

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
