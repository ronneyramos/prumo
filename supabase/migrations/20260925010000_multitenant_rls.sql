-- Multi-tenant de verdade: isolamento por empresa garantido pelo banco.
--
-- Antes: user_empresa_id() lia raw_user_meta_data (editável pelo próprio
-- usuário), 19 policies liberavam SELECT com "true" e havia ~230 policies
-- sobrepostas de migrations antigas.
-- Agora: empresa_membros é a fonte da verdade (só service_role escreve),
-- e cada tabela tem UMA policy padrão de isolamento.
--
-- Compatível com o app antigo: service_role ignora RLS.
-- Rodar DEPOIS de 20260925000000_security_hardening.sql.

BEGIN;

-- ── 1. Vínculo usuário → empresa ────────────────────────────────────────────
ALTER TABLE public.empresa_membros
  ADD CONSTRAINT empresa_membros_user_id_key UNIQUE (user_id);

CREATE TABLE IF NOT EXISTS public.plataforma_admins (
  user_id    uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.plataforma_admins ENABLE ROW LEVEL SECURITY;

-- Dono da plataforma e único membro atual (MBR). Contas de teste ficam sem vínculo.
INSERT INTO public.empresa_membros (user_id, empresa_id, role)
SELECT id, '00000000-0000-0000-0000-000000000001', 'admin'
FROM auth.users WHERE email = 'ronneyramos123@gmail.com'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO public.plataforma_admins (user_id)
SELECT id FROM auth.users WHERE email = 'ronneyramos123@gmail.com'
ON CONFLICT DO NOTHING;

-- Perfis por usuário passam a ser da empresa do membro
UPDATE public.user_roles r SET empresa_id = m.empresa_id
FROM public.empresa_membros m WHERE m.user_id = r.user_id;
DELETE FROM public.user_roles WHERE empresa_id IS NULL;

-- ── 2. Funções de contexto (não confiam em user_metadata) ───────────────────
-- Só retorna empresa se ela estiver ativa: empresa pendente/bloqueada não lê nada.
CREATE OR REPLACE FUNCTION public.user_empresa_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT m.empresa_id
  FROM public.empresa_membros m
  JOIN public.empresas e ON e.id = m.empresa_id
  WHERE m.user_id = auth.uid() AND e.status = 'ativo'
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.user_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role FROM public.empresa_membros WHERE user_id = auth.uid() LIMIT 1
$$;

REVOKE EXECUTE ON FUNCTION public.user_empresa_id() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.user_role()       FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.user_empresa_id() TO authenticated, service_role;
GRANT  EXECUTE ON FUNCTION public.user_role()       TO authenticated, service_role;

-- Cadastro: cria empresa pendente + vínculo admin (chamado só via service_role)
CREATE OR REPLACE FUNCTION public.registrar_empresa(p_nome_empresa text, p_user_id uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_empresa_id uuid;
BEGIN
  IF EXISTS (SELECT 1 FROM public.empresa_membros WHERE user_id = p_user_id) THEN
    RAISE EXCEPTION 'Usuário já pertence a uma empresa';
  END IF;
  INSERT INTO public.empresas (nome, status) VALUES (p_nome_empresa, 'pendente')
  RETURNING id INTO v_empresa_id;
  INSERT INTO public.empresa_membros (user_id, empresa_id, role)
  VALUES (p_user_id, v_empresa_id, 'admin');
  INSERT INTO public.user_roles (user_id, role, empresa_id)
  VALUES (p_user_id, 'admin', v_empresa_id)
  ON CONFLICT (user_id, role) DO UPDATE SET empresa_id = EXCLUDED.empresa_id;
  RETURN v_empresa_id;
END;
$$;
REVOKE EXECUTE ON FUNCTION public.registrar_empresa(text, uuid) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.registrar_empresa(text, uuid) TO service_role;

-- ── 3. contas_bancarias ganha empresa_id ────────────────────────────────────
ALTER TABLE public.contas_bancarias
  ADD COLUMN IF NOT EXISTS empresa_id uuid REFERENCES public.empresas(id);
UPDATE public.contas_bancarias
  SET empresa_id = '00000000-0000-0000-0000-000000000001' WHERE empresa_id IS NULL;

-- ── 4. Remove TODAS as policies antigas do schema public ────────────────────
DO $$
DECLARE p record;
BEGIN
  FOR p IN SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' LOOP
    EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, p.tablename);
  END LOOP;
END $$;

-- ── 5. Tabelas com empresa_id: isolamento direto ────────────────────────────
-- DEFAULT user_empresa_id() preenche empresa_id em inserts que não o enviam.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'adicionais_funcionario','aditivos','alocacoes','colaboradores','composicoes',
    'conciliacao','contas_bancarias','contratos','cotacoes','eap_itens',
    'estoque_movimentos','ferias','folha_pagamento','fornecedores','inspecoes',
    'insumos','lancamentos','medicao_itens','medicoes','nao_conformidades','obras',
    'orcamento_colmap_templates','orcamento_itens','orcamentos','pedidos_compra',
    'ponto','rdo','recebimentos','requisicao_itens','requisicoes','rescisoes',
    'subempreiteiros'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE public.%I ALTER COLUMN empresa_id SET DEFAULT public.user_empresa_id()', t);
    EXECUTE format($p$CREATE POLICY tenant_isolamento ON public.%I FOR ALL TO authenticated
                      USING (empresa_id = (SELECT public.user_empresa_id()))
                      WITH CHECK (empresa_id = (SELECT public.user_empresa_id()))$p$, t);
  END LOOP;
END $$;

-- ── 6. Tabelas filhas (sem empresa_id): isolamento pelo pai ─────────────────
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('centros_custo',             'obra_id',          'obras'),
    ('diario_obra',               'obra_id',          'obras'),
    ('composicao_itens',          'composicao_id',    'composicoes'),
    ('conciliacao_itens',         'conciliacao_id',   'conciliacao'),
    ('cotacao_itens',             'cotacao_id',       'cotacoes'),
    ('pedido_itens',              'pedido_id',        'pedidos_compra'),
    ('recebimento_itens',         'recebimento_id',   'recebimentos'),
    ('subempreiteiro_contratos',  'subempreiteiro_id','subempreiteiros'),
    ('subempreiteiro_documentos', 'subempreiteiro_id','subempreiteiros')
  ) AS v(tabela, fk, pai) LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tabela);
    EXECUTE format($p$CREATE POLICY tenant_isolamento ON public.%I FOR ALL TO authenticated
                      USING (EXISTS (SELECT 1 FROM public.%I p WHERE p.id = %I.%I
                                     AND p.empresa_id = (SELECT public.user_empresa_id())))
                      WITH CHECK (EXISTS (SELECT 1 FROM public.%I p WHERE p.id = %I.%I
                                     AND p.empresa_id = (SELECT public.user_empresa_id())))$p$,
                   r.tabela, r.pai, r.tabela, r.fk, r.pai, r.tabela, r.fk);
  END LOOP;
