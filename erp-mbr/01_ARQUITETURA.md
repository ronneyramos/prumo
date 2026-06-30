# Arquitetura — ERP MBR

## Decisões

| Item | Decisão | Por quê |
|------|---------|---------|
| Framework | TanStack Start v1 (SSR + server fns) | Type-safe routing, server fns sem Edge |
| UI | React 19 + Tailwind v4 + shadcn/ui | Componentes acessíveis, customizáveis |
| Banco | Postgres (Supabase) | RLS nativa, auth integrada, realtime |
| Server logic | `createServerFn` | Sem cold start de Edge; co-localizado |
| Auth | Supabase Auth (email + Google) | Pronto, RLS via `auth.uid()` |
| Storage | Supabase Storage | NFs, fotos, documentos |
| Estado client | TanStack Query | Cache, invalidação, SSR-friendly |
| Validação | Zod (client + server) | Mesma fonte de verdade |
| Forms | react-hook-form + zod resolver | Padrão de mercado |
| Tabelas | TanStack Table | Sort/filter/paginação |
| Datas | date-fns + date-fns-tz (TZ America/Fortaleza) | Evita bugs UTC |

## Estrutura de pastas

```
src/
  routes/
    __root.tsx
    index.tsx                  # Dashboard público (KPIs gerais)
    auth.tsx                   # Login
    _authenticated/
      route.tsx                # Gate (managed)
      dashboard.tsx
      obras/
        index.tsx              # Lista
        $obraId.tsx            # Layout da obra (abas)
        $obraId.index.tsx      # Resumo
        $obraId.medicoes.tsx
        $obraId.eap.tsx
        $obraId.diario.tsx
      suprimentos/
        requisicoes.tsx
        cotacoes.tsx
        pedidos.tsx
        estoque.tsx
        fornecedores.tsx
      financeiro/
        contas-pagar.tsx
        contas-receber.tsx
        fluxo-caixa.tsx
        conciliacao.tsx
      pessoal/
        colaboradores.tsx
        ponto.tsx
        folha.tsx
      qualidade/
        checklists.tsx
        nao-conformidades.tsx
        ensaios.tsx
      orcamento/
        index.tsx
        $orcId.tsx             # Composições, BDI, curva ABC
    api/
      public/
        webhooks.*.ts
  lib/
    *.functions.ts             # createServerFn (importáveis no cliente)
  server/                      # helpers .server.ts (NÃO importar no cliente)
  components/
    ui/                        # shadcn
    obras/, financeiro/, ...   # componentes de domínio
  integrations/supabase/       # auto-gerado, NÃO editar
```

## Convenções

- **TZ:** todo timestamp salvo em `timestamptz` (UTC). UI converte para `America/Fortaleza`.
- **Dinheiro:** `numeric(14,2)` no banco; nunca `float`. No client, usar `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`.
- **IDs:** `uuid` (gen_random_uuid()) em tudo.
- **Soft delete:** coluna `deleted_at timestamptz` em tabelas críticas (obras, contratos, lançamentos). Filtrar `deleted_at IS NULL` em todas as policies.
- **Auditoria:** colunas `created_at`, `updated_at`, `created_by` em todas as tabelas. Trigger `set_updated_at` em todas.
- **Numeração de documentos:** sequências dedicadas por tipo (`req_seq`, `pedido_seq`, `nc_seq`) com formato `REQ-2026-00001`.
- **RLS:** sempre ON. Policies por role usando `has_role(auth.uid(), 'role')`.
- **Validação:** Zod schemas em `src/lib/schemas/` reusados por server fn e form.

## Módulos e dependências

```
Orçamento ──► EAP ──► Obras ──► Medições ──► Financeiro (CR)
                              │
                              ├─► Diário de obra
                              └─► Qualidade (checklists, NCs)

Suprimentos: Requisição ─► Cotação ─► Pedido ─► Recebimento ─► Estoque
                                                      │
                                                      └─► Financeiro (CP)

Pessoal: Colaborador ─► Alocação em obra ─► Ponto ─► Folha ─► Financeiro (CP)
```
