-- 17_MIGRACAO_CONCILIACAO.sql
-- Conciliação bancária

create table if not exists conciliacao (
    id              uuid primary key default gen_random_uuid(),
    empresa_id      uuid not null,
    obra_id         uuid references obras(id),
    data_importacao timestamptz not null default now(),
    arquivo_nome    text,
    total_transacoes integer not null default 0,
    total_conciliadas integer not null default 0,
    saldo_inicial   numeric(14,2) not null default 0,
    saldo_final     numeric(14,2) not null default 0,
    created_at      timestamptz not null default now()
);

create table if not exists conciliacao_itens (
    id              uuid primary key default gen_random_uuid(),
    conciliacao_id  uuid not null references conciliacao(id) on delete cascade,
    data            date not null,
    descricao       text not null,
    valor           numeric(14,2) not null,
    tipo            text not null default 'Debito',  -- Debito, Credito
    categoria       text,
    lancamento_id   uuid references lancamentos(id) on delete set null,
    conciliado      boolean not null default false,
    created_at      timestamptz not null default now()
);

create index if not exists idx_conciliacao_itens_conc on conciliacao_itens(conciliacao_id);
create index if not exists idx_conciliacao_itens_lanc on conciliacao_itens(lancamento_id);
