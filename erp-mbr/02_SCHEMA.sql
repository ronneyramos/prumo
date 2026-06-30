-- ============================================================
-- ERP MBR — Schema completo
-- Aplicar em ordem: este arquivo, depois 03_ROLES_RLS.sql, depois 04_SEED.sql
-- ============================================================

-- ====== EXTENSÕES ======
create extension if not exists "pgcrypto";

-- ====== ENUMS ======
do $$ begin
  create type public.app_role as enum
    ('admin','engenheiro','financeiro','suprimentos','qualidade','rh','visualizador');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.obra_status as enum
    ('Planejamento','Em andamento','Paralisada','Concluída','Cancelada');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.req_status as enum
    ('Rascunho','Aprovação','Aprovada','Cotando','Comprada','Cancelada');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.pedido_status as enum
    ('Aberto','Parcial','Recebido','Cancelado');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.fin_tipo as enum ('PAGAR','RECEBER');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.fin_status as enum ('Previsto','Aprovado','Pago','Cancelado');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.nc_severidade as enum ('Baixa','Média','Alta','Crítica');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.nc_status as enum ('Aberta','Em tratamento','Verificação','Encerrada');
exception when duplicate_object then null; end $$;

-- ====== FUNÇÕES UTILITÁRIAS ======
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = public as $$
begin new.updated_at = now(); return new; end $$;

-- ============================================================
-- USUÁRIOS / ROLES (já criados em migrations anteriores, mantidos aqui para referência)
-- ============================================================
-- profiles, user_roles, has_role, handle_new_user já existem.

-- ============================================================
-- OBRAS
-- ============================================================
-- Tabela `obras` já existe. Estender com colunas que faltam:
alter table public.obras
  add column if not exists tipo text,            -- residencial, comercial, infra
  add column if not exists cnpj_cliente text,
  add column if not exists bdi numeric(6,4) default 0.25,
  add column if not exists deleted_at timestamptz;

