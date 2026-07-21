-- 19_MIGRACAO_SUBEMPREITEIROS.sql
-- Cadastro de subempreiteiros + contratos + medições + documentos

create table if not exists subempreiteiros (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null,
    razao_social text not null,
    nome_fantasia text,
    cnpj text,
    inscricao_estadual text,
    contato_nome text,
    contato_email text,
    contato_telefone text,
    endereco text,
    especialidades text[] default '{}',
    crea_ca text,
    observacoes text,
    ativo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists subempreiteiro_contratos (
    id uuid primary key default gen_random_uuid(),
    subempreiteiro_id uuid not null references subempreiteiros(id) on delete cascade,
    obra_id uuid not null references obras(id) on delete cascade,
    numero_contrato text not null,
    objeto text not null,
    valor_contrato numeric(14,2) not null default 0,
    data_inicio date,
    data_fim date,
    prazo_dias integer,
    condicoes_pagamento text,
    retencao_percentual numeric(5,2) not null default 0,
    garantia text,
    status text not null default 'vigente',
    observacoes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists subempreiteiro_medicoes (
    id uuid primary key default gen_random_uuid(),
    contrato_id uuid not null references subempreiteiro_contratos(id) on delete cascade,
    mes_referencia date not null,
    valor_medido numeric(14,2) not null default 0,
    valor_aprovado numeric(14,2) not null default 0,
    percentual_executado numeric(5,2) not null default 0,
    retencao_valor numeric(14,2) not null default 0,
    valor_liquido numeric(14,2) not null default 0,
    data_pagamento date,
    status text not null default 'medido',
    observacoes text,
    created_at timestamptz not null default now()
);

create table if not exists subempreiteiro_documentos (
    id uuid primary key default gen_random_uuid(),
    subempreiteiro_id uuid not null references subempreiteiros(id) on delete cascade,
    tipo_documento text not null,
    numero text,
    data_emissao date,
    data_validade date,
    observacoes text,
    created_at timestamptz not null default now()
);

grant select, insert, update, delete on subempreiteiros to authenticated;
grant all on subempreiteiros to service_role;
grant select, insert, update, delete on subempreiteiro_contratos to authenticated;
grant all on subempreiteiro_contratos to service_role;
grant select, insert, update, delete on subempreiteiro_medicoes to authenticated;
grant all on subempreiteiro_medicoes to service_role;
grant select, insert, update, delete on subempreiteiro_documentos to authenticated;
grant all on subempreiteiro_documentos to service_role;
