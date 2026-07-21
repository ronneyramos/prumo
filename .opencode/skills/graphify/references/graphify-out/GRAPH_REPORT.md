# Graph Report - .opencode\skills\graphify\references  (2026-07-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 271 nodes · 645 edges · 32 communities (18 shown, 14 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.78)
- Token cost: 1,605 input · 357 output

## Graph Freshness
- Built from commit: `f96cc5f1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Collaborator and EAP Management
- Report and Document Generation
- Data Loading Utilities
- Database Persistence Layer
- Progress Tracking and Sync
- Authentication and Main Entry
- Project and Measurement Pages
- User Access and Navigation
- Financial and Quality Modules
- Email Alert System
- Dashboard and UI Notifications
- Project and Plan Management
- Attendance and Time Tracking
- Financial Transaction Updates
- Budget and EAP Processing
- Inventory and Stock Management
- Branding and Assets
- Cache Management
- Batch Date Updates
- Measurement Updates
- Budget Persistence
- Excel Processing Library
- Data Analysis Library
- Image Processing Library
- Data Visualization Library
- Word Document Library
- Environment Configuration Library
- PDF Generation Library
- Web Interface Framework
- Database Client Library
- Legacy Excel Library

## God Nodes (most connected - your core abstractions)
1. `sb()` - 75 edges
2. `_df()` - 21 edges
3. `_empresa_id()` - 21 edges
4. `pagina_obras()` - 20 edges
5. `app()` - 20 edges
6. `pagina_pessoal()` - 19 edges
7. `pagina_suprimentos()` - 18 edges
8. `_init()` - 17 edges
9. `_obras_nomes()` - 15 edges
10. `pagina_financeiro()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `lancamento_delete()` --calls--> `sb()`  [INFERRED]
  sync.py → db.py
- `pagina_dev_panel()` --calls--> `_enviar_email()`  [INFERRED]
  main.py → alertas.py
- `pagina_suprimentos()` --calls--> `_enviar_email()`  [INFERRED]
  main.py → alertas.py
- `app()` --calls--> `sb()`  [INFERRED]
  main.py → db.py
- `_auth_login()` --calls--> `sb()`  [INFERRED]
  main.py → db.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Prumo ERP Technology Stack** — requirements_streamlit, requirements_supabase, requirements_pandas, requirements_plotly, prumo_erp_concept [INFERRED 0.80]

## Communities (32 total, 14 thin omitted)

### Community 0 - "Collaborator and EAP Management"
Cohesion: 0.09
Nodes (55): colaborador_atualizar(), colaborador_criar(), colaboradores_listar(), colmap_template_atualizar(), colmap_template_criar(), colmap_template_deletar(), colmap_templates_listar(), _df() (+47 more)

### Community 1 - "Report and Document Generation"
Cohesion: 0.13
Nodes (26): _estilos(), _fmt_brl(), gerar_bm(), gerar_folha_pagamento(), gerar_orcamento(), gerar_rdo(), gerar_rdo_docx(), gerar_relatorio_gerencial() (+18 more)

### Community 2 - "Data Loading Utilities"
Cohesion: 0.13
Nodes (22): _attr(), colaboradores_load(), estoque_movimentos_load(), estoque_saldo_load(), faltas_load(), insumos_load(), _iso_to_br(), lancamentos_load() (+14 more)

### Community 3 - "Database Persistence Layer"
Cohesion: 0.11
Nodes (21): _br_to_iso(), colaborador_save(), eap_load(), eap_save_from_orcamento(), eap_update_datas(), _empresa_id(), medicao_itens_save(), medicao_save() (+13 more)

### Community 4 - "Progress Tracking and Sync"
Cohesion: 0.10
Nodes (20): eap_save_all_progresso(), eap_update_progresso(), lancamento_delete(), medicao_delete(), medicao_itens_load(), medicao_ultimo_pct(), obra_delete(), _parse_fotos() (+12 more)

### Community 5 - "Authentication and Main Entry"
Cohesion: 0.15
Nodes (12): _auth_login(), _dados_obras_dash(), _dev_log(), _norm_col(), _obras_validas(), pagina_dev_panel(), _parse_num_br(), Filtra apenas obras que têm SB_ID (UUID válido no Supabase). (+4 more)

### Community 6 - "Project and Measurement Pages"
Cohesion: 0.26
Nodes (14): _exibir_oxr(), _obra_uuid(), _obra_valida(), _obras_nomes(), pagina_medicao(), pagina_orcado_realizado(), pagina_orcamento(), pagina_rdo() (+6 more)

