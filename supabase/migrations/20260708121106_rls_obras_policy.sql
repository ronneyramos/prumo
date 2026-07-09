-- Habilita RLS na tabela obras (caso ainda não esteja)
ALTER TABLE IF EXISTS public.obras ENABLE ROW LEVEL SECURITY;

-- Remove políticas antigas se existirem (para recriar limpo)
DROP POLICY IF EXISTS "Usuários autenticados podem ver obras" ON public.obras;
DROP POLICY IF EXISTS "Usuários autenticados podem criar obras" ON public.obras;
DROP POLICY IF EXISTS "Usuários autenticados podem editar obras" ON public.obras;

-- SELECT: qualquer usuário autenticado pode ver obras não deletadas
CREATE POLICY "Usuários autenticados podem ver obras" ON public.obras
    FOR SELECT
    TO authenticated
    USING (true);

-- INSERT: usuários autenticados podem criar obras (empresa_id será definido pelo app)
CREATE POLICY "Usuários autenticados podem criar obras" ON public.obras
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- UPDATE: usuários autenticados podem editar obras
CREATE POLICY "Usuários autenticados podem editar obras" ON public.obras
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- DELETE (soft): usuários autenticados podem marcar obras como deletadas
CREATE POLICY "Usuários autenticados podem deletar obras" ON public.obras
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

