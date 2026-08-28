// Espelho local da funcao /api/radar para desenvolvimento (o `vite dev` nao
// executa funcoes da Vercel). Roda o MESMO handler de api/radar.ts.
//
//   RADAR_SUPABASE_URL=... RADAR_SUPABASE_SERVICE_KEY=... node scripts/radar-api-dev.mjs
//
// RADAR_DEV_SEM_AUTH=1 pula a validacao de sessao (so faz sentido localmente).
// Requer Node 22.6+ (type stripping para importar o .ts direto).
import http from "node:http";
import handler from "../api/radar.ts";

const PORTA = 8788;

http
  .createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    req.query = Object.fromEntries(url.searchParams);
    res.status = (codigo) => {
      res.statusCode = codigo;
      return res;
    };
    res.json = (objeto) => {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify(objeto));
    };
    // A Vercel entrega req.body ja interpretado; aqui juntamos o corpo na mao.
    const pedacos = [];
    req.on("data", (p) => pedacos.push(p));
    req.on("end", () => {
      try {
        req.body = pedacos.length ? JSON.parse(Buffer.concat(pedacos).toString("utf8")) : undefined;
      } catch {
        req.body = undefined;
      }
      handler(req, res).catch((erro) => {
        res.statusCode = 500;
        res.end(JSON.stringify({ erro: String(erro) }));
      });
    });
  })
  .listen(PORTA, () => {
    console.log(`radar-api-dev na porta ${PORTA} (RADAR_DEV_SEM_AUTH=${process.env.RADAR_DEV_SEM_AUTH || "0"})`);
  });
