-- ============================================================
-- ERP MBR — Migração 09: Correções de Schema (Junho/2026)
-- Execute TODO este conteúdo no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
--
-- OBJETIVO:
--   Corrigir todas as incompatibilidades entre o schema do banco
--   e o que o app Streamlit espera, conforme análise de código.
--
-- INSTRUÇÕES:
--   1. Execute o script completo de uma vez (é idempotente)
--   2. Reinicie o Streamlit
--   3. Faça login — tudo deve funcionar sem erros 400
--
-- MUDANÇAS:
--   • Cria tabela usuario_obras (vínculo usuário ↔ obra)
--   • Adiciona fotos (JSONB) à tabela rdo
--   • Adiciona progresso, data_inicio, data_termino à eap_itens
--   • Adiciona forma_pagamento à lancamentos
--   • Adiciona categoria (TEXT) à lancamentos (se não existir)
--   • Garante que empresa_id existe em TODAS as tabelas que o app usa
--   • Garante RLS policies corretas (multi-tenant via empresa_id)
--   • Adiciona índices para performance
-- ============================================================

-- ============================================================
-- SEÇÃO 1 — Tabela usuario_obras (usada pelo painel admin)
-- ============================================================
-- O app em main.py faz:
--   sb().table("usuario_obras").select("obra_id").eq("user_id", uid).execute()
--   sb().table("usuario_obras").insert([{"user_id": uid, "obra_id": oid}]).execute()
-- ============================================================

CREATE TABLE IF NOT EXISTS public.usuario_obras (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  obra_id    UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, obra_id)
);

ALTER TABLE public.usuario_obras ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, DELETE ON public.usuario_obras TO authenticated;
GRANT ALL ON public.usuario_obras TO service_role;

-- Admins podem ver e gerenciar todos os vínculos
DROP POLICY IF EXISTS p_uo_select ON public.usuario_obras;
CREATE POLICY p_uo_select ON public.usuario_obras
  FOR SELECT TO authenticated
  USING (
    public.has_role(auth.uid(), 'admin') OR
    user_id = auth.uid()
  );

DROP POLICY IF EXISTS p_uo_insert ON public.usuario_obras;
CREATE POLICY p_uo_insert ON public.usuario_obras
  FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS p_uo_delete ON public.usuario_obras;
CREATE POLICY p_uo_delete ON public.usuario_obras
  FOR DELETE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

CREATE INDEX IF NOT EXISTS idx_uo_user ON public.usuario_obras(user_id);
CREATE INDEX IF NOT EXISTS idx_uo_obra ON public.usuario_obras(obra_id);

-- ============================================================
-- SEÇÃO 2 — rdo: adicionar coluna fotos (JSONB)
-- ============================================================
-- O app em sync.py usa:
--   rdo_update_fotos() → sb().table("rdo").update({"fotos": fotos})
--   rdo_load()         → r.get("fotos")
-- ============================================================

ALTER TABLE public.rdo
  ADD COLUMN IF NOT EXISTS fotos JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.rdo.fotos IS 'Lista de fotos [{nome, url}]';

-- ============================================================
-- SEÇÃO 3 — eap_itens: adicionar colunas de progresso e datas
-- ============================================================
-- O app em sync.py usa:
--   eap_update_progresso() → update({"progresso": ...})
--   eap_update_datas()     → update({"data_inicio": ..., "data_termino": ...})
-- ============================================================

ALTER TABLE public.eap_itens
  ADD COLUMN IF NOT EXISTS progresso   NUMERIC(6,4) DEFAULT 0;

ALTER TABLE public.eap_itens
  ADD COLUMN IF NOT EXISTS data_inicio DATE;

ALTER TABLE public.eap_itens
  ADD COLUMN IF NOT EXISTS data_termino DATE;

COMMENT ON COLUMN public.eap_itens.progresso    IS 'Percentual de avanço (0..1)';
COMMENT ON COLUMN public.eap_itens.data_inicio  IS 'Início programado da etapa';
COMMENT ON COLUMN public.eap_itens.data_termino IS 'Término programado da etapa';

