-- Origem da imagem destacada (outubro/2026): a URL da foto no acervo
-- (pagina do Pexels/Openverse). O nome do arquivo no WP vem do titulo do
-- post, entao sem esta coluna o banco nao sabia QUAL foto foi usada — e a
-- busca devolvia sempre a primeira da consulta do hub: tres posts seguidos
-- com a mesma foto (doll, 25/09). Ver radar/imagens.py busca(evitar=...).
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.

alter table artigos add column if not exists imagem_origem text;
comment on column artigos.imagem_origem is
  'URL da foto no acervo de origem; a proxima busca do site evita repeti-la';
