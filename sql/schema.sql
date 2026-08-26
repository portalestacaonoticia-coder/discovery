-- Radar de noticias — esquema Supabase.
-- RLS ligado em tudo desde o dia 1: o radar escreve com service_role (fora do navegador),
-- entao nenhuma policy publica e' necessaria. Sem RLS, a chave anon leria tudo.

create table if not exists fontes (
  id          bigserial primary key,
  site        text not null,
  tipo        text not null,                 -- rss | google_news | sitemap_news
  referencia  text not null,                 -- url do feed ou consulta do google news
  ativo       boolean not null default true,
  criado_em   timestamptz not null default now(),
  unique (site, tipo, referencia)
);

create table if not exists itens (
  id            bigserial primary key,
  site          text not null,
  titulo        text not null,
  url           text not null,
  url_canonica  text not null,
  hash_dedup    text not null,               -- titulo normalizado + dia: mata a mesma noticia em 10 portais
  veiculo       text,
  resumo        text,                        -- so' o resumo do feed. Nunca o texto integral do outro site.
  publicado_em  timestamptz,
  coletado_em   timestamptz not null default now(),
  unique (site, hash_dedup)
);
create index if not exists idx_itens_site_data on itens (site, publicado_em desc);

create table if not exists pautas (
  id           bigserial primary key,
  item_id      bigint references itens(id) on delete cascade,
  site         text not null,
  hub          text,                         -- id do hub em config/sites.yaml
  tipo         text not null default 'radar',-- radar | calendario
  angulo       text not null,                -- id da taxonomia (ver radar/angulos.py)
  titulo_sug   text,
  dado_proprio text,                         -- o numero vindo da base propria; e' o que justifica o artigo
  prioridade   int not null default 0,
  status       text not null default 'nova', -- nova | aprovada | descartada | rascunho | publicada
  criado_em    timestamptz not null default now()
);
create index if not exists idx_pautas_status on pautas (site, status, prioridade desc);

-- ---------------------------------------------------------------------------
-- Bases proprias: o diferencial defensavel de cada site.
-- Sem elas o radar so' sabe reescrever o que os outros publicaram.
-- ---------------------------------------------------------------------------

-- ferrugem: historico de shows. Origem do angulo "ja tocou N vezes na cidade".
create table if not exists eventos (
  id         bigserial primary key,
  site       text not null,
  data       date not null,
  cidade     text not null,
  uf         text,
  local      text,
  turne      text,
  fonte      text not null,                  -- URL oficial de onde o dado saiu
  criado_em  timestamptz not null default now(),
  unique (site, data, cidade, local)
);
create index if not exists idx_eventos_cidade on eventos (site, lower(cidade));

-- doll: serie historica de cotacao. Origem dos angulos de variacao e recorde.
create table if not exists cotacoes (
  id          bigserial primary key,
  site        text not null,
  data        date not null,
  moeda       text not null default 'USD',
  ptax_compra numeric(10,4),
  ptax_venda  numeric(10,4),
  fonte       text not null,
  unique (site, data, moeda)
);

-- Artigos gerados (calendario) e rascunhos aguardando revisao.
create table if not exists artigos (
  id            bigserial primary key,
  site          text not null,
  tipo          text not null,               -- calendario | radar
  hub           text,
  referencia    text not null,               -- chave do fato (ex.: data da cotacao)
  titulo        text not null,
  resumo        text,
  corpo_md      text not null,
  jsonld        text,
  status        text not null default 'rascunho',  -- rascunho | publicada
  motivo_portao text,                        -- por que passou (ou nao) no portao
  url_publicada text,
  wp_post_id    bigint,
  criado_em     timestamptz not null default now(),
  unique (site, tipo, referencia)
);
create index if not exists idx_artigos_status on artigos (site, status, criado_em desc);

-- Meta editorial por site: quantas pautas o site quer soltar por dia e onde
-- fica o WordPress para contar o que ja saiu. Editada pela aba Radar do
-- conteudo.tihee; os crons nao escrevem aqui.
create table if not exists metas (
  site            text primary key,
  pautas_por_dia  int not null default 5,
  wp_url          text,
  criterios       jsonb,                 -- pesos da selecao automatica (ver radar/pontua.py)
  atualizado_em   timestamptz not null default now()
);

-- Colunas da selecao automatica (radar/selecao.py preenche; a aba exibe).
-- Em bases criadas antes delas, os alter abaixo completam o schema.
alter table metas  add column if not exists criterios jsonb;
alter table pautas add column if not exists pontuacao int;
alter table pautas add column if not exists motivo_selecao text;
alter table pautas add column if not exists selecionada_em timestamptz;
alter table pautas add column if not exists horario_sugerido timestamptz;  -- quente = ja; fixa = slot na janela
create index if not exists idx_pautas_selecao on pautas (site, selecionada_em desc);

-- Registro de execucao dos crons. E' o que o painel le para responder
-- "rodou? quando? deu certo?" sem precisar abrir o GitHub Actions.
create table if not exists execucoes (
  id      bigserial primary key,
  fluxo   text not null,                -- radar | dolar
  site    text,
  status  text not null,                -- ok | sem_cotacao | erro
  resumo  text,                         -- "3 itens, 5 pautas" ou a mensagem de erro
  inicio  timestamptz not null,
  fim     timestamptz not null default now()
);
create index if not exists idx_execucoes_fluxo on execucoes (fluxo, fim desc);

alter table artigos   enable row level security;
alter table fontes    enable row level security;
alter table itens     enable row level security;
alter table pautas    enable row level security;
alter table eventos   enable row level security;
alter table cotacoes  enable row level security;
alter table execucoes enable row level security;
alter table metas     enable row level security;
