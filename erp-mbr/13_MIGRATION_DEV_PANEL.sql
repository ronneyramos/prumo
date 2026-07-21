-- Migration 13: Developer Panel
-- dev_grants, partner fields, empresa_limites upgrade, exec_sql RPC

-- 1. Tabela de grants de parceiro
CREATE TABLE IF NOT EXISTS public.dev_grants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  grant_type TEXT NOT NULL DEFAULT 'partner',
  granted_to TEXT NOT NULL DEFAULT '',
  granted_by UUID REFERENCES auth.users(id),
  expires_at TIMESTAMPTZ,
  reason TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.dev_grants ENABLE ROW LEVEL SECURITY;
GRANT ALL ON public.dev_grants TO service_role;
GRANT SELECT ON public.dev_grants TO authenticated;

-- 2. Partner e custom limits nas empresas
ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS is_partner BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS partner_notes TEXT,
  ADD COLUMN IF NOT EXISTS custom_max_obras INTEGER,
  ADD COLUMN IF NOT EXISTS custom_max_usuarios INTEGER;

-- 3. View empresa_limites atualizada (partner bypassa limites)
CREATE OR REPLACE VIEW empresa_limites AS
SELECT
  e.id AS empresa_id,
  e.nome AS empresa_nome,
  COALESCE(p.slug, 'pro') AS plano_slug,
  CASE WHEN e.is_partner THEN 999999
       ELSE COALESCE(e.custom_max_obras, p.max_obras, 999999)
  END AS max_obras,
  CASE WHEN e.is_partner THEN 999999
       ELSE COALESCE(e.custom_max_usuarios, p.max_usuarios, 999999)
  END AS max_usuarios,
  p.modulos,
  e.trial_expires_at,
  e.status,
  e.is_partner
FROM empresas e
LEFT JOIN planos p ON p.id = e.plan_id;

GRANT SELECT ON empresa_limites TO authenticated;
GRANT ALL ON empresa_limites TO service_role;

-- 4. RPC function para SQL Console (dev panel)
CREATE OR REPLACE FUNCTION exec_sql(query_text text)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result JSON;
  is_select BOOLEAN;
BEGIN
  is_select := LOWER(TRIM(query_text)) LIKE 'select%'
            OR LOWER(TRIM(query_text)) LIKE 'with%';

  IF is_select THEN
    EXECUTE format('SELECT COALESCE(json_agg(row_to_json(t)), ''[]''::json) FROM (%s) t', query_text) INTO result;
  ELSE
    EXECUTE query_text;
    result := '{"ok": true}'::json;
  END IF;

  RETURN result;
EXCEPTION WHEN OTHERS THEN
  RETURN json_build_object('error', SQLERRM);
END;
$$;

GRANT EXECUTE ON FUNCTION exec_sql TO service_role;
GRANT EXECUTE ON FUNCTION exec_sql TO authenticated;

-- 5. Tabela de logs do sistema
CREATE TABLE IF NOT EXISTS public.system_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  level TEXT NOT NULL DEFAULT 'info' CHECK (level IN ('info','warning','error')),
  category TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL DEFAULT '',
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  empresa_id UUID REFERENCES empresas(id) ON DELETE SET NULL,
  details JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.system_logs ENABLE ROW LEVEL SECURITY;
GRANT ALL ON public.system_logs TO service_role;
GRANT SELECT ON public.system_logs TO authenticated;

-- 6. Feature toggles
CREATE TABLE IF NOT EXISTS public.feature_toggles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_key TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  description TEXT DEFAULT '',
  empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(feature_key, empresa_id)
);

ALTER TABLE public.feature_toggles ENABLE ROW LEVEL SECURITY;
GRANT ALL ON public.feature_toggles TO service_role;
GRANT SELECT ON public.feature_toggles TO authenticated;

INSERT INTO public.feature_toggles (feature_key, label, description, enabled) VALUES
  ('modulo_orcamento', 'Módulo Orçamento', 'Habilita aba de orçamento completo', true),
  ('modulo_eap_avancado', 'EAP Avançado', 'Habilita planejamento de EAP com custos', true),
  ('modulo_qualidade', 'Módulo Qualidade', 'Habilita inspeções e não conformidades', true),
  ('modulo_pessoal_avancado', 'Pessoal Avançado', 'Habilita folha de pagamento e ponto', true),
  ('modulo_financeiro_avancado', 'Financeiro Avançado', 'Habilita fluxo de caixa e DRE', true),
  ('dev_panel', 'Painel do Desenvolvedor', 'Habilita acesso ao /desenvolvedor', true)
ON CONFLICT (feature_key, empresa_id) DO NOTHING;

-- 7. App config (chave-valor global)
CREATE TABLE IF NOT EXISTS public.app_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  description TEXT DEFAULT '',
  updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.app_config ENABLE ROW LEVEL SECURITY;
GRANT ALL ON public.app_config TO service_role;
GRANT SELECT ON public.app_config TO authenticated;

INSERT INTO public.app_config (key, value, description) VALUES
  ('app_name', 'Prumo ERP', 'Nome do sistema'),
  ('app_version', '1.0.0', 'Versão atual'),
  ('max_upload_mb', '50', 'Tamanho máximo de upload em MB'),
  ('trial_days', '30', 'Dias de teste gratuito'),
  ('support_email', 'suporte@prumoerp.com.br', 'E-mail de suporte'),
  ('maintenance_mode', 'false', 'Modo manutenção (true/false)')
ON CONFLICT (key) DO NOTHING;

-- 8. Índices para performance
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON public.system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_category ON public.system_logs(category);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON public.system_logs(level);
CREATE INDEX IF NOT EXISTS idx_feature_toggles_key ON public.feature_toggles(feature_key);
CREATE INDEX IF NOT EXISTS idx_dev_grants_empresa ON public.dev_grants(empresa_id);
