-- ============================================================
-- ERP MBR — Schema completo para projeto NOVO no Supabase
-- Cole TODO este conteúdo no SQL Editor e execute de uma vez.
-- ============================================================

-- ====== EXTENSÕES ======
create extension if not exists "pgcrypto";

-- ====== ENUMS ======
do $$ begin
  create type public.app_role as enum
    ('admin','engenheiro','financeiro','suprimentos','qualidade','rh','visualizador');
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
  create type public.nc_severidade as enum ('Baixa','Média','Alta','Crítica');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.nc_status as enum ('Aberta','Em tratamento','Verificação','Encerrada');
exception when duplicate_object then null; end $$;

-- ====== FUNÇÃO updated_at ======
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = public as $$
begin new.updated_at = now(); return new; end $$;

-- ============================================================
-- PERFIS E CONTROLE DE ACESSO
-- ============================================================
create table if not exists public.profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  nome       text,
  email      text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
drop policy if exists p_prof_own on public.profiles;
create policy p_prof_own on public.profiles for all to authenticated
  using (auth.uid() = id) with check (auth.uid() = id);
create trigger trg_profiles_updated before update on public.profiles
  for each row execute function public.set_updated_at();

-- Cria perfil automaticamente ao cadastrar usuário
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles(id, nome, email)
  values (new.id,
          coalesce(new.raw_user_meta_data->>'full_name', new.email),
          new.email)
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Roles por usuário
create table if not exists public.user_roles (
  id      uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role    public.app_role not null,
  unique (user_id, role)
);
alter table public.user_roles enable row level security;

-- Função has_role (criada antes das policies que dependem dela)
create or replace function public.has_role(uid uuid, r public.app_role)
returns boolean language sql security definer stable set search_path = public as $$
  select exists (
    select 1 from public.user_roles where user_id = uid and role = r
  );
$$;

drop policy if exists p_roles_read on public.user_roles;
create policy p_roles_read on public.user_roles for select to authenticated using (true);
drop policy if exists p_roles_admin on public.user_roles;
create policy p_roles_admin on public.user_roles for all to authenticated
  using (public.has_role(auth.uid(), 'admin'))
  with check (public.has_role(auth.uid(), 'admin'));

