-- ============================================================
-- ERP MBR — Migração 05: Multi-tenancy (empresa_id)
-- Execute no Supabase SQL Editor como postgres:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
--
-- ORDEM DE EXECUÇÃO:
--   1. Cria tabela empresas
--   2. Insere empresa padrão MBR
--   3. Adiciona empresa_id em todas as tabelas
--   4. Migra dados existentes para a MBR
--   5. Cria função registrar_empresa (self-service)
--   6. Atualiza RLS de todas as tabelas
--
-- APÓS RODAR:
--   Descomente e execute o bloco da Seção 7 para vincular
--   o usuário Ronney à empresa MBR.
-- ============================================================


-- ============================================================
-- SEÇÃO 1 — Tabela de empresas
-- ============================================================

CREATE TABLE IF NOT EXISTS public.empresas (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome       TEXT NOT NULL,
  cnpj       TEXT,
  telefone   TEXT,
  email      TEXT,
  cidade     TEXT,
  estado     TEXT DEFAULT 'CE',
  plano      TEXT DEFAULT 'basico',  -- basico | pro | enterprise
  ativo      BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.empresas ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON public.empresas TO authenticated;
GRANT ALL ON public.empresas TO service_role;

-- Leitura: usuário vê somente a sua empresa
DROP POLICY IF EXISTS p_emp_select ON public.empresas;
CREATE POLICY p_emp_select ON public.empresas FOR SELECT TO authenticated
  USING (id = ((auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID));

-- Inserção livre: self-service (qualquer authenticated cria uma empresa)
DROP POLICY IF EXISTS p_emp_insert ON public.empresas;
CREATE POLICY p_emp_insert ON public.empresas FOR INSERT TO authenticated
  WITH CHECK (true);

-- Atualização: somente quem pertence à empresa
DROP POLICY IF EXISTS p_emp_update ON public.empresas;
CREATE POLICY p_emp_update ON public.empresas FOR UPDATE TO authenticated
  USING (id = ((auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID));


-- ============================================================
-- SEÇÃO 2 — Empresa padrão MBR (preserva dados existentes)
-- ============================================================

INSERT INTO public.empresas (id, nome, cnpj, cidade, estado, plano)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'MBR Engenharia',
  '',
  'Fortaleza',
  'CE',
  'pro'
)
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- SEÇÃO 3 — Adicionar empresa_id em todas as tabelas
-- ============================================================

ALTER TABLE public.obras              ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.colaboradores      ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.lancamentos        ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.estoque_movimentos ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.insumos            ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.inspecoes          ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.nao_conformidades  ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.orcamentos         ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.orcamento_itens    ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.eap_itens          ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.medicoes           ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.ponto              ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.folha_pagamento    ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
ALTER TABLE public.rdo                ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);


-- ============================================================
-- SEÇÃO 4 — Migrar dados existentes para a empresa MBR
-- ============================================================

UPDATE public.obras              SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.colaboradores      SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.lancamentos        SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.estoque_movimentos SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.insumos            SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.inspecoes          SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.nao_conformidades  SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.orcamentos         SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.orcamento_itens    SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.eap_itens          SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.medicoes           SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.ponto              SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.folha_pagamento    SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;
UPDATE public.rdo                SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;


-- ============================================================
-- SEÇÃO 5 — Função self-service: registrar nova empresa
-- Chamada pelo app quando um novo cliente se cadastra.
-- SECURITY DEFINER: cria empresa e vincula ao usuário em uma
-- única transação sem precisar de permissões extras.
-- ============================================================

CREATE OR REPLACE FUNCTION public.registrar_empresa(
  p_nome_empresa TEXT,
  p_user_id      UUID
) RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_empresa_id UUID;
BEGIN
  -- Cria a empresa
  INSERT INTO public.empresas (nome)
  VALUES (p_nome_empresa)
  RETURNING id INTO v_empresa_id;

  -- Vincula o usuário à empresa como admin
  UPDATE auth.users
    SET raw_user_meta_data = raw_user_meta_data ||
        jsonb_build_object(
          'empresa_id', v_empresa_id::text,
          'role',       'admin'
        )
  WHERE id = p_user_id;

  RETURN v_empresa_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.registrar_empresa TO authenticated;


-- ============================================================
-- SEÇÃO 6 — Atualizar RLS: filtrar por empresa_id
-- Substitui as policies permissivas (USING true) por policies
-- que isolam os dados de cada empresa.
-- ============================================================

-- OBRAS
DROP POLICY IF EXISTS p_obras_all ON public.obras;
CREATE POLICY p_obras_all ON public.obras FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- COLABORADORES
DROP POLICY IF EXISTS p_colab_all ON public.colaboradores;
CREATE POLICY p_colab_all ON public.colaboradores FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- LANÇAMENTOS FINANCEIROS
DROP POLICY IF EXISTS p_lanc_all ON public.lancamentos;
CREATE POLICY p_lanc_all ON public.lancamentos FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ESTOQUE MOVIMENTOS
DROP POLICY IF EXISTS p_estmov_all ON public.estoque_movimentos;
CREATE POLICY p_estmov_all ON public.estoque_movimentos FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- INSUMOS
DROP POLICY IF EXISTS p_ins_all ON public.insumos;
CREATE POLICY p_ins_all ON public.insumos FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- INSPEÇÕES
DROP POLICY IF EXISTS p_insp_all ON public.inspecoes;
CREATE POLICY p_insp_all ON public.inspecoes FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- NÃO-CONFORMIDADES
DROP POLICY IF EXISTS p_nc_all ON public.nao_conformidades;
CREATE POLICY p_nc_all ON public.nao_conformidades FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ORÇAMENTOS
DROP POLICY IF EXISTS p_orc_all ON public.orcamentos;
CREATE POLICY p_orc_all ON public.orcamentos FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ITENS DE ORÇAMENTO
DROP POLICY IF EXISTS p_orcit_all ON public.orcamento_itens;
CREATE POLICY p_orcit_all ON public.orcamento_itens FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- EAP
DROP POLICY IF EXISTS p_eap_all ON public.eap_itens;
CREATE POLICY p_eap_all ON public.eap_itens FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- MEDIÇÕES
DROP POLICY IF EXISTS p_med_all ON public.medicoes;
CREATE POLICY p_med_all ON public.medicoes FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- PONTO
DROP POLICY IF EXISTS p_ponto_all ON public.ponto;
CREATE POLICY p_ponto_all ON public.ponto FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- FOLHA DE PAGAMENTO
DROP POLICY IF EXISTS p_folha_all ON public.folha_pagamento;
CREATE POLICY p_folha_all ON public.folha_pagamento FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- RDO
DROP POLICY IF EXISTS p_rdo_all ON public.rdo;
CREATE POLICY p_rdo_all ON public.rdo FOR ALL TO authenticated
  USING      (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID))
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));


