-- Onde cada site roda (novembro/2026): 'nuvem' (GitHub Actions, OpenAI) ou
-- 'mac' (cluster local, exo). Escolhido na tela Radar do conteudo.tihee;
-- quem le e' radar/config.py:site_ativo, comparando com RADAR_AMBIENTE do
-- ambiente. Substitui a variavel RADAR_IGNORA_SITES do GitHub.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.

alter table metas add column if not exists ambiente text not null default 'nuvem';
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'metas_ambiente_valido') then
    alter table metas add constraint metas_ambiente_valido check (ambiente in ('nuvem', 'mac'));
  end if;
end $$;
