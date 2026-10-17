# Radar do doll nos Macs (IA local)

Desde 16/10/2026 o doll pode rodar nos Macs, com o modelo local (exo) no lugar
da OpenAI. Custo por post: zero. O preço é tempo: ~4 min por post no
Qwen3.8-27B em dois Macs (14,7 tok/s).

## O que muda

| Parte | Na nuvem (GitHub Actions) | No Mac |
|---|---|---|
| Texto (classificação, brief, artigo, checagem) | OpenAI | exo (`LLM_LOCAL_URL`) |
| Busca nas fontes oficiais | busca da OpenAI | SearXNG + leitura das páginas (`radar/busca_local.py`) |
| Número de fato | vem da página que a OpenAI leu | tem de estar no **texto** da página lida, conferido por código (`pesquisa._valor_lido`) |
| Imagem destacada | OpenAI/Pexels | Pexels (sem `OPENAI_API_KEY`, a IA de imagem não roda) |
| SerpAPI do motor | se houver chave | sem chave: só o RSS grátis |
| Cotação diária e textos-âncora | GitHub (não usam IA) | continuam no GitHub |
| Coleta, satélites, guias, piso | GitHub | Mac, só no modo `publicar` |

## Instalar (uma vez, no Mac mini)

1. Docker aberto e o exo com o modelo **READY**.
2. Baixar o repositório para `~/discovery` (fora de Documentos/Mesa, que o
   macOS protege do agendador).
3. `bash mac/instalar.sh` — Python 3.12, dependências, `.env`, SearXNG.
4. Preencher no `.env` (`open -e .env`): `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `WP_DOLL_USUARIO`, `WP_DOLL_SENHA`,
   `PEXELS_API_KEY`. **Não** preencher `OPENAI_API_KEY` nem `SERPAPI_KEY`.
5. Ensaio à mão: `bash mac/rodar_doll.sh` — os textos saem em `saida/ensaio/`.

## Ensaio → publicação

`RADAR_MODO=ensaio` (padrão) reescreve com o modelo local as **10 últimas
pautas já publicadas** e salva cada texto ao lado do que está no ar
(`saida/ensaio/<ref>-local.md` × `<ref>-no-ar.md`), com o veredito da checagem
e o tempo gasto (`radar/ensaio_local.py`). Só lê o banco: o GitHub continua
dono do doll, então nada interfere. É a revisão dos 10 primeiros posts.

Aprovado, a troca é feita junta, nos dois lados:

1. No Mac: `RADAR_MODO=publicar` no `.env` e `bash mac/ligar_agendamento.sh`
   (de 30 em 30 min; log em `tail -f ~/Library/Logs/radar-doll.log`).
2. No GitHub: Settings → Secrets and variables → Actions → **Variables** →
   `RADAR_IGNORA_SITES` = `doll`. Sem isso o doll sai nos dois lados.

Voltar à nuvem: apagar a variável e `bash mac/ligar_agendamento.sh desligar`.
