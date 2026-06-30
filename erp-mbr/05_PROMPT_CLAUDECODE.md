# Prompt mestre — Claude Code

Cole isto no Claude Code como instrução inicial do projeto. Depois, peça módulo por módulo.

---

## CONTEXTO

Você está construindo o **ERP MBR Construções**, web app para gestão de obras civis. Substitui um protótipo Streamlit.

**Stack obrigatória:**
- TanStack Start v1 + React 19 + TypeScript strict
- Tailwind v4 + shadcn/ui
- Supabase (Postgres + Auth + Storage) — schema já aplicado (ver `02_SCHEMA.sql`)
- TanStack Query para data fetching, TanStack Table para tabelas
- react-hook-form + zod para forms
- date-fns + date-fns-tz (TZ `America/Fortaleza`)
- Server logic via `createServerFn` do `@tanstack/react-start` (NÃO Edge Functions)

**Regras inegociáveis:**
1. Toda página com dados privados fica em `src/routes/_authenticated/`.
2. Toda chamada ao Supabase que envolve escrita ou dado sensível passa por `createServerFn` com middleware `requireSupabaseAuth`.
3. RLS está ativa: nunca usar service_role no client. Para leituras públicas, usar publishable key.
4. Dinheiro: sempre `numeric(14,2)` no banco, `Intl.NumberFormat('pt-BR', { style:'currency', currency:'BRL' })` no client.
5. Datas: salvar `timestamptz` ou `date`; renderizar com `formatInTimeZone(..., 'America/Fortaleza', 'dd/MM/yyyy')`.
6. Toda lista grande tem: busca, filtros, paginação server-side, ordenação.
7. Toda mutação dispara `toast` (sonner) + `queryClient.invalidateQueries`.
8. Forms: validação Zod compartilhada com server. Erros inline por campo.
9. Tabelas têm ações por linha (ver, editar, excluir com confirm dialog).
10. Acessibilidade: labels, aria, foco visível, navegação por teclado.

**Roles existentes:** admin, engenheiro, financeiro, suprimentos, qualidade, rh, visualizador.
Use `useHasRole('engenheiro')` (hook a criar) para ocultar botões; servidor é a fonte da verdade (RLS).

---

## ESTRUTURA DE PASTAS (ver `01_ARQUITETURA.md`)

---

## ORDEM DE IMPLEMENTAÇÃO

Implemente nesta ordem. Não pule.

### Fase 0 — Setup
- [ ] Bootstrap TanStack Start, Tailwind v4, shadcn.
- [ ] Configurar Supabase client (browser + server publishable + admin).
- [ ] Layout `_authenticated/route.tsx` com sidebar de módulos + header com usuário/logout.
- [ ] Página `/auth` (login email/senha + Google).
- [ ] Hook `useCurrentUser()` e `useHasRole(role)`.
- [ ] Componentes base: `DataTable`, `FormField`, `ConfirmDialog`, `PageHeader`, `EmptyState`, `LoadingSkeleton`, `ErrorBoundary`.

### Fase 1 — Cadastros base
- [ ] Módulo **Fornecedores** (CRUD completo, busca por CNPJ).
- [ ] Módulo **Insumos** (CRUD, import CSV).
- [ ] Módulo **Plano de contas** e **Centros de custo** (árvore expansível).
- [ ] Módulo **Colaboradores** (CRUD).

### Fase 2 — Obras + EAP + Orçamento
- [ ] Lista de Obras + form (admin/engenheiro).
- [ ] Página da obra com abas: Resumo, EAP, Medições, Diário, Qualidade, Financeiro.
- [ ] EAP: árvore drag-and-drop, importação do orçamento aprovado.
- [ ] Orçamento: composições, itens, BDI, curva ABC, exportação PDF/Excel.

