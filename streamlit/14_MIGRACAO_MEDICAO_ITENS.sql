-- 14_MIGRACAO_MEDICAO_ITENS.sql
-- Cria tabela para medição itemizada por EAP

-- Drop clean (tabela nova, sem dados importantes)
drop table if exists medicao_itens cascade;

create table medicao_itens (
    id              uuid primary key default gen_random_uuid(),
    medicao_id      uuid not null references medicoes(id) on delete cascade,
    eap_item_id     uuid references eap_itens(id) on delete set null,
    codigo          text not null default '',
    descricao       text not null default '',
    unidade         text not null default '',
    qtd_prevista    numeric(14,2) not null default 0,
    qtd_periodo     numeric(14,2) not null default 0,
    qtd_acumulada   numeric(14,2) not null default 0,
    preco_unitario  numeric(14,2) not null default 0,
    valor_periodo   numeric(14,2) not null default 0,
    valor_acumulado numeric(14,2) not null default 0,
    created_at      timestamptz not null default now(),
    empresa_id      uuid not null references empresas(id)
);

create index idx_medicao_itens_medicao on medicao_itens(medicao_id);
create index idx_medicao_itens_eap on medicao_itens(eap_item_id);

-- Workflow columns on medicoes
alter table medicoes add column if not exists workflow_status text not null default 'Aprovado'
    check (workflow_status in ('Rascunho','Pendente','Aprovado','Faturado'));
alter table medicoes add column if not exists retencao_ir numeric(14,2) not null default 0;
alter table medicoes add column if not exists retencao_iss numeric(14,2) not null default 0;
alter table medicoes add column if not exists retencao_inss numeric(14,2) not null default 0;
alter table medicoes add column if not exists valor_liquido numeric(14,2) not null default 0;

-- Migrate existing medicoes (compatibility)
do $$
declare
    m record;
    e record;
    q_prev numeric; v_prev numeric; pct numeric; qtd_per numeric; v_per numeric;
begin
    for m in select * from medicoes loop
        pct := coalesce((regexp_match(coalesce(m.observacoes,''), 'PCT:([0-9.]+)'))[1]::numeric, 0);
        for e in select * from eap_itens where obra_id = m.obra_id loop
            q_prev := coalesce(e.qtd_prevista, 0);
            v_prev := coalesce(e.valor_previsto, 0);
            qtd_per := round(q_prev * pct / 100, 2);
            v_per   := round(v_prev * pct / 100, 2);
            insert into medicao_itens (medicao_id, eap_item_id, codigo, descricao, unidade,
                qtd_prevista, qtd_periodo, qtd_acumulada, preco_unitario, valor_periodo, valor_acumulado, empresa_id)
            values (m.id, e.id, e.codigo, e.descricao, e.unidade,
                q_prev, qtd_per, qtd_per,
                case when q_prev > 0 then round(v_prev / q_prev, 2) else 0 end,
                v_per, v_per, m.empresa_id);
        end loop;
        if not exists (select 1 from eap_itens where obra_id = m.obra_id) then
            insert into medicao_itens (medicao_id, codigo, descricao, unidade,
                qtd_prevista, qtd_periodo, qtd_acumulada, preco_unitario, valor_periodo, valor_acumulado, empresa_id)
            values (m.id, '001', 'Medição geral da obra', 'vb',
                1, 1, 1, m.valor_total, m.valor_total, m.valor_total, m.empresa_id);
        end if;
    end loop;
end;
$$;
