-- ============================================================
-- ERP MBR — RLS Policies (aplicar APÓS 02_SCHEMA.sql)
-- Modelo: leitura ampla para autenticados; escrita por role.
-- ============================================================

-- Helper macro: criar policies padrão para uma tabela.
-- Como não há macro em SQL puro, repetimos por tabela.

-- ====== ORÇAMENTO ======
drop policy if exists p_orc_read on public.orcamentos;
create policy p_orc_read on public.orcamentos for select to authenticated using (true);
drop policy if exists p_orc_write on public.orcamentos;
create policy p_orc_write on public.orcamentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_ins_read on public.insumos;
create policy p_ins_read on public.insumos for select to authenticated using (true);
drop policy if exists p_ins_write on public.insumos;
create policy p_ins_write on public.insumos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_comp_read on public.composicoes;
create policy p_comp_read on public.composicoes for select to authenticated using (true);
drop policy if exists p_comp_write on public.composicoes;
create policy p_comp_write on public.composicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_compit_read on public.composicao_itens;
create policy p_compit_read on public.composicao_itens for select to authenticated using (true);
drop policy if exists p_compit_write on public.composicao_itens;
create policy p_compit_write on public.composicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_orcit_read on public.orcamento_itens;
create policy p_orcit_read on public.orcamento_itens for select to authenticated using (true);
drop policy if exists p_orcit_write on public.orcamento_itens;
create policy p_orcit_write on public.orcamento_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ====== EAP ======
drop policy if exists p_eap_read on public.eap_itens;
create policy p_eap_read on public.eap_itens for select to authenticated using (true);
drop policy if exists p_eap_write on public.eap_itens;
create policy p_eap_write on public.eap_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ====== MEDIÇÕES ======
drop policy if exists p_med_read on public.medicoes;
create policy p_med_read on public.medicoes for select to authenticated using (true);
drop policy if exists p_med_write on public.medicoes;
create policy p_med_write on public.medicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_medit_read on public.medicao_itens;
create policy p_medit_read on public.medicao_itens for select to authenticated using (true);
drop policy if exists p_medit_write on public.medicao_itens;
create policy p_medit_write on public.medicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro'));

-- ====== DIÁRIO ======
drop policy if exists p_diario_read on public.diario_obra;
create policy p_diario_read on public.diario_obra for select to authenticated using (true);
drop policy if exists p_diario_write on public.diario_obra;
create policy p_diario_write on public.diario_obra for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'qualidade'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'engenheiro') or public.has_role(auth.uid(),'qualidade'));

-- ====== SUPRIMENTOS ======
drop policy if exists p_forn_read on public.fornecedores;
create policy p_forn_read on public.fornecedores for select to authenticated using (true);
drop policy if exists p_forn_write on public.fornecedores;
create policy p_forn_write on public.fornecedores for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_req_read on public.requisicoes;
create policy p_req_read on public.requisicoes for select to authenticated using (true);
drop policy if exists p_req_write on public.requisicoes;
create policy p_req_write on public.requisicoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_reqit_read on public.requisicao_itens;
create policy p_reqit_read on public.requisicao_itens for select to authenticated using (true);
drop policy if exists p_reqit_write on public.requisicao_itens;
create policy p_reqit_write on public.requisicao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_cot_read on public.cotacoes;
create policy p_cot_read on public.cotacoes for select to authenticated using (true);
drop policy if exists p_cot_write on public.cotacoes;
create policy p_cot_write on public.cotacoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_cotit_read on public.cotacao_itens;
create policy p_cotit_read on public.cotacao_itens for select to authenticated using (true);
drop policy if exists p_cotit_write on public.cotacao_itens;
create policy p_cotit_write on public.cotacao_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_ped_read on public.pedidos_compra;
create policy p_ped_read on public.pedidos_compra for select to authenticated using (true);
drop policy if exists p_ped_write on public.pedidos_compra;
create policy p_ped_write on public.pedidos_compra for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_pedit_read on public.pedido_itens;
create policy p_pedit_read on public.pedido_itens for select to authenticated using (true);
drop policy if exists p_pedit_write on public.pedido_itens;
create policy p_pedit_write on public.pedido_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos'));

