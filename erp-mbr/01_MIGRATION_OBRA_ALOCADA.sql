-- Migração: adiciona coluna obra_alocada na tabela colaboradores
-- Execute no Supabase SQL Editor em: https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql

ALTER TABLE public.colaboradores
  ADD COLUMN IF NOT EXISTS obra_alocada TEXT;

-- Comentário de rastreabilidade
COMMENT ON COLUMN public.colaboradores.obra_alocada IS 'Nome da obra atual do colaborador (referência direta para o app)';
