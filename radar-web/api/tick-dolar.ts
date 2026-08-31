// Cron da Vercel (vercel.json): 14h16 e 15h20 de São Paulo, dias úteis —
// desperta o workflow do artigo do dólar + guias âncora (idempotente; a
// segunda tentativa cobre boletim PTAX atrasado).
import { desperta } from "./_despertador";

export default function handler(req: never, res: never) {
  return desperta("dolar.yml", req, res);
}
