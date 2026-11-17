-- Botao liga/desliga por site (novembro/2026). Desligado na tela Radar do
-- conteudo.tihee, o site nao coleta, nao escreve e nao publica em nenhum
-- ambiente (nuvem ou Mac) a partir da rodada seguinte. Quem le e'
-- radar/config.py:site_ligado. Meta, periodo de producao e ambiente ficam
-- como estao: religar devolve o site ao que era.
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.
-- Antes de rodar, o botao da tela nao salva e todo site conta como ligado.

alter table metas add column if not exists ligado boolean not null default true;
