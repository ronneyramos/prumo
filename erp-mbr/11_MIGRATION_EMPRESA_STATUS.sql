-- ─────────────────────────────────────────────────────────────
-- Migration 11: Controle de status de empresas (aprovação)
-- ─────────────────────────────────────────────────────────────

-- 1. Adiciona coluna de status
ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS status      TEXT NOT NULL DEFAULT 'pendente',
  ADD COLUMN IF NOT EXISTS bloqueado_em TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS aprovado_em  TIMESTAMPTZ;

-- 2. Empresas existentes viram 'ativo' (não precisam de aprovação)
UPDATE empresas SET status = 'ativo', aprovado_em = now() WHERE status = 'pendente';

-- 3. Garante que admins da empresa possam ver o status (RLS)
-- A política existente já permite leitura da própria empresa
-- Precisamos de uma política para o app owner (service_role) ver todas
