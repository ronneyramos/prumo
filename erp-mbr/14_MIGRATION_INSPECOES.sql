-- ============================================================
-- ERP MBR — Migração 14: Checklists / Inspeções (persistência)
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

ALTER TABLE public.inspecoes
  ADD COLUMN IF NOT EXISTS item_inspecionado TEXT,
  ADD COLUMN IF NOT EXISTS observacao TEXT,
  ADD COLUMN IF NOT EXISTS responsavel TEXT;

ALTER TABLE public.inspecoes
  ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);

UPDATE public.inspecoes SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_inspecoes_empresa ON public.inspecoes(empresa_id);

DROP POLICY IF EXISTS p_insp_select ON public.inspecoes;
DROP POLICY IF EXISTS p_insp_insert ON public.inspecoes;
DROP POLICY IF EXISTS p_insp_update ON public.inspecoes;
DROP POLICY IF EXISTS p_insp_delete ON public.inspecoes;

CREATE POLICY p_insp_select ON public.inspecoes FOR SELECT TO authenticated
  USING (empresa_id = public.get_empresa_id());

CREATE POLICY p_insp_insert ON public.inspecoes FOR INSERT TO authenticated
  WITH CHECK (empresa_id = public.get_empresa_id());

CREATE POLICY p_insp_update ON public.inspecoes FOR UPDATE TO authenticated
  USING (empresa_id = public.get_empresa_id());

CREATE POLICY p_insp_delete ON public.inspecoes FOR DELETE TO authenticated
  USING (empresa_id = public.get_empresa_id());
