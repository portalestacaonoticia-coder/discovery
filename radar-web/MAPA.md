# Mapa — radar-web (radar.tihee.com.br)

> Hoje este app é SÓ o relógio dos crons + um redirect. As telas Radar e
> Discovery vivem no conteudo.tihee (repo conteudotihee) desde 10/09/2026.
> Atualizado em: 2026-09-10

## O que é

Projeto Vercel **radar-tihee** (plano Pro — é ele quem pode ter cron de
30 min). Duas funções:

1. **Relógio**: crons da Vercel (vercel.json) que dão workflow_dispatch no
   GitHub nos horários certos (radar */30; dólar 14h16/15h20 SP úteis).
   Motivo: o cron do GitHub em repo privado atrasa horas.
2. **Redirect**: radar.tihee.com.br serve um index.html estático que manda
   para https://conteudo.tihee.com.br/radar (bookmarks antigos não quebram).

## Estrutura

- `api/tick-radar.ts` / `api/tick-dolar.ts` — o RELÓGIO. Autônomos de
  propósito: import relativo sem extensão quebra o runtime ESM da Vercel
  (FUNCTION_INVOCATION_FAILED). Env: RELOGIO_GITHUB_TOKEN (PAT fine-grained,
  Actions read&write só no discovery), CRON_SECRET opcional.
- `index.html` — o redirect (estático, sem bundle JS).
- `public/` — favicon "D" (favicon.svg) e afins.
- `vercel.json` — crons + rewrite de SPA (inofensivo agora).
- `package.json` — ainda tem as deps de UI da época do app completo; o
  build (`vite build`) só empacota o index estático. Podar é opcional.

## Histórico e decisões

- 28/08: aba Radar saiu do conteudo.tihee para app próprio aqui
  (radar.tihee.com.br), padrão um subdomínio por produto.
- 10/09: decisão do Filipe REVERTEU a separação — não fazia sentido manter
  duas telas idênticas. Radar e Discovery centralizadas no conteudotihee
  (que já tinha a aba Radar byte a byte igual e a /api/radar no ar). O
  projeto radar-tihee ficou vivo porque o relógio precisa do plano Pro.
- A tela Discovery (revisão de termos/consultas do config/sites.yaml com
  commit direto na main) nasceu aqui em 10/09 e migrou no mesmo dia para o
  conteudotihee — código em `conteudotihee/api/discovery.ts` e
  `conteudotihee/src/pages/Discovery.tsx`.

## Deploy (Vercel)

- Projeto **radar-tihee** (time tihee), repo discovery, Root Directory
  `radar-web`, preset Vite. Push na main = deploy.
- Env usadas hoje: RELOGIO_GITHUB_TOKEN (ticks), CRON_SECRET (opcional).
  RADAR_SUPABASE_*/SUPABASE_* ficaram sem uso após a migração das telas.
- Domínio: radar.tihee.com.br (CNAME `radar` → 50e25864eb4d8daf
  .vercel-dns-016.com, proxy OFF, na zona Cloudflare do tihee.com.br —
  que vive em OUTRA conta Cloudflare, não na Filipe.otavio@tihee).
- Pegadinhas que já mordi: vercel.json com BOM (PS 5.1) = "Invalid
  vercel.json"; sem Root Directory a Vercel builda o Python da raiz.
