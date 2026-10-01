-- Ideias por categoria (outubro/2026): o motor Discover SUGERE ideias por
-- hub a partir dos topicos pontuados; a pessoa MARCA as que quer na tela
-- Radar (ou escreve as suas). Nada e' escrito nem publicado sem marcacao.
-- Ver radar/motor.py e radar/ideias.py.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.

create table if not exists ideias (
  id          bigserial primary key,
  site        text not null,
  hub         text not null,
  origem      text not null default 'motor',   -- motor | manual
  chave       text not null,                   -- topicos.chave (motor) ou hash do titulo (manual)
  topico_id   bigint,
  titulo      text not null,                   -- a ideia como a pessoa le na tela
  motivo      text,                            -- por que o motor sugeriu (componentes)
  pontuacao   int  not null default 0,
  detalhes    jsonb,                           -- manchetes, perguntas, relacionadas (material do brief)
  status      text not null default 'sugerida',
                -- sugerida | marcada | em_producao | publicada | reprovada | descartada
  pauta_id    bigint,
  marcada_em  timestamptz,
  criado_em   timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  unique (site, hub, chave)
);
create index if not exists idx_ideias_fila on ideias (site, status, pontuacao desc);

alter table ideias enable row level security;

-- Retencao sugerida: delete from ideias where status = 'sugerida'
--   and atualizado_em < now() - interval '14 days';
