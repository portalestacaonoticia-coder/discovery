-- Imagem destacada nos artigos (setembro/2026) — o que destrava o Google
-- Discover: sem imagem >= 1200px declarada em og:image/schema.org, o card
-- praticamente nao aparece. Ver radar/imagens.py.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.

alter table artigos add column if not exists wp_media_id    bigint;
alter table artigos add column if not exists imagem_url     text;
alter table artigos add column if not exists imagem_credito text;

comment on column artigos.wp_media_id is
  'id da midia no WordPress; reaproveitado na rerodada para nao duplicar a biblioteca';
comment on column artigos.imagem_url is
  'URL da imagem destacada ja hospedada no proprio dominio (vira og:image)';
comment on column artigos.imagem_credito is
  'credito do acervo (autor / fonte / licenca) — obrigatorio nas imagens CC do Openverse';
