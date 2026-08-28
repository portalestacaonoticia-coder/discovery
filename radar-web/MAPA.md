# Mapa — radar-web (radar.tihee.com.br)

> App próprio da INTERFACE do radar. O motor (coleta, seleção, publicação)
> continua em Python no GitHub Actions; este app só LÊ e configura.
> Atualizado em: 2026-08-28

## O que é

Painel web do radar de pautas, app standalone (tirado de dentro do
conteudo.tihee para casa própria, seguindo o padrão studio.tihee /
conteudo.tihee — um subdomínio por produto). Mostra, por site: resumo do
dia, seleção automática, critérios editáveis, fila, execuções e artigos.

## Stack e como rodar

- Vite + React + TypeScript + shadcn/ui + TanStack Query + Supabase Auth.
- `npm run dev` (porta 8080) | `npm run build`. Deploy na Vercel.
- Auth: reusa o **Supabase do conteudo.tihee** (mesmas contas) — VITE_SUPABASE_*.
- Dados: a função `api/radar.ts` lê o **Supabase do radar** com service key
  (RADAR_SUPABASE_URL / RADAR_SUPABASE_SERVICE_KEY), validando a sessão antes.
- Dev local da função: `node scripts/radar-api-dev.mjs` (vite faz proxy /api).

## Estrutura

- `api/radar.ts` — função serverless: valida a sessão e lê/escreve no radar.
- `src/App.tsx` — só duas rotas: /auth (login) e / (Radar, protegida).
- `src/pages/Radar.tsx` — a tela inteira (resumo, seleção, critérios, fila...).
- `src/pages/Auth.tsx` — login (Supabase Auth do conteudo).
- `src/hooks/useRadar.ts` — fala com /api/radar. `useAuth.tsx` — sessão.
- `src/lib/radar.ts` — tipos, consultas e regras da tela.
- `src/components/ui/` — shadcn (copiado do conteudo).

## Decisões

- App próprio em vez de aba no conteudo (28/08): casa própria, config num
  lugar, autonomia. O motor Python NÃO migrou (funciona, seria caro/arriscado).
- Auth reusa o Supabase do conteudo — mesmas contas, sem criar login novo.

## Deploy (Vercel)

- Projeto **radar-tihee** (time tihee), repo discovery, Root Directory
  `radar-web`, preset Vite. Push na main = deploy.
- Env: o projeto tem os nomes do motor (SUPABASE_URL, SUPABASE_SERVICE_KEY,
  herdados do .env.example na criação) — a função aceita esses OU RADAR_*.
  Auth do front tem fallback literal (chaves públicas), dispensa VITE_*.
- Domínio: radar.tihee.com.br (CNAME `radar` → 50e25864eb4d8daf
  .vercel-dns-016.com, proxy OFF, na zona Cloudflare do tihee.com.br —
  que vive em OUTRA conta Cloudflare, não na Filipe.otavio@tihee).
- Pegadinhas que já mordi: vercel.json com BOM (PS 5.1) = "Invalid
  vercel.json"; sem Root Directory a Vercel builda o Python da raiz.

## Estado atual

- 28/08/2026: app NO AR em radar.tihee.com.br (deploy + domínio ok).
  Pendente: aposentar a aba Radar do conteudo.tihee (decisão do Filipe) e
  limpar env vars não usadas do projeto Vercel (DISCORD_WEBHOOK,
  ANTHROPIC_API_KEY, WP_DOLL_* — a função não as usa).
