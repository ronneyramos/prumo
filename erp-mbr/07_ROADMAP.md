# Roadmap de entrega

## Sprint 0 — Fundação (3-5 dias)
- [x] Schema SQL completo (já entregue neste pacote)
- [ ] Aplicar schema + seed no Supabase
- [ ] Bootstrap TanStack Start + Tailwind + shadcn
- [ ] Auth (email + Google) + layout autenticado
- [ ] Componentes base (DataTable, forms, dialogs)
- **Entregável:** login funcional, sidebar com módulos vazios.

## Sprint 1 — Cadastros (3-4 dias)
- [ ] Fornecedores, Insumos, Plano de contas, Centros de custo, Colaboradores
- **Entregável:** todos os cadastros base operacionais com import CSV onde fizer sentido.

## Sprint 2 — Obras + EAP (4-5 dias)
- [ ] CRUD Obras + página com abas
- [ ] EAP hierárquica com árvore
- [ ] Diário de obra com upload de fotos
- **Entregável:** equipe consegue cadastrar obra e iniciar diário.

## Sprint 3 — Orçamento (5-7 dias)
- [ ] Composições + insumos com recálculo automático
- [ ] Orçamento por obra, BDI, curva ABC
- [ ] Aprovação de orçamento → gera EAP base
- [ ] Exportação Excel/PDF
- **Entregável:** orçar uma obra completa do zero.

## Sprint 4 — Suprimentos (5-7 dias)
- [ ] Requisições → Cotações (comparativo lado a lado) → Pedido
- [ ] Recebimento com NF + movimento de estoque
- [ ] Visualização de estoque por obra
- **Entregável:** ciclo de compra fim a fim.

## Sprint 5 — Medições + Financeiro (5-7 dias)
- [ ] Lançamento de medições por EAP
- [ ] Aprovação gera CR automaticamente
- [ ] Contas a pagar/receber com baixa
- [ ] Fluxo de caixa
- **Entregável:** integração obra → financeiro funcionando.

## Sprint 6 — Pessoal (3-4 dias)
- [ ] Alocação, ponto, folha simplificada → CP
- **Entregável:** custo de mão de obra refletido no financeiro da obra.

## Sprint 7 — Qualidade (3-4 dias)
- [ ] Inspeções, NCs com prazo, ensaios
- **Entregável:** controle de qualidade auditável.

## Sprint 8 — BI + Dashboards (3-5 dias)
- [ ] Dashboard executivo
- [ ] DRE por obra, curva S, margem real
- [ ] Relatórios PDF (medição, diário, NC)
- **Entregável:** visão gerencial consolidada.

## Backlog (depois do MVP)
- PWA mobile com câmera offline
- OCR de NF (Lovable AI / Google Vision)
- Integração bancária (OFX/CNAB)
- Assinatura eletrônica de medições
- Multi-empresa
- App nativo para apontamento de ponto com geolocalização

---

## Critérios de "pronto" por sprint
1. Typecheck e build passam.
2. Smoke test manual: criar, editar, excluir, listar com filtro.
3. RLS testada com 2 usuários de roles diferentes.
4. Sem erros no console.
5. Responsivo mobile (mínimo: visualização).
6. Empty states e loading states em todas as listas.

## Riscos e mitigação
| Risco | Mitigação |
|-------|-----------|
| Schema mudar muito durante implementação | Tudo via migration versionada; nunca editar tabela direto no painel |
| Roles confusas | Documentar matriz role × ação; testar com usuários reais antes da Sprint 4 |
| Performance em tabelas grandes (orçamento com 1k+ itens) | Paginação server-side desde o início; índices em FKs |
| Datas com bug de timezone | Padronizar `timestamptz` + `formatInTimeZone` em TODO render |
| Cálculos financeiros com float | Bloquear `number` em colunas de dinheiro; usar `numeric` + `decimal.js` no client se necessário |
