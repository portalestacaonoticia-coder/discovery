-- Descarte registrado (setembro/2026): o item que o classificador julgou
-- irrelevante passa a ficar em `itens` com relevante=false, so' para o hash
-- existir. No ciclo seguinte `item_existe` o pula e o Claude nao le a mesma
-- manchete de novo. Sem isto, a mesma noticia irrelevante voltava do Google
-- News e era reclassificada a cada 30 min. Ver radar/banco.py grava_descarte.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.
-- Ate rodar, o radar avisa e segue como antes (sem gravar o descarte).

alter table itens add column if not exists relevante boolean not null default true;

comment on column itens.relevante is
  'false = descartado pelo classificador; fica so para dedup, nao gera pauta';

-- As consultas de pauta fazem join em itens pelo item_id, entao o descarte
-- nunca aparece no painel. Indice parcial para a limpeza periodica, se
-- quiser: delete from itens where not relevante and coletado_em < now() - interval '30 days';
create index if not exists idx_itens_descartados on itens (site, coletado_em) where not relevante;