END $$;

-- Neto: medição → contrato → subempreiteiro
ALTER TABLE public.subempreiteiro_medicoes ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolamento ON public.subempreiteiro_medicoes FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.subempreiteiro_contratos c
                 JOIN public.subempreiteiros s ON s.id = c.subempreiteiro_id
                 WHERE c.id = subempreiteiro_medicoes.contrato_id AND s.empresa_id = (SELECT public.user_empresa_id())))
  WITH CHECK (EXISTS (SELECT 1 FROM public.subempreiteiro_contratos c
                 JOIN public.subempreiteiros s ON s.id = c.subempreiteiro_id
                 WHERE c.id = subempreiteiro_medicoes.contrato_id AND s.empresa_id = (SELECT public.user_empresa_id())));

-- ── 7. Casos especiais ──────────────────────────────────────────────────────
-- Empresa: o usuário só enxerga a própria; status/plano só mudam via service_role
CREATE POLICY empresa_propria_leitura ON public.empresas FOR SELECT TO authenticated
  USING (id = (SELECT public.user_empresa_id()));

-- Vínculos: leitura do próprio vínculo (mesmo com empresa pendente) e dos colegas
CREATE POLICY membros_leitura ON public.empresa_membros FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR empresa_id = (SELECT public.user_empresa_id()));
CREATE POLICY roles_leitura ON public.user_roles FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR empresa_id = (SELECT public.user_empresa_id()));
CREATE POLICY plataforma_admin_proprio ON public.plataforma_admins FOR SELECT TO authenticated
  USING (user_id = auth.uid());

-- Obras liberadas por usuário: leitura dentro da empresa; escrita via service_role
ALTER TABLE public.usuario_obras ENABLE ROW LEVEL SECURITY;
CREATE POLICY usuario_obras_leitura ON public.usuario_obras FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.obras o WHERE o.id = usuario_obras.obra_id
                 AND o.empresa_id = (SELECT public.user_empresa_id())));

-- Perfis: o próprio e os colegas de empresa
CREATE POLICY perfis_leitura ON public.profiles FOR SELECT TO authenticated
  USING (id = auth.uid() OR EXISTS (
    SELECT 1 FROM public.empresa_membros m
    WHERE m.user_id = profiles.id AND m.empresa_id = (SELECT public.user_empresa_id())));
CREATE POLICY perfis_edicao_propria ON public.profiles FOR UPDATE TO authenticated
  USING (id = auth.uid()) WITH CHECK (id = auth.uid());

-- Modelos de checklist: globais (empresa_id nulo) + os da empresa
ALTER TABLE public.checklists_modelo ALTER COLUMN empresa_id SET DEFAULT public.user_empresa_id();
CREATE POLICY checklist_leitura ON public.checklists_modelo FOR SELECT TO authenticated
  USING (empresa_id IS NULL OR empresa_id = (SELECT public.user_empresa_id()));
CREATE POLICY checklist_escrita ON public.checklists_modelo FOR ALL TO authenticated
  USING (empresa_id = (SELECT public.user_empresa_id()))
  WITH CHECK (empresa_id = (SELECT public.user_empresa_id()));

-- Configurações e toggles: globais + da empresa, somente leitura
CREATE POLICY config_leitura ON public.app_config FOR SELECT TO authenticated
  USING (empresa_id IS NULL OR empresa_id = (SELECT public.user_empresa_id()));
CREATE POLICY toggles_leitura ON public.feature_toggles FOR SELECT TO authenticated
  USING (empresa_id IS NULL OR empresa_id = (SELECT public.user_empresa_id()));

-- Auditoria: só leitura da própria empresa (inserção vem do trigger)
CREATE POLICY auditoria_leitura ON public.audit_log FOR SELECT TO authenticated
  USING (empresa_id = (SELECT public.user_empresa_id()));

-- Catálogos globais
CREATE POLICY planos_leitura ON public.planos FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY plano_contas_leitura ON public.plano_contas FOR SELECT TO authenticated USING (true);

-- dev_grants e system_logs: sem policy = só service_role.

COMMIT;
