-- Motor Discover (outubro/2026): sinais de interesse, topicos com DiscoverScore,
-- brief editorial por pauta, checagem por artigo e plano de producao por site.
-- Ver radar/motor.py e a secao "Motor Discover" do README.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.
-- `python -m radar.verifica_schema` diz se falta algo daqui.

-- 1. Coletas: quando cada fonte de sinal foi consultada pela ultima vez, por
--    hub e consulta. E' o TTL que segura o custo: o workflow roda a cada 30
--    min, mas SerpAPI/Trends so' sao chamadas quando a coleta anterior venceu.
create table if not exists coletas (
  id           bigserial primary key,
  site         text not null,
  hub          text not null,
  fonte        text not null,           -- google_news_rss | serp | trends | reddit | youtube | tiktok
  consulta     text not null,
  itens        int  not null default 0,
  coletado_em  timestamptz not null default now()
);
create index if not exists idx_coletas_ttl on coletas (site, hub, fonte, consulta, coletado_em desc);

-- 2. Sinais: o que cada fonte devolveu, ja' normalizado. Um sinal e' uma
--    manchete, um resultado organico, uma pergunta (PAA), uma busca
--    relacionada, uma query em alta no Trends ou um post social.
create table if not exists sinais (
  id           bigserial primary key,
  site         text not null,
  hub          text not null,
  fonte        text not null,
  tipo         text not null,           -- noticia | organico | paa | relacionada | trend_rising | trend_top | social
  texto        text not null,
  url          text,
  veiculo      text,
  valor        numeric,                 -- trends: alta em %; social: upvotes/views
  extra        jsonb,
  publicado_em timestamptz,
  dia          date not null,
  hash_dedup   text not null,
  coletado_em  timestamptz not null default now(),
  unique (site, hub, fonte, dia, hash_dedup)
);
create index if not exists idx_sinais_hub_dia on sinais (site, hub, dia desc);

-- 3. Topicos: os sinais agrupados por assunto, com os componentes do
--    DiscoverScore e a nota final. Uma linha por (site, hub, chave, dia).
create table if not exists topicos (
  id             bigserial primary key,
  site           text not null,
  hub            text not null,
  chave          text not null,
  rotulo         text not null,
  termos         jsonb,
  sinais         jsonb,                 -- {total, por_tipo, veiculos_7d, veiculos_30d, ...}
  componentes    jsonb,                 -- {velocidade_tendencia: 0.9, frescor: 1.0, ...}
  pontuacao      int  not null default 0,
  motivo         text,
  primeiro_visto timestamptz,
  ultimo_visto   timestamptz,
  dia            date not null,
  status         text not null default 'novo',   -- novo | pautado | ignorado
  pauta_id       bigint,
  criado_em      timestamptz not null default now(),
  unique (site, hub, chave, dia)
);
create index if not exists idx_topicos_dia on topicos (site, dia desc, pontuacao desc);

-- 4. Pauta ganha o topico de origem, o brief editorial e as evidencias
--    (Etapa 2). Artigo ganha o relatorio da checagem (Etapa 3).
alter table pautas  add column if not exists topico_id  bigint;
alter table pautas  add column if not exists brief      jsonb;
alter table pautas  add column if not exists evidencias jsonb;
alter table artigos add column if not exists checagem   jsonb;

-- 5. Plano de producao por site: quantas pautas por dia (coluna que ja'
--    existe) e POR QUANTO TEMPO. Fora do periodo o site nao gasta SerpAPI
--    nem modelo e nao publica. Sem as duas datas, site com motor: discover
--    nao produz — producao e' sempre uma decisao explicita com prazo.
alter table metas add column if not exists producao_inicio date;
alter table metas add column if not exists producao_fim    date;
comment on column metas.producao_inicio is 'primeiro dia (SP) em que o motor discover produz';
comment on column metas.producao_fim    is 'ultimo dia (SP) em que o motor discover produz; depois para';

alter table coletas enable row level security;
alter table sinais  enable row level security;
alter table topicos enable row level security;

-- Retencao sugerida (rodar de vez em quando):
--   delete from sinais  where dia < current_date - 30;
--   delete from coletas where coletado_em < now() - interval '30 days';
--   delete from topicos where dia < current_date - 90 and status <> 'pautado';
