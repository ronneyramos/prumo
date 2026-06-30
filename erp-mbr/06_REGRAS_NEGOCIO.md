# Regras de Negócio — Triggers e Server Functions

Cada regra abaixo deve ser implementada como **trigger no banco** (consistência garantida) OU como **server function** explícita (fluxo controlado). Indicado em cada caso.

## 1. Medição aprovada → Conta a receber
**Onde:** server function `aprovarMedicao(medicaoId)`.
**O que faz:**
1. Soma `medicao_itens.valor_periodo` → atualiza `medicoes.valor_total`.
2. Muda `status` para `Aprovada`.
3. Insere em `lancamentos`: `tipo='RECEBER'`, `status='Previsto'`, `obra_id`, `valor`, `data_vencimento = medicao.competencia + 30d`, `origem='medicao'`, `origem_id=medicao.id`, `descricao='Medição nº X – Obra Y'`.
4. Atualiza `obras.pct_fisico` recalculando pelo peso EAP × % medido acumulado.

## 2. Pedido de compra → Conta a pagar (no recebimento)
**Onde:** server function `registrarRecebimento(...)`.
**Por quê:** conta a pagar só nasce com NF recebida e conferida.
**O que faz:**
1. Insere `recebimentos` + `recebimento_itens`.
2. Atualiza `pedido_itens.qtd_recebida`.
3. Atualiza `pedidos_compra.status`: `Parcial` se há saldo, `Recebido` se completo.
4. Insere `estoque_movimentos` (ENTRADA) por item.
5. Insere `lancamentos` (PAGAR, Previsto) com vencimento conforme `pedidos_compra.condicao_pagamento` (parsear "30/60/90" → cria N parcelas).

## 3. Requisição aprovada com saldo em estoque
**Onde:** server function `aprovarRequisicao(reqId)`.
**O que faz:**
1. Para cada item: se `estoque_saldo.saldo >= quantidade`, gera `estoque_movimentos` SAIDA imediata e marca item como atendido.
2. Itens sem saldo permanecem para cotação.
3. Status muda para `Aprovada` (se 100% atendido em estoque) ou `Cotando`.

## 4. Cotação vencedora → Pedido
**Onde:** server function `gerarPedido(cotacaoId)`.
**O que faz:**
1. Marca `cotacoes.vencedora=true` (exclusiva por requisição).
2. Cria `pedidos_compra` + `pedido_itens` copiando preços da cotação.
3. Atualiza `requisicoes.status='Comprada'`.

## 5. Lançamento financeiro pago
**Onde:** server function `baixarLancamento(id, contaBancariaId, dataPagamento)`.
**O que faz:**
1. `lancamentos.status='Pago'`, `data_pagamento`, `conta_bancaria_id` setados.
2. (Saldo bancário é calculado por view, não armazenado.)

## 6. Composição → recálculo de preço
**Onde:** trigger `after insert/update/delete` em `composicao_itens` e `insumos` (preco_unit).
**O que faz:**
```sql
update composicoes c set preco_unit = (
  select coalesce(sum(
    ci.coeficiente * coalesce(i.preco_unit, sc.preco_unit, 0)
  ),0)
  from composicao_itens ci
  left join insumos i on i.id = ci.insumo_id
  left join composicoes sc on sc.id = ci.sub_composicao_id
  where ci.composicao_id = c.id
)
where c.id = NEW.composicao_id;
```

## 7. Orçamento → totais
**Onde:** trigger em `orcamento_itens`.
**O que faz:** soma `total` → `orcamentos.total_custo`; `total_venda = total_custo * (1 + bdi)`.

## 8. NC encerrada
**Onde:** server function `encerrarNC(id, evidencias)`.
**O que faz:** valida que tem ação corretiva preenchida; seta `status='Encerrada'`, `encerrada_em=now()`.

## 9. Folha → contas a pagar
**Onde:** server function `fecharFolha(competencia)`.
**O que faz:** para cada `folha_pagamento` da competência, cria `lancamentos` PAGAR com vencimento dia 5 do mês seguinte, plano_conta `2.2.01`.

## 10. Soft delete
Toda operação de "excluir" obra/contrato/orçamento aprovado deve setar `deleted_at = now()` ao invés de DELETE. RLS/queries filtram `deleted_at IS NULL`.

## 11. Auditoria (opcional fase 6)
Tabela `audit_log (table_name, row_id, action, before, after, user_id, at)`. Trigger genérico em tabelas críticas.