-- ============================================================
-- SEÇÃO 7 — Vincular usuário Ronney à empresa MBR
--
-- INSTRUÇÕES:
--   1. Acesse Authentication > Users no painel Supabase
--   2. Clique no usuário ronneyramos123@gmail.com
--   3. Copie o UUID do campo "User UID"
--   4. Descomente as linhas abaixo, substitua <UUID_DO_RONNEY>
--      pelo UUID copiado e execute apenas esse bloco.
-- ============================================================

-- UPDATE auth.users
--   SET raw_user_meta_data = raw_user_meta_data ||
--       '{"empresa_id":"00000000-0000-0000-0000-000000000001","role":"admin"}'::jsonb
-- WHERE email = 'ronneyramos123@gmail.com';

-- Verificação (deve retornar 1 linha com empresa_id preenchido):
-- SELECT id, email, raw_user_meta_data->>'empresa_id' AS empresa_id,
--        raw_user_meta_data->>'role' AS role
-- FROM auth.users WHERE email = 'ronneyramos123@gmail.com';


-- ============================================================
-- PRONTO.
-- Após rodar este script:
--   1. Execute o bloco da Seção 7 com o UUID do Ronney
--   2. Reinicie o Streamlit
--   3. Faça login — os dados da MBR aparecerão normalmente
--   4. Novos clientes que se cadastrarem via tela de registro
--      terão automaticamente seus dados isolados
-- ============================================================
