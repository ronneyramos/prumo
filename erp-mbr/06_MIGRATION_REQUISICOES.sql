-- ============================================================
-- ERP MBR — Migração 06: Requisição de Materiais (v2)
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

-- Remove versão parcial anterior (se existir)
DROP TABLE IF EXISTS public.requisicoes CASCADE;

-- ============================================================
-- SEÇÃO 1 — Tabela requisicoes
-- ============================================================

CREATE TABLE public.requisicoes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id       UUID NOT NULL,
  obra_id          UUID,
  obra_nome        TEXT,
  insumo_nome      TEXT NOT NULL,
  quantidade       NUMERIC(12,3) NOT NULL DEFAULT 1,
  unidade          TEXT DEFAULT 'un',
  status           TEXT NOT NULL DEFAULT 'Pendente',
  solicitante      TEXT,
  observacao       TEXT,
  aprovado_por     TEXT,
  data_solicitacao DATE NOT NULL DEFAULT CURRENT_DATE,
  data_aprovacao   DATE,
  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ DEFAULT now()
);

-- Restrição de status via check
ALTER TABLE public.requisicoes
  ADD CONSTRAINT req_status_check
  CHECK (status IN ('Pendente', 'Aprovada', 'Reprovada'));

-- Índices
CREATE INDEX idx_req_empresa ON public.requisicoes(empresa_id);
CREATE INDEX idx_req_status  ON public.requisicoes(status);
CREATE INDEX idx_req_data    ON public.requisicoes(data_solicitacao DESC);

-- ============================================================
-- SEÇÃO 2 — RLS
-- ============================================================

ALTER TABLE public.requisicoes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "req_select" ON public.requisicoes
  FOR SELECT
  USING (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::uuid);

CREATE POLICY "req_insert" ON public.requisicoes
  FOR INSERT
  WITH CHECK (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::uuid);

CREATE POLICY "req_update" ON public.requisicoes
  FOR UPDATE
  USING (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::uuid);

GRANT SELECT, INSERT, UPDATE ON public.requisicoes TO authenticated;
GRANT ALL ON public.requisicoes TO service_role;

-- ============================================================
-- SEÇÃO 3 — Trigger updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_req_updated_at ON public.requisicoes;
CREATE TRIGGER trg_req_updated_at
  BEFORE UPDATE ON public.requisicoes
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
