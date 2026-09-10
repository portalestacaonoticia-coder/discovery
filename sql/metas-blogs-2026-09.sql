-- Metas iniciais dos 5 blogs Tihee (setembro/2026). Rodar UMA vez no SQL
-- Editor do Supabase do RADAR (o mesmo banco de itens/pautas — nao e' o
-- Supabase do conteudo.tihee). Upsert: rodar de novo nao duplica.
--
-- pautas_por_dia = 3 como ponto de partida; ajusta-se depois na propria aba
-- Radar do conteudo.tihee (POST /api/radar). wp_url alimenta o contador
-- "ja' saiu hoje" (X-WP-Total do endpoint publico do WordPress).
-- guiadomotorista.com.br estava fora do ar (HTTP 500) em 10/09/2026 — o
-- wp_url ja' fica gravado e o contador passa a funcionar quando o site voltar.

insert into metas (site, pautas_por_dia, wp_url) values
  ('broune',          3, 'https://broune.com.br'),
  ('divadabeleza',    3, 'https://divadabeleza.com.br'),
  ('cineartcafe',     3, 'https://cineartcafe.com.br'),
  ('pescaria',        3, 'https://pescaria.co'),
  ('guiadomotorista', 3, 'https://guiadomotorista.com.br')
on conflict (site) do update
  set pautas_por_dia = excluded.pautas_por_dia,
      wp_url         = excluded.wp_url,
      atualizado_em  = now();
