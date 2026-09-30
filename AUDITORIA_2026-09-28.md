# Auditoria do Prumo ERP — 28/09/2026

Leitura completa de `main.py`, `sync.py`, `db.py`, `alertas.py`, `nfe.py`, das views do banco e das migrations.
Testes: 65/65 passando (eles não cobrem nenhum dos itens abaixo). Não houve teste manual no navegador.
Itens marcados com ✔ foram reproduzidos em código; os demais são leitura direta do código.
A parte de atividades/encarregados/Telegram (em standby) ficou fora.

## Status das correções (branch `fix/auditoria-2026-09-28`)

**Corrigidos**
- Itens **1 a 10** (seção 1).
- Itens **26 a 30** (seção 3).
- Parte do item 16: custos com categorias fora das 4 fixas agora entram na DRE como "Outros".
- A parte de SQL do item 15 (as views).

**Encontrados durante a correção e também corrigidos**
- O perfil "gestor" não existe no banco: convidar alguém como gestor falhava.
- Alterar a situação em lote apagava nome, salário e cargo.
- O Portal do Contratante ficava sempre vazio, porque as obras dele não eram carregadas no login.
- A tela de editar permissões mostrava "atualizado" mesmo quando dava erro.
- Um convite que falhava deixava um login sem empresa.
- Banco fora do ar aparecia como "empresa sem dados".
- Havia duas telas de medição com regras diferentes; agora só o menu Medição registra medições.

