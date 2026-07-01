-- ============================================================
-- ERP Prumo — Migração 08: Correção de medicao_itens
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
--
-- PROBLEMA 1: policies ainda usam has_role() — risco N+1 por linha
-- PROBLEMA 2: sem empresa_id — isolamento multi-tenant dependia de join
-- ============================================================

-- ── 1. Adiciona empresa_id ────────────────────────────────────────────────
ALTER TABLE public.medicao_itens
  ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES public.empresas(id);

-- ── 2. Preenche empresa_id a partir de medicoes ───────────────────────────
UPDATE public.medicao_itens mi
SET    empresa_id = m.empresa_id
FROM   public.medicoes m
WHERE  mi.medicao_id = m.id
  AND  mi.empresa_id IS NULL;

-- ── 3. Torna empresa_id NOT NULL após backfill ────────────────────────────
ALTER TABLE public.medicao_itens
  ALTER COLUMN empresa_id SET NOT NULL;

-- ── 4. Índice de suporte para a policy e queries ──────────────────────────
CREATE INDEX IF NOT EXISTS idx_medit_empresa ON public.medicao_itens(empresa_id);

-- ── 5. Substitui policies has_role() por JWT (sem subquery por linha) ─────
DROP POLICY IF EXISTS p_medit_read  ON public.medicao_itens;
DROP POLICY IF EXISTS p_medit_write ON public.medicao_itens;

CREATE POLICY p_medit_select ON public.medicao_itens
  FOR SELECT TO authenticated
  USING (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID);

CREATE POLICY p_medit_insert ON public.medicao_itens
  FOR INSERT TO authenticated
  WITH CHECK (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID);

CREATE POLICY p_medit_update ON public.medicao_itens
  FOR UPDATE TO authenticated
  USING     (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID)
  WITH CHECK (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID);

CREATE POLICY p_medit_delete ON public.medicao_itens
  FOR DELETE TO authenticated
  USING (empresa_id = (auth.jwt() -> 'user_metadata' ->> 'empresa_id')::UUID);

-- ── 6. Trigger para propagar empresa_id automaticamente em novos inserts ──
CREATE OR REPLACE FUNCTION public.medit_set_empresa()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF NEW.empresa_id IS NULL THEN
    SELECT empresa_id INTO NEW.empresa_id
    FROM   public.medicoes
    WHERE  id = NEW.medicao_id;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_medit_empresa ON public.medicao_itens;
CREATE TRIGGER trg_medit_empresa
  BEFORE INSERT ON public.medicao_itens
  FOR EACH ROW EXECUTE FUNCTION public.medit_set_empresa();

-- ============================================================
-- RESULTADO:
-- • medicao_itens agora tem empresa_id isolando dados por empresa
-- • Policies usam JWT direto (O(1)) em vez de has_role() subquery (O(N))
-- • Trigger preenche empresa_id automaticamente em novos inserts
-- ============================================================
