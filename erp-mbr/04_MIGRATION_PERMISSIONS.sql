-- ============================================================
-- ERP MBR — Migração 04: Permissões para todas as tabelas
-- Execute no Supabase SQL Editor como postgres
-- ============================================================

-- 1. OBRAS
GRANT SELECT, INSERT, UPDATE, DELETE ON public.obras TO authenticated;
ALTER TABLE public.obras ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_obras_all ON public.obras;
CREATE POLICY p_obras_all ON public.obras FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 2. COLABORADORES
GRANT SELECT, INSERT, UPDATE, DELETE ON public.colaboradores TO authenticated;
ALTER TABLE public.colaboradores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_colab_all ON public.colaboradores;
CREATE POLICY p_colab_all ON public.colaboradores FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 3. LANÇAMENTOS FINANCEIROS
GRANT SELECT, INSERT, UPDATE, DELETE ON public.lancamentos TO authenticated;
ALTER TABLE public.lancamentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_lanc_all ON public.lancamentos;
CREATE POLICY p_lanc_all ON public.lancamentos FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 4. MOVIMENTOS DE ESTOQUE
GRANT SELECT, INSERT, UPDATE, DELETE ON public.estoque_movimentos TO authenticated;
ALTER TABLE public.estoque_movimentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_estmov_all ON public.estoque_movimentos;
CREATE POLICY p_estmov_all ON public.estoque_movimentos FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 5. INSUMOS
GRANT SELECT, INSERT, UPDATE, DELETE ON public.insumos TO authenticated;
ALTER TABLE public.insumos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_ins_all ON public.insumos;
CREATE POLICY p_ins_all ON public.insumos FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 6. INSPEÇÕES
GRANT SELECT, INSERT, UPDATE, DELETE ON public.inspecoes TO authenticated;
ALTER TABLE public.inspecoes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_insp_all ON public.inspecoes;
CREATE POLICY p_insp_all ON public.inspecoes FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 7. NÃO-CONFORMIDADES
GRANT SELECT, INSERT, UPDATE, DELETE ON public.nao_conformidades TO authenticated;
ALTER TABLE public.nao_conformidades ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_nc_all ON public.nao_conformidades;
CREATE POLICY p_nc_all ON public.nao_conformidades FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 8. ORÇAMENTOS
GRANT SELECT, INSERT, UPDATE, DELETE ON public.orcamentos TO authenticated;
ALTER TABLE public.orcamentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_orc_all ON public.orcamentos;
CREATE POLICY p_orc_all ON public.orcamentos FOR ALL TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.orcamento_itens TO authenticated;
ALTER TABLE public.orcamento_itens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_orcit_all ON public.orcamento_itens;
CREATE POLICY p_orcit_all ON public.orcamento_itens FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 9. EAP
GRANT SELECT, INSERT, UPDATE, DELETE ON public.eap_itens TO authenticated;
ALTER TABLE public.eap_itens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_eap_all ON public.eap_itens;
CREATE POLICY p_eap_all ON public.eap_itens FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 10. MEDIÇÕES
GRANT SELECT, INSERT, UPDATE, DELETE ON public.medicoes TO authenticated;
ALTER TABLE public.medicoes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_med_all ON public.medicoes;
CREATE POLICY p_med_all ON public.medicoes FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 11. PONTO
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ponto TO authenticated;
ALTER TABLE public.ponto ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_ponto_all ON public.ponto;
CREATE POLICY p_ponto_all ON public.ponto FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 12. FOLHA DE PAGAMENTO
GRANT SELECT, INSERT, UPDATE, DELETE ON public.folha_pagamento TO authenticated;
ALTER TABLE public.folha_pagamento ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_folha_all ON public.folha_pagamento;
CREATE POLICY p_folha_all ON public.folha_pagamento FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 13. SERVICE ROLE — acesso total
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

-- ============================================================
-- PRONTO. Reinicie o Streamlit após rodar este script.
-- ============================================================