### Community 7 - "User Access and Navigation"
Cohesion: 0.22
Nodes (13): app(), _apply_css(), _obras_filtradas(), pagina_admin(), pagina_pessoal(), pagina_portal_contratante(), _pode(), _pos_login_choice() (+5 more)

### Community 8 - "Financial and Quality Modules"
Cohesion: 0.31
Nodes (13): _carregar_obras_service(), _export_excel(), _init(), _next_id(), pagina_financeiro(), pagina_qualidade(), pagina_suprimentos(), DataFrame (+5 more)

### Community 9 - "Email Alert System"
Cohesion: 0.25
Nodes (10): _enviar_email(), enviar_resumo_alertas(), _fmt(), DataFrame, Sistema de alertas por email para o ERP MBR Engenharia. Envia notificações via G, Monta o HTML e envia o email de resumo de alertas., Envia email via Gmail SMTP. Retorna True se enviou com sucesso., Verifica todos os alertas e retorna dict com listas de itens críticos.     Não e (+2 more)

### Community 10 - "Dashboard and UI Notifications"
Cohesion: 0.27
Nodes (11): _dash_alert_banner(), _exibir_orcamento_processado(), _fmt(), _normalizar_orc_data(), _notify(), pagina_dashboard(), pagina_eap(), Agenda um toast para aparecer APÓS o próximo st.rerun(). (+3 more)

### Community 11 - "Project and Plan Management"
Cohesion: 0.40
Nodes (6): _limite_obras_atingido(), pagina_obras(), _plano_info(), Retorna o UUID (SB_ID) de uma linha a partir do ID inteiro., Retorna dicionário com plano da empresa atual., _sb_id()

### Community 12 - "Attendance and Time Tracking"
Cohesion: 0.33
Nodes (6): _colaborador_uuid_por_nome(), falta_save(), ponto_registro_save(), Busca UUID do colaborador pelo nome., Registra uma falta/abono no ponto. Retorna UUID ou None., Registra o ponto batido do dia (entrada/almoço/saída) de um colaborador. Retorna

### Community 13 - "Financial Transaction Updates"
Cohesion: 0.40
Nodes (5): lancamento_atualizar(), lancamento_save(), lancamento_status_update(), Cria ou atualiza um lançamento. Retorna UUID ou None., Atualiza apenas o status de um lançamento.

### Community 14 - "Budget and EAP Processing"
Cohesion: 0.40
Nodes (5): _limpar_col_num(), _nivel_eap(), _processar_orcamento(), Retorna profundidade hierárquica pelo nº de pontos: '1'→1, '1.1'→2, '1.1.1'→3., State machine linha-a-linha para classificar ETAPA vs ITEM.     Retorna (result

### Community 15 - "Inventory and Stock Management"
Cohesion: 0.50
Nodes (4): estoque_movimento_save(), _get_or_create_insumo(), Retorna UUID do insumo pelo nome, criando se não existir., Salva movimento de estoque (ENTRADA ou SAIDA).     dados: Insumo, Unidade, Tipo

### Community 16 - "Branding and Assets"
Cohesion: 0.67
Nodes (3): Prumo ERP - Software de Construção Civil, Construction Site Illustration, Prumo ERP Logo

## Knowledge Gaps
- **12 isolated node(s):** `streamlit`, `supabase`, `pandas`, `plotly`, `reportlab` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sb()` connect `Collaborator and EAP Management` to `Data Loading Utilities`, `Database Persistence Layer`, `Progress Tracking and Sync`, `Authentication and Main Entry`, `User Access and Navigation`, `Project and Plan Management`, `Financial Transaction Updates`, `Batch Date Updates`, `Budget Persistence`?**
  _High betweenness centrality (0.327) - this node is a cross-community bridge._
- **Why does `pagina_pessoal()` connect `User Access and Navigation` to `Collaborator and EAP Management`, `Authentication and Main Entry`, `Project and Measurement Pages`, `Financial and Quality Modules`, `Dashboard and UI Notifications`, `Project and Plan Management`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `_empresa_id()` connect `Database Persistence Layer` to `Data Loading Utilities`, `Progress Tracking and Sync`, `Project and Plan Management`, `Attendance and Time Tracking`, `Financial Transaction Updates`, `Inventory and Stock Management`, `Budget Persistence`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `sb()` (e.g. with `app()` and `_auth_login()`) actually correct?**
  _`sb()` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `pagina_obras()` (e.g. with `sb_admin()` and `_fmt()`) actually correct?**
  _`pagina_obras()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `streamlit`, `supabase`, `pandas` to the rest of the system?**
  _12 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Collaborator and EAP Management` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._