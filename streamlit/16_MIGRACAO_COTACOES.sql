-- 16_MIGRACAO_COTACOES.sql
-- Cria sistema de cotações standalone (funciona mesmo sem migrations anteriores)

-- ====== COTAÇÕES ======
create table if not exists cotacoes (
    id uuid primary key default gen_random_uuid(),
    data date not null default current_date,
    fornecedor_id uuid references fornecedores(id),
    obra_id uuid references obras(id),
    requisicao_id uuid,
    empresa_id uuid not null default '00000000-0000-0000-0000-000000000001',
    total numeric(14,2) not null default 0,
    validade text,
    condicao_pagamento text,
    prazo_entrega text,
    vencedora boolean not null default false,
    observacao text,
    created_at timestamptz not null default now()
);

-- ====== COTAÇÃO ITENS ======
create table if not exists cotacao_itens (
    id bigserial primary key,
    cotacao_id uuid not null references cotacoes(id) on delete cascade,
    requisicao_item_id uuid,
    descricao text not null default '',
    quantidade numeric(14,4) not null default 0,
    unidade text not null default 'un',
    total numeric(14,2) not null default 0,
    created_at timestamptz not null default now()
);

-- Ajustes para compatibilidade
alter table cotacoes alter column requisicao_id drop not null;
alter table cotacoes add column if not exists obra_id uuid references obras(id);
alter table cotacoes add column if not exists empresa_id uuid not null default '00000000-0000-0000-0000-000000000001';
alter table cotacoes add column if not exists observacao text;
alter table cotacao_itens add column if not exists descricao text not null default '';
alter table cotacao_itens add column if not exists quantidade numeric(14,4) not null default 0;
alter table cotacao_itens add column if not exists unidade text not null default 'un';
alter table cotacao_itens add column if not exists total numeric(14,2) not null default 0;
alter table cotacao_itens alter column requisicao_item_id drop not null;

-- Sequence para id serial
create sequence if not exists seq_cotacao;

grant select, insert, update, delete on cotacoes to authenticated;
grant all on cotacoes to service_role;
grant select, insert, update, delete on cotacao_itens to authenticated;
grant all on cotacao_itens to service_role;
