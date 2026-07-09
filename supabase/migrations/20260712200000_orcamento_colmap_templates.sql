-- ============================================================
-- ERP MBR — Migração: Templates de Mapeamento de Colunas
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

-- ====== Tabela: orcamento_colmap_templates ======
CREATE TABLE IF NOT EXISTS public.orcamento_colmap_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id  UUID NOT NULL REFERENCES public.empresas(id),
    nome        TEXT NOT NULL,
    mapping     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.orcamento_colmap_templates
    IS 'Templates de mapeamento de colunas para importação de orçamentos';

CREATE INDEX IF NOT EXISTS idx_colmap_empresa ON public.orcamento_colmap_templates(empresa_id);

-- ============================================================
-- PRONTO. Execute todo o script de uma vez e reinicie o Streamlit.
-- ============================================================
