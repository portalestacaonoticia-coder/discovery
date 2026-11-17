-- Tela Qwen do conteudo.tihee (novembro/2026): a ponte entre a tela na nuvem
-- e o cluster local, que so' responde na rede do Mac. Ver radar/cluster.py.
--
--   cluster_estado    o Mac escreve (agente de minuto em minuto + a rodada)
--   cluster_apps      a tela escreve: blogs/aplicacoes, prioridade, pautas
--                     por rodada, pausa; a rodada do Mac le
--   cluster_comandos  a tela enfileira; o agente executa
--
-- Rodar UMA vez no SQL Editor do Supabase do RADAR. Idempotente.

create table if not exists cluster_estado (
  no             text primary key,
  atualizado_em  timestamptz not null default now(),
  exo_no_ar      boolean not null default false,
  modelo         text,
  instancias     int not null default 0,
  runners_prontos int not null default 0,
  runners        jsonb,
  nos            jsonb,
  rodada_em_curso boolean not null default false,
  rodada_inicio  timestamptz,
  etapa          text,
  ultima_rodada_fim timestamptz,
  ultimo_teste_ok boolean,
  ultimo_teste_em timestamptz,
  falhas_seguidas int not null default 0,
  aviso          text
);
alter table cluster_estado enable row level security;

create table if not exists cluster_apps (
  id          text primary key,
  nome        text not null,
  tipo        text not null default 'blog' check (tipo in ('blog', 'aplicacao')),
  site        text,                    -- blog: a chave do site no config/sites.yaml
  descricao   text,
  prioridade  int not null default 50, -- menor roda primeiro
  por_rodada  int not null default 2 check (por_rodada between 0 and 20),
  pausado     boolean not null default false,
  criado_em   timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
alter table cluster_apps enable row level security;

create table if not exists cluster_comandos (
  id           bigserial primary key,
  comando      text not null check (comando in ('rodar_agora', 'recarregar_modelo')),
  status       text not null default 'pendente' check (status in ('pendente', 'executando', 'feito', 'falhou')),
  resultado    text,
  criado_por   text,
  criado_em    timestamptz not null default now(),
  executado_em timestamptz
);
create index if not exists idx_cluster_comandos_fila on cluster_comandos (status, criado_em);
alter table cluster_comandos enable row level security;
