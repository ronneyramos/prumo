-- plataforma_admins foi criada sem GRANT: o login não conseguia ler a
-- tabela e o dono da plataforma perdia o acesso ao Painel Dev.
GRANT SELECT ON public.plataforma_admins TO authenticated;
GRANT ALL    ON public.plataforma_admins TO service_role;
