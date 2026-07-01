-- ============================================================
-- ERP MBR — Migração 07: Função de seed com dados de demo
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
--
-- OBJETIVO:
--   Cria a função seed_demo_data(p_empresa_id) que popula uma
--   empresa nova com obras, medições, lançamentos, colaboradores
--   e RDOs realistas (construção civil, Fortaleza-CE).
--
--   Chamada automaticamente pelo app após novo cadastro.
--   Idempotente: não insere se já houver dados.
-- ============================================================

CREATE OR REPLACE FUNCTION public.seed_demo_data(p_empresa_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_obra1 UUID := gen_random_uuid();
  v_obra2 UUID := gen_random_uuid();
  v_obra3 UUID := gen_random_uuid();
BEGIN
  -- Não repetir se empresa já tem obras
  IF EXISTS (SELECT 1 FROM public.obras WHERE empresa_id = p_empresa_id LIMIT 1) THEN
    RETURN;
  END IF;

  -- ── Obras ──────────────────────────────────────────────────────────────────
  INSERT INTO public.obras
    (id, empresa_id, nome, tipo, cliente, endereco, responsavel,
     valor_contrato, bdi, data_inicio, data_termino, pct_fisico, status)
  VALUES
    (v_obra1, p_empresa_id,
     'Residencial Solar das Acácias', 'Residencial',
     'João Paulo Construções Ltda',
     'Rua das Acácias, 120 — Fortaleza/CE',
     'Eng. Carlos Menezes',
     850000, 0.25, '2025-03-01', '2026-09-30', 65, 'Em andamento'),

    (v_obra2, p_empresa_id,
     'Galpão Logístico Maracanaú', 'Industrial',
     'LogNorte Distribuidora S.A.',
     'Av. Industrial, 580 — Maracanaú/CE',
     'Eng. Ana Figueiredo',
     1450000, 0.22, '2026-06-15', '2027-12-20', 12, 'Em andamento'),

    (v_obra3, p_empresa_id,
     'Reforma Escritório Meireles', 'Comercial',
     'Consultoria Silva & Associados',
     'Av. Beira Mar, 2500 — Fortaleza/CE',
     'Eng. Carlos Menezes',
     95000, 0.20, '2024-08-01', '2025-01-31', 100, 'Concluída');

  -- ── Medições ───────────────────────────────────────────────────────────────
  INSERT INTO public.medicoes
    (empresa_id, obra_id, numero, competencia, data_emissao, status, valor_total)
  VALUES
    (p_empresa_id, v_obra1, 1, '2025-03-31', '2025-03-31', 'Aprovada', 85000),
    (p_empresa_id, v_obra1, 2, '2025-06-30', '2025-06-30', 'Aprovada', 120000),
    (p_empresa_id, v_obra1, 3, '2025-09-30', '2025-09-30', 'Aprovada', 110000),
    (p_empresa_id, v_obra1, 4, '2025-12-31', '2025-12-31', 'Aprovada', 95000),
    (p_empresa_id, v_obra1, 5, '2026-03-31', '2026-03-31', 'Rascunho', 117500),
    (p_empresa_id, v_obra2, 1, '2026-06-30', '2026-06-30', 'Rascunho',  60000),
    (p_empresa_id, v_obra3, 1, '2024-10-31', '2024-10-31', 'Aprovada',  47500),
    (p_empresa_id, v_obra3, 2, '2025-01-31', '2025-01-31', 'Aprovada',  47500);

  -- ── Lançamentos financeiros ────────────────────────────────────────────────
  INSERT INTO public.lancamentos
    (empresa_id, obra_id, tipo, status, descricao, valor, categoria,
     data_emissao, data_vencimento, cliente_nome)
  VALUES
    -- Contas a Pagar
    (p_empresa_id, v_obra1, 'PAGAR', 'Previsto',
     'Concreto usinado — BT Concretos', 32000, 'Materiais',
     CURRENT_DATE, CURRENT_DATE + 15, 'BT Concretos Fortaleza'),

    (p_empresa_id, v_obra1, 'PAGAR', 'Previsto',
     'Folha de pagamento — Junho/2026', 28000, 'Folha de Pagamento',
     CURRENT_DATE, CURRENT_DATE + 5, 'Colaboradores'),

    (p_empresa_id, v_obra2, 'PAGAR', 'Previsto',
     'Estrutura metálica — Aço Norte', 145000, 'Materiais',
     CURRENT_DATE, CURRENT_DATE + 30, 'Aço Norte Distribuidora'),

    (p_empresa_id, v_obra1, 'PAGAR', 'Pago',
     'Aluguel de andaimes — Maio/2026', 4800, 'Equipamentos',
     CURRENT_DATE - 20, CURRENT_DATE - 10, 'Scaffolding CE Locações'),

    -- Contas a Receber
    (p_empresa_id, v_obra1, 'RECEBER', 'Previsto',
     'Medição #5 — Residencial Solar das Acácias', 117500, NULL,
     CURRENT_DATE, CURRENT_DATE + 10, 'João Paulo Construções Ltda'),

    (p_empresa_id, v_obra2, 'RECEBER', 'Previsto',
     'Medição #1 — Galpão Logístico Maracanaú', 60000, NULL,
     CURRENT_DATE, CURRENT_DATE + 20, 'LogNorte Distribuidora S.A.'),

    (p_empresa_id, v_obra3, 'RECEBER', 'Pago',
     'Saldo final — Reforma Meireles', 47500, NULL,
     CURRENT_DATE - 30, CURRENT_DATE - 15, 'Consultoria Silva & Associados');

  -- ── Colaboradores ──────────────────────────────────────────────────────────
  -- CPF e matrícula deixados NULL (unique global — não pode repetir entre demos)
  INSERT INTO public.colaboradores
    (empresa_id, nome, funcao, admissao, salario, tipo_contrato)
  VALUES
    (p_empresa_id, 'Carlos Eduardo Menezes',   'Engenheiro Civil',          '2023-01-15', 8500, 'CLT'),
    (p_empresa_id, 'Ana Paula Figueiredo',      'Engenheira Civil',          '2023-03-01', 8500, 'CLT'),
    (p_empresa_id, 'José Raimundo Ferreira',    'Mestre de Obras',           '2022-06-10', 4200, 'CLT'),
    (p_empresa_id, 'Francisco Bezerra Lima',    'Pedreiro Oficial',          '2023-02-20', 2800, 'CLT'),
    (p_empresa_id, 'Maria das Graças Souza',    'Auxiliar Administrativo',   '2024-01-08', 2200, 'CLT'),
    (p_empresa_id, 'Antônio Soares Cavalcante', 'Eletricista',               '2023-07-03', 3100, 'CLT');

  -- ── Diários de Obra (RDO) ─────────────────────────────────────────────────
  INSERT INTO public.rdo
    (empresa_id, obra_id, data, responsavel, clima_manha, clima_tarde,
     efetivo_total, atividades, status_dia)
  VALUES
    (p_empresa_id, v_obra1, CURRENT_DATE,
     'Eng. Carlos Menezes', 'Ensolarado', 'Nublado', 12,
     'Concretagem da laje do 2º pavimento. Instalação de forma metálica nas colunas do bloco B.',
     'Normal'),

    (p_empresa_id, v_obra1, CURRENT_DATE - 1,
     'Eng. Carlos Menezes', 'Nublado', 'Chuvoso', 8,
     'Aguardo de tempo para retomada da concretagem. Serviços internos de alvenaria no bloco A.',
     'Chuva — paralisação parcial'),

    (p_empresa_id, v_obra1, CURRENT_DATE - 2,
     'Eng. Carlos Menezes', 'Ensolarado', 'Ensolarado', 14,
     'Montagem de armadura da laje. Chegada de aço CA-50 (12,5t). Revisão do cronograma com encarregado.',
     'Normal'),

    (p_empresa_id, v_obra2, CURRENT_DATE,
     'Eng. Ana Figueiredo', 'Ensolarado', 'Ensolarado', 18,
     'Montagem da estrutura metálica — vãos 3 e 4. Chegada de material: vigas IPE 200.',
     'Normal');

END;
$$;

GRANT EXECUTE ON FUNCTION public.seed_demo_data TO authenticated;
GRANT EXECUTE ON FUNCTION public.seed_demo_data TO service_role;

-- ============================================================
-- PRONTO.
-- Após rodar este script:
--   O app chamará automaticamente seed_demo_data(empresa_id)
--   após cada novo cadastro via tela de registro.
--
-- Para rodar manualmente em uma empresa existente:
--   SELECT seed_demo_data('<UUID_DA_EMPRESA>');
-- ============================================================
