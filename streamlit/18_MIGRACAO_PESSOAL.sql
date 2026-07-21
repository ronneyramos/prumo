-- 18_MIGRACAO_PESSOAL.sql
-- Férias, Adicionais e Rescisão

create table if not exists ferias (
    id uuid primary key default gen_random_uuid(),
    colaborador_id uuid not null references colaboradores(id) on delete cascade,
    data_inicio date not null,
    data_fim date not null,
    dias integer not null default 30,
    periodo_aquisitivo text,
    valor_bruto numeric(14,2) not null default 0,
    valor_terco numeric(14,2) not null default 0,
    valor_liquido numeric(14,2) not null default 0,
    status text not null default 'Agendada',
    data_pagamento date,
    observacao text,
    empresa_id uuid not null,
    created_at timestamptz not null default now()
);

create table if not exists adicionais_funcionario (
    id uuid primary key default gen_random_uuid(),
    colaborador_id uuid not null references colaboradores(id) on delete cascade,
    tipo text not null,
    percentual numeric(5,2) not null default 0,
    valor numeric(14,2) not null default 0,
    ativo boolean not null default true,
    empresa_id uuid not null,
    created_at timestamptz not null default now()
);

create table if not exists rescisoes (
    id uuid primary key default gen_random_uuid(),
    colaborador_id uuid not null references colaboradores(id) on delete cascade,
    data_rescisao date not null,
    tipo text not null default 'Sem justa causa',
    aviso_previo text not null default 'Trabalhado',
    saldo_salario numeric(14,2) not null default 0,
    ferias_vencidas numeric(14,2) not null default 0,
    ferias_proporcionais numeric(14,2) not null default 0,
    terco_constitucional numeric(14,2) not null default 0,
    decimo_terceiro numeric(14,2) not null default 0,
    aviso_previo_valor numeric(14,2) not null default 0,
    multa_fgts numeric(14,2) not null default 0,
    descontos numeric(14,2) not null default 0,
    total_bruto numeric(14,2) not null default 0,
    total_liquido numeric(14,2) not null default 0,
    status text not null default 'Calculada',
    data_pagamento date,
    observacao text,
    empresa_id uuid not null,
    created_at timestamptz not null default now()
);

grant select, insert, update, delete on ferias to authenticated;
grant all on ferias to service_role;
grant select, insert, update, delete on adicionais_funcionario to authenticated;
grant all on adicionais_funcionario to service_role;
grant select, insert, update, delete on rescisoes to authenticated;
grant all on rescisoes to service_role;
