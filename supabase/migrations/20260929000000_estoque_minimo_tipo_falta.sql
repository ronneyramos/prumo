-- 2ª leva da auditoria de 28/09/2026.
--
-- 1. insumos.estoque_minimo: o mínimo digitado na tela não tinha onde ser
--    gravado (voltava sempre 0) e o alerta de estoque crítico nunca disparava.
-- 2. ponto.tipo_falta: Injustificada/Justificada/Atestado/Folga/Férias eram
--    perdidos — tudo voltava como "Falta".
--
-- Rodar ANTES de publicar o branch fix/auditoria-telas.

BEGIN;

ALTER TABLE public.insumos
  ADD COLUMN IF NOT EXISTS estoque_minimo numeric NOT NULL DEFAULT 0;

ALTER TABLE public.ponto
  ADD COLUMN IF NOT EXISTS tipo_falta text;

-- Faltas antigas: abono virava prefixo na observação
UPDATE public.ponto
   SET tipo_falta = CASE WHEN observacao LIKE 'ABONO:%' THEN 'Justificada' ELSE 'Injustificada' END,
       observacao = CASE WHEN observacao LIKE 'ABONO:%' THEN btrim(substr(observacao, 7)) ELSE observacao END
 WHERE falta AND tipo_falta IS NULL;

COMMIT;
