-- ============================================================
-- ERP MBR — Migração 10: Módulo Orçado x Realizado
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

-- ====== 1. Coluna eap_item_id em lancamentos ======
ALTER TABLE public.lancamentos
  ADD COLUMN IF NOT EXISTS eap_item_id UUID REFERENCES public.eap_itens(id);

COMMENT ON COLUMN public.lancamentos.eap_item_id
  IS 'Vincula a despesa a uma etapa da EAP para comparar orcado x realizado';

-- ====== 2. Coluna tipo_custo em lancamentos ======
ALTER TABLE public.lancamentos
  ADD COLUMN IF NOT EXISTS tipo_custo TEXT;

COMMENT ON COLUMN public.lancamentos.tipo_custo
  IS 'Classificacao do custo: Material, Mao-de-obra, Equipamento, Subempreiteiro, Administrativo';

-- ====== 3. Indices ======
CREATE INDEX IF NOT EXISTS idx_lanc_eap ON public.lancamentos(eap_item_id);
CREATE INDEX IF NOT EXISTS idx_lanc_tipo_custo ON public.lancamentos(tipo_custo);

-- ====== 4. View Orçado x Realizado ======
CREATE OR REPLACE VIEW public.vw_orcado_realizado AS
SELECT
  o.id       AS obra_id,
  o.nome     AS obra_nome,
  e.id       AS eap_id,
  e.codigo   AS eap_codigo,
  e.descricao AS etapa,
  e.valor_previsto AS orcado,
  COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) AS realizado,
  e.valor_previsto - COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) AS desvio,
  CASE WHEN e.valor_previsto > 0
       THEN ROUND((COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) - e.valor_previsto) / e.valor_previsto * 100, 2)
       ELSE 0 END AS desvio_pct
FROM public.eap_itens e
JOIN public.obras o ON o.id = e.obra_id AND o.deleted_at IS NULL
LEFT JOIN public.lancamentos l ON l.eap_item_id = e.id
GROUP BY o.id, o.nome, e.id, e.codigo, e.descricao, e.valor_previsto
ORDER BY o.nome, e.ordem;

COMMENT ON VIEW public.vw_orcado_realizado
  IS 'Comparacao orcado x realizado por etapa EAP';

GRANT SELECT ON public.vw_orcado_realizado TO authenticated;
GRANT ALL ON public.vw_orcado_realizado TO service_role;

-- ====== 5. View Resumo por Obra ======
CREATE OR REPLACE VIEW public.vw_resumo_obra AS
SELECT
  o.id AS obra_id,
  o.nome AS obra_nome,
  ROUND(SUM(e.valor_previsto), 2) AS total_orcado,
  ROUND(COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS total_realizado,
  ROUND(SUM(e.valor_previsto) - COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS desvio,
  CASE WHEN SUM(e.valor_previsto) > 0
       THEN ROUND((COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) - SUM(e.valor_previsto)) / SUM(e.valor_previsto) * 100, 2)
       ELSE 0 END AS desvio_pct,
  ROUND(AVG(e.progresso) * 100, 2) AS pct_fisico_medio
FROM public.obras o
LEFT JOIN public.eap_itens e ON e.obra_id = o.id
LEFT JOIN public.lancamentos l ON l.eap_item_id = e.id
WHERE o.deleted_at IS NULL
GROUP BY o.id, o.nome
ORDER BY o.nome;

COMMENT ON VIEW public.vw_resumo_obra
  IS 'Resumo financeiro por obra (orcado x realizado agregado)';

GRANT SELECT ON public.vw_resumo_obra TO authenticated;
GRANT ALL ON public.vw_resumo_obra TO service_role;

-- ============================================================
-- PRONTO.
-- Execute todo o script de uma vez e reinicie o Streamlit.
-- ============================================================