-- ============================================================
-- ORÇAMENTO
-- ============================================================
create table if not exists public.orcamentos (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid references public.obras(id) on delete cascade,
  nome text not null,
  versao integer not null default 1,
  base_referencia text,                          -- SINAPI 11/2025, SBC, etc.
  bdi numeric(6,4) not null default 0.25,
  encargos_sociais numeric(6,4) not null default 0.80,
  total_custo numeric(14,2) not null default 0,
  total_venda numeric(14,2) not null default 0,
  status text not null default 'Rascunho',       -- Rascunho, Aprovado, Substituído
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.orcamentos to authenticated;
grant all on public.orcamentos to service_role;
alter table public.orcamentos enable row level security;
create trigger trg_orcamentos_updated before update on public.orcamentos
  for each row execute function public.set_updated_at();

create table if not exists public.insumos (
  id uuid primary key default gen_random_uuid(),
  codigo text unique not null,
  descricao text not null,
  unidade text not null,
  tipo text not null default 'Material',         -- Material, Mão de obra, Equipamento
  preco_unit numeric(14,4) not null default 0,
  fonte text,                                     -- SINAPI, Mercado, etc.
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.insumos to authenticated;
grant all on public.insumos to service_role;
alter table public.insumos enable row level security;
create trigger trg_insumos_updated before update on public.insumos
  for each row execute function public.set_updated_at();

create table if not exists public.composicoes (
  id uuid primary key default gen_random_uuid(),
  codigo text unique not null,
  descricao text not null,
  unidade text not null,
  preco_unit numeric(14,4) not null default 0,   -- recalculado por trigger
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.composicoes to authenticated;
grant all on public.composicoes to service_role;
alter table public.composicoes enable row level security;
create trigger trg_composicoes_updated before update on public.composicoes
  for each row execute function public.set_updated_at();

create table if not exists public.composicao_itens (
  id uuid primary key default gen_random_uuid(),
  composicao_id uuid not null references public.composicoes(id) on delete cascade,
  insumo_id uuid references public.insumos(id),
  sub_composicao_id uuid references public.composicoes(id),
  coeficiente numeric(14,6) not null,
  check (insumo_id is not null or sub_composicao_id is not null)
);
grant select, insert, update, delete on public.composicao_itens to authenticated;
grant all on public.composicao_itens to service_role;
alter table public.composicao_itens enable row level security;

create table if not exists public.orcamento_itens (
  id uuid primary key default gen_random_uuid(),
  orcamento_id uuid not null references public.orcamentos(id) on delete cascade,
  ordem text not null,                            -- "1.2.3" hierárquico
  descricao text not null,
  composicao_id uuid references public.composicoes(id),
  unidade text not null,
  quantidade numeric(14,4) not null default 0,
  preco_unit numeric(14,4) not null default 0,
  total numeric(14,2) generated always as (quantidade * preco_unit) stored,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.orcamento_itens to authenticated;
grant all on public.orcamento_itens to service_role;
alter table public.orcamento_itens enable row level security;
create index if not exists idx_orcitens_orc on public.orcamento_itens(orcamento_id);

-- ============================================================
-- EAP (Estrutura Analítica do Projeto)
-- ============================================================
create table if not exists public.eap_itens (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id) on delete cascade,
  parent_id uuid references public.eap_itens(id) on delete cascade,
  codigo text not null,                           -- "1.2.3"
  descricao text not null,
  unidade text,
  qtd_prevista numeric(14,4) default 0,
  valor_previsto numeric(14,2) default 0,
  peso numeric(6,4) default 0,                    -- % do total
  ordem integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (obra_id, codigo)
);
grant select, insert, update, delete on public.eap_itens to authenticated;
grant all on public.eap_itens to service_role;
alter table public.eap_itens enable row level security;
create trigger trg_eap_updated before update on public.eap_itens
  for each row execute function public.set_updated_at();
create index if not exists idx_eap_obra on public.eap_itens(obra_id);

-- ============================================================
-- MEDIÇÕES (avanço físico/financeiro)
-- ============================================================
create table if not exists public.medicoes (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id) on delete cascade,
  numero integer not null,                        -- sequencial por obra
  competencia date not null,                      -- mês de referência
  data_emissao date not null default current_date,
  status text not null default 'Rascunho',        -- Rascunho, Aprovada, Faturada
  valor_total numeric(14,2) not null default 0,
  observacoes text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (obra_id, numero)
);
grant select, insert, update, delete on public.medicoes to authenticated;
grant all on public.medicoes to service_role;
alter table public.medicoes enable row level security;
create trigger trg_medicoes_updated before update on public.medicoes
  for each row execute function public.set_updated_at();

create table if not exists public.medicao_itens (
  id uuid primary key default gen_random_uuid(),
  medicao_id uuid not null references public.medicoes(id) on delete cascade,
  eap_id uuid not null references public.eap_itens(id),
  qtd_periodo numeric(14,4) not null default 0,
  pct_periodo numeric(6,4) not null default 0,
  valor_periodo numeric(14,2) not null default 0
);
grant select, insert, update, delete on public.medicao_itens to authenticated;
grant all on public.medicao_itens to service_role;
alter table public.medicao_itens enable row level security;

-- ============================================================
-- DIÁRIO DE OBRA
-- ============================================================
create table if not exists public.diario_obra (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id) on delete cascade,
  data date not null,
  clima_manha text, clima_tarde text,
  efetivo jsonb default '[]'::jsonb,              -- [{funcao, qtd}]
  atividades text,
  ocorrencias text,
  fotos text[] default '{}',                      -- paths em storage
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  unique (obra_id, data)
);
grant select, insert, update, delete on public.diario_obra to authenticated;
grant all on public.diario_obra to service_role;
alter table public.diario_obra enable row level security;

-- ============================================================
-- SUPRIMENTOS
-- ============================================================
create table if not exists public.fornecedores (
  id uuid primary key default gen_random_uuid(),
  cnpj text unique,
  razao_social text not null,
  nome_fantasia text,
  email text, telefone text,
  endereco text,
  categoria text,                                 -- material, serviço, locação
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.fornecedores to authenticated;
grant all on public.fornecedores to service_role;
alter table public.fornecedores enable row level security;
create trigger trg_forn_updated before update on public.fornecedores
  for each row execute function public.set_updated_at();

create table if not exists public.requisicoes (
  id uuid primary key default gen_random_uuid(),
  numero text unique,                             -- REQ-2026-00001 (preenchido por trigger)
  obra_id uuid not null references public.obras(id),
  solicitante_id uuid references auth.users(id),
  data_necessidade date,
  prioridade text default 'Normal',
  status public.req_status not null default 'Rascunho',
  justificativa text,
  aprovador_id uuid references auth.users(id),
  aprovado_em timestamptz,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.requisicoes to authenticated;
grant all on public.requisicoes to service_role;
alter table public.requisicoes enable row level security;
create trigger trg_req_updated before update on public.requisicoes
  for each row execute function public.set_updated_at();

create table if not exists public.requisicao_itens (
  id uuid primary key default gen_random_uuid(),
  requisicao_id uuid not null references public.requisicoes(id) on delete cascade,
  insumo_id uuid references public.insumos(id),
  descricao text not null,
  unidade text not null,
  quantidade numeric(14,4) not null
);
grant select, insert, update, delete on public.requisicao_itens to authenticated;
grant all on public.requisicao_itens to service_role;
alter table public.requisicao_itens enable row level security;

create table if not exists public.cotacoes (
  id uuid primary key default gen_random_uuid(),
  requisicao_id uuid not null references public.requisicoes(id) on delete cascade,
  fornecedor_id uuid not null references public.fornecedores(id),
  data date not null default current_date,
  validade date,
  condicao_pagamento text,
  prazo_entrega_dias integer,
  total numeric(14,2) not null default 0,
  vencedora boolean not null default false,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.cotacoes to authenticated;
grant all on public.cotacoes to service_role;
alter table public.cotacoes enable row level security;

create table if not exists public.cotacao_itens (
  id uuid primary key default gen_random_uuid(),
  cotacao_id uuid not null references public.cotacoes(id) on delete cascade,
  requisicao_item_id uuid not null references public.requisicao_itens(id),
  preco_unit numeric(14,4) not null,
  total numeric(14,2) generated always as (preco_unit *
    (select quantidade from public.requisicao_itens ri where ri.id = requisicao_item_id)) stored
);
grant select, insert, update, delete on public.cotacao_itens to authenticated;
grant all on public.cotacao_itens to service_role;
alter table public.cotacao_itens enable row level security;

create table if not exists public.pedidos_compra (
  id uuid primary key default gen_random_uuid(),
  numero text unique,                             -- PC-2026-00001
  obra_id uuid not null references public.obras(id),
  fornecedor_id uuid not null references public.fornecedores(id),
  cotacao_id uuid references public.cotacoes(id),
  data date not null default current_date,
  previsao_entrega date,
  condicao_pagamento text,
  total numeric(14,2) not null default 0,
  status public.pedido_status not null default 'Aberto',
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.pedidos_compra to authenticated;
grant all on public.pedidos_compra to service_role;
alter table public.pedidos_compra enable row level security;
create trigger trg_ped_updated before update on public.pedidos_compra
  for each row execute function public.set_updated_at();

create table if not exists public.pedido_itens (
  id uuid primary key default gen_random_uuid(),
  pedido_id uuid not null references public.pedidos_compra(id) on delete cascade,
  insumo_id uuid references public.insumos(id),
  descricao text not null,
  unidade text not null,
  quantidade numeric(14,4) not null,
  qtd_recebida numeric(14,4) not null default 0,
  preco_unit numeric(14,4) not null,
  total numeric(14,2) generated always as (quantidade * preco_unit) stored
);
grant select, insert, update, delete on public.pedido_itens to authenticated;
grant all on public.pedido_itens to service_role;
alter table public.pedido_itens enable row level security;

create table if not exists public.recebimentos (
  id uuid primary key default gen_random_uuid(),
  pedido_id uuid not null references public.pedidos_compra(id),
  data date not null default current_date,
  nf_numero text, nf_chave text,
  nf_arquivo text,                                -- path em storage
  observacoes text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.recebimentos to authenticated;
grant all on public.recebimentos to service_role;
alter table public.recebimentos enable row level security;

create table if not exists public.recebimento_itens (
  id uuid primary key default gen_random_uuid(),
  recebimento_id uuid not null references public.recebimentos(id) on delete cascade,
  pedido_item_id uuid not null references public.pedido_itens(id),
  qtd_recebida numeric(14,4) not null
);
grant select, insert, update, delete on public.recebimento_itens to authenticated;
grant all on public.recebimento_itens to service_role;
alter table public.recebimento_itens enable row level security;

-- ====== ESTOQUE ======
create table if not exists public.estoque_movimentos (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id),
  insumo_id uuid not null references public.insumos(id),
  tipo text not null,                             -- ENTRADA, SAIDA, AJUSTE
  quantidade numeric(14,4) not null,
  custo_unit numeric(14,4),
  origem text,                                    -- recebimento_id, requisicao_id, manual
  origem_id uuid,
  data timestamptz not null default now(),
  created_by uuid references auth.users(id)
);
grant select, insert, update, delete on public.estoque_movimentos to authenticated;
grant all on public.estoque_movimentos to service_role;
alter table public.estoque_movimentos enable row level security;
create index if not exists idx_estoque_obra_insumo on public.estoque_movimentos(obra_id, insumo_id);

-- View de saldo
create or replace view public.estoque_saldo as
select
  obra_id, insumo_id,
  sum(case when tipo='ENTRADA' then quantidade
           when tipo='SAIDA'   then -quantidade
           when tipo='AJUSTE'  then quantidade end) as saldo,
  sum(case when tipo='ENTRADA' then quantidade*coalesce(custo_unit,0) else 0 end)
    / nullif(sum(case when tipo='ENTRADA' then quantidade else 0 end),0) as custo_medio
from public.estoque_movimentos
group by obra_id, insumo_id;

-- ============================================================
-- FINANCEIRO
-- ============================================================
create table if not exists public.plano_contas (
  id uuid primary key default gen_random_uuid(),
  codigo text unique not null,                    -- 1.1.01
  nome text not null,
  tipo text not null,                             -- RECEITA, DESPESA
  parent_id uuid references public.plano_contas(id),
  ativo boolean not null default true
);
grant select, insert, update, delete on public.plano_contas to authenticated;
grant all on public.plano_contas to service_role;
alter table public.plano_contas enable row level security;

create table if not exists public.centros_custo (
  id uuid primary key default gen_random_uuid(),
  codigo text unique not null,
  nome text not null,
  obra_id uuid references public.obras(id),       -- opcional: CC vinculado a obra
  ativo boolean not null default true
);
grant select, insert, update, delete on public.centros_custo to authenticated;
grant all on public.centros_custo to service_role;
alter table public.centros_custo enable row level security;

create table if not exists public.contas_bancarias (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  banco text, agencia text, conta text,
  saldo_inicial numeric(14,2) not null default 0,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.contas_bancarias to authenticated;
grant all on public.contas_bancarias to service_role;
alter table public.contas_bancarias enable row level security;

create table if not exists public.lancamentos (
  id uuid primary key default gen_random_uuid(),
  tipo public.fin_tipo not null,
  status public.fin_status not null default 'Previsto',
  obra_id uuid references public.obras(id),
  centro_custo_id uuid references public.centros_custo(id),
  plano_conta_id uuid references public.plano_contas(id),
  fornecedor_id uuid references public.fornecedores(id),    -- p/ PAGAR
  cliente_nome text,                                         -- p/ RECEBER (cliente vem da obra)
  descricao text not null,
  valor numeric(14,2) not null,
  data_emissao date not null default current_date,
  data_vencimento date not null,
  data_pagamento date,
  conta_bancaria_id uuid references public.contas_bancarias(id),
  documento text,                                            -- número NF, boleto
  arquivo text,                                              -- path storage
  origem text,                                               -- 'medicao', 'pedido', 'folha', 'manual'
  origem_id uuid,
  parcela_num integer, parcela_total integer,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.lancamentos to authenticated;
grant all on public.lancamentos to service_role;
alter table public.lancamentos enable row level security;
create trigger trg_lanc_updated before update on public.lancamentos
  for each row execute function public.set_updated_at();
create index if not exists idx_lanc_venc on public.lancamentos(data_vencimento);
create index if not exists idx_lanc_obra on public.lancamentos(obra_id);

-- ============================================================
-- PESSOAL / RH
-- ============================================================
create table if not exists public.colaboradores (
  id uuid primary key default gen_random_uuid(),
  cpf text unique,
  nome text not null,
  funcao text,
  matricula text unique,
  admissao date, demissao date,
  salario numeric(14,2),
  tipo_contrato text default 'CLT',               -- CLT, PJ, Diarista
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.colaboradores to authenticated;
grant all on public.colaboradores to service_role;
alter table public.colaboradores enable row level security;
create trigger trg_col_updated before update on public.colaboradores
  for each row execute function public.set_updated_at();

create table if not exists public.alocacoes (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references public.colaboradores(id),
  obra_id uuid not null references public.obras(id),
  data_inicio date not null,
  data_fim date,
  funcao_obra text
);
grant select, insert, update, delete on public.alocacoes to authenticated;
grant all on public.alocacoes to service_role;
alter table public.alocacoes enable row level security;

create table if not exists public.ponto (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references public.colaboradores(id),
  obra_id uuid references public.obras(id),
  data date not null,
  entrada time, saida_almoco time, retorno_almoco time, saida time,
  horas_normais numeric(5,2), horas_extras numeric(5,2),
  falta boolean default false,
  observacao text,
  unique (colaborador_id, data)
);
grant select, insert, update, delete on public.ponto to authenticated;
grant all on public.ponto to service_role;
alter table public.ponto enable row level security;

create table if not exists public.folha_pagamento (
  id uuid primary key default gen_random_uuid(),
  competencia date not null,                      -- primeiro dia do mês
  colaborador_id uuid not null references public.colaboradores(id),
  obra_id uuid references public.obras(id),
  proventos numeric(14,2) not null default 0,
  descontos numeric(14,2) not null default 0,
  liquido numeric(14,2) generated always as (proventos - descontos) stored,
  status text default 'Aberta',                   -- Aberta, Fechada, Paga
  detalhes jsonb,                                 -- rubricas
  created_at timestamptz not null default now(),
  unique (competencia, colaborador_id)
);
grant select, insert, update, delete on public.folha_pagamento to authenticated;
grant all on public.folha_pagamento to service_role;
alter table public.folha_pagamento enable row level security;

-- ============================================================
-- QUALIDADE
-- ============================================================
create table if not exists public.checklists_modelo (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  servico text,                                    -- ex: Alvenaria, Concretagem
  itens jsonb not null default '[]'::jsonb,        -- [{ordem, descricao, criterio}]
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.checklists_modelo to authenticated;
grant all on public.checklists_modelo to service_role;
alter table public.checklists_modelo enable row level security;

create table if not exists public.inspecoes (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id),
  modelo_id uuid references public.checklists_modelo(id),
  eap_id uuid references public.eap_itens(id),
  data date not null default current_date,
  responsavel_id uuid references auth.users(id),
  resultado text,                                  -- Aprovado, Reprovado, Aprovado c/ ressalva
  respostas jsonb,                                 -- [{item_id, ok, obs, foto}]
  fotos text[] default '{}',
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.inspecoes to authenticated;
grant all on public.inspecoes to service_role;
alter table public.inspecoes enable row level security;

create table if not exists public.nao_conformidades (
  id uuid primary key default gen_random_uuid(),
  numero text unique,                              -- NC-2026-00001
  obra_id uuid not null references public.obras(id),
  inspecao_id uuid references public.inspecoes(id),
  titulo text not null,
  descricao text,
  severidade public.nc_severidade not null default 'Média',
  status public.nc_status not null default 'Aberta',
  responsavel_id uuid references auth.users(id),
  prazo date,
  acao_corretiva text,
  acao_preventiva text,
  encerrada_em timestamptz,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.nao_conformidades to authenticated;
grant all on public.nao_conformidades to service_role;
alter table public.nao_conformidades enable row level security;
create trigger trg_nc_updated before update on public.nao_conformidades
  for each row execute function public.set_updated_at();

create table if not exists public.ensaios (
  id uuid primary key default gen_random_uuid(),
  obra_id uuid not null references public.obras(id),
  tipo text not null,                              -- Slump, Compressão, Granulometria
  data date not null,
  amostra text,
  resultado jsonb,
  laudo_arquivo text,
  conforme boolean,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.ensaios to authenticated;
grant all on public.ensaios to service_role;
alter table public.ensaios enable row level security;

-- ============================================================
-- SEQUÊNCIAS DE NUMERAÇÃO
-- ============================================================
create sequence if not exists public.seq_requisicao;
create sequence if not exists public.seq_pedido;
create sequence if not exists public.seq_nc;

create or replace function public.gen_numero(prefix text, seqname text)
returns text language sql as $$
  select prefix || '-' || to_char(now(),'YYYY') || '-' ||
         lpad(nextval(seqname)::text, 5, '0');
$$;

create or replace function public.trg_requisicao_numero()
returns trigger language plpgsql as $$
begin
  if new.numero is null then
    new.numero := public.gen_numero('REQ','public.seq_requisicao');
  end if;
  return new;
end $$;
drop trigger if exists trg_req_num on public.requisicoes;
create trigger trg_req_num before insert on public.requisicoes
  for each row execute function public.trg_requisicao_numero();

create or replace function public.trg_pedido_numero()
returns trigger language plpgsql as $$
begin
  if new.numero is null then
    new.numero := public.gen_numero('PC','public.seq_pedido');
  end if;
  return new;
end $$;
drop trigger if exists trg_ped_num on public.pedidos_compra;
create trigger trg_ped_num before insert on public.pedidos_compra
  for each row execute function public.trg_pedido_numero();

create or replace function public.trg_nc_numero()
returns trigger language plpgsql as $$
begin
  if new.numero is null then
    new.numero := public.gen_numero('NC','public.seq_nc');
  end if;
  return new;
end $$;
drop trigger if exists trg_nc_num on public.nao_conformidades;
create trigger trg_nc_num before insert on public.nao_conformidades
  for each row execute function public.trg_nc_numero();
