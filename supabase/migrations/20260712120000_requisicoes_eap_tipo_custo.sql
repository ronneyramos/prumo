-- ============================================================
-- ERP MBR — Migração: Etapa EAP + Tipo de Custo em requisições
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

-- ====== 1. Coluna eap_item_id em requisicoes ======
ALTER TABLE public.requisicoes
  ADD COLUMN IF NOT EXISTS eap_item_id UUID REFERENCES public.eap_itens(id);

COMMENT ON COLUMN public.requisicoes.eap_item_id
  IS 'Vincula a requisicao a uma etapa da EAP';

-- ====== 2. Coluna tipo_custo em requisicoes ======
ALTER TABLE public.requisicoes
  ADD COLUMN IF NOT EXISTS tipo_custo TEXT;

COMMENT ON COLUMN public.requisicoes.tipo_custo
  IS 'Classificacao do custo: Material, Mao-de-obra, Equipamento, Subempreiteiro, Administrativo';

-- ====== 3. Indices ======
CREATE INDEX IF NOT EXISTS idx_req_eap ON public.requisicoes(eap_item_id);
CREATE INDEX IF NOT EXISTS idx_req_tipo_custo ON public.requisicoes(tipo_custo);

-- ============================================================
-- PRONTO.
-- Execute todo o script de uma vez e reinicie o Streamlit.
-- ============================================================
