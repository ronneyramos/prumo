-- Auditoria 25/09/2026 — fecha acesso anônimo a funções e views.
-- Contexto: o Postgres concede EXECUTE a PUBLIC por padrão, então exec_sql
-- (SQL arbitrário, SECURITY DEFINER) era executável só com a anon key.
-- O app usa service_role para tudo, então nada disso afeta o Streamlit.

-- 1. Funções administrativas: somente service_role
REVOKE EXECUTE ON FUNCTION public.exec_sql(text)                    FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.exec_sql_readonly(text)           FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.enable_rls_if_table(text)         FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.registrar_empresa(text, uuid)     FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.seed_demo_data(uuid)              FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.gerar_conta_receber_medicao(uuid) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.recalcular_valor_contrato(uuid)   FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.exec_sql(text)                    TO service_role;
GRANT EXECUTE ON FUNCTION public.exec_sql_readonly(text)           TO service_role;
GRANT EXECUTE ON FUNCTION public.enable_rls_if_table(text)         TO service_role;
GRANT EXECUTE ON FUNCTION public.registrar_empresa(text, uuid)     TO service_role;
GRANT EXECUTE ON FUNCTION public.seed_demo_data(uuid)              TO service_role;
GRANT EXECUTE ON FUNCTION public.gerar_conta_receber_medicao(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.recalcular_valor_contrato(uuid)   TO service_role;

-- 2. Nenhuma função do schema public executável por anon
--    (helpers de RLS continuam liberados para authenticated; triggers não
--    dependem de EXECUTE do chamador)
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon;

-- 3. Views passam a respeitar o RLS das tabelas de quem consulta
ALTER VIEW public.vw_orcado_realizado SET (security_invoker = true);
ALTER VIEW public.vw_resumo_obra      SET (security_invoker = true);
ALTER VIEW public.estoque_saldo       SET (security_invoker = true);
ALTER VIEW public.empresa_limites     SET (security_invoker = true);
REVOKE ALL ON public.vw_orcado_realizado, public.vw_resumo_obra,
              public.estoque_saldo, public.empresa_limites FROM anon;
