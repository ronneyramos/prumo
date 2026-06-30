-- ============================================================
-- ERP MBR — Migração 02: Autenticação e controle de acesso
-- Execute no Supabase SQL Editor:
-- https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
-- ============================================================

-- 1. Adiciona perfil adm_obra ao enum de roles
DO $$ BEGIN
  ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'adm_obra';
EXCEPTION WHEN others THEN NULL;
END $$;

-- 2. Adiciona campo obra_alocada em colaboradores (se ainda não rodou 01_MIGRATION)
ALTER TABLE public.colaboradores
  ADD COLUMN IF NOT EXISTS obra_alocada TEXT;

-- 3. Tabela de vínculo usuário ↔ obras permitidas
-- Engenheiro/adm_obra só vê as obras cadastradas aqui
-- Admin e financeiro ignoram essa tabela (veem tudo)
CREATE TABLE IF NOT EXISTS public.usuario_obras (
  user_id  UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  obra_id  UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, obra_id)
);

ALTER TABLE public.usuario_obras ENABLE ROW LEVEL SECURITY;

-- Admin pode gerenciar vínculos; usuário pode ler os próprios
DROP POLICY IF EXISTS p_uobras_admin ON public.usuario_obras;
CREATE POLICY p_uobras_admin ON public.usuario_obras FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS p_uobras_self ON public.usuario_obras;
CREATE POLICY p_uobras_self ON public.usuario_obras FOR SELECT TO authenticated
  USING (user_id = auth.uid());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.usuario_obras TO authenticated;
GRANT ALL ON public.usuario_obras TO service_role;

-- 4. Função auxiliar: retorna os IDs de obras que o usuário pode ver
CREATE OR REPLACE FUNCTION public.obras_do_usuario(uid UUID)
RETURNS TABLE(obra_id UUID) LANGUAGE sql SECURITY DEFINER STABLE
SET search_path = public AS $$
  SELECT uo.obra_id
  FROM public.usuario_obras uo
  WHERE uo.user_id = uid;
$$;

-- ============================================================
-- PRONTO. Próximo passo: criar usuários em Authentication > Users
-- no painel do Supabase, depois atribuir roles em user_roles e
-- obras em usuario_obras conforme perfil de cada pessoa.
-- ============================================================
