DROP VIEW IF EXISTS public.vw_orcado_realizado CASCADE;
CREATE OR REPLACE VIEW public.vw_orcado_realizado AS
SELECT
  o.id       AS obra_id,
  o.nome     AS obra_nome,
  e.id       AS eap_id,
  e.codigo   AS eap_codigo,
  e.descricao AS etapa,
  ROUND(COALESCE(e.valor_previsto, 0), 2) AS orcado,
  ROUND(COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS realizado,
  ROUND(COALESCE(e.valor_previsto, 0) - COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS desvio,
  CASE WHEN COALESCE(e.valor_previsto, 0) > 0
       THEN ROUND((COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) - COALESCE(e.valor_previsto, 0)) / COALESCE(e.valor_previsto, 0) * 100, 2)
       ELSE 0 END AS desvio_pct
FROM public.eap_itens e
JOIN public.obras o ON o.id = e.obra_id AND o.deleted_at IS NULL
LEFT JOIN public.lancamentos l ON l.eap_item_id = e.id
GROUP BY o.id, o.nome, e.id, e.codigo, e.descricao, e.valor_previsto
ORDER BY o.nome, e.ordem;

DROP VIEW IF EXISTS public.vw_resumo_obra CASCADE;
CREATE OR REPLACE VIEW public.vw_resumo_obra AS
SELECT
  o.id AS obra_id,
  o.nome AS obra_nome,
  ROUND(COALESCE(SUM(e.valor_previsto), 0), 2) AS total_orcado,
  ROUND(COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS total_realizado,
  ROUND(COALESCE(SUM(e.valor_previsto), 0) - COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0), 2) AS desvio,
  CASE WHEN COALESCE(SUM(e.valor_previsto), 0) > 0
       THEN ROUND((COALESCE(SUM(l.valor) FILTER (WHERE l.tipo = 'PAGAR'), 0) - COALESCE(SUM(e.valor_previsto), 0)) / COALESCE(SUM(e.valor_previsto), 0) * 100, 2)
       ELSE 0 END AS desvio_pct,
   ROUND(COALESCE(AVG(e.progresso), 0) * 100, 2) AS pct_fisico_medio
FROM public.obras o
LEFT JOIN public.eap_itens e ON e.obra_id = o.id
LEFT JOIN public.lancamentos l ON l.eap_item_id = e.id
WHERE o.deleted_at IS NULL
GROUP BY o.id, o.nome
ORDER BY o.nome;

GRANT SELECT ON public.vw_orcado_realizado TO authenticated;
GRANT SELECT ON public.vw_orcado_realizado TO anon;
GRANT ALL ON public.vw_orcado_realizado TO service_role;

GRANT SELECT ON public.vw_resumo_obra TO authenticated;
GRANT SELECT ON public.vw_resumo_obra TO anon;
GRANT ALL ON public.vw_resumo_obra TO service_role;