### Fase 3 — Operação
- [ ] Suprimentos: Requisição → Cotação (comparativo) → Pedido → Recebimento.
- [ ] Estoque: movimentos automáticos a partir de recebimentos; saídas por requisição interna.
- [ ] Medições: lançamento de avanço por item EAP; geração automática de conta a receber.
- [ ] Diário de obra: registro diário com fotos (Supabase Storage).
- [ ] Qualidade: inspeções com checklist; NCs com prazo e responsável.

### Fase 4 — Financeiro
- [ ] Contas a pagar/receber (lista filtrável por status, vencimento, obra).
- [ ] Baixa de pagamento (atualiza saldo da conta bancária).
- [ ] Fluxo de caixa previsto vs realizado (gráfico).
- [ ] DRE por obra (receitas - custos diretos).

### Fase 5 — Pessoal
- [ ] Alocação de colaboradores em obras.
- [ ] Ponto (lançamento manual + import).
- [ ] Folha simplificada → gera contas a pagar.

### Fase 6 — BI e relatórios
- [ ] Dashboard executivo (obras em andamento, margem, atrasos, NCs abertas).
- [ ] Relatório de medições PDF.
- [ ] Curva S (planejado vs realizado).
- [ ] Exportação Excel de qualquer tabela.

### Fase 7 — Mobile + IA (depois)
- [ ] PWA com câmera (diário, NCs, recebimento).
- [ ] OCR de NF via Lovable AI Gateway.

---

## PADRÃO DE SERVER FUNCTION

```ts
// src/lib/obras.functions.ts
import { createServerFn } from '@tanstack/react-start';
import { requireSupabaseAuth } from '@/integrations/supabase/auth-middleware';
import { z } from 'zod';

export const obraSchema = z.object({
  nome: z.string().min(3),
  cliente: z.string().min(2),
  valor_contrato: z.number().nonnegative(),
  data_inicio: z.string().date().optional(),
  data_termino: z.string().date().optional(),
  status: z.enum(['Planejamento','Em andamento','Paralisada','Concluída','Cancelada']),
});

export const listObras = createServerFn({ method: 'GET' })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from('obras').select('*').is('deleted_at', null)
      .order('created_at', { ascending: false });
    if (error) throw error;
    return data;
  });

export const createObra = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .inputValidator((d) => obraSchema.parse(d))
  .handler(async ({ data, context }) => {
    const { data: row, error } = await context.supabase
      .from('obras').insert({ ...data, created_by: context.userId })
      .select().single();
    if (error) throw error;
    return row;
  });
```

## PADRÃO DE ROTA

```tsx
// src/routes/_authenticated/obras/index.tsx
import { createFileRoute, useRouter } from '@tanstack/react-router';
import { useSuspenseQuery, useMutation } from '@tanstack/react-query';
import { useServerFn } from '@tanstack/react-start';
import { listObras } from '@/lib/obras.functions';

const obrasQuery = () => ({
  queryKey: ['obras'],
  queryFn: () => listObras(),
});

export const Route = createFileRoute('/_authenticated/obras/')({
  loader: ({ context }) => context.queryClient.ensureQueryData(obrasQuery()),
  errorComponent: ({ error, reset }) => { /* ... */ },
  notFoundComponent: () => <div>Não encontrado</div>,
  component: ObrasPage,
});

function ObrasPage() {
  const { data } = useSuspenseQuery(obrasQuery());
  return <DataTable rows={data} columns={cols} />;
}
```

---

## TAREFAS PARA O CLAUDE CODE (peça uma por vez)

1. "Implemente a Fase 0 completa."
2. "Implemente o módulo Fornecedores conforme padrão."
3. "Implemente Insumos com import CSV."
4. "Implemente Obras (lista + form + página com abas vazias)."
5. ... e assim por diante seguindo o roadmap.

Sempre que terminar uma fase, rode:
- `bun run typecheck` (ou `tsgo`)
- `bun run build`
- Teste manual: login → criar registro → editar → excluir.
