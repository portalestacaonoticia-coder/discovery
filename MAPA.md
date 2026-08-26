# MAPA — Radar de pautas

Radar multi-site de noticias: coleta, deduplica, classifica e gera fila de
pautas com angulo e dado proprio. Python + Supabase + GitHub Actions.

```
radar/
├── config/sites.yaml       ← TODA a configuracao de negocio: sites, hubs, fontes,
│                             moldes de titulo e permissao de publicacao automatica.
│                             Site novo se adiciona aqui, sem tocar em codigo.
├── sql/schema.sql          ← tabelas Supabase (itens, pautas, fontes, execucoes) +
│                             bases proprias por site (eventos, cotacoes). RLS ligado.
├── radar/
│   ├── config.py           ← le sites.yaml e .env
│   ├── fontes.py           ← coletores: rss, google_news, sitemap_news.
│   │                         So' titulo/URL/data/resumo — nunca texto integral alheio.
│   ├── normaliza.py        ← titulo normalizado, URL canonica e hash de dedup.
│   │                         E' o que impede a mesma noticia virar 10 pautas.
│   ├── banco.py            ← UNICO ponto de acesso ao Supabase (+ modo seco) e
│   │                         as consultas das bases proprias.
│   ├── angulos.py          ← taxonomia de angulos: o gerador de variacoes do
│   │                         mesmo fato. 'exige_dado' marca quem precisa da base.
│   ├── classifica.py       ← relevancia + hub + montagem dos titulos sugeridos.
│   │                         Usa LLM se houver chave; senao, palavra-chave.
│   ├── ptax.py             ← cliente da API PTAX do Banco Central (fonte primaria
│   │                         do doll). Trata dia sem cotacao e o formato ambiguo
│   │                         de data da Olinda.
│   ├── gerador_dolar.py    ← monta o artigo diario de cotacao a partir da serie.
│   │                         NAO explica causa: so' escreve o que e' derivavel do dado.
│   ├── dolar_diario.py     ← entrypoint da pauta de calendario do dolar:
│   │                         coleta -> base -> portoes -> artigo -> saida/ + banco
│   ├── configurar_wp.py    ← configuracao inicial de um WP novo (titulo, fuso,
│   │                         limpeza dos exemplos, plugins). Uma vez por site.
│   ├── publicador_wp.py    ← publica no WordPress pela REST API (senha de
│   │                         aplicativo). Idempotente: reroda = atualiza o post.
│   ├── alerta.py           ← webhook do Discord (silencioso se nao configurado)
│   └── principal.py        ← orquestra tudo; e' o entrypoint (`python -m radar.principal`)
├── painel/                 ← painel web (Next.js) de acompanhamento: fila de pautas,
│   │                         cotacoes com grafico, artigos e execucoes dos crons.
│   │                         Le o Supabase SO no servidor (service key; RLS trancado)
│   │                         e protege o acesso com senha unica (PAINEL_SENHA).
│   └── src/
│       ├── lib/supabase.js     ← UNICO ponto de acesso ao banco (espelho do banco.py)
│       ├── lib/consultas.js    ← todas as leituras do painel
│       ├── features/           ← pautas, cotacoes (grafico SVG), artigos, execucoes
│       ├── components/Selo.js  ← selo de status (cor sempre com rotulo)
│       ├── app/                ← / (visao geral por site) e /[site] (detalhe)
│       └── middleware.js       ← Basic Auth com PAINEL_SENHA
├── testar_local.py         ← teste offline do radar, com noticias simuladas
├── testar_dolar.py         ← teste offline do gerador de cotacao, com serie simulada
├── wordpress/radar-jsonld.php  ← mu-plugin: imprime o JSON-LD no <head> e ajusta
│                             max-snippet/max-image-preview
├── saida/                  ← artigos gerados (.md + .jsonld), prontos para o CMS
└── .github/workflows/
    ├── radar.yml           ← cron do radar, de 30 em 30 min
    ├── configurar-wp.yml   ← manual: braco remoto do configurar_wp
    └── dolar.yml           ← cron do artigo de cotacao, dias uteis 14h10 (Brasilia)
```

## Onde mexer

- **Adicionar site** → `config/sites.yaml`
- **Novo tipo de fonte** → `radar/fontes.py` (funcao `coleta`)
- **Novo angulo de pauta** → `radar/angulos.py`
- **Nova base propria** → tabela em `sql/schema.sql` + consulta em `radar/banco.py`
  + ramo em `principal.dado_proprio`
- **Publicacao no CMS** → ainda nao existe. Entra como `radar/publicador.py`,
  lendo `pautas` com status `aprovada`.
- **Painel** → `painel/src/features/<area>` para uma secao nova;
  `painel/src/lib/consultas.js` para uma leitura nova do banco.
