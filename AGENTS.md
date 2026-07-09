# AGENTS.md — ERP MBR (Prumo ERP)

## Última sessão: 08/07/2026

### Status geral
- ✅ **Semana 2 (Orçado x Realizado)** — fluxo básico + todos os 5 gaps implementados
- ✅ **Dashboard/Início** — layout refatorado com cards, KPIs coloridos, navegação rápida
- ❌ Pendente: testar com planilha real (usuário faz)

### Sessão atual (08/07 — 6ª rodada) — Dashboard Layout Polish

#### ✅ Implementado

**Dashboard/Início (`pagina_dashboard()`, `main.py:781`)**
- Alerta extraído para `_dash_alert_banner()` (`main.py:738`)
- Barra de navegação rápida `_dash_quick_nav()` com links para Obras, Financeiro, Suprimentos, Pessoal, Orçamento (`main.py:768`)
- KPIs com cores diferenciadas por tipo via `.dash-kpi-row` CSS
- Cards visuais (`.dash-card` + `.dash-card-header`) agrupando: Avanço Físico/Distribuição, Medição/Custos, Status Obras, Fluxo de Caixa, Alertas/Pessoal, mais 4 cards na tab Por Obra
- Estados vazios compactos (`.dash-empty`) substituindo `st.info`

**Todos os 5 gaps da Semana 2 concluídos (sessão anterior):**
| Gap | Implementação |
|-----|--------------|
| Mapeamento de colunas | Migration `20260712200000` + tabela `orcamento_colmap_templates` + CRUD em `db.py:267-283` + expander salvar/carregar |
| Importar composições | `tab_comp` no processamento + marcação de composições + upload manual de insumos + `sync.orcamento_save()` com FK resolvida |
| Tratamento de erros | `_processar_orcamento()` retorna `(resultado, avisos)` + validações de colunas/números |
| Alocar Custos à EAP | `tab_alocar` no Financeiro com selectbox por linha + `lancamento_atualizar()` |
| Código duplicado (OXR) | Extração de `_exibir_oxr()` (~160 linhas) compartilhada por `pagina_orcado_realizado()` e `tab_oxr` |

**Correções sistêmicas (sessões anteriores):**
- `sb()` sempre usa service_key (bypass RLS)
- `_init()` só marca `_erp_init_done` após todas as cargas
- `SB_ID` padronizado como `None` em 11 locais
- `_obras_nomes()` filtra obras sem SB_ID
- Migrações SQL aplicadas via SQL Editor

### Stack
- Streamlit (`main.py` em `C:\Users\ronne\Desktop\erp-construcao\streamlit`)
- Supabase `zotruhqntdfpdhtsmjbb` — REST API (porta 5432 bloqueada)
- `http://localhost:8521`

### Links úteis
- Supabase Dashboard: https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb
- SQL Editor: https://supabase.com/dashboard/project/zotruhqntdfpdhtsmjbb/sql
