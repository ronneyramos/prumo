# AGENTS.md — ERP MBR (Prumo ERP)

## Última sessão: 09/07/2026

### Status geral
- ✅ **Mode selector** — Login → Escolha (App / Dev) para admin; usuários normais vão direto pro App
- ✅ **Orçamento** — importação funcional, EAP gerada no banco
- ✅ **Orçado x Realizado** — categorias agrupadas, sub-itens em expander, gráficos horizontais
- ✅ **Dashboard** — 4 KPIs sem truncamento, CSS ajustado
- ❌ Pendente: testar com planilha real (usuário faz)

### Sessão atual (09/07 — Mode selector + Orçamento fixes)

#### ✅ Implementado

**Tela de escolha pós-login (`_pos_login_choice()`)**
- Admin vê duas opções: "🏗️ Acessar App ERP" ou "🛠️ Painel do Desenvolvedor"
- Usuários normais vão direto para o App
- Botão "⚡ Pular login (dev)" na tela de login para testes

**Orçamento — Parâmetros com borda**
- `st.container(border=True)` ao redor de "Parâmetros do Orçamento" e "Importar Planilha"
- Indentação corrigida (todos os campos estavam fora do expander)
- Colunas duplicadas no cabeçalho agora são renomeadas automaticamente (`nome_n`)

**Orçamento — Bugfixes**
- `_empresa_id` parâmetro sombreava função módulo em `orcamento_load()` e `eap_load()` → sempre retornavam `[]`. Renomeado para `_cid`.
- Cache limpo (`sync.orcamento_load.clear()`) após salvar orçamento
- `EAP save`: `codigo` vazio vira `ORD_NNNN` para evitar unique constraint violation
- `_normalizar_orc_data()` — retrofits `"tipo"` em dados de sessão antigos

**Orçado x Realizado (`_exibir_oxr()`)**
- Itens agrupados por nível hierárquico (`eap_codigo` → `_nivel` / `_pai`)
- Mostra só categorias (nível 1) em containers com expander "📂 N sub-itens"
- Gráficos: horizontais (`orientation="h"`), labels legíveis, escala de cores limpa
- Erro slider (int/float) corrigido com `int(pct_at)`

**Dashboard**
- KPIs reduzidos de 5 para 4 colunas (mais espaço)
- CSS `overflow:visible` nos valores das métricas (números cortados)
- Links rápidos da dashboard restaurados na sidebar (sempre visíveis)

**Developer Panel (sessão anterior)**
- Migration `13_MIGRATION_DEV_PANEL.sql` aplicada
- 7 tabs: Empresas, Usuários, Parcerias, Logs, Config, SQL Console, Sistema

**Performance (sessão anterior)**
- `@st.cache_data(ttl=60)` em todos os `*_load()`
- `use_container_width` → `width`

### Stack
- Streamlit (`main.py` em `C:\Users\ronne\Desktop\erp-construcao\streamlit`)
- Supabase `zotruhqntdfpdhtsmjbb` — REST API (porta 5432 bloqueada)
- `http://localhost:8521`

### Links úteis
- Supabase Dashboard: https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb
- SQL Editor: https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
