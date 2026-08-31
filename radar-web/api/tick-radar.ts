// Cron da Vercel (vercel.json): a cada 30 min, todos os dias — desperta o
// workflow do radar (coleta, seleção, satélites e piso).
import { desperta } from "./_despertador";

export default function handler(req: never, res: never) {
  return desperta("radar.yml", req, res);
}