-- ============================================================
-- OBRAS
-- ============================================================
create table if not exists public.obras (
  id             uuid primary key default gen_random_uuid(),
  nome           text not null,
  tipo           text,
  cliente        text,
  cnpj_cliente   text,
  endereco       text,
  responsavel    text,
  valor_contrato numeric(14,2) not null default 0,
  bdi            numeric(6,4) not null default 0.25,
  data_inicio    date,
  data_termino   date,
  pct_fisico     numeric(5,2) not null default 0,
  status         text not null default 'Planejamento',
  deleted_at     timestamptz,
  created_by     uuid references auth.users(id),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
grant select, insert, update, delete on public.obras to authenticated;
grant all on public.obras to service_role;
alter table public.obras enable row level security;
create trigger trg_obras_updated before update on public.obras
  for each row execute function public.set_updated_at();

drop policy if exists p_obras_read on public.obras;
create policy p_obras_read on public.obras for select to authenticated using (deleted_at is null);
drop policy if exists p_obras_write on public.obras;
create policy p_obras_write on public.obras for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ============================================================
-- ORÇAMENTO
-- ============================================================
create table if not exists public.orcamentos (
  id               uuid primary key default gen_random_uuid(),
  obra_id          uuid references public.obras(id) on delete cascade,
  nome             text not null,
  versao           integer not null default 1,
  base_referencia  text,
  bdi              numeric(6,4) not null default 0.25,
  encargos_sociais numeric(6,4) not null default 0.80,
  total_custo      numeric(14,2) not null default 0,
  total_venda      numeric(14,2) not null default 0,
  status           text not null default 'Rascunho',
  created_by       uuid references auth.users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
grant select, insert, update, delete on public.orcamentos to authenticated;
grant all on public.orcamentos to service_role;
alter table public.orcamentos enable row level security;
create trigger trg_orcamentos_updated before update on public.orcamentos
  for each row execute function public.set_updated_at();
drop policy if exists p_orc_read on public.orcamentos;
create policy p_orc_read on public.orcamentos for select to authenticated using (true);
drop policy if exists p_orc_write on public.orcamentos;
create policy p_orc_write on public.orcamentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.insumos (
  id         uuid primary key default gen_random_uuid(),
  codigo     text unique not null,
  descricao  text not null,
  unidade    text not null,
  tipo       text not null default 'Material',
  preco_unit numeric(14,4) not null default 0,
  fonte      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.insumos to authenticated;
grant all on public.insumos to service_role;
alter table public.insumos enable row level security;
create trigger trg_insumos_updated before update on public.insumos
  for each row execute function public.set_updated_at();
drop policy if exists p_ins_read on public.insumos;
create policy p_ins_read on public.insumos for select to authenticated using (true);
drop policy if exists p_ins_write on public.insumos;
create policy p_ins_write on public.insumos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'suprimentos'));

create table if not exists public.composicoes (
  id         uuid primary key default gen_random_uuid(),
  codigo     text unique not null,
  descricao  text not null,
  unidade    text not null,
  preco_unit numeric(14,4) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.composicoes to authenticated;
grant all on public.composicoes to service_role;
alter table public.composicoes enable row level security;
create trigger trg_composicoes_updated before update on public.composicoes
  for each row execute function public.set_updated_at();
drop policy if exists p_comp_read on public.composicoes;
create policy p_comp_read on public.composicoes for select to authenticated using (true);
drop policy if exists p_comp_write on public.composicoes;
create policy p_comp_write on public.composicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.composicao_itens (
  id                uuid primary key default gen_random_uuid(),
  composicao_id     uuid not null references public.composicoes(id) on delete cascade,
  insumo_id         uuid references public.insumos(id),
  sub_composicao_id uuid references public.composicoes(id),
  coeficiente       numeric(14,6) not null,
  check (insumo_id is not null or sub_composicao_id is not null)
);
grant select, insert, update, delete on public.composicao_itens to authenticated;
grant all on public.composicao_itens to service_role;
alter table public.composicao_itens enable row level security;
drop policy if exists p_compit_read on public.composicao_itens;
create policy p_compit_read on public.composicao_itens for select to authenticated using (true);
drop policy if exists p_compit_write on public.composicao_itens;
create policy p_compit_write on public.composicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.orcamento_itens (
  id            uuid primary key default gen_random_uuid(),
  orcamento_id  uuid not null references public.orcamentos(id) on delete cascade,
  ordem         text not null,
  descricao     text not null,
  composicao_id uuid references public.composicoes(id),
  unidade       text not null default '',
  quantidade    numeric(14,4) not null default 0,
  preco_unit    numeric(14,4) not null default 0,
  total         numeric(14,2) generated always as (quantidade * preco_unit) stored,
  created_at    timestamptz not null default now()
);
grant select, insert, update, delete on public.orcamento_itens to authenticated;
grant all on public.orcamento_itens to service_role;
alter table public.orcamento_itens enable row level security;
create index if not exists idx_orcitens_orc on public.orcamento_itens(orcamento_id);
drop policy if exists p_orcit_read on public.orcamento_itens;
create policy p_orcit_read on public.orcamento_itens for select to authenticated using (true);
drop policy if exists p_orcit_write on public.orcamento_itens;
create policy p_orcit_write on public.orcamento_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ============================================================
-- EAP
-- ============================================================
create table if not exists public.eap_itens (
  id             uuid primary key default gen_random_uuid(),
  obra_id        uuid not null references public.obras(id) on delete cascade,
  parent_id      uuid references public.eap_itens(id) on delete cascade,
  codigo         text not null,
  descricao      text not null,
  unidade        text,
  qtd_prevista   numeric(14,4) default 0,
  valor_previsto numeric(14,2) default 0,
  peso           numeric(6,4) default 0,
  ordem          integer not null default 0,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (obra_id, codigo)
);
grant select, insert, update, delete on public.eap_itens to authenticated;
grant all on public.eap_itens to service_role;
alter table public.eap_itens enable row level security;
create trigger trg_eap_updated before update on public.eap_itens
  for each row execute function public.set_updated_at();
create index if not exists idx_eap_obra on public.eap_itens(obra_id);
drop policy if exists p_eap_read on public.eap_itens;
create policy p_eap_read on public.eap_itens for select to authenticated using (true);
drop policy if exists p_eap_write on public.eap_itens;
create policy p_eap_write on public.eap_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ============================================================
-- MEDIÇÕES
-- ============================================================
create table if not exists public.medicoes (
  id           uuid primary key default gen_random_uuid(),
  obra_id      uuid not null references public.obras(id) on delete cascade,
  numero       integer not null,
  competencia  date not null,
  data_emissao date not null default current_date,
  status       text not null default 'Rascunho',
  valor_total  numeric(14,2) not null default 0,
  observacoes  text,
  created_by   uuid references auth.users(id),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (obra_id, numero)
);
grant select, insert, update, delete on public.medicoes to authenticated;
grant all on public.medicoes to service_role;
alter table public.medicoes enable row level security;
create trigger trg_medicoes_updated before update on public.medicoes
  for each row execute function public.set_updated_at();
drop policy if exists p_med_read on public.medicoes;
create policy p_med_read on public.medicoes for select to authenticated using (true);
drop policy if exists p_med_write on public.medicoes;
create policy p_med_write on public.medicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.medicao_itens (
  id           uuid primary key default gen_random_uuid(),
  medicao_id   uuid not null references public.medicoes(id) on delete cascade,
  eap_id       uuid not null references public.eap_itens(id),
  qtd_periodo  numeric(14,4) not null default 0,
  pct_periodo  numeric(6,4) not null default 0,
  valor_periodo numeric(14,2) not null default 0
);
grant select, insert, update, delete on public.medicao_itens to authenticated;
grant all on public.medicao_itens to service_role;
alter table public.medicao_itens enable row level security;
drop policy if exists p_medit_read on public.medicao_itens;
create policy p_medit_read on public.medicao_itens for select to authenticated using (true);
drop policy if exists p_medit_write on public.medicao_itens;
create policy p_medit_write on public.medicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ============================================================
-- DIÁRIO DE OBRA
-- ============================================================
create table if not exists public.diario_obra (
  id          uuid primary key default gen_random_uuid(),
  obra_id     uuid not null references public.obras(id) on delete cascade,
  data        date not null,
  clima_manha text, clima_tarde text,
  efetivo     jsonb default '[]'::jsonb,
  atividades  text,
  ocorrencias text,
  fotos       text[] default '{}',
  created_by  uuid references auth.users(id),
  created_at  timestamptz not null default now(),
  unique (obra_id, data)
);
grant select, insert, update, delete on public.diario_obra to authenticated;
grant all on public.diario_obra to service_role;
alter table public.diario_obra enable row level security;
drop policy if exists p_diario_read on public.diario_obra;
create policy p_diario_read on public.diario_obra for select to authenticated using (true);
drop policy if exists p_diario_write on public.diario_obra;
create policy p_diario_write on public.diario_obra for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'qualidade'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'qualidade'));

