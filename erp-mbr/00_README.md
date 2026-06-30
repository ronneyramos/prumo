# ERP MBR — Pacote para Claude Code

Este pacote contém tudo o que o Claude Code precisa para implementar o ERP web (TanStack Start + Supabase + Tailwind), substituindo o protótipo Streamlit.

## Conteúdo

1. **01_ARQUITETURA.md** — stack, estrutura de pastas, decisões técnicas.
2. **02_SCHEMA.sql** — schema Postgres COMPLETO de todos os módulos (Obras, Suprimentos, Financeiro, Pessoal, Qualidade, Orçamento, EAP) com RLS, GRANTs, triggers e regras de negócio automáticas.
3. **03_ROLES_RLS.sql** — roles, função `has_role`, políticas de segurança detalhadas.
4. **04_SEED.sql** — dados iniciais (obras, centros de custo, plano de contas).
5. **05_PROMPT_CLAUDECODE.md** — prompt mestre para colar no Claude Code, módulo a módulo.
6. **06_REGRAS_NEGOCIO.md** — regras que devem virar triggers/funções (medição → financeiro, requisição → estoque, etc.).
7. **07_ROADMAP.md** — fases de entrega e checklist.

## Como usar no Claude Code

1. Crie um projeto novo TanStack Start + Supabase local (ou aponte para um Supabase próprio).
2. Aplique `02_SCHEMA.sql` + `03_ROLES_RLS.sql` + `04_SEED.sql` via `supabase db push` ou `psql`.
3. Cole o `05_PROMPT_CLAUDECODE.md` no Claude Code para gerar a UI por módulo.
4. Siga o `07_ROADMAP.md` na ordem indicada — não pule fases.

## Stack alvo

- **Frontend:** TanStack Start v1 + React 19 + Tailwind v4 + shadcn/ui
- **Backend:** Supabase (Postgres + Auth + Storage + RLS)
- **Server logic:** `createServerFn` do TanStack (NÃO Edge Functions, exceto webhooks)
- **Auth:** Email/senha + Google OAuth, com roles (admin, engenheiro, financeiro, suprimentos, qualidade, rh, visualizador)
