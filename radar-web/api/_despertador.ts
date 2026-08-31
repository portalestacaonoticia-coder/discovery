// O despertador do radar: o cron da VERCEL (pontual, ao contrário do cron do
// GitHub em repo privado, que atrasa horas) chama estas funções nos horários
// do vercel.json, e elas dão o toque de workflow_dispatch na API do GitHub.
// O motor continua rodando no GitHub Actions com os secrets de lá — daqui sai
// só o "acorda". O underscore no nome tira este arquivo das rotas.
//
// Env (Vercel, Production): RELOGIO_GITHUB_TOKEN = PAT fine-grained com
// Actions read&write SÓ no repo discovery. CRON_SECRET (opcional, recomendado)
// tranca as rotas para além do cron da própria Vercel.

interface Pedido {
  headers: Record<string, string | string[] | undefined>;
}
interface Resposta {
  status(codigo: number): Resposta;
  json(objeto: unknown): void;
}

const REPO = "portalestacaonoticia-coder/discovery";

export async function desperta(workflow: string, req: Pedido, res: Resposta) {
  const segredo = process.env.CRON_SECRET;
  if (segredo && req.headers.authorization !== `Bearer ${segredo}`) {
    res.status(401).json({ erro: "não autorizado" });
    return;
  }
  const token = process.env.RELOGIO_GITHUB_TOKEN;
  if (!token) {
    res.status(500).json({ erro: "falta RELOGIO_GITHUB_TOKEN nas variáveis da Vercel" });
    return;
  }
  const resposta = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
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
  // 204 = o GitHub aceitou o toque; qualquer outra coisa aparece nos logs da
  // função para o diagnóstico (401 = token ruim; 404 = sem alcance no repo).
  if (resposta.status === 204) {
    res.status(200).json({ ok: true, workflow, despertado: true });
  } else {
    res.status(502).json({
      ok: false, workflow, github: resposta.status,
      detalhe: (await resposta.text()).slice(0, 300),
    });
  }
}