-- ============================================================
-- SUPRIMENTOS
-- ============================================================
create table if not exists public.fornecedores (
  id            uuid primary key default gen_random_uuid(),
  cnpj          text unique,
  razao_social  text not null,
  nome_fantasia text,
  email         text,
  telefone      text,
  endereco      text,
  categoria     text,
  ativo         boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
grant select, insert, update, delete on public.fornecedores to authenticated;
grant all on public.fornecedores to service_role;
alter table public.fornecedores enable row level security;
create trigger trg_forn_updated before update on public.fornecedores
  for each row execute function public.set_updated_at();
drop policy if exists p_forn_read on public.fornecedores;
create policy p_forn_read on public.fornecedores for select to authenticated using (true);
drop policy if exists p_forn_write on public.fornecedores;
create policy p_forn_write on public.fornecedores for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

create table if not exists public.requisicoes (
  id              uuid primary key default gen_random_uuid(),
  numero          text unique,
  obra_id         uuid not null references public.obras(id),
  solicitante_id  uuid references auth.users(id),
  data_necessidade date,
  prioridade      text default 'Normal',
  status          public.req_status not null default 'Rascunho',
  justificativa   text,
  aprovador_id    uuid references auth.users(id),
  aprovado_em     timestamptz,
  created_by      uuid references auth.users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
grant select, insert, update, delete on public.requisicoes to authenticated;
grant all on public.requisicoes to service_role;
alter table public.requisicoes enable row level security;
create trigger trg_req_updated before update on public.requisicoes
  for each row execute function public.set_updated_at();
drop policy if exists p_req_read on public.requisicoes;
create policy p_req_read on public.requisicoes for select to authenticated using (true);
drop policy if exists p_req_write on public.requisicoes;
create policy p_req_write on public.requisicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.requisicao_itens (
  id             uuid primary key default gen_random_uuid(),
  requisicao_id  uuid not null references public.requisicoes(id) on delete cascade,
  insumo_id      uuid references public.insumos(id),
  descricao      text not null,
  unidade        text not null,
  quantidade     numeric(14,4) not null
);
grant select, insert, update, delete on public.requisicao_itens to authenticated;
grant all on public.requisicao_itens to service_role;
alter table public.requisicao_itens enable row level security;
drop policy if exists p_reqit_read on public.requisicao_itens;
create policy p_reqit_read on public.requisicao_itens for select to authenticated using (true);
drop policy if exists p_reqit_write on public.requisicao_itens;
create policy p_reqit_write on public.requisicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

-- ====== ESTOQUE ======
create table if not exists public.estoque_movimentos (
  id         uuid primary key default gen_random_uuid(),
  obra_id    uuid not null references public.obras(id),
  insumo_id  uuid not null references public.insumos(id),
  tipo       text not null,
  quantidade numeric(14,4) not null,
  custo_unit numeric(14,4),
  origem     text,
  origem_id  uuid,
  data       timestamptz not null default now(),
  created_by uuid references auth.users(id)
);
grant select, insert, update, delete on public.estoque_movimentos to authenticated;
grant all on public.estoque_movimentos to service_role;
alter table public.estoque_movimentos enable row level security;
create index if not exists idx_estoque_obra_insumo on public.estoque_movimentos(obra_id, insumo_id);
drop policy if exists p_est_read on public.estoque_movimentos;
create policy p_est_read on public.estoque_movimentos for select to authenticated using (true);
drop policy if exists p_est_write on public.estoque_movimentos;
create policy p_est_write on public.estoque_movimentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

create or replace view public.estoque_saldo as
select
  obra_id, insumo_id,
  sum(case when tipo='ENTRADA' then quantidade
           when tipo='SAIDA'   then -quantidade
           when tipo='AJUSTE'  then quantidade end) as saldo,
  sum(case when tipo='ENTRADA' then quantidade * coalesce(custo_unit,0) else 0 end)
    / nullif(sum(case when tipo='ENTRADA' then quantidade else 0 end), 0) as custo_medio
from public.estoque_movimentos
group by obra_id, insumo_id;

-- ============================================================
-- FINANCEIRO
-- ============================================================
create table if not exists public.plano_contas (
  id        uuid primary key default gen_random_uuid(),
  codigo    text unique not null,
  nome      text not null,
  tipo      text not null,
  parent_id uuid references public.plano_contas(id),
  ativo     boolean not null default true
);
grant select, insert, update, delete on public.plano_contas to authenticated;
grant all on public.plano_contas to service_role;
alter table public.plano_contas enable row level security;
drop policy if exists p_pc_read on public.plano_contas;
create policy p_pc_read on public.plano_contas for select to authenticated using (true);
drop policy if exists p_pc_write on public.plano_contas;
create policy p_pc_write on public.plano_contas for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

create table if not exists public.centros_custo (
  id      uuid primary key default gen_random_uuid(),
  codigo  text unique not null,
  nome    text not null,
  obra_id uuid references public.obras(id),
  ativo   boolean not null default true
);
grant select, insert, update, delete on public.centros_custo to authenticated;
grant all on public.centros_custo to service_role;
alter table public.centros_custo enable row level security;
drop policy if exists p_cc_read on public.centros_custo;
create policy p_cc_read on public.centros_custo for select to authenticated using (true);
drop policy if exists p_cc_write on public.centros_custo;
create policy p_cc_write on public.centros_custo for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

create table if not exists public.contas_bancarias (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null,
  banco         text,
  agencia       text,
  conta         text,
  saldo_inicial numeric(14,2) not null default 0,
  ativo         boolean not null default true,
  created_at    timestamptz not null default now()
);
grant select, insert, update, delete on public.contas_bancarias to authenticated;
grant all on public.contas_bancarias to service_role;
alter table public.contas_bancarias enable row level security;
drop policy if exists p_cb_read on public.contas_bancarias;
create policy p_cb_read on public.contas_bancarias for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));
drop policy if exists p_cb_write on public.contas_bancarias;
create policy p_cb_write on public.contas_bancarias for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