drop policy if exists p_rec_read on public.recebimentos;
create policy p_rec_read on public.recebimentos for select to authenticated using (true);
drop policy if exists p_rec_write on public.recebimentos;
create policy p_rec_write on public.recebimentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_recit_read on public.recebimento_itens;
create policy p_recit_read on public.recebimento_itens for select to authenticated using (true);
drop policy if exists p_recit_write on public.recebimento_itens;
create policy p_recit_write on public.recebimento_itens for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_est_read on public.estoque_movimentos;
create policy p_est_read on public.estoque_movimentos for select to authenticated using (true);
drop policy if exists p_est_write on public.estoque_movimentos;
create policy p_est_write on public.estoque_movimentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'suprimentos') or public.has_role(auth.uid(),'engenheiro'));

-- ====== FINANCEIRO ======
drop policy if exists p_pc_read on public.plano_contas;
create policy p_pc_read on public.plano_contas for select to authenticated using (true);
drop policy if exists p_pc_write on public.plano_contas;
create policy p_pc_write on public.plano_contas for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

drop policy if exists p_cc_read on public.centros_custo;
create policy p_cc_read on public.centros_custo for select to authenticated using (true);
drop policy if exists p_cc_write on public.centros_custo;
create policy p_cc_write on public.centros_custo for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

drop policy if exists p_cb_read on public.contas_bancarias;
create policy p_cb_read on public.contas_bancarias for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));
drop policy if exists p_cb_write on public.contas_bancarias;
create policy p_cb_write on public.contas_bancarias for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

drop policy if exists p_lanc_read on public.lancamentos;
create policy p_lanc_read on public.lancamentos for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_lanc_write on public.lancamentos;
create policy p_lanc_write on public.lancamentos for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'financeiro'));

-- ====== PESSOAL ======
drop policy if exists p_col_read on public.colaboradores;
create policy p_col_read on public.colaboradores for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_col_write on public.colaboradores;
create policy p_col_write on public.colaboradores for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'));

drop policy if exists p_aloc_read on public.alocacoes;
create policy p_aloc_read on public.alocacoes for select to authenticated using (true);
drop policy if exists p_aloc_write on public.alocacoes;
create policy p_aloc_write on public.alocacoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_ponto_read on public.ponto;
create policy p_ponto_read on public.ponto for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));
drop policy if exists p_ponto_write on public.ponto;
create policy p_ponto_write on public.ponto for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_folha_read on public.folha_pagamento;
create policy p_folha_read on public.folha_pagamento for select to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh') or public.has_role(auth.uid(),'financeiro'));
drop policy if exists p_folha_write on public.folha_pagamento;
create policy p_folha_write on public.folha_pagamento for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'rh'));

-- ====== QUALIDADE ======
drop policy if exists p_chk_read on public.checklists_modelo;
create policy p_chk_read on public.checklists_modelo for select to authenticated using (true);
drop policy if exists p_chk_write on public.checklists_modelo;
create policy p_chk_write on public.checklists_modelo for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade'));

drop policy if exists p_insp_read on public.inspecoes;
create policy p_insp_read on public.inspecoes for select to authenticated using (true);
drop policy if exists p_insp_write on public.inspecoes;
create policy p_insp_write on public.inspecoes for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_nc_read on public.nao_conformidades;
create policy p_nc_read on public.nao_conformidades for select to authenticated using (true);
drop policy if exists p_nc_write on public.nao_conformidades;
create policy p_nc_write on public.nao_conformidades for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'));

drop policy if exists p_ens_read on public.ensaios;
create policy p_ens_read on public.ensaios for select to authenticated using (true);
drop policy if exists p_ens_write on public.ensaios;
create policy p_ens_write on public.ensaios for all to authenticated
  using (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'))
  with check (public.has_role(auth.uid(),'admin') or public.has_role(auth.uid(),'qualidade') or public.has_role(auth.uid(),'engenheiro'));
