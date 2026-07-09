-- ─────────────────────────────────────────────────────────────
-- Migration 12: Planos de assinatura e vínculo com empresas
-- ─────────────────────────────────────────────────────────────

-- 1. Tabela de planos
CREATE TABLE IF NOT EXISTS public.planos (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome          TEXT NOT NULL,
  slug          TEXT UNIQUE NOT NULL,
  preco_mensal  DECIMAL(10,2) NOT NULL DEFAULT 0,
  preco_anual   DECIMAL(10,2) NOT NULL DEFAULT 0,
  max_obras     INTEGER,              -- NULL = ilimitado
  max_usuarios  INTEGER,              -- NULL = ilimitado
  modulos       JSONB NOT NULL DEFAULT '[]',
  created_at    TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.planos ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.planos TO authenticated;
GRANT ALL ON public.planos TO service_role;

-- 2. Planos padrão
INSERT INTO public.planos (slug, nome, preco_mensal, preco_anual, max_obras, max_usuarios, modulos) VALUES
  ('gratis',   'Grátis',     0,   0,  1, 2,  '["dashboard","obras"]'::JSONB),
  ('pro',      'Pro',       97,  997, 5, 10, '["dashboard","obras","financeiro","suprimentos","pessoal","qualidade","orcamento"]'::JSONB),
  ('enterprise','Enterprise',297, 2997,NULL,NULL,'["dashboard","obras","financeiro","suprimentos","pessoal","qualidade","orcamento","rh"]'::JSONB)
ON CONFLICT (slug) DO NOTHING;

-- 3. Colunas novas em empresas
ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS plan_id          UUID REFERENCES planos(id),
  ADD COLUMN IF NOT EXISTS trial_expires_at TIMESTAMPTZ;

-- 4. Empresas existentes vinculam ao plano Pro (mantém acesso total)
UPDATE empresas
  SET plan_id = (SELECT id FROM planos WHERE slug = 'pro')
WHERE plan_id IS NULL;

-- 5. Cria view útil pra checar limites
CREATE OR REPLACE VIEW empresa_limites AS
SELECT
  e.id AS empresa_id,
  e.nome AS empresa_nome,
  COALESCE(p.slug, 'pro') AS plano_slug,
  COALESCE(p.max_obras, 999999) AS max_obras,
  COALESCE(p.max_usuarios, 999999) AS max_usuarios,
  p.modulos,
  e.trial_expires_at,
  e.status
FROM empresas e
LEFT JOIN planos p ON p.id = e.plan_id;

GRANT SELECT ON empresa_limites TO authenticated;
GRANT ALL ON empresa_limites TO service_role;