create table if not exists public.lancamentos (
  id                uuid primary key default gen_random_uuid(),
  tipo              text not null,          -- PAGAR, RECEBER
  status            text not null default 'Previsto',
  obra_id           uuid references public.obras(id),
  plano_conta_id    uuid references public.plano_contas(id),
  fornecedor_id     uuid references public.fornecedores(id),
  cliente_nome      text,
  descricao         text not null,
  valor             numeric(14,2) not null,
  categoria         text,                   -- Materiais, Folha de Pagamento, Impostos, Outros
  data_emissao      date not null default current_date,
  data_vencimento   date not null,
  data_pagamento    date,
  conta_bancaria_id uuid references public.contas_bancarias(id),
  documento         text,
  forma_pagamento   text,
  origem            text,
  origem_id         uuid,
  parcela_num       integer,
  parcela_total     integer,
  created_by        uuid references auth.users(id),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
grant select, insert, update, delete on public.lancamentos to authenticated;
grant all on public.lancamentos to service_role;
alter table public.lancamentos enable row level security;
create trigger trg_lanc_updated before update on public.lancamentos
  for each row execute function public.set_updated_at();
create index if not exists idx_lanc_venc on public.lancamentos(data_vencimento);
create index if not exists idx_lanc_obra on public.lancamentos(obra_id);
drop policy if exists p_lanc_read on public.lancamentos;
create policy p_lanc_read on public.lancamentos for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_lanc_write on public.lancamentos;
create policy p_lanc_write on public.lancamentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

-- ============================================================
-- PESSOAL
-- ============================================================
create table if not exists public.colaboradores (
  id             uuid primary key default gen_random_uuid(),
  cpf            text unique,
  nome           text not null,
  funcao         text,
  matricula      text unique,
  admissao       date,
  demissao       date,
  salario        numeric(14,2),
  tipo_contrato  text default 'CLT',
  ativo          boolean not null default true,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
grant select, insert, update, delete on public.colaboradores to authenticated;
grant all on public.colaboradores to service_role;
alter table public.colaboradores enable row level security;
create trigger trg_col_updated before update on public.colaboradores
  for each row execute function public.set_updated_at();
drop policy if exists p_col_read on public.colaboradores;
create policy p_col_read on public.colaboradores for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_col_write on public.colaboradores;
create policy p_col_write on public.colaboradores for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'));

create table if not exists public.alocacoes (
  id              uuid primary key default gen_random_uuid(),
  colaborador_id  uuid not null references public.colaboradores(id),
  obra_id         uuid not null references public.obras(id),
  data_inicio     date not null,
  data_fim        date,
  funcao_obra     text
);
grant select, insert, update, delete on public.alocacoes to authenticated;
grant all on public.alocacoes to service_role;
alter table public.alocacoes enable row level security;
drop policy if exists p_aloc_read on public.alocacoes;
create policy p_aloc_read on public.alocacoes for select to authenticated using (true);
drop policy if exists p_aloc_write on public.alocacoes;
create policy p_aloc_write on public.alocacoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.ponto (
  id              uuid primary key default gen_random_uuid(),
  colaborador_id  uuid not null references public.colaboradores(id),
  obra_id         uuid references public.obras(id),
  data            date not null,
  entrada         time,
  saida_almoco    time,
  retorno_almoco  time,
  saida           time,
  horas_normais   numeric(5,2),
  horas_extras    numeric(5,2),
  falta           boolean default false,
  observacao      text,
  unique (colaborador_id, data)
);
grant select, insert, update, delete on public.ponto to authenticated;
grant all on public.ponto to service_role;
alter table public.ponto enable row level security;
drop policy if exists p_ponto_read on public.ponto;
create policy p_ponto_read on public.ponto for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_ponto_write on public.ponto;
create policy p_ponto_write on public.ponto for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.folha_pagamento (
  id              uuid primary key default gen_random_uuid(),
  competencia     date not null,
  colaborador_id  uuid not null references public.colaboradores(id),
  obra_id         uuid references public.obras(id),
  proventos       numeric(14,2) not null default 0,
  descontos       numeric(14,2) not null default 0,
  liquido         numeric(14,2) generated always as (proventos - descontos) stored,
  status          text default 'Aberta',
  detalhes        jsonb,
  created_at      timestamptz not null default now(),
  unique (competencia, colaborador_id)
);
grant select, insert, update, delete on public.folha_pagamento to authenticated;
grant all on public.folha_pagamento to service_role;
alter table public.folha_pagamento enable row level security;
drop policy if exists p_folha_read on public.folha_pagamento;
create policy p_folha_read on public.folha_pagamento for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'financeiro'));
drop policy if exists p_folha_write on public.folha_pagamento;
create policy p_folha_write on public.folha_pagamento for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'));