-- ============================================================
-- SEÇÃO 4 — lancamentos: garantir colunas que o app usa
-- ============================================================
-- O app em sync.py usa:
--   "forma_pagamento": dados.get("Forma Pag.") or None
--   "categoria":       dados.get("Categoria") or ...
-- ============================================================

ALTER TABLE public.lancamentos
  ADD COLUMN IF NOT EXISTS forma_pagamento TEXT;

COMMENT ON COLUMN public.lancamentos.forma_pagamento IS 'Boleto, PIX, Cartão, etc.';

-- Garante que categoria existe (já está no 00_SCHEMA_COMPLETO mas pode faltar)
ALTER TABLE public.lancamentos
  ADD COLUMN IF NOT EXISTS categoria TEXT;

COMMENT ON COLUMN public.lancamentos.categoria IS 'Materiais, Folha de Pagamento, Impostos, Outros';

-- ============================================================
-- SEÇÃO 5 — Garantir empresa_id em todas as tabelas
-- (caso 05_MIGRATION_MULTITENANT.sql não tenha sido executada)
-- ============================================================

-- Cria empresas table se não existir
CREATE TABLE IF NOT EXISTS public.empresas (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome       TEXT NOT NULL,
  cnpj       TEXT,
  telefone   TEXT,
  email      TEXT,
  cidade     TEXT,
  estado     TEXT DEFAULT 'CE',
  plano      TEXT DEFAULT 'basico',
  ativo      BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.empresas ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON public.empresas TO authenticated;
GRANT ALL ON public.empresas TO service_role;

-- Insere empresa padrão MBR se não existir
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

-- Policies para empresas
DROP POLICY IF EXISTS p_emp_select ON public.empresas;
CREATE POLICY p_emp_select ON public.empresas FOR SELECT TO authenticated
  USING (id = ((auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID));

DROP POLICY IF EXISTS p_emp_insert ON public.empresas;
CREATE POLICY p_emp_insert ON public.empresas FOR INSERT TO authenticated
  WITH CHECK (true);

DROP POLICY IF EXISTS p_emp_update ON public.empresas;
CREATE POLICY p_emp_update ON public.empresas FOR UPDATE TO authenticated
  USING (id = ((auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID));


-- Adicionar empresa_id + backfill em TODAS as tabelas que o app usa
DO \$\$
DECLARE
  v_mbr_id CONSTANT UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
  -- obras
  ALTER TABLE public.obras ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.obras SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- colaboradores
  ALTER TABLE public.colaboradores ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.colaboradores SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- lancamentos
  ALTER TABLE public.lancamentos ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.lancamentos SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- estoque_movimentos
  ALTER TABLE public.estoque_movimentos ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.estoque_movimentos SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- insumos
  ALTER TABLE public.insumos ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.insumos SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- inspecoes
  ALTER TABLE public.inspecoes ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.inspecoes SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- nao_conformidades
  ALTER TABLE public.nao_conformidades ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.nao_conformidades SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- orcamentos
  ALTER TABLE public.orcamentos ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.orcamentos SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- orcamento_itens
  ALTER TABLE public.orcamento_itens ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.orcamento_itens SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- eap_itens
  ALTER TABLE public.eap_itens ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.eap_itens SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- medicoes
  ALTER TABLE public.medicoes ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.medicoes SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- ponto
  ALTER TABLE public.ponto ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.ponto SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- folha_pagamento
  ALTER TABLE public.folha_pagamento ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.folha_pagamento SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- rdo
  ALTER TABLE public.rdo ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.rdo SET empresa_id = COALESCE(empresa_id, v_mbr_id) WHERE empresa_id IS NULL;

  -- medicao_itens (caso 08_MIGRATION_MEDICAO_ITENS.sql não tenha rodado)
  ALTER TABLE public.medicao_itens ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
  UPDATE public.medicao_itens mi SET empresa_id = COALESCE(mi.empresa_id, m.empresa_id, v_mbr_id)
  FROM public.medicoes m WHERE mi.medicao_id = m.id AND mi.empresa_id IS NULL;
END;
\$\$;

-- ============================================================
-- SEÇÃO 6 — Atualizar RLS para multi-tenant via empresa_id
-- Substitui policies permissivas por filtro de empresa_id
-- (Compatível com 05_MIGRATION_MULTITENANT.sql)
-- ============================================================

-- OBRAS
DROP POLICY IF EXISTS p_obras_read ON public.obras;
DROP POLICY IF EXISTS p_obras_write ON public.obras;
DROP POLICY IF EXISTS p_obras_all ON public.obras;
CREATE POLICY p_obras_select ON public.obras FOR SELECT TO authenticated
  USING (deleted_at IS NULL AND empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_obras_insert ON public.obras FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_obras_update ON public.obras FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_obras_delete ON public.obras FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- COLABORADORES
DROP POLICY IF EXISTS p_col_read ON public.colaboradores;
DROP POLICY IF EXISTS p_col_write ON public.colaboradores;
DROP POLICY IF EXISTS p_colab_all ON public.colaboradores;
CREATE POLICY p_colab_select ON public.colaboradores FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_colab_insert ON public.colaboradores FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_colab_update ON public.colaboradores FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_colab_delete ON public.colaboradores FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- LANÇAMENTOS
DROP POLICY IF EXISTS p_lanc_read ON public.lancamentos;
DROP POLICY IF EXISTS p_lanc_write ON public.lancamentos;
DROP POLICY IF EXISTS p_lanc_all ON public.lancamentos;
CREATE POLICY p_lanc_select ON public.lancamentos FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_lanc_insert ON public.lancamentos FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_lanc_update ON public.lancamentos FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_lanc_delete ON public.lancamentos FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ESTOQUE MOVIMENTOS
DROP POLICY IF EXISTS p_est_read ON public.estoque_movimentos;
DROP POLICY IF EXISTS p_est_write ON public.estoque_movimentos;
DROP POLICY IF EXISTS p_estmov_all ON public.estoque_movimentos;
CREATE POLICY p_est_select ON public.estoque_movimentos FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_est_insert ON public.estoque_movimentos FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_est_update ON public.estoque_movimentos FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_est_delete ON public.estoque_movimentos FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- INSUMOS
DROP POLICY IF EXISTS p_ins_read ON public.insumos;
DROP POLICY IF EXISTS p_ins_write ON public.insumos;
DROP POLICY IF EXISTS p_ins_all ON public.insumos;
CREATE POLICY p_ins_select ON public.insumos FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ins_insert ON public.insumos FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ins_update ON public.insumos FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ins_delete ON public.insumos FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- INSPEÇÕES
DROP POLICY IF EXISTS p_insp_read ON public.inspecoes;
DROP POLICY IF EXISTS p_insp_write ON public.inspecoes;
DROP POLICY IF EXISTS p_insp_all ON public.inspecoes;
CREATE POLICY p_insp_select ON public.inspecoes FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_insp_insert ON public.inspecoes FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_insp_update ON public.inspecoes FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_insp_delete ON public.inspecoes FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- NÃO-CONFORMIDADES
DROP POLICY IF EXISTS p_nc_read ON public.nao_conformidades;
DROP POLICY IF EXISTS p_nc_write ON public.nao_conformidades;
DROP POLICY IF EXISTS p_nc_all ON public.nao_conformidades;
CREATE POLICY p_nc_select ON public.nao_conformidades FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_nc_insert ON public.nao_conformidades FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_nc_update ON public.nao_conformidades FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_nc_delete ON public.nao_conformidades FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ORÇAMENTOS
DROP POLICY IF EXISTS p_orc_read ON public.orcamentos;
DROP POLICY IF EXISTS p_orc_write ON public.orcamentos;
DROP POLICY IF EXISTS p_orc_all ON public.orcamentos;
CREATE POLICY p_orc_select ON public.orcamentos FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orc_insert ON public.orcamentos FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orc_update ON public.orcamentos FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orc_delete ON public.orcamentos FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- ITENS DE ORÇAMENTO
DROP POLICY IF EXISTS p_orcit_read ON public.orcamento_itens;
DROP POLICY IF EXISTS p_orcit_write ON public.orcamento_itens;
DROP POLICY IF EXISTS p_orcit_all ON public.orcamento_itens;
CREATE POLICY p_orcit_select ON public.orcamento_itens FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orcit_insert ON public.orcamento_itens FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orcit_update ON public.orcamento_itens FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_orcit_delete ON public.orcamento_itens FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- EAP
DROP POLICY IF EXISTS p_eap_read ON public.eap_itens;
DROP POLICY IF EXISTS p_eap_write ON public.eap_itens;
DROP POLICY IF EXISTS p_eap_all ON public.eap_itens;
CREATE POLICY p_eap_select ON public.eap_itens FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_eap_insert ON public.eap_itens FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_eap_update ON public.eap_itens FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_eap_delete ON public.eap_itens FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- MEDIÇÕES
DROP POLICY IF EXISTS p_med_read ON public.medicoes;
DROP POLICY IF EXISTS p_med_write ON public.medicoes;
DROP POLICY IF EXISTS p_med_all ON public.medicoes;
CREATE POLICY p_med_select ON public.medicoes FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_med_insert ON public.medicoes FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_med_update ON public.medicoes FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_med_delete ON public.medicoes FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- PONTO
DROP POLICY IF EXISTS p_ponto_read ON public.ponto;
DROP POLICY IF EXISTS p_ponto_write ON public.ponto;
DROP POLICY IF EXISTS p_ponto_all ON public.ponto;
CREATE POLICY p_ponto_select ON public.ponto FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ponto_insert ON public.ponto FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ponto_update ON public.ponto FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_ponto_delete ON public.ponto FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- FOLHA DE PAGAMENTO
DROP POLICY IF EXISTS p_folha_read ON public.folha_pagamento;
DROP POLICY IF EXISTS p_folha_write ON public.folha_pagamento;
DROP POLICY IF EXISTS p_folha_all ON public.folha_pagamento;
CREATE POLICY p_folha_select ON public.folha_pagamento FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_folha_insert ON public.folha_pagamento FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_folha_update ON public.folha_pagamento FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_folha_delete ON public.folha_pagamento FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- RDO
DROP POLICY IF EXISTS p_rdo_all ON public.rdo;
CREATE POLICY p_rdo_select ON public.rdo FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_rdo_insert ON public.rdo FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_rdo_update ON public.rdo FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_rdo_delete ON public.rdo FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- MEDIÇÃO ITENS (já tem políticas específicas na 08_MIGRATION, mas garantimos)
DROP POLICY IF EXISTS p_medit_read  ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_write ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_select ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_insert ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_update ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_delete ON public.medicao_itens;
CREATE POLICY p_medit_select ON public.medicao_itens FOR SELECT TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_medit_insert ON public.medicao_itens FOR INSERT TO authenticated
  WITH CHECK (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_medit_update ON public.medicao_itens FOR UPDATE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));
CREATE POLICY p_medit_delete ON public.medicao_itens FOR DELETE TO authenticated
  USING (empresa_id = ((auth.jwt()->'user_metadata'->>'empresa_id')::UUID));

-- REQUISIÇÕES (já tem políticas próprias na 06_MIGRATION)
-- Garantimos que empresa_id existe
ALTER TABLE public.requisicoes ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);
UPDATE public.requisicoes SET empresa_id = COALESCE(empresa_id, '00000000-0000-0000-0000-000000000001') WHERE empresa_id IS NULL;

-- ============================================================
-- SEÇÃO 7 — Função registrar_empresa (self-service)
-- ============================================================

CREATE OR REPLACE FUNCTION public.registrar_empresa(
  p_nome_empresa TEXT,
  p_user_id      UUID
) RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS \$\$
DECLARE
  v_empresa_id UUID;
BEGIN
  INSERT INTO public.empresas (nome)
  VALUES (p_nome_empresa)
  RETURNING id INTO v_empresa_id;

  UPDATE auth.users
    SET raw_user_meta_data = raw_user_meta_data ||
        jsonb_build_object(
          'empresa_id', v_empresa_id::text,
          'role',       'admin'
        )
  WHERE id = p_user_id;

  RETURN v_empresa_id;
END;
\$\$;

GRANT EXECUTE ON FUNCTION public.registrar_empresa TO authenticated;

-- ============================================================
-- SEÇÃO 8 — Trigger para preencher empresa_id em lancamentos
-- (baseado na obra_id se não informado)
-- ============================================================

CREATE OR REPLACE FUNCTION public.lanc_set_empresa()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS \$\$
BEGIN
  IF NEW.empresa_id IS NULL AND NEW.obra_id IS NOT NULL THEN
    SELECT empresa_id INTO NEW.empresa_id
    FROM   public.obras
    WHERE  id = NEW.obra_id;
  END IF;
  RETURN NEW;
END;
\$\$;

DROP TRIGGER IF EXISTS trg_lanc_empresa ON public.lancamentos;
CREATE TRIGGER trg_lanc_empresa
  BEFORE INSERT ON public.lancamentos
  FOR EACH ROW EXECUTE FUNCTION public.lanc_set_empresa();

-- ============================================================
-- SEÇÃO 9 — Garantir índices de performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lanc_empresa     ON public.lancamentos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_obras_empresa    ON public.obras(empresa_id);
CREATE INDEX IF NOT EXISTS idx_colab_empresa    ON public.colaboradores(empresa_id);
CREATE INDEX IF NOT EXISTS idx_insumos_empresa  ON public.insumos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_eap_empresa      ON public.eap_itens(empresa_id);
CREATE INDEX IF NOT EXISTS idx_orc_empresa      ON public.orcamentos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_orcit_empresa    ON public.orcamento_itens(empresa_id);
CREATE INDEX IF NOT EXISTS idx_med_empresa      ON public.medicoes(empresa_id);
CREATE INDEX IF NOT EXISTS idx_ponto_empresa    ON public.ponto(empresa_id);
CREATE INDEX IF NOT EXISTS idx_folha_empresa    ON public.folha_pagamento(empresa_id);
CREATE INDEX IF NOT EXISTS idx_nc_empresa       ON public.nao_conformidades(empresa_id);
CREATE INDEX IF NOT EXISTS idx_insp_empresa     ON public.inspecoes(empresa_id);
CREATE INDEX IF NOT EXISTS idx_estmov_empresa   ON public.estoque_movimentos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_rdo_empresa      ON public.rdo(empresa_id);
CREATE INDEX IF NOT EXISTS idx_rdo_obra_data    ON public.rdo(obra_id, data);

-- ============================================================
-- SEÇÃO 10 — Verificação final (lista tudo que foi alterado)
-- ============================================================

DO \$\$
DECLARE
  v_fix TEXT;
BEGIN
  RAISE NOTICE '============================================';
  RAISE NOTICE 'Migração 09 concluída.';
  RAISE NOTICE 'Verificações recomendadas:';
  RAISE NOTICE '  1. SELECT * FROM public.usuario_obras LIMIT 5;';
  RAISE NOTICE '  2. SELECT column_name FROM information_schema.columns WHERE table_name=''rdo'' AND column_name=''fotos'';';
  RAISE NOTICE '  3. SELECT column_name FROM information_schema.columns WHERE table_name=''eap_itens'' AND column_name IN (''progresso'',''data_inicio'',''data_termino'');';
  RAISE NOTICE '  4. SELECT column_name FROM information_schema.columns WHERE table_name=''lancamentos'' AND column_name=''forma_pagamento'';';
  RAISE NOTICE '  5. SELECT COUNT(*) FROM public.empresas;';
  RAISE NOTICE '============================================';
END;
\$\$;

-- ============================================================
-- PRONTO.
-- Após executar, reinicie o Streamlit.
-- As páginas de Admin, RDO, EAP e Financeiro devem funcionar
-- sem erros de coluna inexistente ou RLS bloqueando.
-- ============================================================
