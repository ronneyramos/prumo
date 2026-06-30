-- ============================================================
-- ERP MBR — Migração 03: Diário de Obra (RDO)
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

CREATE TABLE IF NOT EXISTS public.rdo (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  obra_id         UUID REFERENCES public.obras(id) ON DELETE CASCADE,
  data            DATE NOT NULL,
  responsavel     TEXT,
  clima_manha     TEXT DEFAULT 'Ensolarado',
  clima_tarde     TEXT DEFAULT 'Ensolarado',
  efetivo_total   INTEGER DEFAULT 0,
  atividades      TEXT,
  ocorrencias     TEXT,
  equipamentos    TEXT,
  status_dia      TEXT DEFAULT 'Normal',
  observacoes     TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.rdo ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_rdo_all ON public.rdo;
CREATE POLICY p_rdo_all ON public.rdo FOR ALL TO authenticated
  USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.rdo TO authenticated;
GRANT ALL ON public.rdo TO service_role;

-- ============================================================
-- PRONTO. Após rodar, o módulo "Diário de Obra" estará
-- disponível no ERP para engenheiro, adm_obra, qualidade e admin.
-- ============================================================