-- ============================================================
-- QUALIDADE
-- ============================================================
create table if not exists public.checklists_modelo (
  id         uuid primary key default gen_random_uuid(),
  nome       text not null,
  servico    text,
  itens      jsonb not null default '[]'::jsonb,
  ativo      boolean not null default true,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.checklists_modelo to authenticated;
grant all on public.checklists_modelo to service_role;
alter table public.checklists_modelo enable row level security;
drop policy if exists p_chk_read on public.checklists_modelo;
create policy p_chk_read on public.checklists_modelo for select to authenticated using (true);
drop policy if exists p_chk_write on public.checklists_modelo;
create policy p_chk_write on public.checklists_modelo for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade'));

create table if not exists public.inspecoes (
  id            uuid primary key default gen_random_uuid(),
  obra_id       uuid not null references public.obras(id),
  modelo_id     uuid references public.checklists_modelo(id),
  eap_id        uuid references public.eap_itens(id),
  data          date not null default current_date,
  responsavel_id uuid references auth.users(id),
  resultado     text,
  respostas     jsonb,
  fotos         text[] default '{}',
  created_at    timestamptz not null default now()
);
grant select, insert, update, delete on public.inspecoes to authenticated;
grant all on public.inspecoes to service_role;
alter table public.inspecoes enable row level security;
drop policy if exists p_insp_read on public.inspecoes;
create policy p_insp_read on public.inspecoes for select to authenticated using (true);
drop policy if exists p_insp_write on public.inspecoes;
create policy p_insp_write on public.inspecoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'));

create table if not exists public.nao_conformidades (
  id               uuid primary key default gen_random_uuid(),
  numero           text unique,
  obra_id          uuid not null references public.obras(id),
  inspecao_id      uuid references public.inspecoes(id),
  titulo           text not null,
  descricao        text,
  severidade       public.nc_severidade not null default 'Média',
  status           public.nc_status not null default 'Aberta',
  responsavel_id   uuid references auth.users(id),
  prazo            date,
  acao_corretiva   text,
  acao_preventiva  text,
  encerrada_em     timestamptz,
  created_by       uuid references auth.users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
grant select, insert, update, delete on public.nao_conformidades to authenticated;
grant all on public.nao_conformidades to service_role;
alter table public.nao_conformidades enable row level security;
create trigger trg_nc_updated before update on public.nao_conformidades
  for each row execute function public.set_updated_at();
drop policy if exists p_nc_read on public.nao_conformidades;
create policy p_nc_read on public.nao_conformidades for select to authenticated using (true);
drop policy if exists p_nc_write on public.nao_conformidades;
create policy p_nc_write on public.nao_conformidades for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'));

-- ============================================================
-- SEQUÊNCIAS DE NUMERAÇÃO
-- ============================================================
create sequence if not exists public.seq_requisicao;
create sequence if not exists public.seq_nc;

create or replace function public.gen_numero(prefix text, seqname text)
returns text language sql as $$
  select prefix || '-' || to_char(now(),'YYYY') || '-' ||
         lpad(nextval(seqname)::text, 5, '0');
$$;

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

-- ============================================================
-- SEED INICIAL
-- ============================================================
insert into public.plano_contas (codigo, nome, tipo) values
  ('1','RECEITAS','RECEITA'),
  ('1.1','Receita de Obras','RECEITA'),
  ('1.1.01','Medições de contrato','RECEITA'),
  ('2','DESPESAS','DESPESA'),
  ('2.1','Materiais','DESPESA'),
  ('2.1.01','Cimento e argamassas','DESPESA'),
  ('2.1.02','Aço','DESPESA'),
  ('2.1.03','Concreto usinado','DESPESA'),
  ('2.2','Mão de obra','DESPESA'),
  ('2.2.01','Folha CLT','DESPESA'),
  ('2.2.02','Encargos','DESPESA'),
  ('2.2.03','Empreiteiros','DESPESA'),
  ('2.3','Serviços de terceiros','DESPESA'),
  ('2.4','Equipamentos e locação','DESPESA'),
  ('2.5','Administrativas','DESPESA'),
  ('2.6','Impostos','DESPESA')
on conflict (codigo) do nothing;

insert into public.centros_custo (codigo, nome) values
  ('ADM','Administrativo'),
  ('COM','Comercial')
on conflict (codigo) do nothing;

insert into public.contas_bancarias (nome, banco, agencia, conta, saldo_inicial)
values ('Conta Principal','Banco do Brasil','0001','12345-6', 0)
on conflict do nothing;

insert into public.checklists_modelo (nome, servico, itens) values
  ('Concretagem de laje','Concretagem',
   '[{"ordem":1,"descricao":"Formas niveladas e estanques","criterio":"Visual"},
     {"ordem":2,"descricao":"Armadura conforme projeto","criterio":"Visual + medida"},
     {"ordem":3,"descricao":"Slump test realizado","criterio":"NBR NM 67"},
     {"ordem":4,"descricao":"Corpos de prova moldados","criterio":"NBR 5738"},
     {"ordem":5,"descricao":"Cura iniciada em até 12h","criterio":"Registro"}]'::jsonb)
on conflict do nothing;
