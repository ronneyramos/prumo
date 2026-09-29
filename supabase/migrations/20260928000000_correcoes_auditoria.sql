-- Correções da auditoria de 28/09/2026.
--
-- 1. colaboradores.situacao: Férias/Afastado/Demitido eram gravados como
--    ativo = false, e o app só lista ativos — o funcionário sumia.
--    "ativo" continua significando "não foi excluído do sistema".
-- 2. nao_conformidades.responsavel_nome: o responsável digitado na tela
--    não tinha onde ser gravado (responsavel_id é um usuário do sistema).
-- 3. Views de Orçado x Realizado: ignoram lançamentos cancelados/excluídos,
--    e vw_resumo_obra deixa de somar o previsto uma vez por lançamento.
--
-- Rodar ANTES de publicar o branch fix/auditoria-2026-09-28.

BEGIN;

-- ── 1. Situação do colaborador ──────────────────────────────────────────────
ALTER TABLE public.colaboradores
  ADD COLUMN IF NOT EXISTS situacao text NOT NULL DEFAULT 'Ativo';

ALTER TABLE public.colaboradores DROP CONSTRAINT IF EXISTS colaboradores_situacao_check;
ALTER TABLE public.colaboradores
  ADD CONSTRAINT colaboradores_situacao_check
  CHECK (situacao IN ('Ativo', 'Férias', 'Afastado', 'Demitido'));

-- ── 2. Responsável da NC (texto livre) ──────────────────────────────────────
ALTER TABLE public.nao_conformidades
  ADD COLUMN IF NOT EXISTS responsavel_nome text;

-- ── 3. Views ────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.vw_orcado_realizado
WITH (security_invoker = true) AS
WITH realizado AS (
  SELECT eap_item_id, SUM(valor) AS valor
  FROM public.lancamentos
  WHERE tipo = 'PAGAR'
    AND deleted_at IS NULL
    AND COALESCE(status, '') <> 'Cancelado'
    AND eap_item_id IS NOT NULL
  GROUP BY eap_item_id
)
SELECT
  o.id        AS obra_id,
  o.nome      AS obra_nome,
  e.id        AS eap_id,
  e.codigo    AS eap_codigo,
  e.descricao AS etapa,
  ROUND(COALESCE(e.valor_previsto, 0), 2) AS orcado,
  ROUND(COALESCE(r.valor, 0), 2)          AS realizado,
  ROUND(COALESCE(e.valor_previsto, 0) - COALESCE(r.valor, 0), 2) AS desvio,
  CASE WHEN COALESCE(e.valor_previsto, 0) > 0
       THEN ROUND((COALESCE(r.valor, 0) - e.valor_previsto) / e.valor_previsto * 100, 2)
       ELSE 0 END AS desvio_pct
FROM public.eap_itens e
JOIN public.obras o ON o.id = e.obra_id AND o.deleted_at IS NULL
LEFT JOIN realizado r ON r.eap_item_id = e.id
ORDER BY o.nome, e.ordem;

-- Agrega EAP e lançamentos separadamente: o JOIN direto multiplicava o
-- valor previsto de cada etapa pelo número de lançamentos ligados a ela.
CREATE OR REPLACE VIEW public.vw_resumo_obra
WITH (security_invoker = true) AS
WITH eap AS (
  SELECT obra_id,
         SUM(valor_previsto) AS orcado,
         AVG(progresso)      AS progresso
  FROM public.eap_itens
  GROUP BY obra_id
),
realizado AS (
  SELECT e.obra_id, SUM(l.valor) AS valor
  FROM public.lancamentos l
  JOIN public.eap_itens e ON e.id = l.eap_item_id
  WHERE l.tipo = 'PAGAR'
    AND l.deleted_at IS NULL
    AND COALESCE(l.status, '') <> 'Cancelado'
  GROUP BY e.obra_id
)
SELECT
  o.id   AS obra_id,
  o.nome AS obra_nome,
  ROUND(COALESCE(eap.orcado, 0), 2) AS total_orcado,
  ROUND(COALESCE(r.valor, 0), 2)    AS total_realizado,
  ROUND(COALESCE(eap.orcado, 0) - COALESCE(r.valor, 0), 2) AS desvio,
  CASE WHEN COALESCE(eap.orcado, 0) > 0
       THEN ROUND((COALESCE(r.valor, 0) - eap.orcado) / eap.orcado * 100, 2)
       ELSE 0 END AS desvio_pct,
  ROUND(COALESCE(eap.progresso, 0) * 100, 2) AS pct_fisico_medio
FROM public.obras o
LEFT JOIN eap       ON eap.obra_id = o.id
LEFT JOIN realizado r ON r.obra_id = o.id
WHERE o.deleted_at IS NULL
ORDER BY o.nome;

REVOKE ALL ON public.vw_orcado_realizado, public.vw_resumo_obra FROM anon;
GRANT SELECT ON public.vw_orcado_realizado, public.vw_resumo_obra TO authenticated;
GRANT ALL    ON public.vw_orcado_realizado, public.vw_resumo_obra TO service_role;

COMMIT;