**Status:** publicado em 29/09 (PR #3).

**2ª leva** (branch `fix/auditoria-telas`)
- **Corrigidos:** itens **11 a 25** da seção 2.
- **Encontrados durante a correção e também corrigidos:**
  - As cores da DRE mostravam valores negativos em verde.
  - A DRE usava contrato × % físico como receita; agora usa as medições faturadas.
  - Faltas e pontos do mesmo dia se sobrescreviam sem aviso.
- **Antes de publicar:** rodar `supabase/migrations/20260929000000_estoque_minimo_tipo_falta.sql`.

**Pendentes:** seções 4 e 5.

## 1. Crítico — perde dados ou erra dinheiro

1. **Funcionário some ao mudar a Situação.** `colaborador_save` grava `ativo = (Situação == "Ativo")` e `colaboradores_listar` só traz `ativo = true`. Pôr alguém de Férias, Afastado ou Demitido faz o funcionário sumir de todas as telas no próximo carregamento. (sync.py:334, db.py:130)
2. **Medição com EAP cobra o acumulado como se fosse do período.** Em *Medição → Nova Medição*, `valor_periodo = valor_acumulado = valor_previsto × %`. A 2ª medição cobra de novo o que a 1ª já cobrou. Além disso: um % menor que o anterior gera conta a receber negativa, a conta vence no 1º dia da competência (já nasce vencida) e ela não aparece no Financeiro até o próximo login. (main.py:6773-6845)
3. **EAP grava zeros por cima do progresso salvo.** As flags `eap_progresso_saved` e `eap_datas_saved` valem para a sessão inteira, não por obra. Ao abrir a 2ª obra, os sliders aparecem zerados; clicar em "Salvar Progresso" apaga o que estava no banco. O mesmo vale para as datas do cronograma. (main.py:6409-6420, 6459-6483)
4. **"Gerar EAP no Banco" apaga a EAP antiga.** Com isso se perdem os vínculos de lançamentos e requisições com as etapas, o progresso e as datas. E o orçamento salvo só grava ITENS (as etapas são descartadas), então uma EAP gerada a partir de um orçamento salvo perde toda a hierarquia. (sync.py:1218, 1319)
5. **O status "Vencido" nunca é salvo.** `_STATUS_SB` converte "Vencido" em "Previsto", que volta como "A Pagar". Nada marca uma conta como vencida pela data. Por isso a métrica "Vencido" e os filtros ficam sempre zerados depois de recarregar. (sync.py:163-170)
6. **Lançamento cancelado entra como custo** na DRE, em Custos por Obra, no Dashboard, no fluxo mensal e na view `vw_orcado_realizado`.
7. **Não-conformidade: a mudança de status não vai para o banco.** Só a sessão é alterada, então a NC volta a "Aberta" e o alerta de "+30 dias" continua disparando. O Responsável também nunca é salvo. (main.py:5023-5026, sync.py:487)
8. **Conciliação bancária lê o valor errado ✔.** `1500.50` vira **150050**; `-1.234,56` vira 1234 com categoria "56", porque a vírgula quebra o CSV. A tela diz que aceita ponto como decimal. A data vai para o banco como "dd/mm/aaaa". (sync.py:1847)
9. **Fluxo de caixa projetado ignora contas atrasadas.** Só entra o que vence de hoje em diante; o que já venceu e não foi pago some da projeção. (main.py:3940-3954)
10. **Falha de gravação silenciosa.** Quase todo `sync.*_save` engole o erro e devolve `None`; a tela mostra "✅ salvo" e guarda só na sessão (RDO, lançamentos, requisição, falta, ponto, cotação, fornecedor, NF manual...). Quando o Supabase falha ou está pausado, o usuário acha que salvou e perde o dado ao sair.

## 2. Alto — funcionalidade quebrada

11. **Cotações, Fornecedores e Rescisões: clicar na linha não faz nada.** `_tabela_clicavel` devolve uma Series em modo de linha única, mas o código testa `isinstance(..., DataFrame)`. Resultado: não dá para editar nem excluir fornecedor, marcar cotação vencedora ou cancelar rescisão. E quando for consertado: "marcar vencedora" hoje zera o total e a data da cotação, porque manda o payload inteiro vazio. (main.py:2843, 2924, 4911; sync.py:1716)
12. **A Curva S do Orçado x Realizado quebra ✔** ("All arrays must be of the same length") sempre que os meses com receita são diferentes dos meses com despesa. (main.py:4279-4285)
13. **Aplicar template de mapeamento do orçamento dá erro do Streamlit**, porque o código altera o `session_state` de um widget já criado. O mesmo acontece nos botões de SQL pré-definido do Painel Dev. (main.py:5688, 1589)
14. **Orçamento com "BDI já incluso" (o padrão) soma mais 25% no resumo.** O "Total Venda" aparece inflado. Além disso, a área de importação está fora da aba e aparece também embaixo da aba "Orçado x Realizado". (main.py:5789, 5499)
15. **Os números do Orçado x Realizado estão errados.**
    - A view `vw_resumo_obra` faz JOIN de EAP × lançamentos e soma o previsto várias vezes, o que distorce o orçado total e o % físico médio (a base do "Custo Projetado").
    - Os cartões de etapa mostram Orçado R$ 0, porque o valor fica só nos itens filhos e não é somado na etapa.
16. **Custos de categorias fora da lista somem da DRE.** O RDO gera contas com categoria "Mão-de-obra", "Material" etc., que não estão entre as 4 categorias da DRE (Materiais / Folha / Impostos / Outros). Esses custos não entram na DRE; em Custos por Obra caem em "Outros". A DRE também soma "Medições faturadas" na tela mas não na receita, e usa contrato × % físico. (main.py:3797-3821, 5975)
17. **Dashboard → Equipe Alocada: custo sempre R$ 0.** O código lê a coluna "Salário", mas ela se chama "Salário (R$)". (main.py:1973)
18. **Filtro de data do relatório de RDO ✔.** A data do RDO é ISO e é lida com `dayfirst=True`: 10/09 vira 09/10, e dias acima de 12 viram vazio. O relatório Financeiro ignora o mês escolhido. (main.py:6984, 6923)
19. **Estoque mínimo nunca é salvo** (volta sempre como 0), então o alerta de estoque crítico nunca dispara. O filtro Entrada/Saída de Movimentações não casa com ENTRADA/SAIDA do banco. (sync.py:1488, main.py:2455)
20. **Faltas: o tipo (Justificada, Atestado, Folga...) não é salvo.** Tudo volta como "Falta". Falta e ponto do mesmo dia se sobrescrevem (upsert em colaborador+data). (sync.py:762, 801, 871)
21. **Os botões "Rever alertas" e "Re-verificar alertas" não fazem nada.** Os alertas só são calculados no primeiro carregamento da sessão. (main.py:169-180)
22. **Período "mm/aaaa" comparado como texto ✔.** "02/2027" < "11/2026". Na virada do ano, a medição anterior e o número do BM ficam errados. As datas do Ponto também são ordenadas como texto. (main.py:2196, 4479)
23. **Cronograma físico-financeiro inconsistente.** "Físico Planejado" dá sempre 100%, o total planejado é o valor do 1º item da EAP e a linha "realizado" é uma reta. (main.py:6590, 6639)
24. **Aprovar requisição não confere o saldo.** O estoque no banco pode ficar negativo, enquanto a tela local trava em 0.
25. **Medições de subempreiteiro não geram conta a pagar**, então esse custo fica fora do Financeiro e da DRE. O valor líquido é digitado à mão (não calcula a retenção).

## 3. Permissões (importante antes de convidar a equipe)

26. **Convite:** o campo diz "deixe vazio para todas" as obras, mas engenheiro, suprimentos, qualidade e gestor **sem obra vinculada não veem nenhuma obra**. (main.py:864 × 811-813)
27. **Perfis suprimentos e rh caem no Dashboard** (portfólio, contas a pagar, folha), porque o redirecionamento para "Principal" não confere a permissão. (main.py:7764)
28. **Permissões folgadas demais:**
    - O **visualizador** pode editar e excluir obras.
    - Qualquer perfil com "obras" (visualizador, qualidade) pode registrar medição, o que gera conta a receber, e alterar a EAP.
    - Relatórios mostra a aba financeira para qualidade e rh.
    - O engenheiro entra em Pessoal e pode editar ou excluir funcionário e lançar rescisão.
29. **Dashboard, listas de requisições e contas não filtram pelas obras do usuário**; só os seletores filtram.
30. **Em caso de erro, o traceback completo aparece para qualquer usuário.**

## 4. Cálculos trabalhistas (não usar como oficial)

31. **Rescisão: os valores sugeridos são fixos**: 15 dias de saldo, 5/12 de férias, 7/12 de 13º e multa de 40% sobre 1 salário (o certo é 40% do saldo do FGTS). Eles não consideram tipo de desligamento, admissão nem data. E são calculados pelo **1º funcionário da lista**: dentro do formulário, trocar o funcionário não recalcula. O mesmo acontece em Férias e Adicionais.
32. **Folha:**
    - INSS de 11% fixo, quando a tabela real é progressiva de 7,5% a 14% e tem teto.
    - Não há IRRF.
    - Os encargos de 31% são aplicados também a MEI, autônomo e diarista.
    - Funcionário Demitido entra na folha até o recarregamento.
33. **Férias:** o "Valor Líquido" é o bruto × 1,333, e o fim fica um dia depois do correto (início + dias).

## 5. Menores / consistência

- **Nome fixo nos PDFs:** "MBR ENGENHARIA LTDA" aparece em todos os PDFs e "MBR Engenharia" no Portal do Contratante. Fica errado para outras empresas; confirmar também a razão social da MBR.
- **Mês em inglês:** o relatório gerencial do Dashboard sugere o mês em inglês ("September/2026").
- **Nome usado como chave:** obras, funcionários e fornecedores são ligados pelo nome. Homônimos pegam o registro errado, e `_obra_uuid` usa "contém", então pode casar com a obra errada. Renomear uma obra desalinha a sessão.
- **Duas telas de medição com regras diferentes:** Obras → Medições (vence em 15 dias, usa contrato × incremento) e a página Medição (EAP, vence na competência).
- **Obra excluída continua somando:** os lançamentos de obras excluídas seguem nos totais do Financeiro.
- **Cores da DRE:** na pizza, as cores trocam de categoria quando uma delas é zero.
- **Cotação:** mais de uma cotação pode ser marcada como vencedora na mesma obra.
- **Validação de NF e RDO:** nada impede NF manual com número repetido nem RDO duplicado para a mesma obra e data.
- **Lentidão:**
  - `colaboradores_load` faz uma consulta por funcionário.
  - O PDF e o Word do RDO, com as fotos, são gerados de novo a cada clique na tela.
- **Composições e "orcamento_por_obra"** ficam só na sessão; o BM e o Dashboard não enxergam o orçamento salvo.
