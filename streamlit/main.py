import os
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
import pandas as pd
from datetime import date, datetime, time, timedelta
import io
import unicodedata
import importlib
import sync
importlib.reload(sync)
import db
importlib.reload(db)

st.set_page_config(page_title="Prumo ERP", layout="wide", page_icon="🏗️",
                   initial_sidebar_state="expanded")

# ── Inicialização do estado ───────────────────────────────────────────────────

def _is_dev() -> bool:
    return os.path.exists(os.path.join(os.path.dirname(__file__), ".env"))

def _supabase_ok() -> bool:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    return bool(url and key and "SEU_PROJETO" not in url)


def _sb_id(df: pd.DataFrame, int_id) -> str | None:
    """Retorna o UUID (SB_ID) de uma linha a partir do ID inteiro."""
    if "SB_ID" not in df.columns:
        return None
    row = df[df["ID"] == int_id]
    if not len(row):
        return None
    v = row.iloc[0]["SB_ID"]
    return str(v) if (v and str(v) not in ("nan", "None", "")) else None


def _obra_uuid(obra_nome: str) -> str | None:
    """Retorna o UUID da obra pelo nome. Retorna None se nome inválido ou não encontrado."""
    if not _obra_valida(obra_nome):
        return None
    df = st.session_state.obras
    nome_clean = obra_nome.strip()
    rows = df[df["Nome"].str.strip() == nome_clean]
    if rows.empty:
        rows = df[df["Nome"].str.strip().str.lower() == nome_clean.lower()]
    if rows.empty:
        rows = df[df["Nome"].str.contains(nome_clean, case=False, na=False)]
    return _sb_id(df, rows["ID"].iloc[0]) if len(rows) else None


def _carregar_obras_service():
    """Carrega obras via service_role (bypassa RLS). Retorna DataFrame ou None."""
    try:
        from db import sb_admin
        admin = sb_admin()
        if not admin: return None
        r = admin.table("obras").select("*").is_("deleted_at", None).order("created_at").execute()
        df = pd.DataFrame(r.data) if r.data else pd.DataFrame()
        if df.empty: return None
        rows = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            _id_raw = getattr(row, "id", None)
            _sb_id  = str(_id_raw) if _id_raw else None
            rows.append({
                "ID": i, "SB_ID": _sb_id,
                "Nome": getattr(row, "nome", ""), "Tipo": getattr(row, "tipo", ""),
                "Cliente": getattr(row, "cliente", ""),
                "CNPJ Cliente": getattr(row, "cnpj_cliente", ""),
                "Endereço": getattr(row, "endereco", ""),
                "Valor Contrato (R$)": float(getattr(row, "valor_contrato", 0) or 0),
                "BDI (%)": round(float(getattr(row, "bdi", 0.25) or 0.25) * 100, 2),
                "Início": "", "Término": "",
                "% Físico": int(float(getattr(row, "pct_fisico", 0) or 0)),
                "Status": getattr(row, "status", "Planejamento"),
                "Responsável": getattr(row, "responsavel", ""),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"[_carregar_obras_service] ERRO: {e}")
        return None

def _load_supabase_data(emp_id: str) -> bool:
    """Carrega todos os datasets do Supabase em série."""
    _cargas = [
        ("obras",          sync.obras_load,          emp_id),
        ("contas_pagar",   sync.lancamentos_load,    "PAGAR", emp_id),
        ("contas_receber", sync.lancamentos_load,    "RECEBER", emp_id),
        ("funcionarios",   sync.colaboradores_load,  emp_id),
        ("ncs",            sync.ncs_load,            emp_id),
        ("medicoes",       sync.medicoes_load,      emp_id),
        ("ponto",          sync.faltas_load,         emp_id),
        ("ponto_registros", sync.ponto_registro_load, emp_id),
        ("rdo",            sync.rdo_load,             emp_id),
        ("insumos",        sync.insumos_load,         emp_id),
        ("estoque",        sync.estoque_saldo_load,   emp_id),
        ("movimentacoes",  sync.estoque_movimentos_load, emp_id),
    ]
    erros = []
    for chave, fn, *args in _cargas:
        try:
            st.session_state[chave] = fn(*args)
        except Exception as _e:
            print(f"[_init] Erro em {chave}: {_e}")
            erros.append(chave)
    return not erros


def _init():
    _first = not st.session_state.get("_erp_init_done")

    # ── Carrega do Supabase (paralelo) na primeira vez ───────────────────────
    if _first:
        emp_id = st.session_state.get("empresa_id", "")
        ok = True
        if _supabase_ok():
            ok = _load_supabase_data(emp_id)
        if ok:
            st.session_state._erp_init_done = True

    # ── Se obras ainda está vazio, tenta fallback service_role ────────────────
    if st.session_state.get("obras", pd.DataFrame()).empty:
        df = _carregar_obras_service()
        if df is not None:
            st.session_state.obras = df

    # ── Fallback: tabelas que ainda não têm integração Supabase ───────────────
    if "obras" not in st.session_state:
        st.session_state.obras = pd.DataFrame(columns=["ID","SB_ID","Nome","Tipo","Cliente","CNPJ Cliente","Endereço","Valor Contrato (R$)","BDI (%)","Início","Término","% Físico","Status","Responsável"])
    if "contas_pagar" not in st.session_state:
        st.session_state.contas_pagar = pd.DataFrame(columns=["ID","SB_ID","Obra","Fornecedor","Descrição","Categoria","Valor (R$)","Vencimento","Status","NF","Forma Pag."])
    if "contas_receber" not in st.session_state:
        st.session_state.contas_receber = pd.DataFrame(columns=["ID","SB_ID","Obra","Cliente","Descrição","Valor (R$)","Vencimento","Status"])
    if "funcionarios" not in st.session_state:
        st.session_state.funcionarios = pd.DataFrame(columns=["ID","SB_ID","Nome","Cargo","Tipo Contrato","Obra","Salário (R$)","Admissão","Situação"])
    if "ncs" not in st.session_state:
        st.session_state.ncs = pd.DataFrame(columns=["ID","SB_ID","Data Abertura","Obra","Descrição","Gravidade","Responsável","Status","Prazo","Ação Corretiva"])

    # ── Módulos com fallback para DataFrame vazio ────────────────────────────
    if "requisicoes" not in st.session_state:
        try:
            st.session_state.requisicoes = sync.requisicoes_load()
        except Exception:
            st.session_state.requisicoes = pd.DataFrame(columns=[
                "ID","SB_ID","Data","Obra","Insumo","Quantidade",
                "Unidade","Status","Solicitante","Observação","Aprovado Por","Data Aprovação"
            ])
    if "ponto" not in st.session_state:
        st.session_state.ponto = pd.DataFrame(columns=["ID","Data","Funcionário","Obra","Tipo","Observação"])
    if "ponto_registros" not in st.session_state:
        st.session_state.ponto_registros = pd.DataFrame(columns=[
            "ID","SB_ID","Data","Funcionário","Obra","Entrada","Saída Almoço",
            "Retorno Almoço","Saída","Horas Normais","Horas Extras","Observação"
        ])
    if "medicoes" not in st.session_state:
        st.session_state.medicoes = pd.DataFrame(columns=["ID","Data","Obra","Período","% Medido","Valor Medido (R$)","Observação"])
    if "checklists" not in st.session_state:
        st.session_state.checklists = pd.DataFrame({
            "ID": list(range(1,9)),
            "Data": ["10/06/2026","12/06/2026","15/06/2026","18/06/2026","20/06/2026","22/06/2026","23/06/2026","24/06/2026"],
            "Obra": ["Residencial Beira Mar"]*4+["Comercial Centro"]*4,
            "Item Inspecionado": ["Concretagem pilar P-12","Alvenaria 1º pav. bloco A","Revestimento fachada","Inst. elétrica quadro Q-01","Fundação sapata S-05","Estrutura metálica nível 2","Impermeabilização reservatório","Inst. hidrossanitárias"],
            "Responsável": ["Eng. Carlos","Mestre Paulo","Eng. Carlos","Eng. Carlos","Eng. Ana","Eng. Ana","Eng. Ana","Eng. Ana"],
            "Resultado": ["Aprovado","Aprovado","Reprovado","Aprovado","Aprovado","Aprovado","Reprovado","Aprovado"],
            "Observação": ["Resistência atingida","Prumo dentro da tolerância","Rachadura detectada","Aterramento OK","Armadura correta","Soldas conferidas","Falha de continuidade","Estanqueidade OK"],
        })
    if "orcamento_df"       not in st.session_state: st.session_state.orcamento_df       = None
    if "orcamento_nome"     not in st.session_state: st.session_state.orcamento_nome     = None
    if "orcamento_por_obra" not in st.session_state: st.session_state.orcamento_por_obra = {}
    if "rdo" not in st.session_state:
        st.session_state.rdo = pd.DataFrame(columns=["ID","SB_ID","Obra","Data","Responsável","Clima Manhã","Clima Tarde","Efetivo Total","Atividades","Ocorrências","Equipamentos","Status Dia","Observações"])

    # ── Migrações e alertas: executam só uma vez por sessão ──────────────────
    if _first:
        if "Tipo Contrato" not in st.session_state.funcionarios.columns:
            st.session_state.funcionarios.insert(3, "Tipo Contrato", "CLT")
        if "Forma Pag." not in st.session_state.contas_pagar.columns:
            st.session_state.contas_pagar["Forma Pag."] = "—"
        if "Categoria" not in st.session_state.contas_pagar.columns:
            st.session_state.contas_pagar["Categoria"] = "Materiais"

        try:
            import alertas as _alrt
            _nc_df = st.session_state.get("ncs", pd.DataFrame())
            _al = _alrt.verificar_alertas(
                st.session_state.get("contas_pagar", pd.DataFrame()),
                _nc_df,
                st.session_state.get("estoque", pd.DataFrame()),
            )
            st.session_state["_alertas_cache"] = _al
        except Exception:
            st.session_state["_alertas_cache"] = {"vencimentos": [], "ncs_abertas": [], "estoque_critico": []}
        st.session_state["_alertas_verificados"] = True


def _obras_validas(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra apenas obras que têm SB_ID (UUID válido no Supabase)."""
    if df.empty or "SB_ID" not in df.columns:
        return df
    return df[df["SB_ID"].notna() & (df["SB_ID"] != "")]

def _obras_nomes(extra: list | None = None) -> list:
    """Retorna lista de nomes de obras visíveis ao usuário; nunca vazia (evita crash em selectbox)."""
    df = st.session_state.get("obras", pd.DataFrame())
    df = _obras_validas(df)
    if not df.empty and "usuario_role" in st.session_state:
        df = _obras_filtradas(df)
    nomes = df["Nome"].tolist() if not df.empty else []
    nomes = nomes + (extra or [])
    return nomes if nomes else ["(nenhuma obra — cadastre em Obras)"]


def _obra_valida(nome: str) -> bool:
    """Verifica se o nome de obra é real (não é o placeholder vazio)."""
    return bool(nome) and not nome.startswith("(")


def _fmt(v):
    return f"R$ {_to_num(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")

def _notify(msg: str, icon: str = "✅"):
    """Agenda um toast para aparecer APÓS o próximo st.rerun()."""
    st.session_state["_toast_pending"] = (msg, icon)

def _show_toast():
    """Chama no início de cada página para exibir o toast agendado."""
    if "_toast_pending" in st.session_state:
        msg, icon = st.session_state.pop("_toast_pending")
        st.toast(msg, icon=icon)

def _sem_id(df: pd.DataFrame) -> pd.DataFrame:
    """Remove colunas ID e SB_ID do DataFrame se existirem."""
    return df.drop(columns=[c for c in ["ID", "SB_ID"] if c in df.columns], errors="ignore")


def _uniq(series) -> list:
    """Retorna lista ordenada de valores únicos não-nulos de uma Series."""
    return sorted([v for v in series.unique() if pd.notna(v) and str(v).strip()])

def _to_num(v) -> float:
    """Converte para float aceitando strings R$ 58.000,00 ou numéricos."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return 0.0 if pd.isna(v) else float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def _next_id(df):
    return int(df["ID"].max()) + 1 if len(df) > 0 else 1


def _tabela_clicavel(df: pd.DataFrame, colunas_exibir: list | None = None,
                      key: str = "tbl", height="auto", formatters: dict | None = None,
                      selection_mode: str = "single-row"):
    """
    Mostra uma tabela onde clicar numa linha a seleciona (sem dropdown separado).
    Retorna a Series da primeira linha selecionada (com TODAS as colunas do df original)
    em 'single-row', ou None se nada selecionado.
    Em 'multi-row' retorna um DataFrame com as linhas selecionadas (vazio se nada).

    formatters: dict opcional {coluna: função} aplicado apenas na exibição.
    """
    if df.empty:
        st.info("Nenhum registro encontrado.")
        return None if selection_mode == "single-row" else pd.DataFrame()
    view = df[colunas_exibir].copy() if colunas_exibir else df.copy()
    if formatters:
        for col, fn in formatters.items():
            if col in view.columns:
                view[col] = view[col].apply(fn)
    caption = "💡 Selecione uma ou mais linhas para ação em lote." if selection_mode == "multi-row" else "💡 Clique em uma linha para editar."
    st.caption(caption)
    event = st.dataframe(
        view, width='stretch', hide_index=True, height=height,
        on_select="rerun", selection_mode=selection_mode, key=key,
    )
    sel_rows = (event.get("selection") or {}).get("rows") or [] if event else []
    if selection_mode == "multi-row":
        return df.iloc[sel_rows] if sel_rows else pd.DataFrame()
    return df.iloc[sel_rows[0]] if sel_rows else None


def _export_excel(df: pd.DataFrame, nome_arquivo: str = "dados.xlsx") -> bytes:
    import io
    try:
        import openpyxl  # noqa
        engine = "openpyxl"
    except ImportError:
        engine = "xlsxwriter"
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
    return buf.getvalue()


# ── Autenticação e controle de acesso ────────────────────────────────────────

def _pos_login_choice():
    """Tela pós-login: escolher entre App ERP ou Painel do Desenvolvedor."""
    st.markdown("""<style>
        :root { --primary-color: #1B3A5E !important; }
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #EDE8DF !important; }
        .main .block-container { max-width: 800px !important; padding-top: 6vh !important; }
    </style>""", unsafe_allow_html=True)
    _usr = st.session_state.get("usuario", {})
    st.markdown(f"""
    <div style='text-align:center;margin-bottom:0.5rem;'>
        <div style='font-size:1.8rem;font-weight:900;color:#1B3A5E;letter-spacing:-0.5px;line-height:1;'>
            PRUMO<span style='font-size:0.9rem;font-weight:600;color:#2AACA0;margin-left:4px;vertical-align:super;'>ERP</span>
        </div>
        <div style='font-size:0.85rem;color:#6B7280;margin-top:6px;font-weight:500;letter-spacing:1px;text-transform:uppercase;'>
            Software de Construção Civil
        </div>
    </div>
    <div style='text-align:center;margin:1.5rem 0 0.3rem;font-size:0.95rem;color:#4B5563;'>
        Olá, <strong>{_usr.get("nome","")}</strong>! O que deseja acessar?
    </div>
    """, unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div style='background:white;border-radius:16px;padding:2rem 1.5rem;text-align:center;
                    box-shadow:0 2px 20px rgba(27,58,94,0.08);border:2px solid transparent;
                    transition:all 0.2s;margin-bottom:0.5rem;'>
            <div style='font-size:3rem;margin-bottom:0.8rem;'>🏗️</div>
            <div style='font-size:1.2rem;font-weight:700;color:#1B3A5E;'>App ERP</div>
            <div style='font-size:0.8rem;color:#6B7280;margin-top:6px;'>Obras, Financeiro,<br>Suprimentos e mais</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar App", key="escolha_app", type="primary", use_container_width=True):
            st.session_state.modo = "app"
            st.session_state.pagina_atual = "Principal"
            st.rerun()
    with c2:
        st.markdown("""
        <div style='background:white;border-radius:16px;padding:2rem 1.5rem;text-align:center;
                    box-shadow:0 2px 20px rgba(27,58,94,0.08);border:2px solid transparent;
                    transition:all 0.2s;margin-bottom:0.5rem;'>
            <div style='font-size:3rem;margin-bottom:0.8rem;'>🛠️</div>
            <div style='font-size:1.2rem;font-weight:700;color:#1B3A5E;'>Desenvolvedor</div>
            <div style='font-size:0.8rem;color:#6B7280;margin-top:6px;'>SQL Console, Logs,<br>Config, Debug</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar Dev", key="escolha_dev", type="secondary", use_container_width=True):
            st.session_state.modo = "dev"
            st.session_state.pagina_atual = "Desenvolvedor"
            st.rerun()


def _auth_login():
    """Tela de login fiel ao mockup: fundo bege, split, imagem."""
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    st.markdown("""<style>
        :root { --primary-color: #1B3A5E !important; }
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #EDE8DF !important; }
        .main .block-container {
            max-width: 1200px !important; padding-top: 3vh !important;
            padding-left: 1.5rem !important; padding-right: 1.5rem !important;
        }
        /* Inputs com borda teal */
        [data-testid="stTextInput"] input {
            border-radius: 8px !important;
            border: 1.5px solid #2AACA0 !important;
            font-size: 14px !important; background: #FFFFFF !important;
            padding: 12px 14px !important; color: #1B3A5E !important;
        }
        [data-testid="stTextInput"] input::placeholder { color: #A8B0BB !important; }
        [data-testid="stTextInput"] input:focus {
            border-color: #2AACA0 !important;
            box-shadow: 0 0 0 3px rgba(42,172,160,0.15) !important;
            outline: none !important;
        }
        [data-testid="InputInstructions"] { display: none !important; }
        /* Botão azul escuro */
        [data-testid="stFormSubmitButton"],
        [data-testid="stFormSubmitButton"] button {
            background: #1B3A5E !important;
            border: none !important;
            border-radius: 8px !important; font-weight: 800 !important;
            font-size: 15px !important; letter-spacing: 2px; text-transform: uppercase;
            box-shadow: 0 4px 14px rgba(27,58,94,0.25) !important;
            height: 48px !important;
            color: #FFFFFF !important;
        }
        [data-testid="stFormSubmitButton"]:hover,
        [data-testid="stFormSubmitButton"]:hover button {
            background: #122A45 !important;
        }
        /* Card branco do formulário */
        [data-testid="stForm"] {
            background: #FFFFFF !important; border: none !important;
            border-radius: 12px !important; padding: 28px 28px 20px !important;
            box-shadow: 0 2px 24px rgba(27,58,94,0.09) !important;
            margin-bottom: 14px !important;
        }
        [data-testid="stTextInput"] { margin-bottom: 2px !important; }
        [data-testid="stSelectbox"] label { font-size: 12px !important; color: #6B7280 !important; }
        /* Colunas mesma altura */
        section[data-testid="stHorizontalBlock"] > div {
            display: flex; flex-direction: column;
        }
        /* Imagem preenche toda a coluna direita */
        .login-illus-wrap {
            border-radius: 16px; overflow: hidden; width: 100%;
            box-shadow: 0 2px 24px rgba(27,58,94,0.09);
            flex: 1; display: flex;
        }
        .login-illus-wrap img {
            width: 100%; flex: 1; display: block;
            object-fit: cover; object-position: center 30%;
        }
    </style>""", unsafe_allow_html=True)

    col_form, col_illus = st.columns([1, 1], gap="large")

    # ═══ COLUNA ESQUERDA — Logo + Form ═══════════════════════════════════════
    with col_form:
        # Logo oficial (Modelo 3)
        _logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.png")
        st.image(_logo_path, width=340)
        st.markdown('<div style="margin-bottom:1.2rem;"></div>', unsafe_allow_html=True)

        if st.session_state.auth_mode == "login":
            st.markdown("""
            <div style="margin-bottom:1.6rem;">
                <div style="font-size:1.55rem;font-weight:900;color:#1B3A5E;text-transform:uppercase;
                            letter-spacing:0.5px;line-height:1.15;">OLÁ, GESTOR!</div>
                <div style="font-size:0.9rem;font-weight:700;color:#1B3A5E;text-transform:uppercase;
                            opacity:0.55;margin-top:5px;letter-spacing:0.3px;">
                    ACESSE SUA CONTA DE CONSTRUÇÃO
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.form("form_login"):
                st.markdown('<p style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#6B7280;margin:0 0 6px;">E-MAIL DA OBRA</p>', unsafe_allow_html=True)
                email = st.text_input("email", placeholder="engenheiro@obra.com", label_visibility="collapsed")
                st.markdown('<p style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#6B7280;margin:14px 0 6px;">SENHA</p>', unsafe_allow_html=True)
                senha  = st.text_input("senha", type="password", label_visibility="collapsed")
                st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
                entrar = st.form_submit_button("ENTRAR", width='stretch')

            st.markdown("""
            <div style="text-align:center;margin-top:14px;">
                <p style="font-size:13px;color:#6B7280;margin:0 0 6px;">Esqueceu a senha?</p>
                <p style="font-size:13px;color:#6B7280;margin:0;">
                    Ainda não tem conta?
                    <strong style="color:#1B3A5E;cursor:pointer;">Solicite uma demonstração</strong>
                    ou <strong style="color:#1B3A5E;cursor:pointer;">cadastre-se.</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Criar conta gratuita →", key="btn_ir_cadastro", width='content'):
                st.session_state.auth_mode = "cadastro"
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            if _is_dev() and st.button("⚡ Pular login (dev)", key="btn_dev_skip", width='stretch', type="secondary"):
                import uuid
                st.session_state.usuario = {
                    "id":    str(uuid.uuid4()),
                    "email": "dev@prumo.local",
                    "nome":  "Desenvolvedor",
                }
                st.session_state.usuario_role  = "admin"
                st.session_state.empresa_id    = "00000000-0000-0000-0000-000000000001"
                st.session_state.usuario_obras_ids = []
                st.rerun()

            if entrar:
                if not email or not senha:
                    st.error("Preencha e-mail e senha.")
                    return
                try:
                    from db import sb
                    res  = sb().auth.sign_in_with_password({"email": email, "password": senha})
                    meta = res.user.user_metadata or {}
                    st.session_state.usuario = {
                        "id":    res.user.id,
                        "email": res.user.email,
                        "nome":  meta.get("full_name") or res.user.email,
                    }
                    role = None
                    try:
                        from db import sb_admin as _sb_adm
                        _adm = _sb_adm()
                        if _adm:
                            role_res = _adm.table("user_roles").select("role").eq("user_id", res.user.id).execute()
                        else:
                            role_res = sb().table("user_roles").select("role").eq("user_id", res.user.id).execute()
                        role = role_res.data[0]["role"] if (role_res and role_res.data) else None
                    except Exception:
                        role = None
                    if not role:
                        role = meta.get("role") or "admin"
                    st.session_state.usuario_role  = role
                    st.session_state.empresa_id    = meta.get("empresa_id") or "00000000-0000-0000-0000-000000000001"
                    try:
                        _st_res = sb().table("empresas").select("status").eq("id", st.session_state.empresa_id).execute()
                        _st_emp = _st_res.data[0]["status"] if _st_res.data else "ativo"
                    except Exception:
                        _st_emp = "ativo"
                    if _st_emp == "pendente":
                        st.error("⏳ **Sua conta está aguardando aprovação.** Entraremos em contato em breve.")
                        st.session_state.clear()
                        st.stop()
                    if _st_emp == "bloqueado":
                        st.error("🚫 **Sua conta foi bloqueada.** Entre em contato com o suporte.")
                        st.session_state.clear()
                        st.stop()
                    if role in ("engenheiro", "adm_obra", "suprimentos", "qualidade"):
                        try:
                            obras_res = sb().table("usuario_obras").select("obra_id").eq("user_id", res.user.id).execute()
                            st.session_state.usuario_obras_ids = [r["obra_id"] for r in (obras_res.data or [])]
                        except Exception:
                            st.session_state.usuario_obras_ids = []
                    else:
                        st.session_state.usuario_obras_ids = []
                    st.rerun()
                except Exception as _auth_e:
                    st.error(f"Login inválido: {_auth_e}")
                    print(f"[auth] erro login: {_auth_e}")

        else:  # ── Criar conta ──────────────────────────────────────────────
            st.markdown("""
            <div style="margin-bottom:1.4rem;">
                <div style="font-size:1.4rem;font-weight:900;color:#1B3A5E;text-transform:uppercase;">
                    CRIAR CONTA
                </div>
                <div style="font-size:0.85rem;color:#6B7280;margin-top:4px;">
                    30 dias gratuitos · sem cartão de crédito
                </div>
            </div>
            """, unsafe_allow_html=True)
            with st.form("form_cadastro"):
                nome_usuario = st.text_input("Nome completo", placeholder="Ex: João Silva")
                email_cad    = st.text_input("E-mail", placeholder="seu@email.com")
                senha_cad    = st.text_input("Senha", type="password", placeholder="Mínimo 6 caracteres")
                nome_empresa = st.text_input("Nome da empresa / construtora", placeholder="Ex: MBR Engenharia")
                cidade_cad   = st.text_input("Cidade", value="Fortaleza")
                estado_cad   = st.selectbox("Estado", ["CE","SP","RJ","MG","BA","PE","RS","SC","PR","GO","DF","AM","PA","MA","PI","RN","PB","AL","SE","ES","MT","MS","RO","AC","RR","AP","TO"])
                cadastrar    = st.form_submit_button("CRIAR CONTA", width='stretch')
            if st.button("← Voltar ao login", key="btn_voltar_login"):
                st.session_state.auth_mode = "login"
                st.rerun()
            if cadastrar:
                if not all([nome_usuario, email_cad, senha_cad, nome_empresa]):
                    st.error("Preencha todos os campos obrigatórios.")
                elif len(senha_cad) < 6:
                    st.error("Senha deve ter no mínimo 6 caracteres.")
                else:
                    try:
                        from db import sb
                        res_cad = sb().auth.sign_up({
                            "email": email_cad, "password": senha_cad,
                            "options": {"data": {"full_name": nome_usuario, "role": "admin"}},
                        })
                        if not res_cad.user:
                            st.error("Não foi possível criar o usuário. Tente outro e-mail.")
                        else:
                            user_id = res_cad.user.id
                            try:
                                rpc_res    = sb().rpc("registrar_empresa", {"p_nome_empresa": nome_empresa, "p_user_id": user_id}).execute()
                                empresa_id = rpc_res.data
                            except Exception as _e_rpc:
                                print(f"[cadastro] RPC: {_e_rpc}")
                                emp_res    = sb().table("empresas").insert({"nome": nome_empresa, "cidade": cidade_cad, "estado": estado_cad}).execute()
                                empresa_id = (emp_res.data[0] if emp_res.data else {}).get("id")
                            if empresa_id:
                                try:
                                    sb().table("empresas").update({"status": "pendente"}).eq("id", empresa_id).execute()
                                except Exception:
                                    pass
                                try:
                                    sb().rpc("seed_demo_data", {"p_empresa_id": str(empresa_id)}).execute()
                                except Exception as _e_seed:
                                    print(f"[cadastro] seed_demo_data: {_e_seed}")
                            st.success("""
                            ✅ **Cadastro realizado com sucesso!**
                            Sua conta está **aguardando aprovação** da administração.
                            Entraremos em contato em breve para liberar o acesso.
                            """)
                            st.session_state.auth_mode = "login"
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")
                        print(f"[cadastro] erro: {e}")

    with col_illus:
        import os as _os
        import base64 as _base64
        _img_path = _os.path.join(_os.path.dirname(__file__), "static", "building.png")
        with open(_img_path, "rb") as _f:
            _img_b64 = _base64.b64encode(_f.read()).decode()
        st.markdown(
            f'<div class="login-illus-wrap">'
            f'<img src="data:image/png;base64,{_img_b64}" alt="Prédio" />'
            f'</div>',
            unsafe_allow_html=True,
        )


def _role() -> str:
    """Retorna o perfil do usuário logado. Padrão 'admin' para sessões sem auth."""
    return st.session_state.get("usuario_role", "admin")


def _pode(modulos: list) -> bool:
    """True se o perfil atual tem acesso a pelo menos um dos módulos."""
    r = _role()
    if r == "admin":
        return True
    if r == "contratante":
        return any(m in ["portal"] for m in modulos)
    if "orcamento" in modulos:
        return False  # orçamento exclusivo para admin
    permissoes = {
        "engenheiro":  ["obras", "suprimentos", "ponto", "qualidade", "dashboard", "rdo"],
        "financeiro":  ["dashboard", "financeiro", "pessoal", "folha", "obras"],
        "adm_obra":    ["obras", "suprimentos", "ponto", "dashboard", "rdo"],
        "suprimentos": ["suprimentos"],
        "qualidade":   ["qualidade", "obras", "rdo"],
        "rh":          ["pessoal", "ponto", "folha"],
        "visualizador":["dashboard", "obras"],
        "gestor":      ["dashboard", "obras", "suprimentos", "financeiro", "pessoal",
                        "ponto", "folha", "qualidade", "rdo"],
    }
    permitidos = permissoes.get(r, [])
    return any(m in permitidos for m in modulos)


def _plano_info() -> dict:
    """Retorna dicionário com plano da empresa atual."""
    eid = st.session_state.get("empresa_id")
    if not eid:
        return {"plano_slug": "pro", "max_obras": 999, "max_usuarios": 999, "modulos": []}
    from db import sb
    try:
        res = sb().table("empresa_limites").select("*").eq("empresa_id", eid).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {"plano_slug": "pro", "max_obras": 999, "max_usuarios": 999, "modulos": []}

def _limite_obras_atingido() -> bool:
    info = _plano_info()
    max_o = info.get("max_obras", 999)
    if max_o >= 999:
        return False
    qtd = len(st.session_state.obras) if not st.session_state.obras.empty else 0
    return qtd >= max_o

def _obras_filtradas(df_obras: pd.DataFrame) -> pd.DataFrame:
    """Retorna só as obras que o usuário pode ver (filtra por usuario_obras_ids quando não é admin/financeiro)."""
    if _role() in ("admin", "financeiro", "visualizador"):
        return df_obras
    ids_permitidos = st.session_state.get("usuario_obras_ids", [])
    if not ids_permitidos:
        return df_obras.iloc[0:0]
    if "SB_ID" not in df_obras.columns:
        return df_obras
    return df_obras[df_obras["SB_ID"].isin(ids_permitidos)].reset_index(drop=True)


# ── Administração ────────────────────────────────────────────────────────────

def pagina_admin():
    if _role() != "admin":
        st.error("Acesso restrito a administradores.")
        return

    from db import sb, sb_admin
    _init()
    st.title("⚙️ Administração")

    tabs = st.tabs(["👥 Usuários", "🏢 Empresas", "💳 Assinatura"])

    # ===== TAB 1: USUÁRIOS =====================================================
    with tabs[0]:
        # ── Lista de usuários ──────────────────────────────────────────────────
        try:
            profiles = sb().table("profiles").select("id, nome, email, created_at").order("created_at").execute()
            roles_raw = sb().table("user_roles").select("user_id, role").execute()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

        df_profiles = pd.DataFrame(profiles.data or [])
        df_roles    = pd.DataFrame(roles_raw.data or [])

        # Monta dicionário user_id → [roles]
        _roles_map = df_roles.groupby("user_id")["role"].apply(list).to_dict()

        # ── Invite user ────────────────────────────────────────────────────────
        with st.expander("➕ Convidar novo usuário", expanded=False):
            with st.form("form_invite_user"):
                c1, c2 = st.columns(2)
                inv_nome  = c1.text_input("Nome completo *")
                inv_email = c2.text_input("E-mail *")
                inv_senha = c1.text_input("Senha *", type="password", placeholder="Mínimo 6 caracteres")
                inv_role  = c2.selectbox("Perfil *", ["admin","engenheiro","financeiro","suprimentos","qualidade","rh","visualizador","gestor","contratante"])
                inv_obras = st.multiselect(
                    "Obras com acesso (deixe vazio para todas)",
                    options=st.session_state.obras["SB_ID"].tolist() if not st.session_state.obras.empty else [],
                    format_func=lambda x: st.session_state.obras.loc[st.session_state.obras["SB_ID"] == x, "Nome"].iloc[0] if x in st.session_state.obras["SB_ID"].values else x,
                )
                submitted = st.form_submit_button("Criar usuário", type="primary", width='stretch')

                if submitted:
                    if not inv_nome or not inv_email or not inv_senha:
                        st.error("Preencha nome, e-mail e senha.")
                    else:
                        admin = sb_admin()
                        if not admin:
                            st.error("Chave service_role não configurada no .env")
                        else:
                            try:
                                resp = admin.auth.admin.create_user({
                                    "email": inv_email,
                                    "password": inv_senha,
                                    "email_confirm": True,
                                    "user_metadata": {"full_name": inv_nome},
                                })
                                uid = resp.user.id
                                # Atribui role (usa service_role para bypassar RLS)
                                try:
                                    admin.table("user_roles").insert({
                                        "user_id": uid,
                                        "role": inv_role,
                                    }).execute()
                                except Exception as role_e:
                                    st.warning(f"Usuário criado, mas falha ao atribuir role: {role_e}")
                                # Vincula obras (usa service_role)
                                if inv_obras:
                                    try:
                                        admin.table("usuario_obras").insert([
                                            {"user_id": uid, "obra_id": oid} for oid in inv_obras
                                        ]).execute()
                                    except Exception as obras_e:
                                        st.warning(f"Usuário criado, mas falha ao vincular obras: {obras_e}")
                                st.success(f"✅ Usuário {inv_nome} criado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao criar usuário: {e}")

        # ── Tabela de usuários ─────────────────────────────────────────────────
        # ── Diagnóstico: ver role no banco ─────────────────────────────────────
        if not df_profiles.empty:
            with st.expander("🔍 Diagnóstico: ver roles no banco", expanded=False):
                diag_user = st.selectbox("Selecione o usuário",
                    options=df_profiles["id"].tolist(),
                    format_func=lambda uid: f"{df_profiles[df_profiles['id']==uid]['nome'].iloc[0]} ({df_profiles[df_profiles['id']==uid]['email'].iloc[0]})",
                    key="diag_user")
                if st.button("Ver roles no banco", key="diag_roles"):
                    try:
                        _adm = sb_admin()
                        if _adm:
                            dr = _adm.table("user_roles").select("*").eq("user_id", diag_user).execute()
                            st.write("Registros em `user_roles`:", dr.data)
                        else:
                            dr = sb().table("user_roles").select("*").eq("user_id", diag_user).execute()
                            st.write("Registros em `user_roles`:", dr.data)
                    except Exception as _de:
                        st.error(f"Erro: {_de}")

        if df_profiles.empty:
            st.info("Nenhum usuário encontrado.")
        else:
            for _, row in df_profiles.iterrows():
                uid   = row["id"]
                roles = _roles_map.get(uid, [])
                with st.container(border=True):
                    cc1, cc2, cc3 = st.columns([3, 2, 3])
                    with cc1:
                        st.markdown(f"**{row.get('nome', '—')}**")
                        st.caption(row.get("email", ""))
                    with cc2:
                        st.write(" / ".join(roles) if roles else "—")
                    with cc3:
                        with st.popover("Editar permissões", icon="✏️"):
                            # Role
                            novas_roles = st.multiselect(
                                "Perfis",
                                ["admin","engenheiro","financeiro","suprimentos","qualidade","rh","visualizador","gestor","contratante"],
                                default=roles,
                                key=f"role_{uid}",
                            )
                            # Obras
                            if not st.session_state.obras.empty:
                                obras_atuais = []
                                try:
                                    res_o = sb().table("usuario_obras").select("obra_id").eq("user_id", uid).execute()
                                    obras_atuais = [r["obra_id"] for r in (res_o.data or [])]
                                except Exception:
                                    pass
                                novas_obras = st.multiselect(
                                    "Obras com acesso",
                                    options=st.session_state.obras["SB_ID"].tolist(),
                                    format_func=lambda x: st.session_state.obras.loc[st.session_state.obras["SB_ID"] == x, "Nome"].iloc[0],
                                    default=obras_atuais,
                                    key=f"obras_{uid}",
                                )
                            if st.button("Salvar", key=f"save_{uid}", type="primary"):
                                # Atualiza roles (usa service_role para bypassar RLS)
                                _adm = sb_admin()
                                if not _adm:
                                    st.error("service_role não configurada no .env")
                                else:
                                    removidas = [r for r in roles if r not in novas_roles]
                                    adicionadas = [r for r in novas_roles if r not in roles]
                                    try:
                                        for r in removidas:
                                            _adm.table("user_roles").delete().eq("user_id", uid).eq("role", r).execute()
                                        for r in adicionadas:
                                            _adm.table("user_roles").insert({"user_id": uid, "role": r}).execute()
                                    except Exception as e:
                                        st.error(f"Erro ao atualizar roles: {e}")
                                # Atualiza obras
                                try:
                                    sb().table("usuario_obras").delete().eq("user_id", uid).execute()
                                    if novas_obras:
                                        sb().table("usuario_obras").insert([
                                            {"user_id": uid, "obra_id": oid} for oid in novas_obras
                                        ]).execute()
                                except Exception as e:
                                    st.error(f"Erro ao atualizar obras: {e}")
                                st.success("Permissões atualizadas!")
                                st.rerun()

    # ===== TAB 2: EMPRESAS =====================================================
    with tabs[1]:
        try:
            empresas_data = sb().table("empresas").select("id, nome, status, created_at, aprovado_em, bloqueado_em").order("created_at").execute()
        except Exception as e:
            st.error(f"Erro ao carregar empresas: {e}")
            empresas_data = type("obj", (), {"data": []})()

        df_emp = pd.DataFrame(empresas_data.data or [])
        for _, row in df_emp.iterrows():
            eid    = row["id"]
            sts    = (row.get("status") or "pendente").lower()
            cor    = {"ativo": "#059669", "pendente": "#D97706", "bloqueado": "#DC2626"}.get(sts, "#6B7280")
            sts_label = {"ativo": "✅ Ativo", "pendente": "⏳ Pendente", "bloqueado": "🚫 Bloqueado"}.get(sts, sts)
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.markdown(f"**{row.get('nome', '—')}**")
                    st.caption(f"Cadastro: {row.get('created_at', '—')}")
                with cols[1]:
                    st.markdown(f"<span style='color:{cor};font-weight:700;'>{sts_label}</span>",
                                unsafe_allow_html=True)
                with cols[2]:
                    _agora = datetime.now(timezone.utc).isoformat()
                    if sts == "pendente":
                        if st.button("✅ Aprovar", key=f"aprovar_{eid}", type="primary", width='stretch'):
                            sb().table("empresas").update({"status": "ativo", "aprovado_em": _agora}).eq("id", eid).execute()
                            st.success(f"Empresa {row.get('nome')} aprovada!")
                            st.rerun()
                        if st.button("❌ Bloquear", key=f"bloquear_{eid}", width='stretch'):
                            sb().table("empresas").update({"status": "bloqueado", "bloqueado_em": _agora}).eq("id", eid).execute()
                            st.error(f"Empresa {row.get('nome')} bloqueada!")
                            st.rerun()
                    elif sts == "bloqueado":
                        if st.button("🔄 Reativar", key=f"reativar_{eid}", type="primary", width='stretch'):
                            sb().table("empresas").update({"status": "ativo", "aprovado_em": _agora}).eq("id", eid).execute()
                            st.success(f"Empresa {row.get('nome')} reativada!")
                            st.rerun()
                    elif sts == "ativo":
                        if st.button("🔒 Bloquear", key=f"bloq_{eid}", width='stretch'):
                            sb().table("empresas").update({"status": "bloqueado", "bloqueado_em": _agora}).eq("id", eid).execute()
                            st.error(f"Empresa {row.get('nome')} bloqueada!")
                            st.rerun()

    # ===== TAB 3: ASSINATURA ==================================================
    with tabs[2]:
        _init()
        info = _plano_info()
        planos = []
        try:
            p_res = sb().table("planos").select("*").order("preco_mensal").execute()
            planos = p_res.data or []
        except Exception:
            pass
        slug_atual = info.get("plano_slug", "pro")
        st.subheader(f"Plano atual: **{slug_atual.title()}**")

        col_planos = st.columns(len(planos) if planos else 1)
        for i, p in enumerate(planos):
            with col_planos[i]:
                ativo = p["slug"] == slug_atual
                borda = "2px solid #059669" if ativo else "1px solid #D1D5DB"
                com_atual = "✅ Atual" if ativo else ""
                st.markdown(f"""
                <div style='border:{borda};border-radius:12px;padding:20px;text-align:center;background:{"#F0FDF4" if ativo else "#FAFAFA"};'>
                    <h3 style='margin:0 0 4px;'>{p['nome']}</h3>
                    <p style='font-size:24px;font-weight:900;margin:8px 0;'>R$ {float(p['preco_mensal']):,.0f}<span style='font-size:14px;font-weight:400;color:#6B7280;'>/mês</span></p>
                    <p style='font-size:13px;color:#6B7280;margin:0 0 12px;'>ou R$ {float(p['preco_anual']):,.0f}/ano</p>
                    <p style='font-size:13px;margin:4px 0;'>📋 {p.get('max_obras','∞')} obras · 👥 {p.get('max_usuarios','∞')} usuários</p>
                    <p style='font-size:12px;color:#6B7280;margin:12px 0;'>{com_atual}</p>
                </div>
                """, unsafe_allow_html=True)
                if not ativo:
                    if st.button(f"Alterar para {p['nome']}", key=f"plan_{p['slug']}", width='stretch'):
                        try:
                            sb().table("empresas").update({"plan_id": p["id"]}).eq("id", st.session_state.empresa_id).execute()
                            st.success(f"Plano alterado para {p['nome']}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")


# ── Developer Panel ──────────────────────────────────────────────────────────

def _dev_log(level, category, action, details=None):
    try:
        from db import sb
        sb().table("system_logs").insert({
            "level": level, "category": category, "action": action,
            "user_id": st.session_state.get("usuario", {}).get("id"),
            "empresa_id": st.session_state.get("empresa_id"),
            "details": details or {},
        }).execute()
    except Exception:
        pass

def pagina_dev_panel():
    st.title("🛠️ Painel do Desenvolvedor")
    from db import sb

    tab_emp, tab_users, tab_grants, tab_logs, tab_config, tab_sql, tab_sys = st.tabs([
        "🏢 Empresas", "👥 Usuários", "🤝 Parcerias", "📋 Logs",
        "⚙️ Config", "💻 SQL Console", "🔧 Sistema"
    ])

    # ═══════════════════════════════════════════════════════════════════
    # TAB 1 — EMPRESAS (with deep view)
    # ═══════════════════════════════════════════════════════════════════
    with tab_emp:
        try:
            empresas = sb().table("empresas").select("*, planos(nome, slug)").order("created_at").execute()
            df_emp = pd.DataFrame(empresas.data or [])
        except Exception as e:
            st.error(f"Erro: {e}"); df_emp = pd.DataFrame()

        if df_emp.empty:
            st.info("Nenhuma empresa.")
        else:
            search = st.text_input("🔍 Buscar empresa", key="dev_emp_search")
            if search:
                df_emp = df_emp[df_emp["nome"].str.contains(search, case=False, na=False)]
            st.caption(f"{len(df_emp)} empresa(s)")

        for _, row in df_emp.iterrows():
            eid = row["id"]
            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1, 1, 1])
                cols[0].markdown(f"**{row['nome']}**")
                cols[1].caption(f"Status: {row.get('status','?')}")
                plano_info = row.get("planos") or {}
                cols[2].caption(f"Plano: {plano_info.get('slug','?')}")
                cols[3].caption(f"Partner: {'✅' if row.get('is_partner') else '❌'}")

                # Deep view expander
                with cols[4].popover("🔍", key=f"deep_{eid}"):
                    try:
                        n_obras = sb().table("obras").select("count", count="exact").eq("empresa_id", eid).is_("deleted_at", None).limit(0).execute()
                        n_users = sb().table("user_roles").select("count", count="exact").execute() or type("obj",(),{"count":0})
                        n_grants = sb().table("dev_grants").select("count", count="exact").eq("empresa_id", eid).limit(0).execute()
                        st.metric("Obras", n_obras.count if hasattr(n_obras,'count') else "?")
                        st.metric("Usuários (total)", n_users.count if hasattr(n_users,'count') else "?")
                        st.metric("Grants", n_grants.count if hasattr(n_grants,'count') else "?")
                    except Exception as deep_e:
                        st.caption(f"Erro: {deep_e}")
                    if row.get("partner_notes"):
                        st.caption(f"Obs: {row['partner_notes']}")
                    if row.get("created_at"):
                        st.caption(f"Criada: {row['created_at'][:10]}")
                    if row.get("custom_max_obras"):
                        st.caption(f"Custom obras: {row['custom_max_obras']}")
                    if row.get("custom_max_usuarios"):
                        st.caption(f"Custom users: {row['custom_max_usuarios']}")

                with cols[5].popover("✏️", key=f"edit_emp_{eid}"):
                    with st.form(f"form_edit_emp_{eid}"):
                        novo_nome = st.text_input("Nome", value=row.get("nome",""))
                        novo_status = st.selectbox("Status", ["ativo","pendente","bloqueado"],
                            index=["ativo","pendente","bloqueado"].index(row.get("status","ativo")) if row.get("status") in ["ativo","pendente","bloqueado"] else 0)
                        planos_data = sb().table("planos").select("*").execute() or type("obj",(),{"data":[]})
                        planos_opts = {p["slug"]: p["id"] for p in (planos_data.data or [])}
                        slug_atual = (row.get("planos") or {}).get("slug") or "pro"
                        plano_sel = st.selectbox("Plano", list(planos_opts.keys()),
                            index=list(planos_opts.keys()).index(slug_atual) if slug_atual in planos_opts else 0)
                        is_partner = st.checkbox("Partner (sem limites)", value=row.get("is_partner", False))
                        partner_notes = st.text_area("Obs", value=row.get("partner_notes","") or "")
                        custom_obras = st.number_input("Limite obras (0=plano)", min_value=0, value=int(row.get("custom_max_obras") or 0))
                        custom_usuarios = st.number_input("Limite usuários (0=plano)", min_value=0, value=int(row.get("custom_max_usuarios") or 0))
                        if st.form_submit_button("💾 Salvar", type="primary"):
                            sb().table("empresas").update({
                                "nome": novo_nome, "status": novo_status,
                                "plan_id": planos_opts.get(plano_sel),
                                "is_partner": is_partner, "partner_notes": partner_notes,
                                "custom_max_obras": custom_obras or None,
                                "custom_max_usuarios": custom_usuarios or None,
                            }).eq("id", eid).execute()
                            _dev_log("info", "empresa", f"Editou empresa {novo_nome}",
                                     {"status": novo_status, "plano": plano_sel, "partner": is_partner})
                            _notify(f"✅ {row['nome']} atualizada!"); st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # TAB 2 — USUÁRIOS
    # ═══════════════════════════════════════════════════════════════════
    with tab_users:
        try:
            profiles = sb().table("profiles").select("id, nome, email, created_at").order("created_at").execute()
            roles_raw = sb().table("user_roles").select("user_id, role").execute()
            df_profiles = pd.DataFrame(profiles.data or [])
            df_roles = pd.DataFrame(roles_raw.data or [])
            roles_map = df_roles.groupby("user_id")["role"].apply(list).to_dict()
        except Exception as e:
            st.error(f"Erro: {e}"); df_profiles = pd.DataFrame(); roles_map = {}

        if df_profiles.empty:
            st.info("Nenhum usuário.")
        else:
            for _, row in df_profiles.iterrows():
                uid = row["id"]; roles = roles_map.get(uid, [])
                with st.container(border=True):
                    cols = st.columns([3, 2, 2])
                    cols[0].markdown(f"**{row.get('nome','?')}**")
                    cols[1].markdown(f"`{row.get('email','')}`")
                    cols[2].markdown(" / ".join(roles) if roles else "—")
                    with st.popover("✏️", key=f"edit_user_{uid}"):
                        novas_roles = st.multiselect("Perfis",
                            ["admin","engenheiro","financeiro","suprimentos","qualidade","rh","visualizador","gestor","contratante"],
                            default=roles, key=f"roles_{uid}")
                        if st.button("Salvar", key=f"save_user_{uid}", type="primary"):
                            for r in [r for r in roles if r not in novas_roles]:
                                sb().table("user_roles").delete().eq("user_id", uid).eq("role", r).execute()
                            for r in [r for r in novas_roles if r not in roles]:
                                sb().table("user_roles").insert({"user_id": uid, "role": r}).execute()
                            _dev_log("info", "usuario", f"Editou permissões de {row.get('nome','?')}",
                                     {"roles": novas_roles})
                            _notify("Permissões atualizadas!"); st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # TAB 3 — PARCERIAS
    # ═══════════════════════════════════════════════════════════════════
    with tab_grants:
        st.subheader("Nova Parceria")
        try:
            empresas_data = sb().table("empresas").select("id, nome").eq("status","ativo").order("nome").execute()
            emp_opts = {e["nome"]: e["id"] for e in (empresas_data.data or [])}
        except Exception:
            emp_opts = {}
        with st.form("form_dev_grant"):
            emp_sel = st.selectbox("Empresa", list(emp_opts.keys()) if emp_opts else [])
            grant_to = st.text_input("Concedido a", placeholder="Construtora XYZ")
            reason = st.text_input("Motivo", placeholder="Parceiro de implementação / Teste gratuito")
            c1, c2 = st.columns(2)
            expires = c1.date_input("Expira (vazio=indeterminado)", value=None)
            grant_notes = c2.text_input("Observações")
            if st.form_submit_button("✅ Conceder Acesso Gratuito", type="primary"):
                if not emp_sel or emp_sel not in emp_opts:
                    st.error("Selecione uma empresa.")
                else:
                    eid = emp_opts[emp_sel]
                    sb().table("empresas").update({"is_partner": True,
                        "partner_notes": f"Parceiro: {grant_to or emp_sel} | Motivo: {reason or '—'}"
                    }).eq("id", eid).execute()
                    sb().table("dev_grants").insert({
                        "empresa_id": eid, "grant_type": "partner",
                        "granted_to": grant_to or emp_sel,
                        "granted_by": st.session_state.get("usuario",{}).get("id"),
                        "expires_at": str(expires) if expires else None,
                        "reason": reason, "notes": grant_notes,
                    }).execute()
                    _dev_log("info", "parceria", f"Concedeu parceria a {emp_sel}",
                             {"granted_to": grant_to, "expires": str(expires) if expires else None})
                    _notify(f"✅ Parceria concedida a **{emp_sel}**!"); st.rerun()

        st.markdown("---"); st.subheader("Parcerias Ativas")
        try:
            grants = sb().table("dev_grants").select("*, empresas(nome)").order("created_at", desc=True).execute()
            df_grants = pd.DataFrame(grants.data or [])
        except Exception:
            df_grants = pd.DataFrame()
        if df_grants.empty:
            st.info("Nenhuma parceria ativa.")
        else:
            for _, g in df_grants.iterrows():
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1])
                    emp_nome = (g.get("empresas") or {}).get("nome","?") if isinstance(g.get("empresas"), dict) else "?"
                    cols[0].markdown(f"**{emp_nome}** → {g.get('granted_to','')}")
                    cols[1].caption(f"Motivo: {g.get('reason','?')}")
                    exp = g.get("expires_at")
                    cols[2].caption(f"Expira: {exp[:10] if exp else 'Indeterminado'}")
                    if cols[3].button("🔒 Revogar", key=f"revoke_{g['id']}"):
                        sb().table("empresas").update({"is_partner": False}).eq("id", g["empresa_id"]).execute()
                        sb().table("dev_grants").delete().eq("id", g["id"]).execute()
                        _dev_log("warning", "parceria", f"Revogou parceria de {emp_nome}")
                        _notify("🔒 Parceria revogada!"); st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # TAB 4 — LOGS
    # ═══════════════════════════════════════════════════════════════════
    with tab_logs:
        c1, c2, c3 = st.columns(3)
        filtro_nivel = c1.selectbox("Nível", ["Todos","info","warning","error"])
        filtro_cat = c2.text_input("Categoria (filtro)", placeholder="ex: empresa")
        limite = c3.number_input("Linhas", min_value=10, max_value=500, value=100, step=10)
        try:
            q = sb().table("system_logs").select("*, profiles!system_logs_user_id_fkey(nome)").order("created_at", desc=True).limit(int(limite))
            logs = q.execute()
            df_logs = pd.DataFrame(logs.data or [])
        except Exception:
            try:
                q = sb().table("system_logs").select("*").order("created_at", desc=True).limit(int(limite))
                logs = q.execute()
                df_logs = pd.DataFrame(logs.data or [])
            except Exception as e:
                st.error(f"Erro: {e}"); df_logs = pd.DataFrame()

        if df_logs.empty:
            st.info("Nenhum log registrado.")
        else:
            if filtro_nivel != "Todos":
                df_logs = df_logs[df_logs["level"] == filtro_nivel]
            if filtro_cat:
                df_logs = df_logs[df_logs["category"].str.contains(filtro_cat, case=False, na=False)]
            badges = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}
            df_logs["_nivel"] = df_logs["level"].apply(lambda x: badges.get(x, x))
            df_logs["_usuario"] = df_logs.get("profiles", pd.Series()).apply(
                lambda x: x.get("nome","?") if isinstance(x, dict) else "?")
            df_logs["_data"] = df_logs["created_at"].apply(lambda x: str(x)[:16] if x else "")
            colunas = [c for c in ["_data","_nivel","category","action","_usuario"] if c in df_logs.columns]
            df_exib = df_logs[colunas].rename(columns={
                "_data": "Data", "_nivel": "", "category": "Categoria",
                "action": "Ação", "_usuario": "Usuário"
            })
            st.dataframe(df_exib, width='stretch', hide_index=True)

            with st.expander("🔍 Ver detalhes de um log"):
                opcoes = [f"{r.get('created_at','')[:16]} | {r.get('action','')[:60]}" for _, r in df_logs.iterrows()]
                sel = st.selectbox("Selecionar", opcoes, key="log_sel")
                if sel:
                    idx = opcoes.index(sel)
                    row_log = df_logs.iloc[idx]
                    st.json({
                        "level": row_log.get("level"),
                        "category": row_log.get("category"),
                        "action": row_log.get("action"),
                        "user_id": row_log.get("user_id"),
                        "empresa_id": row_log.get("empresa_id"),
                        "details": row_log.get("details"),
                        "created_at": row_log.get("created_at"),
                    })

    # ═══════════════════════════════════════════════════════════════════
    # TAB 5 — CONFIG (Feature Toggles + App Config + Email Test)
    # ═══════════════════════════════════════════════════════════════════
    with tab_config:
        sub_tab_tog, sub_tab_app, sub_tab_mail = st.tabs(["🚩 Feature Toggles", "📋 App Config", "📧 Teste de E-mail"])

        with sub_tab_tog:
            try:
                toggles = sb().table("feature_toggles").select("*, empresas(nome)").order("feature_key").execute()
                df_tog = pd.DataFrame(toggles.data or [])
            except Exception as e:
                st.error(f"Erro: {e}"); df_tog = pd.DataFrame()

            st.caption("Toggles globais (sem empresa) e por empresa. Desligue uma feature para desabilitá-la.")
            try:
                empresas_lista = sb().table("empresas").select("id, nome").eq("status","ativo").order("nome").execute()
                emp_opts_tog = {"(global)": None}
                emp_opts_tog.update({e["nome"]: e["id"] for e in (empresas_lista.data or [])})
            except Exception:
                emp_opts_tog = {"(global)": None}

            col_filtro, col_novo = st.columns([1, 1])
            filtro_emp_tog = col_filtro.selectbox("Filtrar por empresa", list(emp_opts_tog.keys()), key="tog_filtro")
            with col_novo.popover("➕ Novo toggle", key="new_tog_pop"):
                with st.form("form_new_tog"):
                    nova_feature = st.text_input("Feature key", placeholder="ex: modulo_x")
                    novo_label = st.text_input("Label", placeholder="Módulo X")
                    nova_desc = st.text_area("Descrição")
                    nova_emp = st.selectbox("Empresa", list(emp_opts_tog.keys()), key="tog_new_emp")
                    if st.form_submit_button("Criar", type="primary"):
                        sb().table("feature_toggles").insert({
                            "feature_key": nova_feature.strip(),
                            "label": novo_label or nova_feature.strip(),
                            "description": nova_desc,
                            "empresa_id": emp_opts_tog.get(nova_emp),
                            "enabled": True,
                        }).execute()
                        _dev_log("info", "config", f"Criou toggle {nova_feature}")
                        _notify(f"✅ Toggle {nova_feature} criado!"); st.rerun()

            if df_tog.empty:
                st.info("Nenhum toggle.")
            else:
                if filtro_emp_tog != "(global)":
                    eid_filtro = emp_opts_tog.get(filtro_emp_tog)
                    df_tog = df_tog[(df_tog["empresa_id"] == eid_filtro) | df_tog["empresa_id"].isna()]

            for _, t_row in df_tog.iterrows():
                emp_nome_t = (t_row.get("empresas") or {}).get("nome","GLOBAL") if isinstance(t_row.get("empresas"), dict) else "GLOBAL"
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1])
                    cols[0].markdown(f"**{t_row.get('label','?')}** `{t_row.get('feature_key','')}`")
                    cols[1].caption(emp_nome_t)
                    ativo = t_row.get("enabled", False)
                    novo_val = cols[2].checkbox("Ativo", value=ativo, key=f"tog_{t_row['id']}")
                    if novo_val != ativo:
                        sb().table("feature_toggles").update({"enabled": novo_val}).eq("id", t_row["id"]).execute()
                        _dev_log("info", "config",
                            f"{'Ativou' if novo_val else 'Desativou'} toggle {t_row.get('feature_key','')} para {emp_nome_t}")
                        st.rerun()
                    if cols[3].button("🗑️", key=f"del_tog_{t_row['id']}"):
                        sb().table("feature_toggles").delete().eq("id", t_row["id"]).execute()
                        st.rerun()

        with sub_tab_app:
            try:
                configs = sb().table("app_config").select("*").order("key").execute()
                df_cfg = pd.DataFrame(configs.data or [])
            except Exception as e:
                st.error(f"Erro: {e}"); df_cfg = pd.DataFrame()

            st.caption("Configurações globais do sistema (chave → valor).")
            with st.popover("➕ Nova chave", key="new_cfg_pop"):
                with st.form("form_new_cfg"):
                    nova_chave = st.text_input("Chave", placeholder="ex: max_upload_mb")
                    novo_valor = st.text_input("Valor")
                    nova_desc = st.text_input("Descrição")
                    if st.form_submit_button("Criar", type="primary"):
                        sb().table("app_config").insert({
                            "key": nova_chave.strip(),
                            "value": novo_valor.strip(),
                            "description": nova_desc,
                        }).execute()
                        _dev_log("info", "config", f"Criou config {nova_chave}={novo_valor}")
                        _notify(f"✅ Config {nova_chave} criada!"); st.rerun()

            if df_cfg.empty:
                st.info("Nenhuma config.")
            else:
                for _, c_row in df_cfg.iterrows():
                    with st.container(border=True):
                        cols = st.columns([2, 2, 2, 1])
                        cols[0].markdown(f"**{c_row['key']}**")
                        novo_v = cols[1].text_input("Valor", value=c_row.get("value",""), key=f"cfg_{c_row['key']}", label_visibility="collapsed")
                        cols[2].caption(c_row.get("description",""))
                        if cols[3].button("💾", key=f"save_cfg_{c_row['key']}"):
                            sb().table("app_config").update({
                                "value": novo_v,
                                "updated_by": st.session_state.get("usuario",{}).get("id"),
                            }).eq("key", c_row["key"]).execute()
                            _dev_log("info", "config", f"Alterou config {c_row['key']}={novo_v}")
                            _notify(f"✅ {c_row['key']} = {novo_v}"); st.rerun()

        with sub_tab_mail:
            st.subheader("Testar Envio de E-mail")
            email_to = st.text_input("E-mail de teste", value="ronneyramos123@gmail.com", key="test_email_to")
            if st.button("📧 Enviar e-mail de teste", type="primary", key="btn_test_email"):
                try:
                    from alertas import _enviar_email
                    ok = _enviar_email(
                        assunto="[Prumo ERP] Teste do Painel do Desenvolvedor",
                        corpo="Este é um e-mail de teste enviado do Painel do Desenvolvedor.\n\nSe você recebeu esta mensagem, a configuração de e-mail está funcionando corretamente."
                    )
                    if ok:
                        _dev_log("info", "email", f"E-mail de teste enviado para {email_to}")
                        st.success(f"✅ E-mail enviado para {email_to}!")
                    else:
                        st.error("❌ Falha no envio. Verifique as credenciais SMTP no .env")
                except Exception as mail_e:
                    st.error(f"❌ Erro: {mail_e}")

    # ═══════════════════════════════════════════════════════════════════
    # TAB 6 — SQL CONSOLE
    # ═══════════════════════════════════════════════════════════════════
    with tab_sql:
        st.warning("⚠️ **Cuidado!** Comandos alteram o banco diretamente. Use apenas se souber o que está fazendo.")
        sql_text = st.text_area("SQL", height=150, placeholder="SELECT * FROM empresas LIMIT 10", key="dev_sql_input")
        if st.button("▶️ Executar", type="primary", key="btn_exec_sql"):
            if not sql_text.strip():
                st.error("Digite uma query SQL.")
            else:
                try:
                    import requests
                    url = os.environ["SUPABASE_URL"]
                    key = os.environ.get("SUPABASE_SERVICE_KEY","") or os.environ.get("SUPABASE_ANON_KEY","")
                    resp = requests.post(f"{url}/rest/v1/rpc/exec_sql",
                        json={"query_text": sql_text.strip()},
                        headers={"apikey": key, "Authorization": f"Bearer {key}"})
                    result = resp.json()
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Erro SQL: {result['error']}")
                    elif isinstance(result, list):
                        if result:
                            st.dataframe(pd.DataFrame(result), width='stretch', hide_index=True)
                        else:
                            st.success("✅ Query executada (sem resultados).")
                    else:
                        st.success(f"✅ OK: {result}")
                except Exception as e:
                    st.error(f"Erro na execução: {e}")
        st.caption("📌 Dica: Use `SELECT * FROM tabela LIMIT 50` para explorar dados. Use `UPDATE/DELETE` com cuidado.")

    # ═══════════════════════════════════════════════════════════════════
    # TAB 7 — SISTEMA (env, health, schema, export)
    # ═══════════════════════════════════════════════════════════════════
    with tab_sys:
        sub_sys_env, sub_sys_schema, sub_sys_export, sub_sys_debug = st.tabs([
            "🔧 Ambiente", "📐 Schema", "⬇️ Export", "🧪 Debug"
        ])

        with sub_sys_env:
            st.subheader("🔧 Informações do Sistema")
            c1, c2 = st.columns(2)
            url_ok = bool(os.environ.get("SUPABASE_URL"))
            anon_ok = bool(os.environ.get("SUPABASE_ANON_KEY"))
            svc_ok = bool(os.environ.get("SUPABASE_SERVICE_KEY"))
            c1.metric("SUPABASE_URL", "✅" if url_ok else "❌")
            c1.metric("SUPABASE_ANON_KEY", "✅" if anon_ok else "❌")
            c1.metric("SUPABASE_SERVICE_KEY", "✅" if svc_ok else "❌")
            c2.metric("Streamlit", "✅")
            c2.metric("Python", __import__("sys").version[:5])
            if st.button("🔌 Testar Conexão", key="btn_test_conn"):
                try:
                    test = sb().table("empresas").select("count", count="exact").limit(0).execute()
                    st.success(f"✅ Conexão OK — {test.count or 0} empresas")
                    _dev_log("info", "sistema", "Teste de conexão OK", {"empresas": test.count})
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
            st.json({
                "planos": len((sb().table("planos").select("id").execute()).data or []),
                "empresas": len((sb().table("empresas").select("id").execute()).data or []),
                "obras": len((sb().table("obras").select("id").is_("deleted_at", None).execute()).data or []),
                "usuarios": len((sb().table("profiles").select("id").execute()).data or []),
                "grants": len((sb().table("dev_grants").select("id").execute()).data or []),
                "toggles": len((sb().table("feature_toggles").select("id").execute()).data or []),
                "logs": len((sb().table("system_logs").select("id").execute()).data or []),
            })

        with sub_sys_schema:
            st.subheader("📐 Schema do Banco")
            # Query via SQL console directly
            schema_sql = st.text_area(
                "Query SQL para explorar schema",
                value="SELECT table_name, table_type FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name",
                height=80, key="schema_query"
            )
            if st.button("▶️ Executar", key="btn_schema_exec"):
                try:
                    import requests
                    url = os.environ["SUPABASE_URL"]
                    key = os.environ.get("SUPABASE_SERVICE_KEY","") or os.environ.get("SUPABASE_ANON_KEY","")
                    resp = requests.post(f"{url}/rest/v1/rpc/exec_sql",
                        json={"query_text": schema_sql},
                        headers={"apikey": key, "Authorization": f"Bearer {key}"})
                    result = resp.json()
                    if isinstance(result, list) and result:
                        st.dataframe(pd.DataFrame(result), width='stretch', hide_index=True)
                    elif isinstance(result, list):
                        st.success("Sem resultados.")
                    elif isinstance(result, dict) and "error" in result:
                        st.error(f"Erro: {result['error']}")
                except Exception as e:
                    st.error(f"Erro: {e}")

            st.markdown("---")
            st.caption("💡 Pré-definidos:")
            for label, q in [
                ("Tabelas públicas", "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"),
                ("Colunas de 'empresas'", "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='empresas' ORDER BY ordinal_position"),
                ("Views", "SELECT table_name FROM information_schema.views WHERE table_schema='public' ORDER BY table_name"),
                ("Políticas RLS", "SELECT schemaname, tablename, policyname, permissive, roles, cmd FROM pg_policies WHERE schemaname='public' ORDER BY tablename"),
            ]:
                if st.button(f"📋 {label}", key=f"presql_{label}"):
                    st.session_state["schema_query"] = q
                    st.rerun()

        with sub_sys_export:
            st.subheader("⬇️ Exportar Dados")
            tabelas = ["empresas", "obras", "planos", "profiles", "user_roles",
                       "lancamentos", "colaboradores", "inspecoes", "nao_conformidades",
                       "dev_grants", "feature_toggles", "app_config", "system_logs"]
            tab_sel = st.selectbox("Tabela", tabelas, key="export_tab")
            fmt = st.radio("Formato", ["JSON", "CSV"], horizontal=True, key="export_fmt")
            if st.button("⬇️ Baixar", type="primary", key="btn_export"):
                try:
                    import requests, json, io
                    url = os.environ["SUPABASE_URL"]
                    key = os.environ.get("SUPABASE_SERVICE_KEY","") or os.environ.get("SUPABASE_ANON_KEY","")
                    resp = requests.get(f"{url}/rest/v1/{tab_sel}?select=*&limit=5000",
                        headers={"apikey": key, "Authorization": f"Bearer {key}"})
                    dados = resp.json()
                    if isinstance(dados, list):
                        if fmt == "JSON":
                            buf = io.BytesIO(json.dumps(dados, indent=2, default=str).encode("utf-8"))
                            mime = "application/json"
                            ext = "json"
                        else:
                            df_exp = pd.DataFrame(dados)
                            buf = io.BytesIO()
                            df_exp.to_csv(buf, index=False)
                            buf.seek(0)
                            mime = "text/csv"
                            ext = "csv"
                        st.download_button(f"📥 Baixar {tab_sel}.{ext}", data=buf,
                            file_name=f"{tab_sel}.{ext}", mime=mime, key="dl_export")
                    else:
                        st.error("Erro ao buscar dados.")
                except Exception as e:
                    st.error(f"Erro: {e}")

        with sub_sys_debug:
            st.subheader("🧪 Session State (debug)")
            keys = sorted(st.session_state.keys())
            dados_debug = {}
            for k in keys:
                try:
                    v = st.session_state[k]
                    if isinstance(v, pd.DataFrame):
                        dados_debug[k] = f"DataFrame({len(v)} rows)"
                    elif isinstance(v, (dict, list)):
                        import json
                        dados_debug[k] = json.dumps(v, default=str)[:200]
                    else:
                        dados_debug[k] = str(v)[:200]
                except Exception:
                    dados_debug[k] = "❌"
            st.code("\n".join(f"{k} = {v}" for k, v in dados_debug.items()))

# ── Dashboard ────────────────────────────────────────────────────────────────

def _dash_alert_banner():
    _al_cache = st.session_state.get("_alertas_cache", {})
    _n_venc   = len(_al_cache.get("vencimentos", []))
    _n_nc     = len(_al_cache.get("ncs_abertas", []))
    _n_est    = len(_al_cache.get("estoque_critico", []))
    _total_al = _n_venc + _n_nc + _n_est
    if _total_al > 0:
        _partes = []
        if _n_venc: _partes.append(f"💸 {_n_venc} conta(s) vencendo")
        if _n_nc:   _partes.append(f"🔴 {_n_nc} NC(s) em aberto há +30 dias")
        if _n_est:  _partes.append(f"📦 {_n_est} insumo(s) em estoque crítico")
        st.warning(f"**⚠️ {_total_al} alerta(s) ativo(s):** " + " | ".join(_partes))
        _b1, _b2, _ = st.columns([1, 1, 4])
        if _b1.button("📧 Enviar email de alertas", key="btn_enviar_alertas", type="primary"):
            try:
                import alertas as _alrt_send
                ok = _alrt_send.enviar_resumo_alertas(_al_cache)
                if ok:
                    st.success("✅ Email de alertas enviado para ronneyramos123@gmail.com!")
                else:
                    st.error("❌ Erro ao enviar email. Verifique as credenciais no .env")
            except Exception as _e_email:
                st.error(f"❌ Erro: {_e_email}")
        if _b2.button("🔄 Rever alertas", key="btn_rever_alertas"):
            st.session_state["_alertas_verificados"] = False
            st.rerun()
    else:
        st.info("✅ Nenhum alerta ativo no momento.")


def pagina_dashboard():
    import plotly.express as px
    import plotly.graph_objects as go
    st.title("🏠 Dashboard")
    _init()
    _show_toast()

    _dash_alert_banner()

    CATS = ["Materiais", "Folha de Pagamento", "Impostos", "Outros"]
    CAT_CORES = {"Materiais": "#2B59C3", "Folha de Pagamento": "#E67E22",
                 "Impostos": "#E74C3C",  "Outros": "#95A5A6"}
    STATUS_CORES = {"Em andamento": "#2B59C3", "Paralisada": "#E74C3C",
                    "Concluída": "#27AE60", "Planejamento": "#F39C12", "Cancelada": "#95A5A6"}

    obras_df  = st.session_state.obras.copy()
    contas_df = st.session_state.contas_pagar.copy()
    func_df   = st.session_state.funcionarios.copy()
    est_df    = st.session_state.estoque.copy()
    hoje      = date.today()

    contas_df["Valor (R$)"] = pd.to_numeric(contas_df["Valor (R$)"], errors="coerce").fillna(0.0)
    contas_df["venc_dt"]    = pd.to_datetime(contas_df["Vencimento"], dayfirst=True, errors="coerce").dt.date

    obras_df["Valor Contrato (R$)"] = obras_df["Valor Contrato (R$)"].apply(_to_num)
    obras_df["% Físico"]            = pd.to_numeric(obras_df["% Físico"], errors="coerce").fillna(0.0)
    obras_df["_val_medido"]         = obras_df["Valor Contrato (R$)"] * obras_df["% Físico"] / 100

    total_contratado = obras_df["Valor Contrato (R$)"].sum()
    total_medido     = obras_df["_val_medido"].sum()
    n_ativas         = len(obras_df[obras_df["Status"] == "Em andamento"])
    pct_med          = (total_medido / total_contratado * 100) if total_contratado else 0

    _med_df = st.session_state.medicoes.copy()
    if not _med_df.empty and "Valor Medido (R$)" in _med_df.columns:
        _med_df["Valor Medido (R$)"] = _med_df["Valor Medido (R$)"].apply(_to_num)
        total_medido_real = _med_df["Valor Medido (R$)"].sum()
    else:
        total_medido_real = 0.0
    saldo_a_medir = max(0.0, total_contratado - total_medido_real)

    mask_alertas = (
        (contas_df["Status"] == "Vencido") |
        ((contas_df["Status"] == "A Pagar") & (contas_df["venc_dt"] <= hoje + timedelta(days=7)))
    )
    n_alertas = int(mask_alertas.sum())

    func_df["Salário (R$)"] = pd.to_numeric(func_df.get("Salário (R$)", 0), errors="coerce").fillna(0.0)
    total_folha = func_df["Salário (R$)"].sum() * 1.31 if len(func_df) else 0.0

    # ── KPI row ──
    st.markdown('<div class="dash-kpi-row">', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Obras Ativas",        str(n_ativas))
    k2.metric("Portfólio Total",     f"R$ {total_contratado/1_000_000:.2f}M",
              help="Soma dos valores de contrato de todas as obras")
    k3.metric("Saldo a Medir",       _fmt(saldo_a_medir),
              help="Valor Contrato − Total Medido Acumulado (medições registradas)")
    k4.metric("Alertas Financeiros", str(n_alertas),
              delta=f"{pct_med:.1f}% medido" if total_contratado else "0% medido",
              delta_color="inverse" if n_alertas else "normal")
    st.markdown('</div>', unsafe_allow_html=True)

    tab_geral, tab_obra = st.tabs(["🏢 Visão Geral — Diretoria / Sócios",
                                   "🏗️ Por Obra — Engenharia / Administrativo"])

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1 — VISÃO GERAL
    # ═══════════════════════════════════════════════════════════════════════
    with tab_geral:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">📊 Avanço Físico e Distribuição do Portfólio</div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            st.subheader("Avanço Físico por Obra")
            if len(obras_df):
                fig_av = px.bar(obras_df, x="% Físico", y="Nome", orientation="h",
                                color="Status", color_discrete_map=STATUS_CORES,
                                labels={"% Físico": "% Concluído", "Nome": ""},
                                text="% Físico")
                fig_av.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
                fig_av.update_layout(xaxis_range=[0, 115], height=max(240, len(obras_df)*50),
                                     plot_bgcolor="white", paper_bgcolor="white",
                                     margin=dict(l=0, r=20, t=10, b=0))
                st.plotly_chart(fig_av, width='stretch')
            else:
                st.markdown('<p class="dash-empty">Nenhuma obra cadastrada.</p>', unsafe_allow_html=True)
        with cb:
            st.subheader("Distribuição do Portfólio")
            if len(obras_df):
                fig_pie = px.pie(obras_df, values="Valor Contrato (R$)", names="Nome",
                                 hole=0.42, color_discrete_sequence=px.colors.qualitative.Set2)
                fig_pie.update_traces(textinfo="percent+label", textposition="outside")
                fig_pie.update_layout(height=max(320, len(obras_df)*65),
                                      showlegend=False,
                                      margin=dict(l=40, r=40, t=10, b=40))
                st.plotly_chart(fig_pie, width='stretch')

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">📈 Medição vs Contrato e Custos por Categoria</div>', unsafe_allow_html=True)
        cc, cd = st.columns(2)
        with cc:
            st.subheader("Medição vs Contrato (R$)")
            if len(obras_df):
                fig_med = go.Figure()
                fig_med.add_trace(go.Bar(name="Contratado", x=obras_df["Nome"],
                                         y=obras_df["Valor Contrato (R$)"], marker_color="#AED6F1"))
                fig_med.add_trace(go.Bar(name="Medido (est.)", x=obras_df["Nome"],
                                         y=obras_df["_val_medido"], marker_color="#2B59C3"))
                fig_med.update_layout(barmode="overlay", height=280, plot_bgcolor="white",
                                      paper_bgcolor="white", yaxis_tickformat=",.0f",
                                      margin=dict(l=0, r=0, t=10, b=60),
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig_med, width='stretch')
        with cd:
            st.subheader("Custos por Categoria — Empresa")
            if "Categoria" in contas_df.columns and contas_df["Valor (R$)"].sum() > 0:
                cc_tot = (contas_df.groupby("Categoria")["Valor (R$)"].sum()
                          .reset_index().rename(columns={"Valor (R$)": "Total"}))
                for c in CATS:
                    if c not in cc_tot["Categoria"].values:
                        cc_tot = pd.concat([cc_tot,
                                            pd.DataFrame([{"Categoria": c, "Total": 0}])],
                                           ignore_index=True)
                fig_cat = px.bar(cc_tot, x="Categoria", y="Total",
                                 color="Categoria", color_discrete_map=CAT_CORES,
                                 text="Total", height=280,
                                 labels={"Total": "R$", "Categoria": ""})
                fig_cat.update_traces(texttemplate="R$ %{text:,.0f}", textposition="outside")
                fig_cat.update_layout(showlegend=False, plot_bgcolor="white",
                                      paper_bgcolor="white", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_cat, width='stretch')
            else:
                st.markdown('<p class="dash-empty">Nenhum lançamento financeiro categorizado.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">📊 Status das Obras</div>', unsafe_allow_html=True)

        def _semaforo_obra(row):
            inicio  = pd.to_datetime(row.get("Início"),  dayfirst=True, errors="coerce")
            termino = pd.to_datetime(row.get("Término"), dayfirst=True, errors="coerce")
            pct_fisico = _to_num(row.get("% Físico", 0))
            if row.get("Status") == "Concluída":
                return "✅ Concluída"
            if pd.isna(inicio) or pd.isna(termino):
                return "⚪ Sem data"
            prazo_total     = (termino - inicio).days
            prazo_decorrido = (pd.Timestamp(hoje) - inicio).days
            if prazo_total <= 0:
                return "⚪ Sem data"
            pct_prazo = min(100, max(0, prazo_decorrido / prazo_total * 100))
            gap = pct_fisico - pct_prazo
            if gap >= -5:
                return "🟢 No prazo"
            elif gap >= -15:
                return "🟡 Atenção"
            else:
                return "🔴 Atrasada"

        if not obras_df.empty:
            sem_df = obras_df[["Nome", "Cliente", "% Físico", "Status"]].copy()
            sem_df["Status Prazo"] = obras_df.apply(_semaforo_obra, axis=1)
            sem_df["% Físico"] = sem_df["% Físico"].apply(lambda v: f"{_to_num(v):.1f}%")
            st.dataframe(sem_df[["Nome", "Cliente", "% Físico", "Status", "Status Prazo"]],
                         width='stretch', hide_index=True)
        else:
            st.markdown('<p class="dash-empty">Nenhuma obra cadastrada.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">💰 Fluxo de Caixa Mensal</div>', unsafe_allow_html=True)
        cp_fc = st.session_state.contas_pagar.copy()
        cr_fc = st.session_state.contas_receber.copy()
        cp_fc["Valor (R$)"] = cp_fc["Valor (R$)"].apply(_to_num)
        cr_fc["Valor (R$)"] = cr_fc["Valor (R$)"].apply(_to_num)
        cp_fc["mes"] = pd.to_datetime(cp_fc["Vencimento"], dayfirst=True, errors="coerce").dt.to_period("M")
        cr_fc["mes"] = pd.to_datetime(cr_fc["Vencimento"], dayfirst=True, errors="coerce").dt.to_period("M")
        despesas_mes = cp_fc.dropna(subset=["mes"]).groupby("mes")["Valor (R$)"].sum().reset_index()
        receitas_mes = cr_fc.dropna(subset=["mes"]).groupby("mes")["Valor (R$)"].sum().reset_index()
        despesas_mes["mes_str"] = despesas_mes["mes"].astype(str)
        receitas_mes["mes_str"] = receitas_mes["mes"].astype(str)
        fc = pd.merge(
            receitas_mes.rename(columns={"Valor (R$)": "Receita"})[["mes_str", "Receita"]],
            despesas_mes.rename(columns={"Valor (R$)": "Despesa"})[["mes_str", "Despesa"]],
            on="mes_str", how="outer"
        ).fillna(0).sort_values("mes_str")
        if not fc.empty:
            fc["Saldo"] = fc["Receita"] - fc["Despesa"]
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Bar(name="Despesas", x=fc["mes_str"], y=fc["Despesa"],
                                    marker_color="#E74C3C", opacity=0.7))
            fig_fc.add_trace(go.Bar(name="Receitas", x=fc["mes_str"], y=fc["Receita"],
                                    marker_color="#27AE60", opacity=0.7))
            fig_fc.add_trace(go.Scatter(name="Saldo", x=fc["mes_str"], y=fc["Saldo"],
                                        mode="lines+markers",
                                        line=dict(color="#2B59C3", width=2)))
            fig_fc.update_layout(barmode="group", height=320,
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02),
                                 xaxis_title="Mês", yaxis_tickformat=",.0f",
                                 margin=dict(t=10, b=40), plot_bgcolor="white",
                                 paper_bgcolor="white")
            st.plotly_chart(fig_fc, width='stretch')
        else:
            st.markdown('<p class="dash-empty">Sem lançamentos financeiros para exibir o fluxo de caixa.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        col_al, col_fp = st.columns([2, 1])
        with col_al:
            st.subheader("⚠️ Alertas Financeiros")
            alertas = contas_df[mask_alertas].copy()
            if len(alertas):
                cols_al = [c for c in ["Obra", "Fornecedor", "Valor (R$)", "Vencimento", "Status", "Categoria"]
                           if c in alertas.columns]
                al_exib = alertas[cols_al].copy()
                al_exib["Valor (R$)"] = al_exib["Valor (R$)"].apply(_fmt)
                st.dataframe(al_exib, width='stretch', hide_index=True)
            else:
                st.success("Nenhum alerta financeiro no momento.")
        with col_fp:
            st.subheader("👥 Resumo de Pessoal")
            n_clt  = len(func_df[func_df["Tipo Contrato"] == "CLT"]) \
                     if "Tipo Contrato" in func_df.columns else 0
            n_terc = len(func_df[func_df["Tipo Contrato"] == "Terceirizado"]) \
                     if "Tipo Contrato" in func_df.columns else 0
            st.metric("Total Colaboradores",  len(func_df))
            st.metric("CLT / Terceirizados",  f"{n_clt} / {n_terc}")
            st.metric("Custo Folha Estimado", f"R$ {total_folha:,.0f}".replace(",", "."),
                      help="Salário bruto × 1,31 (INSS + FGTS + RAT)")

        st.markdown('</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2 — POR OBRA
    # ═══════════════════════════════════════════════════════════════════════
    with tab_obra:
        obras_lista = obras_df["Nome"].tolist()
        if not obras_lista:
            st.markdown('<p class="dash-empty">Nenhuma obra cadastrada.</p>', unsafe_allow_html=True)
            return

        obra_sel = st.selectbox("Selecione a Obra", obras_lista, key="dash_obra_sel")
        o_row = obras_df[obras_df["Nome"] == obra_sel]
        if o_row.empty:
            return
        o = o_row.iloc[0]

        val_contrato   = _to_num(o.get("Valor Contrato (R$)", 0))
        pct_fisico     = _to_num(o.get("% Físico", 0))

        contas_obra = contas_df[contas_df["Obra"] == obra_sel].copy()
        custo_comp  = float(contas_obra["Valor (R$)"].sum())
        margem_est  = (val_contrato - custo_comp) / val_contrato * 100 if val_contrato else 0.0

        n_alert_obra = int(((contas_obra["Status"] == "Vencido") |
                            ((contas_obra["Status"] == "A Pagar") &
                             (contas_obra["venc_dt"] <= hoje + timedelta(days=7)))).sum())

        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avanço Físico",      f"{pct_fisico:.1f}%")
        k2.metric("Valor Contrato",     f"R$ {val_contrato:,.0f}".replace(",", "."))
        k3.metric("Custo Comprometido", f"R$ {custo_comp:,.0f}".replace(",", "."),
                  help="Soma das contas a pagar / pagas registradas nesta obra")
        if _role() == "admin":
            k4.metric("Margem Estimada", f"{margem_est:.1f}%",
                      delta="OK" if margem_est >= 10 else "Atenção",
                      delta_color="normal" if margem_est >= 10 else "inverse")
        else:
            k4.metric("Status", o.get("Status", "—"))

        st.caption(
            f"**Status:** {o.get('Status','—')}  |  "
            f"**Início:** {o.get('Início','—')}  |  "
            f"**Término:** {o.get('Término','—')}  |  "
            f"**Responsável:** {o.get('Responsável','—')}  |  "
            f"**Cliente:** {o.get('Cliente','—')}"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">📊 Custos e Equipe</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Custos por Categoria")
            if len(contas_obra) and "Categoria" in contas_obra.columns and custo_comp > 0:
                cc_obra = (contas_obra.groupby("Categoria")["Valor (R$)"].sum()
                           .reset_index().rename(columns={"Valor (R$)": "Total"}))
                fig_cc = px.pie(cc_obra, values="Total", names="Categoria",
                                color="Categoria", color_discrete_map=CAT_CORES,
                                hole=0.38, height=260)
                fig_cc.update_traces(textinfo="percent+label")
                fig_cc.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_cc, width='stretch')
            else:
                st.markdown('<p class="dash-empty">Sem lançamentos financeiros nesta obra.</p>', unsafe_allow_html=True)

        with col_b:
            st.subheader("Equipe Alocada")
            func_obra = func_df[func_df["Obra"] == obra_sel].copy() \
                        if "Obra" in func_df.columns else pd.DataFrame()
            if len(func_obra):
                sal_obra     = pd.to_numeric(func_obra.get("Salário", pd.Series([])), errors="coerce").fillna(0)
                custo_equipe = sal_obra.sum() * 1.31
                fe1, fe2 = st.columns(2)
                fe1.metric("Colaboradores",    len(func_obra))
                fe2.metric("Custo Equipe/Mês", f"R$ {custo_equipe:,.0f}".replace(",", "."))
                cols_f = [c for c in ["Nome", "Cargo", "Tipo Contrato", "Salário"]
                          if c in func_obra.columns]
                f_exib = func_obra[cols_f].copy()
                if "Salário" in f_exib.columns:
                    f_exib["Salário"] = f_exib["Salário"].apply(_fmt)
                st.dataframe(f_exib, width='stretch', hide_index=True)
            else:
                st.markdown('<p class="dash-empty">Nenhum colaborador alocado nesta obra.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown('<div class="dash-card-header">📋 Contas e Materiais</div>', unsafe_allow_html=True)
        col_c, col_d = st.columns(2)

        with col_c:
            st.subheader("Contas a Pagar / Pagas")
            if n_alert_obra:
                st.warning(f"{n_alert_obra} conta(s) vencida(s) ou a vencer em 7 dias.")
            if len(contas_obra):
                cols_cp = [c for c in ["Fornecedor", "Valor (R$)", "Vencimento", "Status", "Categoria"]
                           if c in contas_obra.columns]
                cp_exib = contas_obra[cols_cp].copy()
                cp_exib["Valor (R$)"] = cp_exib["Valor (R$)"].apply(_fmt)
                st.dataframe(cp_exib, width='stretch', hide_index=True)
            else:
                st.markdown('<p class="dash-empty">Sem contas registradas nesta obra.</p>', unsafe_allow_html=True)

        with col_d:
            st.subheader("Materiais em Alerta")
            est_obra = est_df[est_df["Obra"] == obra_sel].copy() \
                       if "Obra" in est_df.columns else pd.DataFrame()
            if len(est_obra):
                est_alerta = est_obra[est_obra["Estoque Atual"] < est_obra["Estoque Mínimo"]]
                em1, em2 = st.columns(2)
                em1.metric("Insumos cadastrados", len(est_obra))
                em2.metric("Abaixo do mínimo",   len(est_alerta),
                           delta=f"{len(est_alerta)} itens" if len(est_alerta) else "Tudo OK",
                           delta_color="inverse" if len(est_alerta) else "normal")
                if len(est_alerta):
                    st.dataframe(est_alerta[["Insumo", "Estoque Atual", "Estoque Mínimo", "Unidade"]],
                                 width='stretch', hide_index=True)
                else:
                    st.success("Todos os materiais acima do mínimo.")
            else:
                st.markdown('<p class="dash-empty">Sem insumos registrados nesta obra.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Orçamento importado — resumo executivo
        orc = _normalizar_orc_data(st.session_state.get("orcamento_por_obra", {}).get(obra_sel))
        if orc:
            itens = [r for r in orc if r["tipo"] == "ITEM"]
            if itens:
                st.markdown('<div class="dash-card">', unsafe_allow_html=True)
                st.markdown('<div class="dash-card-header">📊 Orçamento Importado — Resumo Executivo</div>', unsafe_allow_html=True)
                total_orc_custo = sum(r.get("total_custo") or 0 for r in itens)
                total_orc_venda = sum(r.get("total_venda") or 0 for r in itens)
                bdi_medio = (total_orc_venda / total_orc_custo - 1) * 100 if total_orc_custo else 0
                desvio    = custo_comp - total_orc_custo
                o1, o2, o3, o4 = st.columns(4)
                o1.metric("Custo Orçado",       f"R$ {total_orc_custo:,.0f}".replace(",", "."))
                o2.metric("Venda c/ BDI",        f"R$ {total_orc_venda:,.0f}".replace(",", "."))
                o3.metric("BDI Médio Aplicado",  f"{bdi_medio:.1f}%")
                o4.metric("Desvio (Real – Orc)", f"R$ {desvio:,.0f}".replace(",", "."),
                          delta="Estouro" if desvio > 0 else "Dentro do orçado",
                          delta_color="inverse" if desvio > 0 else "normal")
                st.markdown('</div>', unsafe_allow_html=True)

    # ── RELATÓRIO GERENCIAL PDF ───────────────────────────────────────────────
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown('<div class="dash-card-header">📑 Relatório Gerencial Mensal</div>', unsafe_allow_html=True)
    _rg_c1, _rg_c2 = st.columns([3, 1])
    _mes_ref = _rg_c1.text_input(
        "Mês de referência",
        value=__import__("datetime").date.today().strftime("%B/%Y"),
        key="rg_mes_ref",
        placeholder="Junho/2026",
    )
    if _rg_c2.button("📥 Gerar PDF", key="btn_gerar_rg", type="primary", width='stretch'):
        try:
            from gerar_pdf import gerar_relatorio_gerencial as _gerar_rg
            _dados_rg = {
                "mes_ref":        _mes_ref,
                "obras":          st.session_state.obras.copy(),
                "medicoes":       st.session_state.medicoes.copy(),
                "contas_pagar":   st.session_state.contas_pagar.copy(),
                "contas_receber": st.session_state.contas_receber.copy(),
                "ncs":            st.session_state.ncs.copy(),
                "funcionarios":   st.session_state.funcionarios.copy(),
            }
            _pdf_rg = _gerar_rg(_dados_rg)
            st.download_button(
                label="⬇️ Baixar Relatório Gerencial PDF",
                data=_pdf_rg,
                file_name=f"Relatorio_Gerencial_Prumo_{_mes_ref.replace('/','-')}.pdf",
                mime="application/pdf",
                key="btn_dl_rg",
            )
            st.success("✅ Relatório Gerencial gerado com sucesso!")
        except Exception as _e_rg:
            st.error(f"❌ Erro ao gerar relatório: {_e_rg}")

    st.markdown('</div>', unsafe_allow_html=True)


# ── Obras ────────────────────────────────────────────────────────────────────

def pagina_obras():
    st.title("🏗️ Obras")
    _init()
    _show_toast()
    aba = st.radio("Ação",["📋 Listagem","📏 Medições","➕ Nova Obra"],horizontal=True,label_visibility="collapsed")

    if aba == "📋 Listagem":
        obras = st.session_state.obras.copy()
        cf1,cf2 = st.columns(2)
        fs = cf1.selectbox("Status",["Todos"]+sorted([v for v in obras["Status"].unique() if pd.notna(v) and str(v).strip()]))
        fr = cf2.selectbox("Responsável",["Todos"]+sorted([v for v in obras["Responsável"].unique() if pd.notna(v) and str(v).strip()]))
        if fs != "Todos": obras = obras[obras["Status"]==fs]
        if fr != "Todos": obras = obras[obras["Responsável"]==fr]
        st.markdown(f"**{len(obras)} obra(s)**")

        if obras.empty:
            st.info("Nenhuma obra cadastrada. Use a aba ➕ Nova Obra.")
        else:
            _status_badge = {"Concluída":"🟢","Em andamento":"🔵","Planejamento":"🟡","Paralisada":"🟠","Cancelada":"🔴"}
            colunas_obra = ["Nome","Status","% Físico","Valor Contrato (R$)","Cliente","Responsável","Tipo","Início","Término"]
            L = _tabela_clicavel(
                obras, colunas_exibir=colunas_obra, key="tbl_obras",
                formatters={
                    "Valor Contrato (R$)": _fmt,
                    "Status": lambda s: f"{_status_badge.get(s,'⚪')} {s}",
                    "% Físico": lambda p: f"{int(p)}%",
                },
            )
            excel_src = obras.drop(columns=[c for c in ["ID","SB_ID"] if c in obras.columns]).copy()
            excel_src["Valor Contrato (R$)"] = excel_src["Valor Contrato (R$)"].apply(_fmt)
            st.download_button("⬇️ Exportar Excel", data=_export_excel(excel_src), file_name="obras.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="btn_xls_obras")

            if L is not None:
                id_sel = L["ID"]
                st.markdown("---")
                with st.container(border=True):
                    st.markdown(f"#### ✏️ Editando: {L['Nome']}")
                    with st.form("form_edit_obra"):
                        c1,c2 = st.columns(2)
                        nome   = c1.text_input("Nome",        value=L["Nome"])
                        cliente= c2.text_input("Cliente",     value=L["Cliente"])
                        cnpj   = c1.text_input("CNPJ Cliente",value=L.get("CNPJ Cliente",""))
                        tipo_opts = ["Residencial","Comercial","Industrial","Infraestrutura","Outro"]
                        tipo   = c2.selectbox("Tipo",tipo_opts,index=tipo_opts.index(L.get("Tipo","Residencial")) if L.get("Tipo","") in tipo_opts else 0)
                        end    = c1.text_input("Endereço",    value=L["Endereço"])
                        resp   = c2.text_input("Responsável", value=L["Responsável"])
                        valor  = c1.number_input("Valor Contrato (R$)",value=_to_num(L["Valor Contrato (R$)"]),step=1000.0)
                        if _role() == "admin":
                            bdi = c2.number_input("BDI (%)",value=float(L.get("BDI (%)",25.0)),min_value=0.0,max_value=100.0,step=0.5)
                        else:
                            bdi = float(L.get("BDI (%)", 25.0))
                        ini    = c1.text_input("Início",      value=L["Início"])
                        term   = c2.text_input("Término",     value=L["Término"])
                        pct    = c1.slider("% Físico",0,100,int(L["% Físico"]))
                        status_opts = ["Em andamento","Paralisada","Concluída","Planejamento","Cancelada"]
                        st_idx = status_opts.index(L["Status"]) if L["Status"] in status_opts else 0
                        stat   = c2.selectbox("Status",status_opts,index=st_idx)
                        b1,b2,_ = st.columns([1,1,3])
                        salvar  = b1.form_submit_button("💾 Salvar",type="primary")
                        excluir = b2.form_submit_button("🗑️ Excluir")
                    if salvar:
                        idx = st.session_state.obras[st.session_state.obras["ID"]==id_sel].index[0]
                        st.session_state.obras.loc[idx,["Nome","Tipo","Cliente","CNPJ Cliente","Endereço","Responsável","Valor Contrato (R$)","BDI (%)","Início","Término","% Físico","Status"]] = [nome,tipo,cliente,cnpj,end,resp,valor,bdi,ini,term,pct,stat]
                        try: sync.obra_save({"Nome":nome,"Tipo":tipo,"Cliente":cliente,"CNPJ Cliente":cnpj,"Endereço":end,"Responsável":resp,"Valor Contrato (R$)":valor,"BDI (%)":bdi,"Início":ini,"Término":term,"% Físico":pct,"Status":stat}, sb_id=_sb_id(st.session_state.obras, id_sel))
                        except Exception: st.warning("Obra salva localmente, mas falhou sincronização com servidor.")
                        _notify(f"✅ Obra **{nome}** atualizada com sucesso!"); st.rerun()
                    if excluir:
                        _nome_exc = L["Nome"]
                        uuid_exc = _sb_id(st.session_state.obras, id_sel)
                        st.session_state.obras = st.session_state.obras[st.session_state.obras["ID"]!=id_sel].reset_index(drop=True)
                        if uuid_exc: sync.obra_delete(uuid_exc)
                        _notify(f"✅ Obra **{_nome_exc}** removida!"); st.rerun()
    elif aba == "📏 Medições":
        st.subheader("Histórico de Medições")
        med_df = st.session_state.medicoes.copy()
        if not med_df.empty:
            obra_f_med = st.selectbox("Filtrar por Obra", ["Todas"] + _uniq(med_df["Obra"]), key="med_filtro_obra")
            med_view = med_df if obra_f_med == "Todas" else med_df[med_df["Obra"] == obra_f_med]
            med_view["Valor Medido (R$)"] = med_view["Valor Medido (R$)"].apply(_fmt)
            _med_exib = med_view.drop(columns=[c for c in ["ID","SB_ID"] if c in med_view.columns])
            st.dataframe(_med_exib, width='stretch', hide_index=True)
            st.download_button("⬇️ Exportar Excel", data=_export_excel(_med_exib), file_name="medicoes.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="btn_xls_med")
        else:
            st.info("Nenhuma medição registrada ainda.")

        # ── Exportar BM em PDF ─────────────────────────────────────────────
        if not med_df.empty:
            st.markdown("---")
            st.subheader("📄 Exportar Boletim de Medição (PDF)")
            obras_com_med = _uniq(med_df["Obra"])
            obra_bm_pdf = st.selectbox("Obra para o BM", obras_com_med, key="bm_pdf_obra")
            meds_obra = med_df[med_df["Obra"] == obra_bm_pdf].copy()
            if not meds_obra.empty:
                meds_obra["_label"] = meds_obra.apply(
                    lambda r: f"Período {r['Período']}  |  {r['% Medido']:.1f}%  |  {_fmt(_to_num(r['Valor Medido (R$)']))}",
                    axis=1,
                )
                lbl_sel = st.selectbox("Medição", meds_obra["_label"].tolist(), key="bm_pdf_med")
                med_row  = meds_obra[meds_obra["_label"] == lbl_sel].iloc[0]
                ob_row_bm = st.session_state.obras[st.session_state.obras["Nome"] == obra_bm_pdf]
                val_contrato_bm = _to_num(ob_row_bm["Valor Contrato (R$)"].iloc[0]) if not ob_row_bm.empty else 0.0
                cliente_bm      = ob_row_bm["Cliente"].iloc[0] if not ob_row_bm.empty else ""
                pct_acum_bm  = _to_num(med_row["% Medido"])
                val_per_bm   = _to_num(med_row["Valor Medido (R$)"])
                # Anterior = max de medições antes desta (por data)
                meds_ant = meds_obra[meds_obra["Período"] < med_row["Período"]]
                pct_ant_bm = _to_num(meds_ant["% Medido"].max()) if not meds_ant.empty else 0.0
                pct_per_bm = max(0.0, pct_acum_bm - pct_ant_bm)
                val_ant_bm = round(val_contrato_bm * pct_ant_bm / 100, 2)
                val_acum_bm = round(val_contrato_bm * pct_acum_bm / 100, 2)
                # Número sequencial do BM
                meds_sorted = meds_obra.sort_values("Período").reset_index(drop=True)
                num_bm_pdf  = int(meds_sorted[meds_sorted["Período"] == med_row["Período"]].index[0]) + 1
                dados_bm_pdf = {
                    "obra":           obra_bm_pdf,
                    "cliente":        cliente_bm,
                    "periodo":        med_row["Período"],
                    "num_bm":         num_bm_pdf,
                    "pct_anterior":   pct_ant_bm,
                    "pct_periodo":    pct_per_bm,
                    "pct_acumulado":  pct_acum_bm,
                    "valor_contrato": val_contrato_bm,
                    "valor_anterior": val_ant_bm,
                    "valor_periodo":  val_per_bm,
                    "valor_acumulado":val_acum_bm,
                }
                # Itens do orçamento (se carregados)
                orc_itens_bm = None
                orc_obra = st.session_state.get("orcamento_por_obra", {}).get(obra_bm_pdf)
                if orc_obra:
                    orc_itens_bm = [r for r in orc_obra if r.get("tipo") == "ITEM"]
                if orc_itens_bm:
                    st.caption(f"Orçamento carregado: **{len(orc_itens_bm)} itens** — PDF incluirá tabela detalhada.")
                else:
                    st.caption("Sem orçamento carregado para esta obra — PDF exibirá apenas o resumo financeiro.")
                if st.button("📥 Gerar PDF do Boletim de Medição", key="btn_gerar_bm", type="primary"):
                    try:
                        from gerar_pdf import gerar_bm as _gerar_bm
                        pdf_bytes = _gerar_bm(dados_bm_pdf, itens=orc_itens_bm)
                        nome_arq  = f"BM_{num_bm_pdf:02d}_{obra_bm_pdf[:20].replace(' ','_')}_{med_row['Período'].replace('/','_')}.pdf"
                        st.download_button(
                            label="⬇️ Baixar BM em PDF",
                            data=pdf_bytes,
                            file_name=nome_arq,
                            mime="application/pdf",
                            key="dl_bm_pdf",
                        )
                    except Exception as _e_bm:
                        st.error(f"Erro ao gerar PDF: {_e_bm}")

        st.markdown("---")
        st.subheader("Registrar Nova Medição")
        st.caption("A medição atualiza o **% Físico** da obra e gera automaticamente uma **Conta a Receber** no Financeiro.")
        obras_med = _obras_nomes()
        obra_med = st.selectbox("Obra *", obras_med, key="med_obra_sel")
        with st.form("form_medicao"):
            c1, c2 = st.columns(2)
            periodo_med = c1.text_input("Período (mês/ano) *", value=date.today().strftime("%m/%Y"))
            pct_med_inp = c2.number_input("% Medido (acumulado da obra) *", min_value=0.0, max_value=100.0, step=0.5, value=0.0,
                                           help="Informe o % físico ACUMULADO total da obra até este período.")
            obs_med     = c1.text_input("Observação")
            venc_med    = c2.text_input("Vencimento do BM", value=(date.today() + timedelta(days=15)).strftime("%d/%m/%Y"))
            ok_med = st.form_submit_button("📏 Registrar Medição", type="primary")
        if ok_med:
            if obra_med.startswith("("):
                st.error("Cadastre uma obra antes de registrar medições.")
            elif pct_med_inp <= 0:
                st.error("Informe o % medido acumulado.")
            else:
                # Valor contrato da obra
                ob_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_med]
                val_contrato_med = _to_num(ob_row["Valor Contrato (R$)"].iloc[0]) if not ob_row.empty else 0.0
                # Percentual anterior (para calcular incremento)
                med_ant = st.session_state.medicoes[st.session_state.medicoes["Obra"] == obra_med]
                pct_anterior = _to_num(med_ant["% Medido"].max()) if not med_ant.empty else 0.0
                pct_incremento = max(0.0, pct_med_inp - pct_anterior)
                valor_med = round(val_contrato_med * pct_incremento / 100, 2)
                # 1. Salva medição (local + Supabase)
                nova_med = {"ID": _next_id(st.session_state.medicoes),
                            "Data": date.today().strftime("%d/%m/%Y"),
                            "Obra": obra_med, "Período": periodo_med,
                            "% Medido": pct_med_inp, "Valor Medido (R$)": valor_med,
                            "Observação": obs_med}
                _uuid_med_sb = sync.medicao_save(nova_med, _obra_uuid(obra_med))
                nova_med["SB_ID"] = _uuid_med_sb or ""
                st.session_state.medicoes = pd.concat([
                    st.session_state.medicoes,
                    pd.DataFrame([nova_med])
                ], ignore_index=True)
                # 2. Atualiza % Físico na obra
                idx_ob = st.session_state.obras[st.session_state.obras["Nome"] == obra_med].index
                if len(idx_ob):
                    st.session_state.obras.loc[idx_ob[0], "% Físico"] = int(pct_med_inp)
                    _uuid_ob = _sb_id(st.session_state.obras, st.session_state.obras.loc[idx_ob[0], "ID"])
                    if _uuid_ob:
                        try:
                            from db import sb as _sb
                            _sb().table("obras").update({"pct_fisico": int(pct_med_inp)}).eq("id", _uuid_ob).execute()
                        except Exception:
                            st.warning("Não foi possível sincronizar % físico com o servidor.")
                # 3. Conta a Receber
                if valor_med > 0:
                    dados_bm = {"Obra": obra_med, "Cliente": ob_row["Cliente"].iloc[0] if not ob_row.empty else "",
                                "Descrição": f"BM {periodo_med} — {pct_incremento:.1f}% — {obra_med}",
                                "Valor (R$)": valor_med, "Vencimento": venc_med, "Status": "A Receber"}
                    uuid_bm = sync.lancamento_save(dados_bm, "RECEBER", _obra_uuid(obra_med))
                    st.session_state.contas_receber = pd.concat([
                        st.session_state.contas_receber,
                        pd.DataFrame([{"ID": _next_id(st.session_state.contas_receber),
                                       "SB_ID": uuid_bm or None, **dados_bm}])
                    ], ignore_index=True)
                st.success(f"✅ Medição registrada! {obra_med} avançou para **{pct_med_inp:.0f}%** físico. "
                           + (f"Conta a Receber de **{_fmt(valor_med)}** gerada." if valor_med > 0 else ""))
                st.rerun()
    else:
        if _limite_obras_atingido():
            info = _plano_info()
            st.warning(f"🚫 Seu plano **{info.get('plano_slug','').title()}** permite no máximo **{info.get('max_obras')} obra(s)**. "
                       f"Faça upgrade para cadastrar mais.")
        with st.form("form_nova_obra"):
            c1,c2 = st.columns(2)
            nome   = c1.text_input("Nome *")
            cliente= c2.text_input("Cliente *")
            cnpj   = c1.text_input("CNPJ Cliente")
            tipo   = c2.selectbox("Tipo",["Residencial","Comercial","Industrial","Infraestrutura","Outro"])
            end    = c1.text_input("Endereço")
            resp   = c2.text_input("Responsável")
            valor  = c1.number_input("Valor Contrato (R$)",min_value=0.0,step=1000.0)
            if _role() == "admin":
                bdi = c2.number_input("BDI (%)",min_value=0.0,max_value=100.0,value=25.0,step=0.5)
            else:
                bdi = 25.0
            ini    = c1.text_input("Início (dd/mm/aaaa)",value=date.today().strftime("%d/%m/%Y"))
            term   = c2.text_input("Término (dd/mm/aaaa)")
            pct    = c1.slider("% Físico Inicial",0,100,0)
            stat   = c2.selectbox("Status",["Planejamento","Em andamento","Paralisada","Concluída","Cancelada"])
            ok = st.form_submit_button("➕ Cadastrar",type="primary")
        if ok:
            if _limite_obras_atingido():
                info = _plano_info()
                st.error(f"🚫 Limite de **{info.get('max_obras')} obra(s)** do plano **{info.get('plano_slug','').title()}** atingido.")
            elif not nome or not cliente: st.error("Nome e Cliente obrigatórios.")
            else:
                dados_nova = {"Nome":nome,"Tipo":tipo,"Cliente":cliente,"CNPJ Cliente":cnpj,"Endereço":end,"Valor Contrato (R$)":valor,"BDI (%)":bdi,"Início":ini,"Término":term,"% Físico":pct,"Status":stat,"Responsável":resp}
                uuid_nova = sync.obra_save(dados_nova)
                if not uuid_nova:
                    try:
                        from db import sb_admin
                        admin = sb_admin()
                        if admin:
                            from sync import _empresa_id
                            payload = dict(dados_nova)
                            payload["empresa_id"] = _empresa_id()
                            r2 = admin.table("obras").insert(payload).execute()
                            uuid_nova = r2.data[0]["id"] if r2.data else None
                    except Exception:
                        pass
                st.session_state.obras = pd.concat([st.session_state.obras,pd.DataFrame([{"ID":_next_id(st.session_state.obras),"SB_ID":uuid_nova or "","Nome":nome,"Tipo":tipo,"Cliente":cliente,"CNPJ Cliente":cnpj,"Endereço":end,"Valor Contrato (R$)":valor,"BDI (%)":bdi,"Início":ini,"Término":term,"% Físico":pct,"Status":stat,"Responsável":resp}])],ignore_index=True)
                _notify(f"✅ Obra **{nome}** cadastrada com sucesso!"); st.rerun()


# ── Suprimentos ──────────────────────────────────────────────────────────────

def pagina_suprimentos():
    import plotly.graph_objects as go
    st.title("📦 Suprimentos")
    _init()
    _show_toast()
    aba = st.radio("Ação",["📦 Estoque","🔄 Movimentações","📝 Requisições","📋 Cotações","🏢 Fornecedores","👷 Subempreiteiros","➕ Movimentar","📋 Entrada de NF"],horizontal=True,label_visibility="collapsed")

    if aba == "📦 Estoque":
        est = st.session_state.estoque.copy()
        if "Estoque Mínimo" not in est.columns:
            est["Estoque Mínimo"] = 10
        est["Situação"] = est.apply(lambda r: "🔴 Abaixo do mínimo" if float(r.get("Estoque Atual",0)) < float(r.get("Estoque Mínimo",10)) else "🟢 OK", axis=1)
        c1,c2,c3 = st.columns(3)
        c1.metric("Insumos Cadastrados",len(est))
        c2.metric("Itens em Alerta",len(est[est["Estoque Atual"]<est["Estoque Mínimo"]]))
        c3.metric("Obras Abastecidas",est["Obra"].nunique())
        st.markdown("---")
        fo = st.selectbox("Obra",["Todas"]+_uniq(est["Obra"]))
        if fo != "Todas": est = est[est["Obra"]==fo]
        _est_exib = est.drop(columns=[c for c in ["ID","SB_ID"] if c in est.columns])
        st.dataframe(_est_exib, width='stretch', hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(_est_exib), file_name="estoque.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_estoque")

    elif aba == "🔄 Movimentações":
        mov = st.session_state.movimentacoes.copy()
        if "Tipo" not in mov.columns:
            mov["Tipo"] = ""
        ft = st.radio("Tipo",["Todos","Entrada","Saída"],horizontal=True)
        if ft != "Todos": mov = mov[mov["Tipo"]==ft]
        _mov_exib = mov.drop(columns=[c for c in ["ID","SB_ID"] if c in mov.columns])
        st.dataframe(_mov_exib, width='stretch', hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(_mov_exib), file_name="movimentacoes.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_mov")
        # ── Alertas de Estoque ────────────────────────────────────────────
        st.markdown("---")
        st.subheader("⚠️ Alertas de Estoque")
        est = st.session_state.estoque.copy()
        est["Estoque Atual"]  = pd.to_numeric(est["Estoque Atual"],  errors="coerce").fillna(0.0)
        est["Estoque Mínimo"] = pd.to_numeric(est["Estoque Mínimo"], errors="coerce").fillna(0.0)
        est["_status"] = est.apply(
            lambda r: "✅ OK" if r["Estoque Atual"] >= r["Estoque Mínimo"]
                      else ("🔴 CRÍTICO" if r["Estoque Atual"] <= r["Estoque Mínimo"] * 0.5
                            else "🟡 BAIXO"), axis=1
        )
        criticos = est[est["_status"] != "✅ OK"].sort_values("Estoque Atual")
        if criticos.empty:
            st.success("Todos os insumos estão acima do estoque mínimo.")
        else:
            st.caption(f"{len(criticos)} insumo(s) abaixo do mínimo")
            # Gráfico horizontal: saldo atual vs mínimo
            fig_alerta = go.Figure()
            fig_alerta.add_trace(go.Bar(
                name="Estoque Mínimo",
                x=criticos["Estoque Mínimo"],
                y=criticos["Insumo"] + " / " + criticos["Obra"].fillna(""),
                orientation="h",
                marker_color="#E74C3C",
                opacity=0.4,
            ))
            fig_alerta.add_trace(go.Bar(
                name="Saldo Atual",
                x=criticos["Estoque Atual"],
                y=criticos["Insumo"] + " / " + criticos["Obra"].fillna(""),
                orientation="h",
                marker_color="#2B59C3",
            ))
            fig_alerta.update_layout(
                barmode="overlay",
                height=max(200, len(criticos) * 45),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=0, r=20, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_title="Quantidade",
            )
            st.plotly_chart(fig_alerta, width='stretch')
            # Tabela resumida
            st.dataframe(
                criticos[["Insumo","Obra","Unidade","Estoque Atual","Estoque Mínimo","_status"]]
                .rename(columns={"_status":"Status"}),
                hide_index=True, width='stretch'
            )

    elif aba == "📝 Requisições":
        req = st.session_state.requisicoes.copy()
        badges = {"Aprovada": "🟢", "Pendente": "🟡", "Reprovada": "🔴"}

        # ── Filtros ────────────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns(3)
        obras_req  = ["Todas"] + _uniq(req["Obra"]) if not req.empty else ["Todas"]
        fil_obra   = fc1.selectbox("Filtrar por Obra",   obras_req,                     key="req_fil_obra")
        fil_status = fc2.selectbox("Filtrar por Status", ["Todos","Pendente","Aprovada","Reprovada"], key="req_fil_st")
        if fc3.button("🔄 Recarregar", key="req_reload"):
            try:
                from sync import requisicoes_load
                st.session_state.requisicoes = requisicoes_load()
                st.rerun()
            except Exception:
                pass

        req_view = req.copy()
        if fil_obra   != "Todas":   req_view = req_view[req_view["Obra"]   == fil_obra]
        if fil_status != "Todos":   req_view = req_view[req_view["Status"] == fil_status]

        req_disp = req_view.copy()
        req_disp["Status"] = req_disp["Status"].apply(lambda s: f"{badges.get(s,'⚪')} {s}")
        colunas_vis = [c for c in req_disp.columns if c not in ("ID","SB_ID")]
        st.dataframe(req_disp[colunas_vis], width='stretch', hide_index=True)

        # Métricas rápidas
        m1, m2, m3 = st.columns(3)
        m1.metric("Total",    len(req))
        m2.metric("Pendentes", len(req[req["Status"] == "Pendente"]))
        m3.metric("Aprovadas", len(req[req["Status"] == "Aprovada"]))
        st.markdown("---")

        # ── Aprovar / Reprovar (apenas admin/gestor) ──────────────────
        pendentes = req[req["Status"] == "Pendente"]
        if not pendentes.empty and _role() in ("admin", "gestor"):
            st.subheader("Aprovar / Reprovar Requisição")
            opc_req = {
                f"[{r.ID}] {getattr(r,'Insumo','?')} — {getattr(r,'Quantidade',0)} {getattr(r,'Unidade','un')} — {getattr(r,'Obra','?')}": r
                for r in pendentes.itertuples()
            }
            sel_req_label = st.selectbox("Requisição pendente", list(opc_req.keys()), key="sel_req_ap")
            row_req = opc_req[sel_req_label]
            sb_id_req = getattr(row_req, "SB_ID", None)

            ra, rb = st.columns(2)
            if ra.button("✅ Aprovar — dar saída no estoque", type="primary", key="btn_req_ap"):
                usuario = st.session_state.get("user_email", "gestor")
                # 1. Supabase
                if sb_id_req:
                    try:
                        from sync import requisicao_status_update
                        requisicao_status_update(sb_id_req, "Aprovada", usuario)
                    except Exception:
                        pass
                # 2. Session state
                mask_ss = st.session_state.requisicoes["ID"] == row_req.ID
                st.session_state.requisicoes.loc[mask_ss, "Status"]      = "Aprovada"
                st.session_state.requisicoes.loc[mask_ss, "Aprovado Por"] = usuario
                st.session_state.requisicoes.loc[mask_ss, "Data Aprovação"] = date.today().strftime("%d/%m/%Y")
                # 3. Saída no estoque local
                mask_est = (
                    (st.session_state.estoque["Insumo"] == row_req.Insumo) &
                    (st.session_state.estoque["Obra"]   == row_req.Obra)
                )
                idx_est = st.session_state.estoque[mask_est].index
                if len(idx_est):
                    novo_saldo = max(0.0, float(st.session_state.estoque.loc[idx_est[0], "Estoque Atual"]) - float(row_req.Quantidade))
                    st.session_state.estoque.loc[idx_est[0], "Estoque Atual"] = novo_saldo
                    st.success(f"✅ Aprovada! Saída de **{row_req.Quantidade} {row_req.Unidade}** de **{row_req.Insumo}** "
                               f"em **{row_req.Obra}**. Novo saldo: {novo_saldo:.2f} {row_req.Unidade}.")
                else:
                    st.warning(f"Aprovada, mas **{row_req.Insumo}** não encontrado no estoque de **{row_req.Obra}**.")
                # 4. Movimentação de saída local
                st.session_state.movimentacoes = pd.concat([
                    st.session_state.movimentacoes,
                    pd.DataFrame([{"ID": _next_id(st.session_state.movimentacoes),
                                   "Data": date.today().strftime("%d/%m/%Y"),
                                   "Tipo": "Saída", "Insumo": row_req.Insumo,
                                   "Quantidade": row_req.Quantidade, "Obra": row_req.Obra,
                                   "Responsável": row_req.Solicitante, "NF/Doc": "REQ"}])
                ], ignore_index=True)
                # 5. E-mail de notificação
                try:
                    from alertas import _enviar_email
                    if not _enviar_email(
                        assunto=f"[Prumo ERP] Requisição Aprovada — {row_req.Insumo}",
                        corpo=(f"Requisição aprovada por {usuario}.\n\n"
                               f"Insumo: {row_req.Insumo}\nQuantidade: {row_req.Quantidade} {row_req.Unidade}\n"
                               f"Obra: {row_req.Obra}\nSolicitante: {row_req.Solicitante}")
                    ):
                        st.warning("Requisição aprovada, mas falhou envio de e-mail.")
                except Exception:
                    st.warning("Requisição aprovada, mas falhou envio de e-mail.")
                st.rerun()
            if rb.button("❌ Reprovar", key="btn_req_rep"):
                if sb_id_req:
                    try:
                        from sync import requisicao_status_update
                        requisicao_status_update(sb_id_req, "Reprovada")
                    except Exception:
                        pass
                mask_ss = st.session_state.requisicoes["ID"] == row_req.ID
                st.session_state.requisicoes.loc[mask_ss, "Status"] = "Reprovada"
                st.info("Requisição reprovada.")
                st.rerun()
            st.markdown("---")
        elif not pendentes.empty:
            st.info(f"Há **{len(pendentes)}** requisição(ões) pendente(s) aguardando aprovação do gestor.")

        # ── Nova Requisição ───────────────────────────────────────────
        st.subheader("Nova Requisição de Material")
        insumos_opcoes = _uniq(st.session_state.estoque["Insumo"]) if not st.session_state.estoque.empty else []
        with st.form("form_req"):
            c1, c2 = st.columns(2)
            obra_r    = c1.selectbox("Obra",      _obras_nomes(), key="req_obra")
            insumo_r  = c2.selectbox("Insumo",    insumos_opcoes if insumos_opcoes else [""], key="req_insumo")
            qtd_r     = c1.number_input("Quantidade",  min_value=0.01, step=1.0,  value=1.0, key="req_qtd")
            un_r      = c2.text_input("Unidade",  value="un", key="req_un")
            sol_r     = c1.text_input("Solicitante", key="req_sol")
            obs_r     = c2.text_input("Observação",  key="req_obs")
            st.markdown("##### 🔗 Vinculação à EAP")
            c3, c4 = st.columns(2)
            tipo_custo_r = c3.selectbox("Tipo de Custo",
                ["","Material","Mão-de-obra","Equipamento","Subempreiteiro","Administrativo"])
            eap_item_id_r = None
            try:
                obra_uuid_r = _obra_uuid(obra_r)
                if obra_uuid_r:
                    df_eap_r = db.eap_itens_por_obra(obra_uuid_r)
                    if not df_eap_r.empty:
                        eap_opts_r = {f"{r['codigo']} — {r['descricao']} (R$ {_fmt(r['valor_previsto'])})": r['id'] for _, r in df_eap_r.iterrows()}
                        eap_opts_r = {"(nenhum)": ""} | eap_opts_r
                        eap_sel_r = c4.selectbox("Etapa EAP", list(eap_opts_r.keys()))
                        eap_item_id_r = eap_opts_r[eap_sel_r] or None
            except Exception:
                pass
            ok_r      = st.form_submit_button("📝 Enviar Requisição", type="primary")
        if ok_r:
            dados_req = {"Data": date.today().strftime("%d/%m/%Y"), "Obra": obra_r,
                         "Insumo": insumo_r, "Quantidade": qtd_r, "Unidade": un_r,
                         "Solicitante": sol_r, "Observação": obs_r,
                         "eap_item_id": eap_item_id_r, "tipo_custo": tipo_custo_r or None}
            sb_id_novo = None
            try:
                from sync import requisicao_save
                sb_id_novo = requisicao_save(dados_req)
            except Exception:
                pass
            novo = {"ID": _next_id(st.session_state.requisicoes), "SB_ID": sb_id_novo,
                    "Status": "Pendente", "Aprovado Por": "", "Data Aprovação": "", **dados_req}
            st.session_state.requisicoes = pd.concat(
                [st.session_state.requisicoes, pd.DataFrame([novo])], ignore_index=True
            )
            _notify(f"✅ Requisição de **{qtd_r} {un_r}** de **{insumo_r}** enviada para aprovação!")
            st.rerun()
    elif aba == "➕ Movimentar":
        st.subheader("Registrar Movimentação")
        with st.form("form_mov"):
            c1,c2 = st.columns(2)
            tipo_m   = c1.radio("Tipo", ["Entrada","Saída"])
            obra_m   = c2.selectbox("Obra", _obras_nomes())
            insumo_m = c1.selectbox("Insumo", _uniq(st.session_state.estoque["Insumo"]) or [""])
            qtd_m    = c2.number_input("Quantidade", min_value=0.01, step=1.0)
            resp_m   = c1.text_input("Responsável")
            doc_m    = c2.text_input("NF / Documento")
            ok_m = st.form_submit_button("✅ Registrar", type="primary")
        if ok_m:
            # Localiza o saldo atual do insumo nessa obra
            mask_e = (
                (st.session_state.estoque["Insumo"] == insumo_m) &
                (st.session_state.estoque["Obra"]   == obra_m)
            )
            idx_e       = st.session_state.estoque[mask_e].index
            saldo_atual = float(st.session_state.estoque.loc[idx_e[0], "Estoque Atual"]) if len(idx_e) else 0.0
            _ref_est    = st.session_state.estoque[st.session_state.estoque["Insumo"] == insumo_m]
            _un_ref     = str(_ref_est["Unidade"].iloc[0]) if not _ref_est.empty and "Unidade" in _ref_est.columns else "un"

            if tipo_m == "Saída":
                # ── Valida saldo antes de permitir saída ──────────────────────
                if not len(idx_e) or saldo_atual <= 0:
                    st.error(
                        f"❌ **{insumo_m}** não possui estoque na obra **{obra_m}**. "
                        f"Registre uma Entrada antes de fazer uma Saída."
                    )
                elif qtd_m > saldo_atual:
                    st.error(
                        f"❌ Saldo insuficiente. **{insumo_m}** em **{obra_m}** tem apenas "
                        f"**{saldo_atual:.2f} {_un_ref}** disponíveis. "
                        f"Você tentou retirar **{qtd_m:.2f} {_un_ref}**."
                    )
                else:
                    # Saída válida — registra
                    novo_saldo = saldo_atual - qtd_m
                    st.session_state.estoque.loc[idx_e[0], "Estoque Atual"] = novo_saldo
                    st.session_state.movimentacoes = pd.concat([
                        st.session_state.movimentacoes,
                        pd.DataFrame([{"ID": _next_id(st.session_state.movimentacoes),
                                       "Data": date.today().strftime("%d/%m/%Y"),
                                       "Tipo": "Saída", "Insumo": insumo_m,
                                       "Quantidade": qtd_m, "Obra": obra_m,
                                       "Responsável": resp_m, "NF/Doc": doc_m}])
                    ], ignore_index=True)
                    try:
                        sync.estoque_movimento_save(
                            {"Insumo": insumo_m, "Unidade": _un_ref, "Tipo": "Saída",
                             "Quantidade": qtd_m, "Observação": doc_m},
                            _obra_uuid(obra_m) if _obra_valida(obra_m) else None
                        )
                    except Exception:
                        st.warning("Movimento salvo localmente, mas falhou sincronização.")
                    st.success(
                        f"✅ Saída de **{qtd_m:.2f} {_un_ref}** de **{insumo_m}** registrada. "
                        f"Saldo restante em {obra_m}: **{novo_saldo:.2f} {_un_ref}**"
                    )
                    st.rerun()
            else:
                # ── Entrada ───────────────────────────────────────────────────
                if len(idx_e):
                    novo_saldo = saldo_atual + qtd_m
                    st.session_state.estoque.loc[idx_e[0], "Estoque Atual"] = novo_saldo
                    st.success(f"✅ Entrada de **{qtd_m:.2f} {_un_ref}** de **{insumo_m}** registrada. "
                               f"Saldo em {obra_m}: **{novo_saldo:.2f} {_un_ref}**")
                else:
                    # Insumo ainda sem estoque nessa obra — cria nova linha
                    min_ref = _ref_est["Estoque Mínimo"].iloc[0] if not _ref_est.empty else 0.0
                    st.session_state.estoque = pd.concat([
                        st.session_state.estoque,
                        pd.DataFrame([{"ID": _next_id(st.session_state.estoque),
                                       "Insumo": insumo_m, "Unidade": _un_ref,
                                       "Estoque Atual": qtd_m, "Estoque Mínimo": min_ref,
                                       "Obra": obra_m}])
                    ], ignore_index=True)
                    st.success(f"✅ Entrada de **{qtd_m:.2f} {_un_ref}** de **{insumo_m}** registrada para {obra_m}!")
                st.session_state.movimentacoes = pd.concat([
                    st.session_state.movimentacoes,
                    pd.DataFrame([{"ID": _next_id(st.session_state.movimentacoes),
                                   "Data": date.today().strftime("%d/%m/%Y"),
                                   "Tipo": "Entrada", "Insumo": insumo_m,
                                   "Quantidade": qtd_m, "Obra": obra_m,
                                   "Responsável": resp_m, "NF/Doc": doc_m}])
                ], ignore_index=True)
                try:
                    sync.estoque_movimento_save(
                        {"Insumo": insumo_m, "Unidade": _un_ref, "Tipo": "Entrada",
                         "Quantidade": qtd_m, "Observação": doc_m},
                        _obra_uuid(obra_m) if _obra_valida(obra_m) else None
                    )
                except Exception:
                    st.warning("Movimento salvo localmente, mas falhou sincronização.")
                st.rerun()

    elif aba == "📋 Cotações":
        st.subheader("📋 Cotações")
        from sync import cotacoes_load, cotacao_save, cotacao_delete as _cot_delete, cotacao_itens_load

        if "cotacoes" not in st.session_state:
            st.session_state.cotacoes = cotacoes_load()

        tab_lista, tab_nova = st.tabs(["📋 Lista de Cotações", "➕ Nova Cotação"])

        with tab_nova:
            with st.form("form_cotacao"):
                c1, c2 = st.columns(2)
                forn_opts = _uniq(st.session_state.fornecedores["Razão Social"]) if "fornecedores" in st.session_state and not st.session_state.fornecedores.empty else []
                forn_c = c1.selectbox("Fornecedor *", forn_opts if forn_opts else [""])
                obra_c = c2.selectbox("Obra", _obras_nomes())
                data_c = c1.text_input("Data", value=date.today().strftime("%Y-%m-%d"))
                val_c = c2.text_input("Validade")
                cond_c = c1.text_input("Condição Pagamento")
                prazo_c = c2.number_input("Prazo Entrega (dias)", min_value=0, value=0, step=1)
                obs_c = st.text_area("Observação", height=80)

                st.markdown("##### Itens da Cotação")
                st.caption("Adicione os itens com quantidade e preço")
                qtd_itens = st.number_input("Quantidade de itens", min_value=1, max_value=50, value=1, step=1, key="qtd_itens_cot")

                itens_data = []
                for idx in range(int(qtd_itens)):
                    ci1, ci2, ci3, ci4 = st.columns([3, 1, 1, 1])
                    desc = ci1.text_input(f"Descrição #{idx+1}", key=f"cot_desc_{idx}")
                    qtd = ci2.number_input(f"Qtd #{idx+1}", min_value=0.0, value=0.0, step=1.0, key=f"cot_qtd_{idx}")
                    un = ci3.text_input(f"Un #{idx+1}", value="un", key=f"cot_un_{idx}")
                    pu = ci4.number_input(f"R$/un #{idx+1}", min_value=0.0, value=0.0, step=0.01, key=f"cot_pu_{idx}")
                    if desc.strip():
                        itens_data.append({"descricao": desc, "quantidade": qtd, "unidade": un, "preco_unit": pu})

                ok_c = st.form_submit_button("💾 Salvar Cotação", type="primary")
            if ok_c:
                if not forn_c.strip():
                    st.error("Selecione um fornecedor.")
                elif not itens_data:
                    st.error("Adicione pelo menos um item.")
                else:
                    total = sum(it["quantidade"] * it["preco_unit"] for it in itens_data)
                    dados_c = {"Fornecedor": forn_c, "Obra": obra_c,
                               "Data": data_c, "Validade": val_c,
                               "Condição Pag.": cond_c, "Prazo Entrega": str(prazo_c),
                               "Total (R$)": total, "Vencedora": "Não"}
                    sb_id_c = cotacao_save(dados_c, itens_data)
                    st.session_state.cotacoes = pd.concat([
                        st.session_state.cotacoes,
                        pd.DataFrame([{"ID": _next_id(st.session_state.cotacoes), "SB_ID": sb_id_c or None, **dados_c}])
                    ], ignore_index=True)
                    _notify(f"Cotação de **{forn_c}** — R$ {_fmt(total)} salva!"); st.rerun()

        with tab_lista:
            df_cot = st.session_state.cotacoes.copy()
            if df_cot.empty:
                st.info("Nenhuma cotação registrada. Crie na aba ➕ Nova Cotação.")
            else:
                col_cot = ["Data", "Fornecedor", "Obra", "Total (R$)", "Vencedora", "Validade"]
                col_cot = [c for c in col_cot if c in df_cot.columns]
                sel_cot = _tabela_clicavel(df_cot, colunas_exibir=col_cot, key="tbl_cot",
                    formatters={"Total (R$)": _fmt, "Vencedora": lambda s: "✅" if s == "Sim" else "○"})

                if isinstance(sel_cot, pd.DataFrame) and not sel_cot.empty:
                    row_c = sel_cot.iloc[0]
                    cot_sb_id = _sb_id(st.session_state.cotacoes, row_c["ID"])
                    st.markdown("---")
                    with st.container(border=True):
                        st.markdown(f"#### 📋 {row_c['Fornecedor']} — {row_c['Obra']}")
                        c1, c2 = st.columns(2)
                        c1.markdown(f"**Data:** {row_c.get('Data','')}")
                        c2.markdown(f"**Validade:** {row_c.get('Validade','')}")
                        st.markdown(f"**Total:** {_fmt(float(row_c.get('Total (R$)',0)))}")
                        if cot_sb_id:
                            itens_cot = cotacao_itens_load(cot_sb_id)
                            if itens_cot:
                                st.markdown("##### Itens")
                                for it in itens_cot:
                                    q = float(it.get("quantidade", 0) or 0)
                                    p = float(it.get("preco_unit", 0) or 0)
                                    t = float(it.get("total", 0) or 0)
                                    st.markdown(f"- {it.get('descricao','?')} — {q:.2f} {it.get('unidade','un')} x R$ {p:.2f} = **R$ {t:.2f}**")
                        b1, b2, b3 = st.columns([1, 1, 3])
                        if row_c.get("Vencedora") != "Sim" and b1.button("🏆 Marcar como Vencedora", key=f"venc_{row_c['ID']}", type="primary"):
                            idx_v = st.session_state.cotacoes[st.session_state.cotacoes["ID"] == row_c["ID"]].index[0]
                            st.session_state.cotacoes.loc[idx_v, "Vencedora"] = "Sim"
                            if cot_sb_id: cotacao_save({"Vencedora": "Sim"}, sb_id=cot_sb_id)
                            _notify(f"Cotação de **{row_c['Fornecedor']}** marcada como vencedora!"); st.rerun()
                        _del_cot_key = f"_del_cot_{row_c['ID']}"
                        if st.session_state.get(_del_cot_key):
                            if b2.button("✅ Confirmar", key=f"del_cot_yes_{row_c['ID']}"):
                                st.session_state[_del_cot_key] = False
                                if cot_sb_id: _cot_delete(cot_sb_id)
                                st.session_state.cotacoes = st.session_state.cotacoes[
                                    st.session_state.cotacoes["ID"] != row_c["ID"]
                                ].reset_index(drop=True)
                                _notify("Cotação excluída!"); st.rerun()
                        elif b2.button("🗑️", key=f"del_cot_{row_c['ID']}"):
                            st.session_state[_del_cot_key] = True
                            st.rerun()

    elif aba == "🏢 Fornecedores":
        st.subheader("🏢 Fornecedores")
        from sync import fornecedores_load, fornecedor_save, fornecedor_delete as _forn_delete
        if "fornecedores" not in st.session_state:
            st.session_state.fornecedores = fornecedores_load()
        df_forn = st.session_state.fornecedores.copy()

        with st.expander("➕ Novo Fornecedor", expanded=False):
            with st.form("form_novo_forn"):
                c1, c2 = st.columns(2)
                rz = c1.text_input("Razão Social *")
                fn = c2.text_input("Nome Fantasia")
                cnpj = c1.text_input("CNPJ")
                email = c2.text_input("Email")
                tel = c1.text_input("Telefone")
                end = c2.text_input("Endereço")
                cat = c1.selectbox("Categoria", ["Materiais", "Serviços", "Equipamentos", "Transporte", "Outros"])
                ok_f = st.form_submit_button("💾 Salvar Fornecedor", type="primary")
            if ok_f:
                if not rz.strip():
                    st.error("Razão Social é obrigatória.")
                else:
                    dados_f = {"Razão Social": rz, "Nome Fantasia": fn, "CNPJ": cnpj,
                               "Email": email, "Telefone": tel, "Endereço": end, "Categoria": cat, "Ativo": "Sim"}
                    sb_id_f = fornecedor_save(dados_f)
                    st.session_state.fornecedores = pd.concat([
                        st.session_state.fornecedores,
                        pd.DataFrame([{"ID": _next_id(st.session_state.fornecedores), "SB_ID": sb_id_f or None, **dados_f}])
                    ], ignore_index=True)
                    _notify(f"Fornecedor **{rz}** cadastrado!"); st.rerun()

        st.markdown("---")
        c1f, c2f = st.columns(2)
        f_cat = c1f.selectbox("Filtrar por Categoria", ["Todas"] + _uniq(df_forn["Categoria"]) if not df_forn.empty else ["Todas"])
        f_atv = c2f.selectbox("Filtrar por Status", ["Todos", "Sim", "Não"])
        if f_cat != "Todas": df_forn = df_forn[df_forn["Categoria"] == f_cat]
        if f_atv != "Todos": df_forn = df_forn[df_forn["Ativo"] == f_atv]

        st.metric("Total de Fornecedores", len(df_forn))
        _fc = ["CNPJ","Razão Social","Nome Fantasia","Email","Telefone","Categoria","Ativo"]
        sel_cols = [c for c in _fc if c in df_forn.columns]
        sel_forn = _tabela_clicavel(df_forn, colunas_exibir=sel_cols, key="tbl_forn")

        if isinstance(sel_forn, pd.DataFrame) and not sel_forn.empty:
            st.markdown("---")
            with st.container(border=True):
                st.markdown(f"#### ✏️ {sel_forn['Razão Social'].iloc[0]}")
                row_f = sel_forn.iloc[0]
                with st.form("form_edit_forn"):
                    c1, c2 = st.columns(2)
                    e_rz = c1.text_input("Razão Social", value=row_f.get("Razão Social", ""))
                    e_fn = c2.text_input("Nome Fantasia", value=row_f.get("Nome Fantasia", ""))
                    e_cnpj = c1.text_input("CNPJ", value=row_f.get("CNPJ", ""))
                    e_email = c2.text_input("Email", value=row_f.get("Email", ""))
                    e_tel = c1.text_input("Telefone", value=row_f.get("Telefone", ""))
                    e_end = c2.text_input("Endereço", value=row_f.get("Endereço", ""))
                    e_cat = c1.selectbox("Categoria", ["Materiais", "Serviços", "Equipamentos", "Transporte", "Outros"],
                                         index=["Materiais", "Serviços", "Equipamentos", "Transporte", "Outros"].index(row_f.get("Categoria", "Materiais")) if row_f.get("Categoria", "Materiais") in ["Materiais", "Serviços", "Equipamentos", "Transporte", "Outros"] else 0)
                    e_atv = c2.selectbox("Ativo", ["Sim", "Não"], index=0 if row_f.get("Ativo", "Sim") == "Sim" else 1)
                    b1, b2, _ = st.columns([1, 1, 3])
                    sv_f = b1.form_submit_button("💾 Salvar", type="primary")
                    del_f = b2.form_submit_button("🗑️ Excluir")
                if sv_f:
                    idx_f = st.session_state.fornecedores[st.session_state.fornecedores["ID"] == row_f["ID"]].index[0]
                    novos_dados = {"Razão Social": e_rz, "Nome Fantasia": e_fn, "CNPJ": e_cnpj,
                                   "Email": e_email, "Telefone": e_tel, "Endereço": e_end, "Categoria": e_cat, "Ativo": e_atv}
                    for k, v in novos_dados.items():
                        st.session_state.fornecedores.loc[idx_f, k] = v
                    sb_id_f = _sb_id(st.session_state.fornecedores, row_f["ID"])
                    fornecedor_save(novos_dados, sb_id=sb_id_f)
                    _notify(f"Fornecedor **{e_rz}** atualizado!"); st.rerun()
                if del_f:
                    sb_id_f = _sb_id(st.session_state.fornecedores, row_f["ID"])
                    if sb_id_f: _forn_delete(sb_id_f)
                    st.session_state.fornecedores = st.session_state.fornecedores[
                        st.session_state.fornecedores["ID"] != row_f["ID"]
                    ].reset_index(drop=True)
                    _notify(f"Fornecedor **{row_f['Razão Social']}** excluído!"); st.rerun()

    elif aba == "👷 Subempreiteiros":
        st.subheader("👷 Subempreiteiros")
        try:
            from sync import (subempreiteiros_load, subempreiteiro_save, subempreiteiro_delete,
                              subempreiteiro_contratos_load, subempreiteiro_contrato_save,
                              subempreiteiro_contrato_delete,
                              subempreiteiro_medicoes_load, subempreiteiro_medicao_save,
                              subempreiteiro_medicao_delete,
                              subempreiteiro_documentos_load, subempreiteiro_documento_save,
                              subempreiteiro_documento_delete)
        except Exception:
            st.error("Erro ao carregar módulo de subempreiteiros.")
        else:
            if "subempreiteiros_df" not in st.session_state:
                st.session_state.subempreiteiros_df = subempreiteiros_load()

            sub_tabs = st.tabs(["📋 Cadastro", "📄 Contratos", "📏 Medições", "📁 Documentos"])

            # ── TAB 1: Cadastro ──────────────────────────────────────────────
            with sub_tabs[0]:
                c1, c2 = st.columns([3, 1])
                with c1:
                    _df_sub = st.session_state.subempreiteiros_df
                    if not _df_sub.empty:
                        __cols_disp = [c for c in _df_sub.columns if c not in ("ID", "SB_ID")]
                        st.dataframe(_df_sub[__cols_disp], width='stretch', hide_index=True)
                with c2:
                    if st.button("➕ Novo Subempreiteiro", use_container_width=True):
                        st.session_state["_sub_form"] = not st.session_state.get("_sub_form", False)
                if st.session_state.get("_sub_form", False):
                    with st.form("sub_form", border=True):
                        col1, col2 = st.columns(2)
                        rz = col1.text_input("Razão Social *")
                        nf = col2.text_input("Nome Fantasia")
                        cnpj = col1.text_input("CNPJ")
                        contato = col2.text_input("Contato")
                        tel = col1.text_input("Telefone")
                        email = col2.text_input("Email")
                        crea = col1.text_input("CREA/CA")
                        esp = col2.text_input("Especialidades (separadas por vírgula)")
                        ender = st.text_input("Endereço")
                        obs = st.text_area("Observações", height=80)
                        b1, b2 = st.columns([1, 3])
                        if b1.form_submit_button("💾 Salvar", type="primary"):
                            if rz.strip():
                                dados_sub = {"Razão Social": rz, "Nome Fantasia": nf, "CNPJ": cnpj,
                                             "Contato": contato, "Telefone": tel, "Email": email,
                                             "CREA/CA": crea, "Especialidades": esp, "Ativo": "Sim"}
                                _sb_id = subempreiteiro_save(dados_sub)
                                if _sb_id:
                                    st.session_state["_sub_form"] = False
                                    st.cache_data.clear()
                                    st.session_state.subempreiteiros_df = subempreiteiros_load()
                                    _notify("Subempreiteiro cadastrado!"); st.rerun()
                                else:
                                    st.error("Erro ao salvar. Verifique os dados.")
                            else:
                                st.warning("Razão Social é obrigatória.")
                        if b2.form_submit_button("Cancelar"):
                            st.session_state["_sub_form"] = False
                            st.rerun()
                # ── Edição inline ───────────────────────────────────────
                if not _df_sub.empty:
                    with st.expander("✏️ Editar / Excluir"):
                        nomes_sub = _df_sub["Razão Social"].tolist()
                        sel_sub_nome = st.selectbox("Selecione o subempreiteiro", nomes_sub, key="sub_edit_sel")
                        _matches_sub = _df_sub[_df_sub["Razão Social"] == sel_sub_nome]
                        if _matches_sub.empty:
                            st.warning("Registro não encontrado. Selecione outro.")
                            row_sub = _df_sub.iloc[0]
                        else:
                            row_sub = _matches_sub.iloc[0]
                        with st.form("sub_edit_form", border=True):
                            ec1, ec2 = st.columns(2)
                            e_rz = ec1.text_input("Razão Social", value=row_sub.get("Razão Social", ""))
                            e_nf = ec2.text_input("Nome Fantasia", value=row_sub.get("Nome Fantasia", ""))
                            e_cnpj = ec1.text_input("CNPJ", value=row_sub.get("CNPJ", ""))
                            e_ct = ec2.text_input("Contato", value=row_sub.get("Contato", ""))
                            e_tel = ec1.text_input("Telefone", value=row_sub.get("Telefone", ""))
                            e_email = ec2.text_input("Email", value=row_sub.get("Email", ""))
                            e_crea = ec1.text_input("CREA/CA", value=row_sub.get("CREA/CA", ""))
                            e_esp = ec2.text_input("Especialidades", value=row_sub.get("Especialidades", ""))
                            e_atv = st.selectbox("Ativo", ["Sim", "Não"],
                                                 index=0 if row_sub.get("Ativo", "Sim") == "Sim" else 1)
                            bx1, bx2, _ = st.columns([1, 1, 3])
                            sv_sub = bx1.form_submit_button("💾 Salvar", type="primary")
                            del_sub = bx2.form_submit_button("🗑️ Excluir")
                        if sv_sub:
                            dados_up = {"Razão Social": e_rz, "Nome Fantasia": e_nf, "CNPJ": e_cnpj,
                                        "Contato": e_ct, "Telefone": e_tel, "Email": e_email,
                                        "CREA/CA": e_crea, "Especialidades": e_esp, "Ativo": e_atv}
                            sb_id_sub = _sb_id(st.session_state.subempreiteiros_df, row_sub["ID"])
                            subempreiteiro_save(dados_up, sb_id=sb_id_sub)
                            st.cache_data.clear()
                            st.session_state.subempreiteiros_df = subempreiteiros_load()
                            _notify("Subempreiteiro atualizado!"); st.rerun()
                        if del_sub:
                            sb_id_sub = _sb_id(st.session_state.subempreiteiros_df, row_sub["ID"])
                            if sb_id_sub:
                                subempreiteiro_delete(sb_id_sub)
                            st.session_state.subempreiteiros_df = st.session_state.subempreiteiros_df[
                                st.session_state.subempreiteiros_df["ID"] != row_sub["ID"]
                            ].reset_index(drop=True)
                            _notify("Subempreiteiro excluído!"); st.rerun()

            # ── TAB 2: Contratos ────────────────────────────────────────────
            with sub_tabs[1]:
                c_sub_obra = st.selectbox("Filtrar por Obra", ["Todas"] + _obras_nomes(), key="sub_ct_obra")
                c_sub_forn = st.selectbox("Filtrar por Subempreiteiro", ["Todos"] + _df_sub["Razão Social"].tolist() if not _df_sub.empty else ["Todos"], key="sub_ct_forn")
                _obra_uuid_ct = _obra_uuid(c_sub_obra) if c_sub_obra != "Todas" else None
                _sub_id_ct = None
                if c_sub_forn != "Todos" and not _df_sub.empty:
                    _match_sub = _df_sub[_df_sub["Razão Social"] == c_sub_forn]
                    if not _match_sub.empty:
                        _sub_id_ct = _sb_id(st.session_state.subempreiteiros_df, _match_sub["ID"].iloc[0])
                _contratos_df = subempreiteiro_contratos_load(_sub_id_ct, _obra_uuid_ct)
                if not _contratos_df.empty:
                    __cols_ct = [c for c in _contratos_df.columns if c not in ("ID", "SB_ID", "Subempreiteiro ID")]
                    st.dataframe(_contratos_df[__cols_ct], width='stretch', hide_index=True)
                else:
                    st.info("Nenhum contrato encontrado.")
                with st.expander("➕ Novo Contrato"):
                    with st.form("sub_ct_form", border=True):
                        ct_sub = st.selectbox("Subempreiteiro *", _df_sub["Razão Social"].tolist() if not _df_sub.empty else [])
                        ct_obra = st.selectbox("Obra *", _obras_nomes())
                        ct_num = st.text_input("Nº Contrato *")
                        ct_objeto = st.text_area("Objeto *", height=60)
                        ct_v, ct_p = st.columns(2)
                        ct_valor = ct_v.number_input("Valor (R$)", min_value=0.0, value=0.0, step=1000.0)
                        ct_prazo = ct_p.number_input("Prazo (dias)", min_value=0, value=0)
                        ct_dt_ini, ct_dt_fim, ct_ret = st.columns(3)
                        ct_ini = ct_dt_ini.date_input("Início", value="today")
                        ct_fim = ct_dt_fim.date_input("Fim")
                        ct_retencao = ct_ret.number_input("Retenção (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                        ct_cond = st.text_input("Condições de Pagamento")
                        ct_obs = st.text_area("Observações", height=60)
                        if st.form_submit_button("💾 Salvar Contrato", type="primary"):
                            if ct_sub and ct_obra and ct_num.strip() and ct_objeto.strip():
                                _match_ct = _df_sub[_df_sub["Razão Social"] == ct_sub]
                                _ct_sub_id = _sb_id(st.session_state.subempreiteiros_df,
                                                     _match_ct["ID"].iloc[0]) if not _match_ct.empty else None
                                _ct_obra_id = _obra_uuid(ct_obra)
                                dados_ct = {
                                    "subempreiteiro_id": _ct_sub_id,
                                    "obra_id": _ct_obra_id,
                                    "Nº Contrato": ct_num,
                                    "Objeto": ct_objeto,
                                    "Valor (R$)": ct_valor,
                                    "Início": ct_ini.isoformat(),
                                    "Fim": ct_fim.isoformat() if ct_fim else None,
                                    "Prazo Dias": ct_prazo,
                                    "Condições Pagamento": ct_cond,
                                    "Retenção (%)": ct_retencao,
                                    "Status": "vigente",
                                    "Observações": ct_obs,
                                }
                                subempreiteiro_contrato_save(dados_ct)
                                st.cache_data.clear()
                                _notify("Contrato cadastrado!"); st.rerun()
                            else:
                                st.warning("Preencha todos os campos obrigatórios (*).")
                if not _contratos_df.empty:
                    with st.expander("🗑️ Excluir Contrato"):
                        sel_ct = st.selectbox("Selecione o contrato",
                                              _contratos_df["Nº Contrato"].tolist(), key="sub_ct_del_sel")
                        if st.button("🗑️ Excluir Contrato", type="secondary"):
                            _match_ct_del = _contratos_df[_contratos_df["Nº Contrato"] == sel_ct]
                            if _match_ct_del.empty:
                                st.warning("Contrato não encontrado.")
                            else:
                                row_ct = _match_ct_del.iloc[0]
                                sb_id_ct = _sb_id(_contratos_df, row_ct["ID"])
                                if sb_id_ct:
                                    subempreiteiro_contrato_delete(sb_id_ct)
                                st.cache_data.clear()
                                _notify("Contrato excluído!"); st.rerun()

            # ── TAB 3: Medições ─────────────────────────────────────────────
            with sub_tabs[2]:
                if not _contratos_df.empty:
                    sel_med_ct = st.selectbox("Selecione o Contrato",
                                              _contratos_df["Nº Contrato"].tolist(), key="sub_med_ct_sel")
                    _match_med_ct = _contratos_df[_contratos_df["Nº Contrato"] == sel_med_ct]
                    if _match_med_ct.empty:
                        st.warning("Contrato não encontrado no filtro atual.")
                    else:
                        row_med_ct = _match_med_ct.iloc[0]
                        _med_contrato_id = _sb_id(_contratos_df, row_med_ct["ID"])
                        _medicoes_df = subempreiteiro_medicoes_load(_med_contrato_id)
                        if not _medicoes_df.empty:
                            __cols_med = [c for c in _medicoes_df.columns if c not in ("ID", "SB_ID")]
                            st.dataframe(_medicoes_df[__cols_med], width='stretch', hide_index=True)
                            total_med = _medicoes_df["Valor Aprovado"].sum()
                            st.metric("Total Aprovado", _fmt(total_med))
                        else:
                            st.info("Nenhuma medição registrada para este contrato.")
                        with st.expander("➕ Nova Medição"):
                            with st.form("sub_med_form", border=True):
                                mc1, mc2 = st.columns(2)
                                med_mes = mc1.date_input("Mês Referência", value="today")
                                med_vm = mc2.number_input("Valor Medido (R$)", min_value=0.0, value=0.0, step=100.0)
                                med_va, med_pe = st.columns(2)
                                med_val_aprov = med_va.number_input("Valor Aprovado (R$)", min_value=0.0, value=0.0, step=100.0)
                                med_pct = med_pe.number_input("% Executado", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                                mc3, mc4 = st.columns(2)
                                med_ret = mc3.number_input("Retenção (R$)", min_value=0.0, value=0.0, step=100.0)
                                med_vl = mc4.number_input("Valor Líquido (R$)", min_value=0.0, value=0.0, step=100.0)
                                med_dp = st.date_input("Data Pagamento")
                                med_obs = st.text_area("Observações", height=60)
                                if st.form_submit_button("💾 Salvar Medição", type="primary"):
                                    dados_med = {
                                        "contrato_id": _med_contrato_id,
                                        "Mês Ref.": med_mes.isoformat()[:7] + "-01",
                                        "Valor Medido": med_vm,
                                        "Valor Aprovado": med_val_aprov,
                                        "% Exec.": med_pct,
                                        "Retenção": med_ret,
                                        "Valor Líquido": med_vl,
                                        "Data Pagamento": med_dp.isoformat() if med_dp else None,
                                        "Status": "aprovado" if med_val_aprov > 0 else "medido",
                                    }
                                    subempreiteiro_medicao_save(dados_med)
                                    st.cache_data.clear()
                                    _notify("Medição registrada!"); st.rerun()
                else:
                    st.info("Cadastre um contrato primeiro.")

            # ── TAB 4: Documentos ───────────────────────────────────────────
            with sub_tabs[3]:
                sel_doc_sub = st.selectbox("Selecione o Subempreiteiro",
                                           _df_sub["Razão Social"].tolist() if not _df_sub.empty else [], key="sub_doc_sel")
                if sel_doc_sub:
                    _match_doc_sub = _df_sub[_df_sub["Razão Social"] == sel_doc_sub]
                    _doc_sub_id = _sb_id(st.session_state.subempreiteiros_df,
                                         _match_doc_sub["ID"].iloc[0]) if not _match_doc_sub.empty else None
                    _docs_df = subempreiteiro_documentos_load(_doc_sub_id)
                    if not _docs_df.empty:
                        __cols_doc = [c for c in _docs_df.columns if c not in ("ID", "SB_ID")]
                        st.dataframe(_docs_df[__cols_doc], width='stretch', hide_index=True)
                        # Alertas de vencimento
                        for _, doc_row in _docs_df.iterrows():
                            dias_str = doc_row.get("Dias p/ Venc.", "")
                            if dias_str and dias_str.lstrip("-").isdigit():
                                dias_int = int(dias_str)
                                if dias_int <= 0:
                                    st.error(f"🔴 VENCIDO: {doc_row['Tipo']} — {doc_row.get('Número', '')}")
                                elif dias_int <= 30:
                                    st.warning(f"🟡 Vence em {dias_int} dias: {doc_row['Tipo']} — {doc_row.get('Número', '')}")
                    else:
                        st.info("Nenhum documento registrado.")
                    with st.expander("➕ Novo Documento"):
                        with st.form("sub_doc_form", border=True):
                            doc_tipo = st.selectbox("Tipo *", ["ART", "Alvará", "Seguro", "Certidão", "Contrato Social", "Outro"])
                            doc_num = st.text_input("Número")
                            doc_emi, doc_val = st.columns(2)
                            doc_emissao = doc_emi.date_input("Data Emissão")
                            doc_validade = doc_val.date_input("Data Validade")
                            doc_obs = st.text_area("Observações", height=60)
                            if st.form_submit_button("💾 Salvar Documento", type="primary"):
                                dados_doc = {
                                    "subempreiteiro_id": _doc_sub_id,
                                    "Tipo": doc_tipo,
                                    "Número": doc_num,
                                    "Emissão": doc_emissao.isoformat() if doc_emissao else None,
                                    "Validade": doc_validade.isoformat() if doc_validade else None,
                                    "Observações": doc_obs,
                                }
                                subempreiteiro_documento_save(dados_doc)
                                st.cache_data.clear()
                                _notify("Documento registrado!"); st.rerun()
                    if not _docs_df.empty:
                        with st.expander("🗑️ Excluir Documento"):
                            _doc_labels = _docs_df.apply(
                                lambda r: f"{r['Tipo']} — {r.get('Número', '') if r.get('Número', '') else '(sem nº)'}", axis=1
                            ).tolist()
                            sel_doc_label = st.selectbox("Selecione o documento", _doc_labels, key="sub_doc_del_sel")
                            if st.button("🗑️ Excluir", type="secondary"):
                                _idx_doc = _doc_labels.index(sel_doc_label)
                                row_doc = _docs_df.iloc[_idx_doc]
                                sb_id_doc = _sb_id(_docs_df, row_doc["ID"])
                                if sb_id_doc:
                                    subempreiteiro_documento_delete(sb_id_doc)
                                st.cache_data.clear()
                                _notify("Documento excluído!"); st.rerun()

    elif aba == "📋 Entrada de NF":
        st.subheader("📋 Entrada de Nota Fiscal")
        st.caption("Registra a NF, atualiza o estoque e gera automaticamente uma Conta a Pagar no Financeiro.")

        # Obra (fora do form para manter estado ao adicionar insumo)
        obra_nf = st.selectbox("Obra *", _obras_nomes(), key="nf_obra_sel")

        # ── Seleção de insumo com cadastro dinâmico ───────────────────
        st.markdown("**Insumo ***")
        NOVA_OPCAO = "➕ Cadastrar novo insumo..."
        insumos_base = _uniq(st.session_state.estoque["Insumo"])
        mat_choice = st.selectbox("Selecione o insumo ou cadastre um novo",
                                  [NOVA_OPCAO] + insumos_base, key="nf_mat_sel")

        if mat_choice == NOVA_OPCAO:
            ci1, ci2, ci3 = st.columns([3, 1, 1])
            n_nome = ci1.text_input("Nome do insumo *", key="nf_n_nome",
                                     placeholder="Ex.: Cimento CP-V ARI (sc 50kg)")
            n_un   = ci2.text_input("Unidade", key="nf_n_un", placeholder="sc")
            n_min  = ci3.number_input("Est. mínimo", min_value=0.0, value=0.0, key="nf_n_min")
            if st.button("➕ Salvar insumo na base", key="btn_add_ins", type="secondary"):
                nome_novo = n_nome.strip()
                if not nome_novo:
                    st.error("Informe o nome do insumo.")
                elif nome_novo in st.session_state.estoque["Insumo"].values:
                    st.warning(f"'{nome_novo}' já existe. Selecione-o na lista acima.")
                else:
                    st.session_state.estoque = pd.concat([
                        st.session_state.estoque,
                        pd.DataFrame([{"ID": _next_id(st.session_state.estoque),
                                       "Insumo": nome_novo, "Unidade": n_un,
                                       "Estoque Atual": 0.0, "Estoque Mínimo": n_min,
                                       "Obra": obra_nf}])
                    ], ignore_index=True)
                    _notify(f"'{nome_novo}' cadastrado! Agora selecione-o no campo acima.")
                    st.rerun()
            insumo_final = n_nome.strip()
        else:
            insumo_final = mat_choice

        st.markdown("---")

        # ── Formulário da NF ──────────────────────────────────────────
        with st.form("form_entrada_nf"):
            c1, c2, c3 = st.columns(3)
            forn_nf = c1.text_input("Fornecedor *")
            num_nf  = c2.text_input("Número da NF", value="NF-")
            data_nf = c3.text_input("Data da NF", value=date.today().strftime("%d/%m/%Y"))
            qtd_nf  = c1.number_input("Quantidade", min_value=0.001, step=1.0, value=1.0)
            un_nf   = c2.text_input("Unidade")
            obs_nf  = c3.text_input("Observação")
            st.markdown("**Dados Financeiros**")
            cf1, cf2, cf3 = st.columns(3)
            val_nf   = cf1.number_input("Valor Total da NF (R$)", min_value=0.0, step=100.0)
            venc_nf  = cf2.text_input("Data de Vencimento",
                                       value=(date.today() + timedelta(days=30)).strftime("%d/%m/%Y"))
            forma_nf = cf3.selectbox("Forma de Pagamento",
                                      ["Boleto", "PIX", "Transferência", "Cartão", "Cheque", "A definir"])
            ok_nf = st.form_submit_button("📥 Registrar Entrada + Gerar Conta a Pagar", type="primary")

        if ok_nf:
            erros_nf = []
            if not insumo_final:       erros_nf.append("selecione ou cadastre um insumo")
            if not forn_nf.strip():    erros_nf.append("informe o Fornecedor")
            if val_nf <= 0:            erros_nf.append("informe o Valor Total da NF (maior que zero)")
            if erros_nf:
                st.error("❌ Corrija antes de salvar: " + " · ".join(erros_nf))
            else:
                # 1. Movimentação
                st.session_state.movimentacoes = pd.concat([
                    st.session_state.movimentacoes,
                    pd.DataFrame([{"ID": _next_id(st.session_state.movimentacoes),
                                   "Data": data_nf, "Tipo": "Entrada",
                                   "Insumo": insumo_final, "Quantidade": qtd_nf,
                                   "Obra": obra_nf, "Responsável": forn_nf.strip(),
                                   "NF/Doc": num_nf}])
                ], ignore_index=True)
                # 2. Estoque — busca por Insumo + Obra para não misturar saldos entre obras
                mask_e = (
                    (st.session_state.estoque["Insumo"] == insumo_final) &
                    (st.session_state.estoque["Obra"]   == obra_nf)
                )
                idx_e = st.session_state.estoque[mask_e].index
                if len(idx_e):
                    st.session_state.estoque.loc[idx_e[0], "Estoque Atual"] += qtd_nf
                else:
                    ref = st.session_state.estoque[st.session_state.estoque["Insumo"] == insumo_final]
                    un_ref  = ref["Unidade"].iloc[0]        if len(ref) else (un_nf or "")
                    min_ref = ref["Estoque Mínimo"].iloc[0] if len(ref) else 0.0
                    st.session_state.estoque = pd.concat([
                        st.session_state.estoque,
                        pd.DataFrame([{"ID": _next_id(st.session_state.estoque),
                                       "Insumo": insumo_final, "Unidade": un_nf or un_ref,
                                       "Estoque Atual": qtd_nf, "Estoque Mínimo": min_ref,
                                       "Obra": obra_nf}])
                    ], ignore_index=True)
                # 3. Conta a Pagar — sempre executada, mesmo se Supabase falhar
                desc_cp     = f"NF {num_nf} — Compra de Material: {insumo_final}"
                dados_cp_nf = {"Obra": obra_nf, "Fornecedor": forn_nf.strip(),
                               "Descrição": desc_cp, "Categoria": "Materiais",
                               "Valor (R$)": val_nf, "Vencimento": venc_nf,
                               "Status": "A Pagar", "NF": num_nf, "Forma Pag.": forma_nf}
                try:
                    uuid_cp_nf = sync.lancamento_save(dados_cp_nf, "PAGAR", _obra_uuid(obra_nf))
                except Exception:
                    uuid_cp_nf = None
                st.session_state.contas_pagar = pd.concat([
                    st.session_state.contas_pagar,
                    pd.DataFrame([{"ID": _next_id(st.session_state.contas_pagar),
                                   "SB_ID": uuid_cp_nf or None, **dados_cp_nf}])
                ], ignore_index=True)
                st.success(
                    f"✅ Entrada registrada! Conta a Pagar de **{_fmt(val_nf)}** "
                    f"gerada para **{forn_nf.strip()}** — venc. {venc_nf} via {forma_nf}."
                )
                st.rerun()


# ── Financeiro ────────────────────────────────────────────────────────────────

def pagina_financeiro():
    import plotly.express as px
    import plotly.graph_objects as go
    st.title("💰 Financeiro")
    _init()
    _show_toast()

    CATS     = ["Materiais", "Folha de Pagamento", "Impostos", "Outros"]
    CAT_CORES = {"Materiais":"#2B59C3", "Folha de Pagamento":"#E67E22",
                 "Impostos":"#E74C3C",  "Outros":"#95A5A6"}

    tab_pg, tab_rc, tab_novo, tab_custo, tab_alocar, tab_dre, tab_fc, tab_conc = st.tabs(
        ["💸 Contas a Pagar","💵 Contas a Receber","➕ Novo Lançamento","📊 Custos por Obra","🔗 Alocar Custos à EAP","📈 DRE por Obra","📊 Fluxo de Caixa","🏦 Conciliação"]
    )

    def _tabela_financ(df_key):
        df = st.session_state[df_key].copy()
        todas_obras = sorted(_obras_nomes())
        c1,c2 = st.columns(2)
        f_ob = c1.selectbox("Obra", ["Todas"] + todas_obras, key=f"fo_{df_key}")
        f_st = c2.selectbox("Status",["Todos"]+_uniq(df["Status"]), key=f"fs_{df_key}")
        if f_ob != "Todas": df = df[df["Obra"]==f_ob]
        if f_st != "Todos": df = df[df["Status"]==f_st]
        return df

    # ── Contas a Pagar ────────────────────────────────────────────────
    with tab_pg:
        df = _tabela_financ("contas_pagar")

        # Filtro adicional por Categoria
        cats_disp = ["Todas"] + CATS
        f_cat = st.selectbox("Categoria", cats_disp, key="fo_cat_pg")
        if f_cat != "Todas":
            df = df[df.get("Categoria", pd.Series(dtype=str)) == f_cat] if "Categoria" in df.columns else df

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total",   _fmt(df["Valor (R$)"].sum()))
        c2.metric("Pago",    _fmt(df[df["Status"]=="Pago"]["Valor (R$)"].sum()))
        c3.metric("A Pagar", _fmt(df[df["Status"]=="A Pagar"]["Valor (R$)"].sum()))
        c4.metric("Vencido", _fmt(df[df["Status"]=="Vencido"]["Valor (R$)"].sum()), delta_color="inverse")
        st.markdown("---")

        badges = {"Pago":"🟢","A Pagar":"🟡","Vencido":"🔴"}
        if df.empty:
            st.info("Nenhum lançamento a pagar. Use a aba ➕ Novo Lançamento.")
        else:
            colunas_cp = ["Fornecedor","Descrição","Categoria","Valor (R$)","Vencimento","Status"]
            colunas_cp = [c for c in colunas_cp if c in df.columns]

            sel_cp = _tabela_clicavel(
                df, colunas_exibir=colunas_cp, key="tbl_cp",
                formatters={"Valor (R$)": _fmt, "Status": lambda s: f"{badges.get(s,'⚪')} {s}"},
                selection_mode="multi-row",
            )

            ex = df.pipe(_sem_id).copy()
            ex["Valor (R$)"] = ex["Valor (R$)"].apply(_fmt)
            st.download_button("⬇️ Exportar Excel", data=_export_excel(ex), file_name="contas_pagar.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="btn_xls_cp")

            if isinstance(sel_cp, pd.DataFrame) and not sel_cp.empty:
                st.markdown("---")
                n_sel = len(sel_cp)
                if n_sel == 1:
                    # Edição individual
                    LP = sel_cp.iloc[0]
                    with st.container(border=True):
                        st.markdown(f"#### ✏️ {LP['Fornecedor']} — {LP.get('Descrição','')}")
                        ca, cb = st.columns(2)
                        with ca:
                            st_opts_p = ["Pago","A Pagar","Vencido","Cancelado"]
                            ns_p = st.selectbox("Novo Status", st_opts_p,
                                                 index=st_opts_p.index(LP["Status"]) if LP["Status"] in st_opts_p else 0,
                                                 key="ns_cp")
                            if st.button("✅ Atualizar", key="btn_cp", type="primary"):
                                ix = st.session_state.contas_pagar[st.session_state.contas_pagar["ID"]==LP["ID"]].index[0]
                                st.session_state.contas_pagar.loc[ix,"Status"] = ns_p
                                uuid_cp = _sb_id(st.session_state.contas_pagar, LP["ID"])
                                if uuid_cp: sync.lancamento_status_update(uuid_cp, ns_p)
                                _notify(f"✅ Status atualizado para **{ns_p}**!"); st.rerun()
                        with cb:
                            if st.button("🗑️ Excluir Lançamento", key="del_cp"):
                                uuid_cp_del = _sb_id(st.session_state.contas_pagar, LP["ID"])
                                st.session_state.contas_pagar = st.session_state.contas_pagar[
                                    st.session_state.contas_pagar["ID"] != LP["ID"]
                                ].reset_index(drop=True)
                                if uuid_cp_del: sync.lancamento_delete(uuid_cp_del)
                                _notify(f"✅ Lançamento excluído com sucesso!"); st.rerun()
                else:
                    # Ação em lote
                    cols_lote = st.columns([2, 2, 1])
                    with cols_lote[0]:
                        st.caption(f"**{n_sel}** lançamento(s) selecionado(s)")
                    with cols_lote[1]:
                        novo_status_lote = st.selectbox("Novo Status", ["Pago", "A Pagar", "Vencido", "Cancelado"], key="ns_lote_cp")
                    with cols_lote[2]:
                        st.write("")
                        st.write("")
                        if st.button("✅ Aplicar em Lote", key="btn_lote_cp", type="primary"):
                            for idx, row in sel_cp.iterrows():
                                st.session_state.contas_pagar.loc[idx, "Status"] = novo_status_lote
                                uuid_cp = _sb_id(st.session_state.contas_pagar, row["ID"])
                                if uuid_cp:
                                    sync.lancamento_status_update(uuid_cp, novo_status_lote)
                            _notify(f"✅ {n_sel} lançamento(s) atualizados para **{novo_status_lote}**!")
                            st.rerun()

    # ── Contas a Receber ──────────────────────────────────────────────
    with tab_rc:
        df_r = _tabela_financ("contas_receber")
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Previsto", _fmt(df_r["Valor (R$)"].sum()))
        c2.metric("Recebido",       _fmt(df_r[df_r["Status"]=="Recebido"]["Valor (R$)"].sum()))
        c3.metric("A Receber",      _fmt(df_r[df_r["Status"]=="A Receber"]["Valor (R$)"].sum()))
        st.markdown("---")
        badges_r = {"Recebido":"🟢","A Receber":"🟡","Vencido":"🔴"}
        if df_r.empty:
            st.info("Nenhum lançamento a receber. Use a aba ➕ Novo Lançamento.")
        else:
            colunas_cr = ["Cliente","Descrição","Valor (R$)","Vencimento","Status"]
            colunas_cr = [c for c in colunas_cr if c in df_r.columns]

            sel_cr = _tabela_clicavel(
                df_r, colunas_exibir=colunas_cr, key="tbl_cr",
                formatters={"Valor (R$)": _fmt, "Status": lambda s: f"{badges_r.get(s,'⚪')} {s}"},
                selection_mode="multi-row",
            )

            ex_r = df_r.drop(columns=[c for c in ["ID","SB_ID"] if c in df_r.columns]).copy()
            ex_r["Valor (R$)"] = ex_r["Valor (R$)"].apply(_fmt)
            st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_r), file_name="contas_receber.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="btn_xls_cr")

            if isinstance(sel_cr, pd.DataFrame) and not sel_cr.empty:
                st.markdown("---")
                n_sel_r = len(sel_cr)
                if n_sel_r == 1:
                    # Edição individual
                    LR = sel_cr.iloc[0]
                    with st.container(border=True):
                        st.markdown(f"#### ✏️ {LR['Cliente']} — {LR.get('Descrição','')}")
                        ca_r, cb_r = st.columns(2)
                        with ca_r:
                            st_opts_r = ["Recebido","A Receber","Vencido","Cancelado"]
                            ns_r = st.selectbox("Novo Status", st_opts_r,
                                                 index=st_opts_r.index(LR["Status"]) if LR["Status"] in st_opts_r else 0,
                                                 key="ns_cr")
                            if st.button("✅ Atualizar", key="btn_cr", type="primary"):
                                ix_r = st.session_state.contas_receber[
                                    st.session_state.contas_receber["ID"] == LR["ID"]
                                ].index[0]
                                st.session_state.contas_receber.loc[ix_r,"Status"] = ns_r
                                uuid_cr = _sb_id(st.session_state.contas_receber, LR["ID"])
                                if uuid_cr: sync.lancamento_status_update(uuid_cr, ns_r)
                                _notify(f"✅ Status atualizado para **{ns_r}**!"); st.rerun()
                        with cb_r:
                            if st.button("🗑️ Excluir", key="del_cr"):
                                uuid_cr_del = _sb_id(st.session_state.contas_receber, LR["ID"])
                                st.session_state.contas_receber = st.session_state.contas_receber[
                                    st.session_state.contas_receber["ID"] != LR["ID"]
                                ].reset_index(drop=True)
                                if uuid_cr_del: sync.lancamento_delete(uuid_cr_del)
                                _notify(f"✅ Lançamento excluído com sucesso!"); st.rerun()
                else:
                    # Ação em lote
                    cols_lote_r = st.columns([2, 2, 1])
                    with cols_lote_r[0]:
                        st.caption(f"**{n_sel_r}** lançamento(s) selecionado(s)")
                    with cols_lote_r[1]:
                        novo_status_lote_r = st.selectbox("Novo Status", ["Recebido", "A Receber", "Vencido", "Cancelado"], key="ns_lote_cr")
                    with cols_lote_r[2]:
                        st.write("")
                        st.write("")
                        if st.button("✅ Aplicar em Lote", key="btn_lote_cr", type="primary"):
                            for idx, row in sel_cr.iterrows():
                                st.session_state.contas_receber.loc[idx, "Status"] = novo_status_lote_r
                                uuid_cr = _sb_id(st.session_state.contas_receber, row["ID"])
                                if uuid_cr:
                                    sync.lancamento_status_update(uuid_cr, novo_status_lote_r)
                            _notify(f"✅ {n_sel_r} lançamento(s) atualizados para **{novo_status_lote_r}**!")
                            st.rerun()

    # ── Novo Lançamento ───────────────────────────────────────────────
    with tab_novo:
        tipo_l = st.radio("Tipo", ["Conta a Pagar","Conta a Receber"], horizontal=True)
        with st.form("form_lanc"):
            c1,c2 = st.columns(2)
            obra_l  = c1.selectbox("Obra", _obras_nomes())
            contra  = c2.text_input("Fornecedor" if tipo_l=="Conta a Pagar" else "Cliente")
            desc_l  = c1.text_input("Descrição")
            val_l   = c2.number_input("Valor (R$)", min_value=0.0, step=100.0)
            venc_l  = c1.text_input("Vencimento (dd/mm/aaaa)", value=date.today().strftime("%d/%m/%Y"))
            nf_l    = c2.text_input("NF / Documento", value="—")
            eap_item_id = None
            tipo_custo_l = None
            if tipo_l == "Conta a Pagar":
                c3,c4 = st.columns(2)
                cat_l   = c3.selectbox("Categoria", CATS)
                forma_l = c4.selectbox("Forma de Pagamento",
                                        ["Boleto","PIX","Transferência","Cartão","Cheque","A definir"])
                st.markdown("##### 🔗 Vinculação à EAP")
                c5,c6 = st.columns(2)
                tipo_custo_l = c5.selectbox("Tipo de Custo",
                    ["","Material","Mão-de-obra","Equipamento","Subempreiteiro","Administrativo"])
                try:
                    obra_uuid_for_eap = _obra_uuid(obra_l)
                    if obra_uuid_for_eap:
                        df_eap = db.eap_itens_por_obra(obra_uuid_for_eap)
                        if not df_eap.empty:
                            eap_opts = {f"{r['codigo']} — {r['descricao']} (R$ {_fmt(r['valor_previsto'])})": r['id'] for _, r in df_eap.iterrows()}
                            eap_opts = {"(nenhum)": ""} | eap_opts
                            eap_sel = c6.selectbox("Etapa EAP", list(eap_opts.keys()))
                            eap_item_id = eap_opts[eap_sel] or None
                except Exception:
                    pass
            ok_l = st.form_submit_button("➕ Adicionar", type="primary")
        if ok_l:
            obra_uuid_l = _obra_uuid(obra_l)
            if tipo_l == "Conta a Pagar":
                dados_cp = {"Obra": obra_l, "Fornecedor": contra, "Descrição": desc_l,
                            "Categoria": cat_l, "Valor (R$)": val_l, "Vencimento": venc_l,
                            "Status": "A Pagar", "NF": nf_l, "Forma Pag.": forma_l,
                            "eap_item_id": eap_item_id, "tipo_custo": tipo_custo_l}
                uuid_l = sync.lancamento_save(dados_cp, "PAGAR", obra_uuid_l)
                st.session_state.contas_pagar = pd.concat([
                    st.session_state.contas_pagar,
                    pd.DataFrame([{"ID": _next_id(st.session_state.contas_pagar),
                                   "SB_ID": uuid_l or None, **dados_cp}])
                ], ignore_index=True)
            else:
                dados_cr = {"Obra": obra_l, "Cliente": contra, "Descrição": desc_l,
                            "Valor (R$)": val_l, "Vencimento": venc_l, "Status": "A Receber"}
                uuid_l = sync.lancamento_save(dados_cr, "RECEBER", obra_uuid_l)
                st.session_state.contas_receber = pd.concat([
                    st.session_state.contas_receber,
                    pd.DataFrame([{"ID": _next_id(st.session_state.contas_receber),
                                   "SB_ID": uuid_l or None, **dados_cr}])
                ], ignore_index=True)
            _tipo_msg = "Conta a Pagar" if tipo_l == "Conta a Pagar" else "Conta a Receber"
            _notify(f"✅ {_tipo_msg} de **{_fmt(val_l)}** para **{obra_l}** adicionada!"); st.rerun()

    # ── Custos por Obra ───────────────────────────────────────────────
    with tab_custo:
        st.subheader("Análise de Custos por Obra")
        todas_obras_c = sorted(_obras_nomes())
        obra_c = st.selectbox("Selecione a Obra", todas_obras_c, key="custo_obra_sel")

        cp = st.session_state.contas_pagar.copy()
        if "Categoria" not in cp.columns:
            cp["Categoria"] = "Materiais"
        cp["Categoria"] = cp["Categoria"].fillna("Outros")
        cp["Valor (R$)"] = cp["Valor (R$)"].apply(_to_num)
        # Inclui lançamentos sem obra_id (Obra="") mas cujo descrição referencia a obra
        cp_obra = cp[
            (cp["Obra"] == obra_c) |
            ((cp["Obra"].fillna("") == "") &
             (cp["Descrição"].fillna("").str.contains(obra_c, regex=False, na=False)))
        ].copy()

        # Custo de pessoal direto dos funcionários alocados à obra
        ff_custo = st.session_state.funcionarios.copy()
        ff_custo["Salário (R$)"] = pd.to_numeric(ff_custo.get("Salário (R$)", 0), errors="coerce").fillna(0.0)
        ff_custo["Obra"] = ff_custo["Obra"].fillna("").replace("", "Sem alocação")
        folha_estimada = ff_custo[ff_custo["Obra"] == obra_c]["Salário (R$)"].sum() * 1.31

        # Métricas por categoria
        def _soma_cat(cat):
            return cp_obra[cp_obra["Categoria"] == cat]["Valor (R$)"].sum()

        v_mat  = _soma_cat("Materiais")
        v_folh = _soma_cat("Folha de Pagamento")
        v_imp  = _soma_cat("Impostos")
        v_out  = cp_obra[~cp_obra["Categoria"].isin(["Materiais","Folha de Pagamento","Impostos"])]["Valor (R$)"].sum()
        v_tot  = cp_obra["Valor (R$)"].sum()

        st.markdown(f"**Obra selecionada:** {obra_c} &nbsp;|&nbsp; **Total Lançado:** {_fmt(v_tot)}")
        if folha_estimada > 0:
            st.info(f"👷 **Custo de pessoal estimado (funcionários alocados):** {_fmt(folha_estimada)}/mês "
                    f"— use **Pessoal → Fechar Folha** para lançar no financeiro.")
        st.markdown("---")

        cm1,cm2,cm3,cm4 = st.columns(4)
        cm1.metric("🧱 Materiais",          _fmt(v_mat),
                   delta=f"{v_mat/v_tot*100:.1f}% do total" if v_tot else "—")
        cm2.metric("👷 Folha Lançada",       _fmt(v_folh),
                   delta=f"Est. {_fmt(folha_estimada)}/mês" if folha_estimada > 0 else "—")
        cm3.metric("🏛️ Impostos",            _fmt(v_imp),
                   delta=f"{v_imp/v_tot*100:.1f}% do total" if v_tot else "—")
        cm4.metric("📦 Outros",              _fmt(v_out))
        st.markdown("---")

        if v_tot > 0:
            # Gráfico de barras por categoria
            df_cat = (cp_obra.groupby("Categoria")["Valor (R$)"]
                             .sum().reset_index()
                             .sort_values("Valor (R$)", ascending=False))
            df_cat["% Total"] = (df_cat["Valor (R$)"] / v_tot * 100).round(1)
            cores_bar = [CAT_CORES.get(c,"#95A5A6") for c in df_cat["Categoria"]]
            fig_cat = go.Figure(go.Bar(
                x=df_cat["Categoria"], y=df_cat["Valor (R$)"],
                marker_color=cores_bar,
                text=[f"R${v:,.0f}<br>{p:.1f}%" for v,p in zip(df_cat["Valor (R$)"],df_cat["% Total"])],
                textposition="outside",
            ))
            fig_cat.update_layout(
                height=340, plot_bgcolor="white", paper_bgcolor="white",
                yaxis_tickformat=",.0f", yaxis_title="R$",
                xaxis_title="", margin=dict(t=30,b=20),
            )
            st.plotly_chart(fig_cat, width='stretch')

            # Gráfico de pizza
            fig_pie = px.pie(df_cat, values="Valor (R$)", names="Categoria",
                             hole=0.4, color="Categoria",
                             color_discrete_map=CAT_CORES)
            fig_pie.update_traces(textinfo="percent+label", textposition="outside")
            fig_pie.update_layout(height=300, showlegend=False,
                                  margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_pie, width='stretch')

            # Tabela detalhada
            st.subheader("Lançamentos Detalhados")
            ex_c = cp_obra.drop(columns=[c for c in ["ID","SB_ID"] if c in cp_obra.columns]).copy()
            ex_c["Valor (R$)"] = ex_c["Valor (R$)"].apply(_fmt)
            badges_c = {"Pago":"🟢","A Pagar":"🟡","Vencido":"🔴"}
            if "Status" in ex_c.columns:
                ex_c["Status"] = ex_c["Status"].apply(lambda s: f"{badges_c.get(s,'⚪')} {s}")
            st.dataframe(ex_c, width='stretch', hide_index=True)
        else:
            st.info(f"Nenhum lançamento de Contas a Pagar registrado para **{obra_c}**.")

    # ── Alocar Custos à EAP ────────────────────────────────────────────────
    with tab_alocar:
        st.subheader("🔗 Alocar Custos à EAP")
        st.caption("Vincula lançamentos de Contas a Pagar a etapas da EAP que ainda não foram classificados.")
        al_obras = _obras_nomes()
        al_obra = st.selectbox("Obra", al_obras, key="al_obra_sel")
        if al_obra:
            al_uuid = _obra_uuid(al_obra)
            df_cp = st.session_state.contas_pagar.copy()
            df_cp_obra = df_cp[
                (df_cp["Obra"] == al_obra) &
                (df_cp["eap_item_id"].isna() | (df_cp["eap_item_id"].astype(str).isin(["", "None", "nan"])))
            ].copy()
            if df_cp_obra.empty:
                st.success("✅ Todos os lançamentos desta obra já estão vinculados a uma etapa EAP!")
            else:
                st.info(f"**{len(df_cp_obra)}** lançamento(s) aguardando classificação.")
                df_eap_al = db.eap_itens_por_obra(al_uuid) if al_uuid else pd.DataFrame()
                if df_eap_al.empty:
                    st.warning("Nenhuma etapa EAP cadastrada para esta obra. Crie a EAP primeiro.")
                else:
                    eap_opts_al = {f"{r['codigo']} — {r['descricao']}": r['id'] for _, r in df_eap_al.iterrows()}
                    eap_opts_al = {"(não classificar)": ""} | eap_opts_al
                    with st.form("form_alocar_eap"):
                        alocacoes = {}
                        for idx, row_l in df_cp_obra.iterrows():
                            cols = st.columns([3, 2, 3])
                            cols[0].markdown(f"**{row_l.get('Descrição', '—')}**")
                            cols[1].markdown(f"R$ {row_l.get('Valor (R$)', 0):.2f}")
                            eap_key = f"al_eap_{idx}"
                            alocacoes[idx] = cols[2].selectbox(
                                "Etapa EAP", list(eap_opts_al.keys()),
                                key=eap_key, label_visibility="collapsed"
                            )
                        salvar_al = st.form_submit_button("💾 Salvar Alocações", type="primary")
                    if salvar_al:
                        from db import lancamento_atualizar
                        import traceback
                        ok_count = 0
                        for idx, eap_sel in alocacoes.items():
                            eap_id = eap_opts_al[eap_sel] or None
                            sb_id = df_cp_obra.at[idx, "SB_ID"]
                            try:
                                if sb_id:
                                    lancamento_atualizar(sb_id, {"eap_item_id": eap_id})
                                    st.session_state.contas_pagar.at[idx, "eap_item_id"] = eap_id
                                    ok_count += 1
                            except Exception:
                                print(f"[alocar] ERRO idx={idx} sb_id={sb_id}:\n{traceback.format_exc()}")
                        _notify(f"✅ {ok_count} lançamento(s) vinculado(s) à EAP com sucesso!")
                        st.rerun()

    # ── DRE por Obra ──────────────────────────────────────────────────────────
    with tab_dre:
        st.subheader("📈 Demonstração de Resultados por Obra")
        dre_obras = sorted(_obras_nomes())
        if not dre_obras:
            st.info("Nenhuma obra cadastrada.")
        else:
            dre_sel = st.selectbox("Selecione a Obra", dre_obras, key="dre_obra_sel")
            obra_row = st.session_state.obras[st.session_state.obras["Nome"] == dre_sel]
            valor_contrato = float(obra_row["Valor Contrato (R$)"].iloc[0]) if not obra_row.empty else 0
            bdi = float(obra_row["BDI (%)"].iloc[0]) if not obra_row.empty and "BDI (%)" in obra_row.columns else 0
            pct_fis = float(obra_row["% Físico"].iloc[0]) if not obra_row.empty else 0

            cp = st.session_state.contas_pagar.copy()
            cp_obra = cp[cp["Obra"] == dre_sel].copy()
            cr = st.session_state.contas_receber.copy()
            cr_obra = cr[cr["Obra"] == dre_sel].copy()

            def _soma_cp(cat):
                return cp_obra[cp_obra["Categoria"] == cat]["Valor (R$)"].sum()
            # Receitas
            receita_contrato = valor_contrato * (pct_fis / 100) if pct_fis > 0 else 0
            receita_medicoes = cr_obra["Valor (R$)"].sum()
            receita_recebida = cr_obra[cr_obra["Status"] == "Recebido"]["Valor (R$)"].sum()
            receita_a_receber = cr_obra[cr_obra["Status"].isin(["A Receber", "Vencido"])]["Valor (R$)"].sum()

            # Custos
            custo_materiais = _soma_cp("Materiais")
            custo_folha = _soma_cp("Folha de Pagamento")
            custo_impostos = _soma_cp("Impostos")
            custo_outros = _soma_cp("Outros")
            custo_total = custo_materiais + custo_folha + custo_impostos + custo_outros

            custo_pago = cp_obra[cp_obra["Status"] == "Pago"]["Valor (R$)"].sum()
            custo_a_pagar = cp_obra[cp_obra["Status"].isin(["A Pagar", "Vencido"])]["Valor (R$)"].sum()

            # Funcionários alocados (estimativa)
            funcs_obra = st.session_state.funcionarios[st.session_state.funcionarios["Obra"] == dre_sel]
            folha_estimada = funcs_obra["Salário (R$)"].sum() * 1.31 if not funcs_obra.empty else 0

            # Cálculos DRE
            receita_liquida = receita_contrato - custo_impostos
            lucro_bruto = receita_liquida - (custo_materiais + custo_folha + custo_outros)
            margem_bruta = (lucro_bruto / receita_liquida * 100) if receita_liquida > 0 else 0
            resultado_liquido = lucro_bruto

            st.markdown("---")
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("##### 📊 DRE — " + dre_sel)
                st.markdown(f"**% Físico:** {pct_fis:.1f}%  ·  **BDI:** {bdi:.1f}%  ·  **Valor Contrato:** {_fmt(valor_contrato)}")

                dre_data = [
                    ("📈 RECEITA BRUTA (Contrato)", _fmt(receita_contrato), True),
                    ("   (+) Medições faturadas", _fmt(receita_medicoes), False),
                    ("   (–) Impostos", _fmt(-custo_impostos), False),
                    ("📉 RECEITA LÍQUIDA", _fmt(receita_liquida), True),
                    ("", "", False),
                    ("💸 CUSTOS DIRETOS", "", True),
                    ("   Materiais", _fmt(-custo_materiais), False),
                    ("   Mão-de-Obra (Folha)", _fmt(-custo_folha), False),
                    ("   Outros", _fmt(-custo_outros), False),
                    ("", "", False),
                    ("💰 RESULTADO BRUTO", _fmt(lucro_bruto), True),
                    ("   Margem Bruta", f"{margem_bruta:+.1f}%", True),
                ]
                for label, val, bold in dre_data:
                    if not label:
                        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                        continue
                    b = "**" if bold else ""
                    cor = "#27AE60" if val and val.startswith("R$") and not label.startswith("   (–)") and not label.startswith("💸") else "#E74C3C" if val and val.startswith("R$-") else "inherit"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:3px 0;{'font-weight:700;font-size:15px' if bold else ''}'>"
                        f"<span>{b}{label}{b}</span>"
                        f"<span style='color:{cor}'>{b}{val}{b}</span></div>",
                        unsafe_allow_html=True,
                    )

            with col2:
                st.markdown("##### 📋 Indicadores")
                if receita_liquida > 0:
                    c1, c2 = st.columns(2)
                    c1.metric("Margem Bruta", f"{margem_bruta:+.1f}%",
                              delta="Acima da meta" if margem_bruta >= 15 else "Abaixo da meta" if margem_bruta < 5 else "OK",
                              delta_color="normal" if margem_bruta >= 15 else "inverse" if margem_bruta < 5 else "off")
                    c2.metric("Custo Total", _fmt(custo_total))
                    st.metric("Receita Líquida", _fmt(receita_liquida))
                    st.metric("Resultado Líquido", _fmt(resultado_liquido),
                              delta_color="normal" if resultado_liquido >= 0 else "inverse")
                    st.markdown("---")
                    st.markdown("##### 💵 Fluxo Financeiro")
                    st.metric("Recebido", _fmt(receita_recebida))
                    st.metric("Pago", _fmt(custo_pago))
                    st.metric("Saldo Financeiro", _fmt(receita_recebida - custo_pago),
                              delta_color="normal" if (receita_recebida - custo_pago) >= 0 else "inverse")

                    # Gráfico DRE
                    st.markdown("---")
                    st.markdown("##### 📊 Composição dos Custos")
                    cats_dre = {"Materiais": custo_materiais, "Mão-de-Obra": custo_folha,
                                "Impostos": custo_impostos, "Outros": custo_outros}
                    cats_dre = {k: v for k, v in cats_dre.items() if v > 0}
                    if cats_dre and custo_total > 0:
                        fig_dre = go.Figure(go.Pie(
                            labels=list(cats_dre.keys()),
                            values=list(cats_dre.values()),
                            hole=0.4,
                            marker_colors=["#2B59C3", "#E67E22", "#E74C3C", "#95A5A6"],
                            textinfo="percent+label",
                        ))
                        fig_dre.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                        st.plotly_chart(fig_dre, width='stretch')
                else:
                    st.info("Nenhum dado financeiro para esta obra.")

            st.markdown("---")
            with st.expander("📋 Detalhamento dos Lançamentos"):
                tab_dre_cp, tab_dre_cr = st.tabs(["Contas a Pagar", "Contas a Receber"])
                with tab_dre_cp:
                    if not cp_obra.empty:
                        st.dataframe(cp_obra.drop(columns=[c for c in ["ID", "SB_ID"] if c in cp_obra.columns], errors='ignore'),
                                     width='stretch', hide_index=True)
                    else:
                        st.info("Nenhuma conta a pagar.")
                with tab_dre_cr:
                    if not cr_obra.empty:
                        st.dataframe(cr_obra.drop(columns=[c for c in ["ID", "SB_ID"] if c in cr_obra.columns], errors='ignore'),
                                     width='stretch', hide_index=True)
                    else:
                        st.info("Nenhuma conta a receber.")

    # ── Fluxo de Caixa Projetado ──────────────────────────────────────────────
    with tab_fc:
        st.subheader("📊 Fluxo de Caixa Projetado")
        st.caption("Projeção de entradas e saídas com base nos lançamentos a pagar/receber.")

        cp_fc = st.session_state.contas_pagar.copy()
        cr_fc = st.session_state.contas_receber.copy()

        # Filtro de obra
        fc_obras = ["Todas"] + sorted(_obras_nomes())
        fc_obra = st.selectbox("Filtrar por Obra", fc_obras, key="fc_obra")
        if fc_obra != "Todas":
            cp_fc = cp_fc[cp_fc["Obra"] == fc_obra]
            cr_fc = cr_fc[cr_fc["Obra"] == fc_obra]

        # Preparar dados de fluxo
        hoje = date.today()
        from datetime import timedelta

        def _parse_data_br(d: str) -> date | None:
            try:
                return datetime.strptime(str(d).strip(), "%d/%m/%Y").date()
            except Exception:
                return None

        # Projeção para 12 semanas
        fluxo_semanas = []
        for s in range(12):
            sem_ini = hoje + timedelta(weeks=s)
            sem_fim = sem_ini + timedelta(days=6)
            label = f"{sem_ini.strftime('%d/%b')} - {sem_fim.strftime('%d/%b')}"

            entradas = 0
            saidas = 0
            for _, r in cr_fc.iterrows():
                vd = _parse_data_br(r.get("Vencimento", ""))
                if vd and sem_ini <= vd <= sem_fim and r.get("Status") in ("A Receber", "Vencido"):
                    entradas += float(r.get("Valor (R$)", 0) or 0)
            for _, r in cp_fc.iterrows():
                vd = _parse_data_br(r.get("Vencimento", ""))
                if vd and sem_ini <= vd <= sem_fim and r.get("Status") in ("A Pagar", "Vencido"):
                    saidas += float(r.get("Valor (R$)", 0) or 0)

            fluxo_semanas.append({"Semana": label, "Entradas": entradas, "Saídas": saidas,
                                  "Saldo": entradas - saidas})

        df_fc = pd.DataFrame(fluxo_semanas)

        st.markdown("---")
        k1, k2, k3 = st.columns(3)
        total_entradas = df_fc["Entradas"].sum()
        total_saidas = df_fc["Saídas"].sum()
        saldo_projetado = total_entradas - total_saidas
        k1.metric("Total Entradas (12 sem)", _fmt(total_entradas))
        k2.metric("Total Saídas (12 sem)", _fmt(total_saidas))
        k3.metric("Saldo Projetado", _fmt(saldo_projetado),
                  delta_color="normal" if saldo_projetado >= 0 else "inverse")

        # Gráfico
        if not df_fc.empty:
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Bar(name="Entradas", x=df_fc["Semana"], y=df_fc["Entradas"],
                                     marker_color="#27AE60"))
            fig_fc.add_trace(go.Bar(name="Saídas", x=df_fc["Semana"], y=df_fc["Saídas"],
                                     marker_color="#E74C3C"))
            fig_fc.add_trace(go.Scatter(name="Saldo", x=df_fc["Semana"], y=df_fc["Saldo"],
                                         mode="lines+markers", marker_color="#2B59C3",
                                         line=dict(width=3)))
            fig_fc.update_layout(barmode="group", height=350,
                                  plot_bgcolor="white", paper_bgcolor="white",
                                  margin=dict(l=0, r=20, t=20, b=0),
                                  xaxis_title="Semana", yaxis_title="R$",
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_fc, width='stretch')

        # Tabela detalhada
        st.markdown("---")
        st.subheader("Detalhamento Semanal")
        df_fc_disp = df_fc.copy()
        for c in ["Entradas", "Saídas", "Saldo"]:
            df_fc_disp[c] = df_fc_disp[c].apply(_fmt)
        st.dataframe(df_fc_disp, width='stretch', hide_index=True)

        # Dias críticos (vencimentos nos próximos 7 dias)
        st.markdown("---")
        st.subheader("⚠️ Vencimentos nos Próximos 7 Dias")
        alertas_fc = []
        for _, r in cp_fc.iterrows():
            vd = _parse_data_br(r.get("Vencimento", ""))
            if vd and hoje <= vd <= hoje + timedelta(days=7) and r.get("Status") in ("A Pagar", "Vencido"):
                alertas_fc.append(r)
        for _, r in cr_fc.iterrows():
            vd = _parse_data_br(r.get("Vencimento", ""))
            if vd and hoje <= vd <= hoje + timedelta(days=7) and r.get("Status") in ("A Receber", "Vencido"):
                alertas_fc.append(r)

        if alertas_fc:
            for a in alertas_fc[:10]:
                tipo = "💸 A Pagar" if "Fornecedor" in a.index else "💵 A Receber"
                val = float(a.get("Valor (R$)", 0) or 0)
                st.markdown(f"- {tipo}: **{_fmt(val)}** — {a.get('Descrição','')} venc. {a.get('Vencimento','')}")
        else:
            st.success("Nenhum vencimento nos próximos 7 dias.")

    # ── Conciliação Bancária ──────────────────────────────────────────────────
    with tab_conc:
        st.subheader("🏦 Conciliação Bancária")
        from sync import _parse_csv_extrato, conciliacao_save, conciliacao_delete as _conc_delete

        if "conciliacao_itens_temp" not in st.session_state:
            st.session_state.conciliacao_itens_temp = []

        tab_import, tab_historico = st.tabs(["📤 Importar Extrato", "📋 Histórico"])

        with tab_import:
            st.markdown("##### Importar Extrato Bancário (CSV)")
            st.caption("Formato: Data, Descrição, Valor, Categoria (opcional). Separador: vírgula. Use ponto ou vírgula como separador decimal.")
            st.caption("Valores positivos = Crédito (recebimento), negativos = Débito (pagamento).")

            csv_file = st.file_uploader("Selecione o arquivo CSV", type=["csv", "txt"], key="conc_csv")
            obra_conc = st.selectbox("Vincular à Obra (opcional)", [""] + _obras_nomes(), key="conc_obra")

            if csv_file is not None:
                try:
                    content = csv_file.getvalue().decode("utf-8-sig")
                    transacoes = _parse_csv_extrato(content)
                    if transacoes:
                        st.success(f"{len(transacoes)} transações encontradas.")
                        st.session_state.conciliacao_itens_temp = transacoes
                    else:
                        st.warning("Nenhuma transação encontrada. Verifique o formato.")
                except Exception as e:
                    st.error(f"Erro ao ler arquivo: {e}")

            if st.session_state.conciliacao_itens_temp:
                st.markdown("---")
                st.markdown("##### Transações Importadas")
                df_temp = pd.DataFrame(st.session_state.conciliacao_itens_temp)
                total_cred = df_temp[df_temp["tipo"] == "Credito"]["valor"].sum()
                total_deb = df_temp[df_temp["tipo"] == "Debito"]["valor"].sum()
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Transações", len(df_temp))
                c2.metric("Total Créditos", _fmt(total_cred))
                c3.metric("Total Débitos", _fmt(total_deb))

                st.dataframe(df_temp, width='stretch', hide_index=True)

                col_cred, col_deb = st.columns(2)
                saldo_cred = col_cred.number_input("Saldo Inicial (R$)", min_value=0.0, value=0.0, step=100.0, key="conc_saldo_ini")
                saldo_deb = col_deb.number_input("Saldo Final (R$)", min_value=0.0, value=0.0, step=100.0, key="conc_saldo_fim")

                if st.button("💾 Salvar Conciliação", type="primary", key="btn_salvar_conc"):
                    _itens_conc = st.session_state.conciliacao_itens_temp
                    dados_conc = {
                        "arquivo_nome": csv_file.name if csv_file else "extrato.csv",
                        "total_transacoes": len(_itens_conc),
                        "total_conciliadas": 0,
                        "saldo_inicial": saldo_cred,
                        "saldo_final": saldo_deb,
                        "itens": _itens_conc,
                    }
                    sb_id_conc = conciliacao_save(dados_conc)
                    if sb_id_conc:
                        st.session_state.conciliacao_itens_temp = []
                        _notify(f"Conciliação salva! {len(_itens_conc)} transações importadas.")
                        st.rerun()

        with tab_historico:
            try:
                from db import conciliacao_listar, conciliacao_itens_listar, conciliacao_item_atualizar
                historico = conciliacao_listar()
                if historico.empty:
                    st.info("Nenhuma conciliação realizada ainda.")
                else:
                    for _, row_conc in historico.iterrows():
                        with st.container(border=True):
                            cc1, cc2, cc3, cc4 = st.columns([2, 1, 1, 1])
                            cc1.markdown(f"**{row_conc.get('arquivo_nome', 'Extrato')}**")
                            cc2.markdown(f"Transações: {row_conc.get('total_transacoes', 0)}")
                            cc3.markdown(f"Conciliadas: {row_conc.get('total_conciliadas', 0)}")
                            if cc4.button("🗑️", key=f"del_conc_{row_conc['id']}"):
                                _conc_delete(row_conc["id"])
                                st.rerun()

                            if st.button(f"📋 Ver itens", key=f"ver_conc_{row_conc['id']}"):
                                st.session_state[f"_show_conc_{row_conc['id']}"] = not st.session_state.get(f"_show_conc_{row_conc['id']}", False)

                            if st.session_state.get(f"_show_conc_{row_conc['id']}", False):
                                itens_conc = conciliacao_itens_listar(row_conc["id"])
                                if not itens_conc.empty:
                                    for idx, item in itens_conc.iterrows():
                                        cols = st.columns([2, 1, 1, 1, 1])
                                        cols[0].markdown(f"{item.get('data','')} — {item.get('descricao','')}")
                                        cols[1].markdown(_fmt(float(item.get('valor',0))))
                                        cols[2].markdown(item.get('tipo',''))
                                        conc = item.get('conciliado', False)
                                        if cols[3].button("✅" if conc else "⬜", key=f"conc_item_{item['id']}"):
                                            conciliacao_item_atualizar(item["id"], {"conciliado": not conc, "lancamento_id": None})
                                            st.rerun()
                                        cols[4].markdown("Conciliado" if conc else "Pendente")
            except Exception:
                st.error("Erro ao carregar histórico de conciliações.")

# ── Orçado x Realizado ────────────────────────────────────────────────────────

_TIPO_CUSTO_CORES = {
    "Material": "#2B59C3", "Mão-de-obra": "#E67E22",
    "Equipamento": "#8E44AD", "Subempreiteiro": "#27AE60",
    "Administrativo": "#95A5A6", "Impostos": "#E74C3C",
}

def _exibir_oxr(obra_uuid: str, obra_nome: str):
    """Componente reutilizável de Orçado x Realizado (KPIs, Etapa EAP, Curva S, Categoria)."""
    import numpy as np
    from scipy.special import erf as _erf
    import plotly.express as px
    try:
        df_ov = db.orcado_realizado_por_obra(obra_uuid)
        df_lc = db.lancamentos_listar("PAGAR")
        df_lc_rec = db.lancamentos_listar("RECEBER")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    df_lc_obra = df_lc[df_lc["obra_id"] == obra_uuid].copy() if not df_lc.empty else pd.DataFrame()
    df_lc_rec_obra = df_lc_rec[df_lc_rec["obra_id"] == obra_uuid].copy() if not df_lc_rec.empty else pd.DataFrame()
    total_orcado = df_ov["orcado"].sum() if not df_ov.empty else 0
    total_realizado = df_ov["realizado"].sum() if not df_ov.empty else 0

    df_resumo = db.resumo_obras_listar()
    df_res_obra = df_resumo[df_resumo["obra_id"] == obra_uuid] if not df_resumo.empty else pd.DataFrame()
    pct_fisico = float(df_res_obra["pct_fisico_medio"].iloc[0]) if not df_res_obra.empty else 0.0

    custo_projetado = (total_realizado / (pct_fisico / 100)) if pct_fisico > 0 else 0
    margem_projetada = ((total_orcado - custo_projetado) / total_orcado * 100) if total_orcado > 0 else 0
    desvio_total = total_orcado - total_realizado
    desvio_pct = ((total_realizado - total_orcado) / total_orcado * 100) if total_orcado > 0 else 0

    if margem_projetada >= 15:
        semaforo = "🟢"; sem_cor = "normal"
    elif margem_projetada >= 5:
        semaforo = "🟡"; sem_cor = "off"
    else:
        semaforo = "🔴"; sem_cor = "inverse"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Orçado Total", _fmt(total_orcado))
    c2.metric("Realizado Total", _fmt(total_realizado))
    c3.metric(f"{semaforo} Margem Projetada", f"{margem_projetada:+.1f}%",
              delta=f"Custo Proj: {_fmt(custo_projetado)}", delta_color=sem_cor)
    c4.metric("Custo Projetado Final", _fmt(custo_projetado) if custo_projetado > 0 else "—")
    c5.metric("% Físico Médio", f"{pct_fisico:.1f}%" if pct_fisico > 0 else "—")

    st.caption(
        f"Desvio {_fmt(desvio_total)}  ·  {desvio_pct:+.1f}% em relação ao orçado  ·  "
        f"Semáforo: {semaforo} {'acima da meta' if margem_projetada >= 15 else 'dentro da margem' if margem_projetada >= 5 else 'abaixo da meta (atenção)'}"
    )

    tab_etapa, tab_curva, tab_cat = st.tabs(["🔬 Por Etapa EAP", "📈 Curva S", "🏷️ Por Categoria"])

    with tab_etapa:
        st.subheader("Detalhamento por Etapa EAP")
        if df_ov.empty:
            try:
                df_eap = db.eap_itens_por_obra(obra_uuid)
                tem_eap = not df_eap.empty
            except Exception:
                tem_eap = False
            if not tem_eap:
                st.warning(
                    "Esta obra não possui **EAP (Estrutura Analítica de Projeto)** gerada.\n\n"
                    "1. Vá em **Orçamento** e importe uma planilha de orçamento para esta obra\n"
                    "2. Vá em **Planejamento (EAP)** e clique em **Gerar EAP no Banco**\n"
                    "3. Volte aqui para ver o comparativo Orçado x Realizado"
                )
            else:
                st.info(
                    "A obra possui EAP, mas **nenhum lançamento financeiro** vinculado às etapas.\n\n"
                    "Vá em **Financeiro** → Novo Lançamento e selecione a etapa EAP e o tipo de custo."
                )
        else:
            df_ov = df_ov.copy()
            df_ov["_nivel"] = df_ov["eap_codigo"].astype(str).apply(lambda c: len(c.split(".")))
            df_ov["_pai"] = df_ov["eap_codigo"].astype(str).apply(
                lambda c: ".".join(c.split(".")[:-1]) if "." in c else "")
            top_nivel = df_ov["_nivel"].min()
            for _, r in df_ov[df_ov["_nivel"] == top_nivel].iterrows():
                orc = r.get("orcado", 0) if pd.notna(r.get("orcado")) else 0
                real = r.get("realizado", 0) if pd.notna(r.get("realizado")) else 0
                dv = r.get("desvio", 0) if pd.notna(r.get("desvio")) else 0
                dv_pct = r.get("desvio_pct", 0) if pd.notna(r.get("desvio_pct")) else 0
                pct_exec = (real / orc * 100) if orc > 0 else 0
                if dv_pct <= -15:
                    cor = "🟢"
                elif dv_pct <= 5:
                    cor = "🟡"
                else:
                    cor = "🔴"
                filhos = df_ov[df_ov["_pai"] == r["eap_codigo"]]
                with st.container(border=True):
                    cols = st.columns([3,1,1,1,1])
                    cols[0].markdown(f"**{r['eap_codigo']}** — {r['etapa']}")
                    cols[1].metric("Orçado", _fmt(orc))
                    cols[2].metric("Realizado", _fmt(real))
                    cols[3].metric(f"Desvio {cor}", _fmt(dv), delta=f"{dv_pct:+.1f}%",
                                   delta_color="normal" if dv >= 0 else "inverse")
                    cols[4].markdown(f"<div style='text-align:center;font-size:24px;margin-top:10px;'>{pct_exec:.0f}%</div>", unsafe_allow_html=True)
                    st.progress(min(pct_exec / 100.0, 1.0), text=f"{pct_exec:.1f}% executado do orçado")
                    if not filhos.empty:
                        with st.expander(f"📂 {len(filhos)} sub-itens"):
                            for _, f in filhos.iterrows():
                                _fo = f.get("orcado", 0) if pd.notna(f.get("orcado")) else 0
                                _fr = f.get("realizado", 0) if pd.notna(f.get("realizado")) else 0
                                _fd = f.get("desvio", 0) if pd.notna(f.get("desvio")) else 0
                                _fp = (_fr / _fo * 100) if _fo > 0 else 0
                                _fc = "🟢" if _fd >= 0 else "🔴"
                                sc = st.columns([3,1,1,1,1])
                                sc[0].caption(f"  └ {f['eap_codigo']} — {f['etapa']}")
                                sc[1].caption(_fmt(_fo))
                                sc[2].caption(_fmt(_fr))
                                sc[3].caption(f"{_fc} {_fmt(_fd)}")
                                sc[4].caption(f"{_fp:.0f}%")

            # Aggregate at top level for graphs
            df_topo = df_ov[df_ov["_nivel"] == top_nivel].copy()
            df_plot = df_topo.melt(id_vars=["eap_codigo","etapa"], value_vars=["orcado","realizado"],
                                   var_name="Tipo", value_name="Valor")
            fig_et = px.bar(df_plot, y="etapa", x="Valor", color="Tipo", barmode="group",
                            orientation="h",
                            title="Orçado vs Realizado por Categoria",
                            color_discrete_map={"orcado":"#2B59C3","realizado":"#27AE60"},
                            labels={"etapa":"","Valor":"R$"})
            fig_et.update_layout(height=350, plot_bgcolor="white", paper_bgcolor="white",
                                 xaxis_tickformat=",.0f", margin=dict(t=40,b=10,l=10),
                                 legend=dict(orientation="h", y=1.08))
            fig_et.update_yaxes(automargin=True)
            st.plotly_chart(fig_et, width='stretch')

            fig_dv = px.bar(df_topo, y="etapa", x="desvio", orientation="h",
                            title="Desvio por Categoria (positivo = abaixo do orçado)",
                            color="desvio", color_continuous_scale=["#E74C3C","#F1C40F","#27AE60"],
                            labels={"etapa":"","desvio":"R$"})
            fig_dv.update_layout(height=300, plot_bgcolor="white", paper_bgcolor="white",
                                 xaxis_tickformat=",.0f", margin=dict(t=40,b=10,l=10))
            fig_dv.update_yaxes(automargin=True)
            fig_dv.update_coloraxes(colorbar_title="Desvio")
            st.plotly_chart(fig_dv, width='stretch')

    with tab_curva:
        st.subheader("Curva S — Desembolso Financeiro")
        if not df_lc_obra.empty and "data_vencimento" in df_lc_obra.columns:
            df_lc_obra["_mes"] = pd.to_datetime(df_lc_obra["data_vencimento"], errors="coerce").dt.to_period("M").astype(str)
            df_mensal = df_lc_obra.groupby("_mes")["valor"].sum().reset_index().sort_values("_mes")
            df_mensal["acum"] = df_mensal["valor"].cumsum()
            tem_receita = not df_lc_rec_obra.empty and "data_vencimento" in df_lc_rec_obra.columns
            if tem_receita:
                df_lc_rec_obra["_mes"] = pd.to_datetime(df_lc_rec_obra["data_vencimento"], errors="coerce").dt.to_period("M").astype(str)
                df_rec_mensal = df_lc_rec_obra.groupby("_mes")["valor"].sum().reset_index().sort_values("_mes")
                df_rec_mensal["acum"] = df_rec_mensal["valor"].cumsum()
            if not df_mensal.empty:
                meses = df_mensal["_mes"].tolist()
                if total_orcado > 0 and len(meses) > 1:
                    n = len(meses); _x = np.linspace(-2.0, 2.0, n)
                    curva_s_plan = (_erf(_x) + 1.0) / 2.0 * total_orcado
                    meses_plot = meses * (3 if tem_receita else 2)
                    valores = [curva_s_plan, df_mensal["acum"].values]
                    tipos = ["Planejado"] * n + ["Realizado (Despesa)"] * n
                    if tem_receita:
                        valores.append(df_rec_mensal["acum"].values)
                        tipos += ["Medido (Receita)"] * n
                    df_curva = pd.DataFrame({"Mês": meses_plot, "Valor Acumulado (R$)": np.concatenate(valores), "Tipo": tipos})
                    fig_cv = px.line(df_curva, x="Mês", y="Valor Acumulado (R$)", color="Tipo", markers=True,
                                     color_discrete_map={"Planejado":"#2B59C3","Realizado (Despesa)":"#E67E22","Medido (Receita)":"#27AE60"},
                                     title="Curva S — Orçado vs Realizado Acumulado")
                    fig_cv.add_hline(y=total_orcado, line_dash="dot", line_color="#888", line_width=1,
                                     annotation_text=f"Orçado Total: {_fmt(total_orcado)}")
                    fig_cv.update_layout(height=400, plot_bgcolor="white", paper_bgcolor="white",
                                         yaxis_tickformat=",.0f", margin=dict(t=40,b=20))
                    st.plotly_chart(fig_cv, width='stretch')
                elif len(meses) <= 1:
                    st.info("São necessários pelo menos 2 meses de dados para a Curva S.")
                else:
                    st.info("Orçado total é zero — não é possível calcular a Curva S.")
            else:
                st.info("Nenhum lançamento com data de vencimento válida.")
        else:
            st.info("Nenhum lançamento de Contas a Pagar encontrado para esta obra.")

    with tab_cat:
        st.subheader("Análise por Tipo de Custo")
        if not df_lc_obra.empty and "tipo_custo" in df_lc_obra.columns:
            df_cat = df_lc_obra.copy()
            df_cat["tipo_custo"] = df_cat["tipo_custo"].fillna("Não classificado")
            df_agrup = df_cat.groupby("tipo_custo")["valor"].sum().reset_index().sort_values("valor", ascending=False)
            total_cat = df_agrup["valor"].sum()
            c1c, c2c = st.columns(2)
            c1c.metric("Total Lançado", _fmt(total_cat))
            c2c.metric("Categorias", df_agrup["tipo_custo"].nunique())
            fig_cat = px.pie(df_agrup, values="valor", names="tipo_custo", hole=0.4,
                             title="Distribuição por Tipo de Custo",
                             color="tipo_custo", color_discrete_map=_TIPO_CUSTO_CORES)
            fig_cat.update_traces(textinfo="percent+label", textposition="outside")
            fig_cat.update_layout(height=350, margin=dict(t=40,b=10))
            st.plotly_chart(fig_cat, width='stretch')
            st.dataframe(df_agrup.style.format({"valor": _fmt}), hide_index=True, width='stretch')
        else:
            st.info("Nenhum lançamento classificado por tipo de custo. Use o campo 'Tipo de Custo' ao lançar.")


# ── Pessoal ───────────────────────────────────────────────────────────────────

def pagina_pessoal():
    import plotly.express as px
    st.title("👥 Pessoal")
    _init()
    _show_toast()
    t1,t2,t3,t4,t5,t6,t7 = st.tabs(["👤 Funcionários","🕐 Ponto","💰 Folha","🌴 Férias","⚠️ Adicionais","📄 Rescisão","➕ Novo Funcionário"])

    with t1:
        funcs = st.session_state.funcionarios.copy()
        cf1,cf2 = st.columns(2)
        fo_f = cf1.selectbox("Obra",    ["Todas"]+_uniq(funcs["Obra"]),   key="ff_ob")
        fs_f = cf2.selectbox("Situação",["Todos"]+_uniq(funcs["Situação"]),key="ff_sit")
        if fo_f != "Todas": funcs = funcs[funcs["Obra"]==fo_f]
        if fs_f != "Todos": funcs = funcs[funcs["Situação"]==fs_f]
        c1,c2,c3 = st.columns(3)
        c1.metric("Total",   len(st.session_state.funcionarios))
        c2.metric("Ativos",  len(st.session_state.funcionarios[st.session_state.funcionarios["Situação"]=="Ativo"]))
        if _role() == "admin":
            c3.metric("Folha Bruta", _fmt(st.session_state.funcionarios["Salário (R$)"].sum()))
        st.markdown("---")
        if funcs.empty:
            st.info("Nenhum colaborador cadastrado. Use a aba ➕ Novo Colaborador.")
        else:
            _sit_badge = {"Ativo":"🟢","Férias":"🔵","Afastado":"🟡","Demitido":"🔴"}
            colunas_func = ["Nome","Cargo","Situação","Obra","Tipo Contrato","Admissão"]
            fmts_func = {"Situação": lambda s: f"{_sit_badge.get(s,'⚪')} {s}"}
            if _role() == "admin":
                colunas_func.insert(2, "Salário (R$)")
                fmts_func["Salário (R$)"] = _fmt
            LF = _tabela_clicavel(funcs, colunas_exibir=colunas_func, key="tbl_func", formatters=fmts_func,
                                  selection_mode="multi-row")
            st.download_button("⬇️ Exportar Excel", data=_export_excel(funcs.drop(columns=[c for c in ["ID","SB_ID"] if c in funcs.columns])),
                                file_name="funcionarios.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="btn_xls_func")

            if isinstance(LF, pd.DataFrame) and not LF.empty:
                n_sel_f = len(LF)
                st.markdown("---")
                if n_sel_f == 1:
                        _sf = LF.iloc[0]
                        id_f = _sf["ID"]
                        with st.container(border=True):
                            st.markdown(f"#### ✏️ Editando: {_sf['Nome']}")
                            obras_lista = ["Custo Geral"] + _obras_nomes(["Sede","Todas"])
                            contrato_opts = ["CLT","MEI","Empreiteiro","Autônomo","Diarista","Estagiário"]
                            ob_val_orig = str(_sf.get("Obra","") or "")
                            with st.form("form_edit_func"):
                                c1,c2 = st.columns(2)
                                nome_f  = c1.text_input("Nome",  value=_sf["Nome"])
                                cargo_f = c2.text_input("Cargo (livre)", value=str(_sf.get("Cargo","") or ""),
                                                        help="Digite qualquer função: Pedreiro, Eletricista, Arquiteto, etc.")
                                tc_idx  = contrato_opts.index(_sf.get("Tipo Contrato","CLT")) if _sf.get("Tipo Contrato","CLT") in contrato_opts else 0
                                cont_f  = c1.selectbox("Tipo de Contrato", contrato_opts, index=tc_idx)
                                ob_idx  = obras_lista.index(ob_val_orig) if ob_val_orig in obras_lista else 0
                                obra_f  = c2.selectbox("Obra Alocada", obras_lista, index=ob_idx)
                                if _role() == "admin":
                                    sal_f = c1.number_input("Salário / Valor (R$)", value=_to_num(_sf["Salário (R$)"]),step=100.0)
                                else:
                                    sal_f = _to_num(_sf["Salário (R$)"])
                                adm_f   = c2.text_input("Admissão", value=str(_sf.get("Admissão","") or ""))
                                sit_opts = ["Ativo","Férias","Afastado","Demitido"]
                                sit_val = str(_sf.get("Situação","Ativo") or "Ativo")
                                sit_f   = c1.selectbox("Situação", sit_opts,
                                                        index=sit_opts.index(sit_val) if sit_val in sit_opts else 0)
                                b1,b2,_ = st.columns([1,1,3])
                                sv_f  = b1.form_submit_button("💾 Salvar",type="primary")
                                del_f = b2.form_submit_button("🗑️ Excluir")
                            if sv_f:
                                ix_f = st.session_state.funcionarios[st.session_state.funcionarios["ID"]==id_f].index[0]
                                st.session_state.funcionarios.loc[ix_f,
                                    ["Nome","Cargo","Tipo Contrato","Obra","Salário (R$)","Admissão","Situação"]
                                ] = [nome_f, cargo_f, cont_f, obra_f, sal_f, adm_f, sit_f]
                                sb_uuid = _sb_id(st.session_state.funcionarios, id_f)
                                if obra_f != ob_val_orig and sb_uuid:
                                    data_transf = adm_f if adm_f else date.today().strftime("%d/%m/%Y")
                                    nova_obra_id = None if obra_f == "Custo Geral" else _obra_uuid(obra_f) if _obra_valida(obra_f) else None
                                    sync.colaborador_transferir(sb_uuid, nova_obra_id, sync._br_to_iso(data_transf) or date.today().isoformat(), cargo_f)
                                sync.colaborador_save({"Nome":nome_f,"Cargo":cargo_f,"Tipo Contrato":cont_f,
                                                       "Salário (R$)":sal_f,"Admissão":adm_f,"Situação":sit_f,
                                                       "Obra": obra_f}, sb_id=sb_uuid)
                                _notify(f"✅ Dados de **{nome_f}** atualizados com sucesso!"); st.rerun()
                            if del_f:
                                _nome_del_f = nome_f
                                uuid_f_del = _sb_id(st.session_state.funcionarios, id_f)
                                st.session_state.funcionarios = st.session_state.funcionarios[st.session_state.funcionarios["ID"]!=id_f].reset_index(drop=True)
                                if uuid_f_del:
                                    try:
                                        from db import sb
                                        sb().table("colaboradores").update({"ativo": False}).eq("id", uuid_f_del).execute()
                                    except Exception:
                                        st.warning("Funcionário removido localmente, mas falhou sincronização.")
                                _notify(f"✅ **{_nome_del_f}** removido do sistema!"); st.rerun()

                        sb_uuid_h = _sb_id(st.session_state.funcionarios, id_f)
                        if sb_uuid_h:
                            alocs = sync.alocacoes_load(sb_uuid_h)
                            if alocs:
                                st.markdown("---")
                                st.markdown("#### 📋 Histórico de Alocações")
                                for a in alocs:
                                    ob_nome = (a.get("obras") or {}).get("nome", "Custo Geral") if a.get("obras") else "Custo Geral"
                                    ini = str(a.get("data_inicio") or "")[:10]
                                    fim = str(a.get("data_fim") or "Atual")[:10]
                                    st.caption(f"**{ob_nome}** · {ini} → {fim} · {a.get('funcao_obra') or ''}")
                else:
                    cols_lote_f = st.columns([2, 2, 1])
                    with cols_lote_f[0]:
                        st.caption(f"**{n_sel_f}** funcionário(s) selecionado(s)")
                    with cols_lote_f[1]:
                        novo_status_lote_f = st.selectbox(
                            "Alterar Situação", ["Ativo", "Férias", "Afastado", "Demitido"],
                            key="ns_lote_func")
                    with cols_lote_f[2]:
                        st.write("")
                        st.write("")
                        if st.button("✅ Aplicar em Lote", key="btn_lote_func", type="primary"):
                            for idx, _rf in LF.iterrows():
                                st.session_state.funcionarios.loc[idx, "Situação"] = novo_status_lote_f
                                _uuid_f = _sb_id(st.session_state.funcionarios, _rf["ID"])
                                if _uuid_f:
                                    sync.colaborador_save(
                                        {"Situação": novo_status_lote_f}, sb_id=_uuid_f)
                            _notify(f"✅ {n_sel_f} funcionário(s) atualizados para **{novo_status_lote_f}**!")
                            st.rerun()
                    st.markdown("---")
                    if st.button(f"🗑️ Excluir {n_sel_f} selecionados", type="secondary", key="bulk_del_func"):
                        _removidos = []
                        for _, _rf in LF.iterrows():
                            _id_fd = _rf["ID"]
                            _nome_fd = _rf["Nome"]
                            _uuid_fd = _sb_id(st.session_state.funcionarios, _id_fd)
                            st.session_state.funcionarios = st.session_state.funcionarios[
                                st.session_state.funcionarios["ID"] != _id_fd
                            ].reset_index(drop=True)
                            try:
                                if _uuid_fd:
                                    from db import sb
                                    sb().table("colaboradores").update({"ativo": False}).eq("id", _uuid_fd).execute()
                            except Exception:
                                st.warning(f"Falha ao sincronizar exclusão de {_nome_fd}.")
                            _removidos.append(_nome_fd)
                        if _removidos:
                            _notify(f"✅ {len(_removidos)} funcionário(s) removido(s): {', '.join(_removidos[:3])}{'...' if len(_removidos)>3 else ''}")
                            st.rerun()
    with t2:
        faltas = st.session_state.ponto.copy()
        total_ativos = len(st.session_state.funcionarios[st.session_state.funcionarios["Situação"] == "Ativo"]) if not st.session_state.funcionarios.empty else 0

        datas = sorted(faltas["Data"].unique().tolist(), reverse=True) if not faltas.empty else []
        if datas:
            d_sel = st.selectbox("Data", datas)
            dia   = faltas[faltas["Data"] == d_sel]
            n_faltas   = len(dia)
            n_presentes = max(0, total_ativos - n_faltas)
            c1,c2,c3 = st.columns(3)
            c1.metric("Colaboradores Ativos", total_ativos)
            c2.metric("Presentes", n_presentes)
            c3.metric("Faltas", n_faltas, delta_color="inverse" if n_faltas > 0 else "normal")
            if not dia.empty:
                st.markdown("**Faltas registradas neste dia:**")
                drop_pt = [c for c in ["ID","SB_ID"] if c in dia.columns]
                st.dataframe(dia.drop(columns=drop_pt), width='stretch', hide_index=True)
        else:
            st.info("Nenhuma falta registrada.")
            c1,c2 = st.columns(2)
            c1.metric("Colaboradores Ativos", total_ativos)
            c2.metric("Presentes hoje (est.)", total_ativos)

        st.markdown("---")
        st.subheader("Registrar Falta")
        with st.form("form_ponto"):
            c1,c2 = st.columns(2)
            _ff_pt    = st.session_state.get("funcionarios", pd.DataFrame())
            _funcs_pt = _ff_pt["Nome"].tolist() if not _ff_pt.empty else ["(nenhum colaborador)"]
            func_p  = c1.selectbox("Funcionário", _funcs_pt)
            data_p  = c2.text_input("Data", value=date.today().strftime("%d/%m/%Y"))
            tipo_p  = c1.selectbox("Tipo de Falta", ["Injustificada","Justificada","Atestado","Folga","Férias"])
            obra_p  = c2.selectbox("Obra", _obras_nomes(), key="obra_pt")
            obs_p   = c1.text_input("Observação")
            ok_pt   = st.form_submit_button("⚠️ Registrar Falta", type="primary")
        if ok_pt:
            _dado_pt = {"Data": data_p, "Funcionário": func_p,
                        "Obra": obra_p, "Tipo": tipo_p, "Observação": obs_p}
            _uuid_pt = sync.falta_save(_dado_pt, _obra_uuid(obra_p) if _obra_valida(obra_p) else None)
            st.session_state.ponto = pd.concat([
                st.session_state.ponto,
                pd.DataFrame([{"ID": _next_id(st.session_state.ponto),
                               "SB_ID": _uuid_pt or None, **_dado_pt}])
            ], ignore_index=True)
            _notify(f"Falta de **{func_p}** em {data_p} registrada."); st.rerun()

        st.markdown("---")
        st.subheader("Registro de Horário (Entrada / Saída)")
        regs = st.session_state.ponto_registros.copy()
        if not regs.empty:
            datas_reg = sorted(regs["Data"].unique().tolist(), reverse=True)
            d_sel_reg = st.selectbox("Data", datas_reg, key="ponto_reg_data_filtro")
            dia_reg = regs[regs["Data"] == d_sel_reg]
            drop_reg = [c for c in ["ID","SB_ID"] if c in dia_reg.columns]
            st.dataframe(dia_reg.drop(columns=drop_reg), width='stretch', hide_index=True)
        else:
            st.info("Nenhum registro de horário lançado ainda.")

        st.markdown("**Bater ponto do dia**")
        with st.form("form_ponto_registro"):
            c1, c2 = st.columns(2)
            _funcs_reg = _ff_pt["Nome"].tolist() if not _ff_pt.empty else ["(nenhum colaborador)"]
            func_reg  = c1.selectbox("Funcionário", _funcs_reg, key="ponto_reg_func")
            data_reg  = c2.text_input("Data", value=date.today().strftime("%d/%m/%Y"), key="ponto_reg_data")
            obra_reg  = c1.selectbox("Obra", _obras_nomes(), key="ponto_reg_obra")
            obs_reg   = c2.text_input("Observação", key="ponto_reg_obs")
            c3, c4, c5, c6 = st.columns(4)
            entrada_reg  = c3.time_input("Entrada", value=time(7, 0), key="ponto_reg_entrada")
            said_alm_reg = c4.time_input("Saída Almoço", value=time(12, 0), key="ponto_reg_saida_almoco")
            ret_alm_reg  = c5.time_input("Retorno Almoço", value=time(13, 0), key="ponto_reg_retorno_almoco")
            saida_reg    = c6.time_input("Saída", value=time(17, 0), key="ponto_reg_saida")
            ok_reg = st.form_submit_button("🕐 Registrar Ponto", type="primary")
        if ok_reg:
            horas_manha  = (datetime.combine(date.today(), said_alm_reg) - datetime.combine(date.today(), entrada_reg)).total_seconds() / 3600
            horas_tarde  = (datetime.combine(date.today(), saida_reg) - datetime.combine(date.today(), ret_alm_reg)).total_seconds() / 3600
            horas_trab   = round(max(0.0, horas_manha) + max(0.0, horas_tarde), 2)
            horas_normais = min(horas_trab, 8.0)
            horas_extras  = round(max(0.0, horas_trab - 8.0), 2)
            _dado_reg = {
                "Data": data_reg, "Funcionário": func_reg, "Obra": obra_reg,
                "Entrada": entrada_reg.strftime("%H:%M"),
                "Saída Almoço": said_alm_reg.strftime("%H:%M"),
                "Retorno Almoço": ret_alm_reg.strftime("%H:%M"),
                "Saída": saida_reg.strftime("%H:%M"),
                "Horas Normais": horas_normais, "Horas Extras": horas_extras,
                "Observação": obs_reg,
            }
            _uuid_reg = sync.ponto_registro_save(_dado_reg, _obra_uuid(obra_reg) if _obra_valida(obra_reg) else None)
            st.session_state.ponto_registros = pd.concat([
                st.session_state.ponto_registros,
                pd.DataFrame([{"ID": _next_id(st.session_state.ponto_registros),
                               "SB_ID": _uuid_reg or None, **_dado_reg}])
            ], ignore_index=True)
            _notify(f"Ponto de **{func_reg}** em {data_reg} registrado: "
                    f"{horas_normais:.1f}h normais" + (f" + {horas_extras:.1f}h extras" if horas_extras > 0 else "") + "."); st.rerun()

    with t3:
        if not _pode(["folha"]):
            st.info("Acesso restrito. Solicite ao administrador.")
        else:
            ff_all = st.session_state.funcionarios.copy()
            if ff_all.empty:
                st.info("Nenhum colaborador cadastrado. Use a aba ➕ Novo Colaborador.")
            else:
                ff_all["Salário (R$)"]  = pd.to_numeric(ff_all["Salário (R$)"], errors="coerce").fillna(0.0)
                ff_all["Obra"]          = ff_all["Obra"].fillna("Sem alocação").replace("", "Sem alocação")
                ff_all["INSS (R$)"]     = (ff_all["Salário (R$)"]*0.11).round(2)
                ff_all["FGTS (R$)"]     = (ff_all["Salário (R$)"]*0.08).round(2)
                ff_all["Líquido (R$)"]  = ff_all["Salário (R$)"]-ff_all["INSS (R$)"]
                # ── Totais consolidados ────────────────────────────────────
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Bruto Total",  _fmt(ff_all["Salário (R$)"].sum()))
                c2.metric("INSS",         _fmt(ff_all["INSS (R$)"].sum()))
                c3.metric("FGTS",         _fmt(ff_all["FGTS (R$)"].sum()))
                c4.metric("Líquido Total",_fmt(ff_all["Líquido (R$)"].sum()))
                st.markdown("---")
                # ── Filtro por Obra ────────────────────────────────────────
                todas_ob = ["Todas"] + _uniq(ff_all["Obra"])
                ob_folha = st.selectbox("Filtrar por Obra", todas_ob, key="folha_obra_filtro")
                ff = ff_all.copy() if ob_folha == "Todas" else ff_all[ff_all["Obra"] == ob_folha].copy()
                if ob_folha != "Todas":
                    cf1,cf2,cf3 = st.columns(3)
                    cf1.metric(f"Bruto — {ob_folha}", _fmt(ff["Salário (R$)"].sum()))
                    cf2.metric("Funcionários",         str(len(ff)))
                    cf3.metric("% da Folha Total",
                                f"{ff['Salário (R$)'].sum()/ff_all['Salário (R$)'].sum()*100:.1f}%")
                ex_ff = ff[["Nome","Cargo","Tipo Contrato","Obra","Salário (R$)","INSS (R$)","FGTS (R$)","Líquido (R$)"]].copy()
                for col in ["Salário (R$)","INSS (R$)","FGTS (R$)","Líquido (R$)"]:
                    ex_ff[col] = ex_ff[col].apply(_fmt)
                st.dataframe(ex_ff, width='stretch', hide_index=True)
                st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_ff), file_name="folha_pagamento.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="btn_xls_folha")
                st.markdown("---")
                st.subheader("Custo de Pessoal por Obra")
                custo_obra = ff_all.groupby("Obra")["Salário (R$)"].sum().reset_index().sort_values("Salário (R$)",ascending=False)
                fig_folha = px.bar(custo_obra, x="Obra", y="Salário (R$)",
                                   color_discrete_sequence=["#2B59C3"], text="Salário (R$)",
                                   labels={"Obra":"","Salário (R$)":"R$/mês"})
                fig_folha.update_traces(texttemplate="R$%{text:,.0f}", textposition="outside")
                fig_folha.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white",
                                        yaxis_tickformat=",.0f", margin=dict(t=20,b=80))
                st.plotly_chart(fig_folha, width='stretch')

                # ── Exportar Folha em PDF ──────────────────────────────────
                st.markdown("---")
                st.subheader("📄 Exportar Folha de Pagamento (PDF)")
                ob_pdf_folha = st.selectbox("Obra para exportar", ["Todas as Obras"] + _uniq(ff_all["Obra"]), key="folha_pdf_obra")
                ref_pdf_folha = st.text_input("Mês de referência", value=date.today().strftime("%m/%Y"), key="folha_pdf_ref")
                if st.button("📥 Gerar PDF da Folha", key="btn_gerar_folha", type="primary"):
                    try:
                        from gerar_pdf import gerar_folha_pagamento as _gerar_fp
                        ff_exp = ff_all.copy() if ob_pdf_folha == "Todas as Obras" else ff_all[ff_all["Obra"] == ob_pdf_folha].copy()
                        obra_label = ob_pdf_folha if ob_pdf_folha != "Todas as Obras" else "Todas as Obras"
                        bruto_exp   = ff_exp["Salário (R$)"].sum()
                        inss_p_exp  = round(bruto_exp * 0.20, 2)
                        rat_exp     = round(bruto_exp * 0.03, 2)
                        fgts_exp    = round(bruto_exp * 0.08, 2)
                        custo_exp   = round(bruto_exp + inss_p_exp + rat_exp + fgts_exp, 2)
                        colab_list  = []
                        for _, row in ff_exp.iterrows():
                            sal = _to_num(row["Salário (R$)"])
                            colab_list.append({
                                "nome":          row.get("Nome", "—"),
                                "cargo":         row.get("Cargo", "—"),
                                "tipo_contrato": row.get("Tipo Contrato", "CLT"),
                                "salario":       sal,
                                "inss":          round(sal * 0.11, 2),
                                "fgts":          round(sal * 0.08, 2),
                                "liquido":       round(sal - sal * 0.11, 2),
                            })
                        dados_fp = {
                            "ref_mes":       ref_pdf_folha,
                            "obra":          obra_label,
                            "colaboradores": colab_list,
                            "bruto":         bruto_exp,
                            "inss_patronal": inss_p_exp,
                            "rat":           rat_exp,
                            "fgts":          fgts_exp,
                            "custo_empresa": custo_exp,
                        }
                        pdf_fp = _gerar_fp(dados_fp)
                        nome_fp = f"Folha_{ref_pdf_folha.replace('/','_')}_{obra_label[:20].replace(' ','_')}.pdf"
                        st.download_button(
                            label="⬇️ Baixar Folha em PDF",
                            data=pdf_fp,
                            file_name=nome_fp,
                            mime="application/pdf",
                            key="dl_folha_pdf",
                        )
                    except Exception as _e_fp:
                        st.error(f"Erro ao gerar PDF da Folha: {_e_fp}")

                # ── Fechar Folha e Lançar no Financeiro ───────────────────
                st.markdown("---")
                st.subheader("Fechar Folha e Lançar no Financeiro")
                st.caption(
                    "Consolida o **Custo Total Empresa** (Salário + INSS Patronal 20% + RAT 3% + FGTS 8%) "
                    "para a obra selecionada e gera uma Conta a Pagar com Categoria **Folha de Pagamento**."
                )
                obras_folha_lanc = _obras_nomes()
                ob_lanc = st.selectbox("Obra para lançamento", obras_folha_lanc, key="folha_ob_lanc")
                ref_mes = st.text_input("Mês de referência", value=date.today().strftime("%m/%Y"),
                                         key="folha_ref_mes")
                venc_folha = st.text_input("Vencimento", key="folha_venc",
                                            value=(date.today() + timedelta(days=5)).strftime("%d/%m/%Y"))
                obra_uuid_folha = _obra_uuid(ob_lanc)
                df_eap_folha = db.eap_itens_por_obra(obra_uuid_folha) if obra_uuid_folha else pd.DataFrame()
                eap_opts_folha = [""] + [f"{r['codigo']} — {r['descricao']}" for _, r in df_eap_folha.iterrows()] if not df_eap_folha.empty else [""]
                eap_sel_folha = st.selectbox("Etapa EAP", eap_opts_folha, key="folha_eap")
                tc_folha = st.selectbox("Tipo de Custo",
                    ["Mão-de-obra", "Material", "Equipamento", "Subempreiteiro", "Administrativo", "Impostos"],
                    index=0, key="folha_tc")
                eap_id_folha = str(df_eap_folha.iloc[eap_opts_folha.index(eap_sel_folha) - 1]["id"]) if eap_sel_folha and not df_eap_folha.empty else None
                ff_lanc = ff_all[ff_all["Obra"] == ob_lanc].copy()
                bruto_lanc  = ff_lanc["Salário (R$)"].apply(_to_num).sum()
                inss_pat    = round(bruto_lanc * 0.20, 2)
                rat_lanc    = round(bruto_lanc * 0.03, 2)
                fgts_lanc   = round(bruto_lanc * 0.08, 2)
                custo_emp   = round(bruto_lanc + inss_pat + rat_lanc + fgts_lanc, 2)
                if bruto_lanc > 0:
                    cl1,cl2,cl3,cl4 = st.columns(4)
                    cl1.metric("Salário Bruto",     _fmt(bruto_lanc))
                    cl2.metric("INSS Patronal 20%", _fmt(inss_pat))
                    cl3.metric("RAT 3% + FGTS 8%", _fmt(rat_lanc + fgts_lanc))
                    cl4.metric("Custo Total Empresa", _fmt(custo_emp))
                else:
                    st.info(f"Nenhum colaborador alocado à obra **{ob_lanc}** no sistema.")
                if st.button("⚠️ Fechar e Lançar Folha no Financeiro", type="primary",
                             key="btn_fechar_folha", disabled=(bruto_lanc == 0)):
                    desc_folha = f"Folha de Pagamento {ref_mes} — {ob_lanc} ({len(ff_lanc)} colab.)"
                    ja_existe = st.session_state.contas_pagar[
                        (st.session_state.contas_pagar["Obra"] == ob_lanc) &
                        (st.session_state.contas_pagar["Descrição"] == desc_folha)
                    ]
                    if len(ja_existe):
                        st.warning("Já existe um lançamento idêntico em Contas a Pagar. Verifique antes de relançar.")
                    else:
                        dados_folha = {
                            "Obra": ob_lanc, "Fornecedor": "Folha de Pagamento Interna",
                            "Descrição": desc_folha, "Categoria": "Folha de Pagamento",
                            "Valor (R$)": custo_emp, "Vencimento": venc_folha,
                            "Status": "A Pagar", "NF": "—", "Forma Pag.": "Transferência",
                            "eap_item_id": eap_id_folha,
                            "tipo_custo": tc_folha if tc_folha else None,
                        }
                        uuid_folha = sync.lancamento_save(dados_folha, "PAGAR", obra_uuid_folha)
                        st.session_state.contas_pagar = pd.concat([
                            st.session_state.contas_pagar,
                            pd.DataFrame([{
                                "ID":    _next_id(st.session_state.contas_pagar),
                                "SB_ID": uuid_folha or None,
                                **dados_folha,
                            }])
                        ], ignore_index=True)
                        st.success(
                            f"✅ Folha lançada no Financeiro! Custo Empresa {_fmt(custo_emp)} "
                            f"registrado em Contas a Pagar — {ob_lanc} ref. {ref_mes}."
                        )
                        st.rerun()

    _CARGOS_SUGESTOES = [
        "— digitar abaixo —",
        "Engenheiro Civil","Engenheiro Eletricista","Engenheiro de Segurança",
        "Arquiteto","Técnico em Edificações","Mestre de Obras","Encarregado",
        "Pedreiro Oficial","Pedreiro","Servente","Armador","Carpinteiro",
        "Eletricista","Encanador/Bombeiro","Pintor","Azulejista","Gesseiro",
        "Operador de Máquinas","Soldador","Serralheiro",
        "Técnico de Segurança do Trabalho","Auxiliar Administrativo",
        "Almoxarife","Apontador","Motorista",
    ]
    with t4:
        with st.form("form_novo_func"):
            c1,c2 = st.columns(2)
            nome_nf     = c1.text_input("Nome *")
            cargo_sel   = c2.selectbox("Cargo *", _CARGOS_SUGESTOES)
            cargo_livre = c2.text_input("Cargo (outro — deixe em branco se selecionou acima)")
            cargo_nf    = cargo_livre.strip() if cargo_livre.strip() else (cargo_sel if cargo_sel != "— digitar abaixo —" else "")
            cont_nf  = c1.selectbox("Tipo de Contrato *", ["CLT","MEI","Empreiteiro","Autônomo","Diarista","Estagiário"])
            obra_nf  = c2.selectbox("Obra Alocada", _obras_nomes(["Sede","Todas"]))
            sal_nf   = c1.number_input("Salário / Valor (R$)", min_value=0.0, step=100.0)
            adm_nf   = c2.text_input("Admissão", value=date.today().strftime("%d/%m/%Y"))
            sit_nf   = c1.selectbox("Situação", ["Ativo","Férias","Afastado","Demitido"])
            ok_nf    = st.form_submit_button("➕ Cadastrar", type="primary")
        if ok_nf:
            if not nome_nf or not cargo_nf: st.error("Nome e Cargo obrigatórios. Selecione da lista ou digite no campo 'Cargo (outro)'.")
            else:
                dados_col = {"Nome": nome_nf, "Cargo": cargo_nf, "Tipo Contrato": cont_nf,
                             "Obra": obra_nf, "Salário (R$)": sal_nf, "Admissão": adm_nf, "Situação": sit_nf}
                uuid_col = sync.colaborador_save(dados_col)
                st.session_state.funcionarios = pd.concat([
                    st.session_state.funcionarios,
                    pd.DataFrame([{"ID": _next_id(st.session_state.funcionarios),
                                   "SB_ID": uuid_col or None, **dados_col}])
                ], ignore_index=True)
                _notify(f"✅ Colaborador **{nome_nf}** ({cargo_nf}) cadastrado com sucesso!"); st.rerun()

    # ── Férias ────────────────────────────────────────────────────────────
    with t4:
        st.subheader("🌴 Férias")
        from sync import ferias_load, ferias_save as _ferias_save
        if "ferias" not in st.session_state:
            st.session_state.ferias = ferias_load()

        tab_f_lista, tab_f_nova = st.tabs(["📋 Lista", "➕ Agendar Férias"])
        with tab_f_nova:
            with st.form("form_ferias"):
                c1, c2 = st.columns(2)
                func_opts = _uniq(st.session_state.funcionarios["Nome"]) if not st.session_state.funcionarios.empty else []
                func_f = c1.selectbox("Funcionário *", func_opts if func_opts else [""])
                ini_f = c2.text_input("Data Início *", value=date.today().strftime("%Y-%m-%d"))
                dias_f = c1.number_input("Dias", min_value=1, max_value=30, value=30, step=1)
                sal_f = float(st.session_state.funcionarios[st.session_state.funcionarios["Nome"] == func_f]["Salário (R$)"].iloc[0]) if func_f and not st.session_state.funcionarios.empty else 0
                vb_f = c2.number_input("Valor Bruto (R$)", min_value=0.0, value=sal_f, step=100.0)
                obs_f = st.text_area("Observação", height=60)
                ok_f = st.form_submit_button("💾 Agendar Férias", type="primary")
            if ok_f:
                if not func_f.strip():
                    st.error("Selecione um funcionário.")
                else:
                    fim = datetime.strptime(ini_f, "%Y-%m-%d") + timedelta(days=int(dias_f))
                    dados_f = {"Funcionário": func_f, "Início": ini_f, "Fim": fim.strftime("%Y-%m-%d"),
                               "Dias": dias_f, "Valor Bruto": vb_f, "Valor Líquido": vb_f * 1.333,
                               "Status": "Agendada", "Observação": obs_f}
                    sb_f = _ferias_save(dados_f)
                    st.session_state.ferias = pd.concat([
                        st.session_state.ferias,
                        pd.DataFrame([{"ID": _next_id(st.session_state.ferias), "SB_ID": sb_f or None, **dados_f}])
                    ], ignore_index=True)
                    _notify(f"Férias de **{func_f}** agendadas!"); st.rerun()

        with tab_f_lista:
            df_f = st.session_state.ferias.copy()
            if df_f.empty:
                st.info("Nenhum período de férias registrado.")
            else:
                st.dataframe(df_f.drop(columns=[c for c in ["ID", "SB_ID"] if c in df_f.columns], errors='ignore'),
                             width='stretch', hide_index=True)
                st.metric("Total de Registros", len(df_f))
                pend = len(df_f[df_f["Status"] == "Agendada"])
                if pend:
                    st.info(f"{pend} período(s) de férias aguardando início.")

    # ── Adicionais ────────────────────────────────────────────────────────
    with t5:
        st.subheader("⚠️ Adicionais Salariais")
        from sync import adicionais_load, adicional_save as _adic_save, adicional_delete as _adic_delete

        func_a = st.selectbox("Funcionário", _uniq(st.session_state.funcionarios["Nome"]) if not st.session_state.funcionarios.empty else [""], key="adic_func")
        if func_a:
            func_uuid = _sb_id(st.session_state.funcionarios, st.session_state.funcionarios[st.session_state.funcionarios["Nome"] == func_a]["ID"].iloc[0]) if func_a in st.session_state.funcionarios["Nome"].values else None

            tab_a_lista, tab_a_novo = st.tabs(["📋 Adicionais", "➕ Novo Adicional"])

            with tab_a_novo:
                with st.form("form_adicional"):
                    c1, c2 = st.columns(2)
                    tipo_a = c1.selectbox("Tipo", ["Insalubridade", "Periculosidade", "Horas Extras", "Noturno", "Comissão", "Outros"])
                    pct_a = c2.number_input("Percentual (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                    sal_base = float(st.session_state.funcionarios[st.session_state.funcionarios["Nome"] == func_a]["Salário (R$)"].iloc[0]) if not st.session_state.funcionarios.empty else 0
                    val_a = c1.number_input("Valor (R$)", min_value=0.0, value=sal_base * pct_a / 100, step=10.0)
                    ok_a = st.form_submit_button("💾 Salvar Adicional", type="primary")
                if ok_a:
                    dados_a = {"Funcionário": func_a, "Tipo": tipo_a, "Percentual": pct_a, "Valor (R$)": val_a, "Ativo": "Sim"}
                    sb_a = _adic_save(dados_a)
                    _notify(f"Adicional **{tipo_a}** de **{_fmt(val_a)}** salvo!"); st.rerun()

            with tab_a_lista:
                df_a = adicionais_load(func_uuid)
                if df_a.empty:
                    st.info(f"Nenhum adicional para {func_a}.")
                else:
                    st.dataframe(df_a.drop(columns=[c for c in ["ID", "SB_ID"] if c in df_a.columns], errors='ignore'),
                                 width='stretch', hide_index=True)
                    total_adic = df_a[df_a["Ativo"] == "Sim"]["Valor (R$)"].sum()
                    st.metric("Total de Adicionais Ativos", _fmt(total_adic))

    # ── Rescisão ──────────────────────────────────────────────────────────
    with t6:
        st.subheader("📄 Rescisão Contratual")
        from sync import rescisoes_load, rescicao_save as _resc_save

        if "rescisoes" not in st.session_state:
            st.session_state.rescisoes = rescisoes_load()

        tab_r_lista, tab_r_nova = st.tabs(["📋 Lista", "➕ Calcular Rescisão"])
        with tab_r_nova:
            with st.form("form_rescisao"):
                c1, c2 = st.columns(2)
                func_opts_r = _uniq(st.session_state.funcionarios["Nome"]) if not st.session_state.funcionarios.empty else []
                func_r = c1.selectbox("Funcionário *", func_opts_r if func_opts_r else [""])
                data_r = c2.text_input("Data da Rescisão *", value=date.today().strftime("%Y-%m-%d"))
                tipo_r = c1.selectbox("Tipo", ["Sem justa causa", "Com justa causa", "Pedido demissão", "Término contrato", "Acordo"])
                aviso_r = c2.selectbox("Aviso Prévio", ["Trabalhado", "Indenizado", "Dispensado"])
                sal_r = float(st.session_state.funcionarios[st.session_state.funcionarios["Nome"] == func_r]["Salário (R$)"].iloc[0]) if func_r and not st.session_state.funcionarios.empty else 0
                st.markdown("##### Verbas Rescisórias")
                c3, c4 = st.columns(2)
                ss_r = c3.number_input("Saldo Salário", min_value=0.0, value=sal_r / 30 * 15 if sal_r else 0, step=100.0)
                fv_r = c4.number_input("Férias Vencidas", min_value=0.0, value=sal_r if sal_r else 0, step=100.0)
                fp_r = c3.number_input("Férias Proporcionais", min_value=0.0, value=sal_r / 12 * 5 if sal_r else 0, step=100.0)
                tc_r = c4.number_input("1/3 Constitucional", min_value=0.0, value=(fv_r + fp_r) / 3, step=100.0)
                d13_r = c3.number_input("13º Salário", min_value=0.0, value=sal_r / 12 * 7 if sal_r else 0, step=100.0)
                ap_r = c4.number_input("Aviso Prévio Valor", min_value=0.0, value=sal_r if sal_r else 0, step=100.0)
                mf_r = c1.number_input("Multa FGTS", min_value=0.0, value=sal_r * 0.4 if sal_r else 0, step=100.0)
                desc_r = c2.number_input("Descontos", min_value=0.0, value=0.0, step=100.0)
                total_br = ss_r + fv_r + fp_r + tc_r + d13_r + ap_r + mf_r
                total_liq = total_br - desc_r
                st.metric("Total Bruto", _fmt(total_br))
                st.metric("Total Líquido", _fmt(total_liq))
                obs_r = st.text_area("Observação", height=60)
                ok_r = st.form_submit_button("💾 Salvar Rescisão", type="primary")
            if ok_r:
                if not func_r.strip():
                    st.error("Selecione um funcionário.")
                else:
                    dados_r = {"Funcionário": func_r, "Data Rescisão": data_r, "Tipo": tipo_r,
                               "Aviso Prévio": aviso_r, "Saldo Salário": ss_r, "Férias Vencidas": fv_r,
                               "Férias Proporcionais": fp_r, "1/3 Constitucional": tc_r,
                               "13º Salário": d13_r, "Aviso Prévio Valor": ap_r,
                               "Multa FGTS": mf_r, "Descontos": desc_r,
                               "Total Bruto": total_br, "Total Líquido": total_liq,
                               "Status": "Calculada", "Observação": obs_r}
                    sb_r = _resc_save(dados_r)
                    st.session_state.rescisoes = pd.concat([
                        st.session_state.rescisoes,
                        pd.DataFrame([{"ID": _next_id(st.session_state.rescisoes), "SB_ID": sb_r or None, **dados_r}])
                    ], ignore_index=True)
                    _notify(f"Rescisão de **{func_r}** — **{_fmt(total_liq)}** calculada!"); st.rerun()

        with tab_r_lista:
            df_r = st.session_state.rescisoes.copy()
            if df_r.empty:
                st.info("Nenhuma rescisão registrada.")
            else:
                cols_r = ["Funcionário", "Data Rescisão", "Tipo", "Total Bruto", "Total Líquido", "Status"]
                sel_r = _tabela_clicavel(df_r, colunas_exibir=[c for c in cols_r if c in df_r.columns], key="tbl_resc",
                    formatters={"Total Bruto": _fmt, "Total Líquido": _fmt})
                if isinstance(sel_r, pd.DataFrame) and not sel_r.empty:
                    row_r = sel_r.iloc[0]
                    st.markdown("---")
                    with st.container(border=True):
                        st.markdown(f"#### 📄 Rescisão: {row_r['Funcionário']}")
                        st.markdown(f"**Data:** {row_r.get('Data Rescisão','')}  ·  **Tipo:** {row_r.get('Tipo','')}")
                        st.markdown(f"**Total Bruto:** {_fmt(float(row_r.get('Total Bruto',0)))}")
                        st.markdown(f"**Total Líquido:** {_fmt(float(row_r.get('Total Líquido',0)))}")
                        if st.button("🗑️ Excluir", key=f"del_resc_{row_r['ID']}"):
                            sb_id_r = _sb_id(st.session_state.rescisoes, row_r["ID"])
                            if sb_id_r:
                                from db import rescicao_atualizar
                                rescicao_atualizar(sb_id_r, {"status": "Cancelada"})
                            st.session_state.rescisoes = st.session_state.rescisoes[
                                st.session_state.rescisoes["ID"] != row_r["ID"]
                            ].reset_index(drop=True)
                            _notify("Rescisão cancelada!"); st.rerun()

# ── Qualidade ─────────────────────────────────────────────────────────────────

def pagina_qualidade():
    st.title("✅ Qualidade")
    _init()
    _show_toast()
    t1,t2,t3,t4 = st.tabs(["📋 Checklists","⚠️ Não-Conformidades","➕ Nova Inspeção","➕ Abrir NC"])

    with t1:
        chk = st.session_state.checklists.copy()
        cf1,cf2 = st.columns(2)
        fo_q = cf1.selectbox("Obra",      ["Todas"]+_uniq(chk["Obra"]),      key="fq_ob")
        fr_q = cf2.selectbox("Resultado", ["Todos"]+_uniq(chk["Resultado"]),  key="fq_res")
        if fo_q != "Todas": chk = chk[chk["Obra"]==fo_q]
        if fr_q != "Todos": chk = chk[chk["Resultado"]==fr_q]
        tot = st.session_state.checklists
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Inspeções", len(tot))
        c2.metric("Aprovadas",  len(tot[tot["Resultado"]=="Aprovado"]))
        c3.metric("Reprovadas", len(tot[tot["Resultado"]=="Reprovado"]))
        st.markdown("---")
        bdg = {"Aprovado":"🟢","Reprovado":"🔴"}
        ex_q = chk.drop(columns=[c for c in ["ID","SB_ID"] if c in chk.columns]).copy()
        ex_q["Resultado"] = ex_q["Resultado"].apply(lambda r:f"{bdg.get(r,'⚪')} {r}")
        st.dataframe(ex_q,width='stretch',hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_q), file_name="checklists.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_chk")

    with t2:
        ncs = st.session_state.ncs.copy()
        cf3,cf4 = st.columns(2)
        fo_nc = cf3.selectbox("Obra",  ["Todas"]+_uniq(ncs["Obra"]),   key="fnc_ob")
        fs_nc = cf4.selectbox("Status",["Todos"]+_uniq(ncs["Status"]),  key="fnc_st")
        if fo_nc != "Todas": ncs = ncs[ncs["Obra"]==fo_nc]
        if fs_nc != "Todos": ncs = ncs[ncs["Status"]==fs_nc]
        bdg_nc = {"Aberta":"🔴","Em tratamento":"🟡","Encerrada":"🟢"}
        grv_nc = {"Alta":"🔴","Moderada":"🟡","Baixa":"🟢"}
        LNC = None
        if not ncs.empty:
            colunas_nc = ["Obra","Descrição","Gravidade","Status","Responsável","Prazo"]
            colunas_nc = [c for c in colunas_nc if c in ncs.columns]
            LNC = _tabela_clicavel(
                ncs, colunas_exibir=colunas_nc, key="tbl_nc",
                formatters={
                    "Gravidade": lambda g: f"{grv_nc.get(g,'⚪')} {g}",
                    "Status": lambda s: f"{bdg_nc.get(s,'⚪')} {s}",
                },
            )
        ex_nc = ncs.copy()
        if not ex_nc.empty:
            ex_nc["Gravidade"] = ex_nc["Gravidade"].apply(lambda g:("🔴 " if g=="Alta" else "🟡 " if g=="Moderada" else "🟢 ")+g)
            ex_nc["Status"]    = ex_nc["Status"].apply(lambda s:f"{bdg_nc.get(s,'⚪')} {s}")
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_nc), file_name="nao_conformidades.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_nc")
        if st.button("📥 Gerar Relatório de NCs em PDF", key="btn_gerar_nc_pdf"):
            try:
                from gerar_pdf import gerar_relatorio_nc as _gerar_nc
                ncs_pdf = [{
                    "id": r["ID"], "data_abertura": r["Data Abertura"], "obra": r["Obra"],
                    "gravidade": r["Gravidade"], "descricao": r["Descrição"],
                    "acao_corretiva": r["Ação Corretiva"], "responsavel": r["Responsável"],
                    "prazo": r["Prazo"], "status": r["Status"],
                } for _, r in ncs.iterrows()]
                pdf_bytes = _gerar_nc({"obra": fo_nc, "status": fs_nc}, ncs_pdf)
                st.download_button(
                    label="⬇️ Baixar Relatório de NCs em PDF",
                    data=pdf_bytes,
                    file_name=f"relatorio_ncs_{date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    key="dl_nc_pdf",
                )
            except Exception as _e_nc:
                st.error(f"Erro ao gerar PDF: {_e_nc}")
        if ncs.empty:
            st.info("Nenhuma NC registrada.")
        elif LNC is not None:
            id_nc = LNC["ID"]
            st.markdown("---")
            with st.container(border=True):
                st.markdown(f"#### ✏️ NC — {LNC['Obra']}")
                st.caption(LNC.get("Descrição", ""))
                st_opts_nc = ["Aberta","Em tratamento","Encerrada"]
                ns_nc = st.selectbox("Novo Status", st_opts_nc,
                                      index=st_opts_nc.index(LNC["Status"]) if LNC["Status"] in st_opts_nc else 0,
                                      key="ns_nc")
                if st.button("✅ Atualizar NC", type="primary"):
                    ix_nc = st.session_state.ncs[st.session_state.ncs["ID"]==id_nc].index[0]
                    st.session_state.ncs.loc[ix_nc,"Status"]=ns_nc
                    _notify(f"✅ NC de **{LNC['Obra']}** atualizada para status **{ns_nc}**!"); st.rerun()

    with t3:
        with st.form("form_chk"):
            c1,c2 = st.columns(2)
            obra_chk  = c1.selectbox("Obra",_obras_nomes())
            item_chk  = c2.text_input("Item Inspecionado")
            resp_chk  = c1.text_input("Responsável")
            res_chk   = c2.radio("Resultado",["Aprovado","Reprovado"])
            obs_chk   = c1.text_area("Observação",height=80)
            ok_chk    = st.form_submit_button("✅ Registrar Inspeção",type="primary")
        if ok_chk:
            st.session_state.checklists = pd.concat([st.session_state.checklists,pd.DataFrame([{"ID":_next_id(st.session_state.checklists),"Data":date.today().strftime("%d/%m/%Y"),"Obra":obra_chk,"Item Inspecionado":item_chk,"Responsável":resp_chk,"Resultado":res_chk,"Observação":obs_chk}])],ignore_index=True)
            _res_icon = "🟢" if res_chk == "Aprovado" else "🔴"
            _notify(f"✅ Inspeção de **{item_chk}** registrada! Resultado: {_res_icon} {res_chk}"); st.rerun()

    with t4:
        with st.form("form_nc"):
            c1,c2 = st.columns(2)
            obra_nc  = c1.selectbox("Obra",_obras_nomes())
            grav_nc  = c2.selectbox("Gravidade",["Alta","Moderada","Baixa"])
            desc_nc  = c1.text_area("Descrição",height=80)
            acao_nc  = c2.text_area("Ação Corretiva",height=80)
            resp_nc  = c1.text_input("Responsável")
            prazo_nc = c2.text_input("Prazo (dd/mm/aaaa)")
            ok_nc    = st.form_submit_button("⚠️ Abrir NC",type="primary")
        if ok_nc:
            novo_id_nc = f"NC-{(len(st.session_state.ncs)+1):03d}"
            dados_nc = {"Descrição":desc_nc,"Gravidade":grav_nc,"Status":"Aberta","Prazo":prazo_nc,"Ação Corretiva":acao_nc}
            uuid_nc = sync.nc_save(dados_nc, obra_sb_id=_obra_uuid(obra_nc))
            st.session_state.ncs = pd.concat([st.session_state.ncs,pd.DataFrame([{"ID":novo_id_nc,"SB_ID":uuid_nc or "","Data Abertura":date.today().strftime("%d/%m/%Y"),"Obra":obra_nc,**dados_nc,"Responsável":resp_nc}])],ignore_index=True)
            _notify(f"✅ NC **{novo_id_nc}** aberta em **{obra_nc}** (Gravidade: {grav_nc})!"); st.rerun()


# ── Orçamento (importação) ───────────────────────────────────────────────────

# ── Helpers de importação de orçamento ───────────────────────────────────────

def _norm_col(s):
    """
    Normaliza um nome de coluna para comparação insensível a maiúsculas e acentos.
    Ex.: 'Preço Unitário' → 'preco unitario' | 'V.Unit com Mat.' → 'v.unit com mat.'
    """
    s = str(s).lower().strip()
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')


def _parse_num_br(val):
    """
    Converte célula de planilha para float, respeitando o padrão BR.
    Usada exclusivamente na importação de orçamento.
    - float/int vindos do pandas  → retorna direto (sem manipulação de string)
    - string BR com ponto+vírgula → "1.234,56"  → 1234.56  (remove . e troca ,)
    - string BR só com vírgula   → "1234,56"   → 1234.56  (troca , por .)
    - string US/Python só ponto  → "1234.56"   → 1234.56  (sem alteração)
    Retorna None para valores inválidos/NaN (diferente de _to_num que retorna 0.0).
    """
    import math
    if val is None:
        return None
    # Já numérico (pandas leu a célula como número): retorna direto
    if isinstance(val, (int, float)):
        return None if math.isnan(float(val)) else float(val)
    s = str(val).strip().replace("R$", "").replace("\xa0", "").replace(" ", "")
    if not s or s in ("-", "—", "nan"):
        return None
    if "." in s and "," in s:
        # Padrão BR completo: 1.234,56 → 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Só separador decimal BR: 1234,56 → 1234.56
        s = s.replace(",", ".")
    # Caso só tenha ponto: já é formato Python/US — não mexer
    v = pd.to_numeric(s, errors="coerce")
    return None if pd.isna(v) else float(v)


def _limpar_col_num(col):
    if isinstance(col, pd.DataFrame):
        col = col.iloc[:, 0]
    s = pd.Series(col).astype(str).str.strip()
    s = s.str.replace(r'R\$\s*', '', regex=True)
    s = s.str.replace(r'[\s\xa0]', '', regex=True)

    # Três caminhos — mesma lógica de _to_num mas vetorizada:
    #   1) ponto E vírgula  → BR milhar: "1.234,56" → remover pontos, trocar vírgula
    #   2) só vírgula       → BR decimal: "1234,56"  → trocar vírgula
    #   3) só ponto         → US/Python:  "1234.56"  → não mexer
    mask_br = s.str.contains(r'\d\.', regex=True) & s.str.contains(',', regex=False)
    mask_comma = ~mask_br & s.str.contains(',', regex=False)

    s_out = s.copy()
    s_out[mask_br] = (s[mask_br]
                      .str.replace('.', '', regex=False)
                      .str.replace(',', '.', regex=False))
    s_out[mask_comma] = s[mask_comma].str.replace(',', '.', regex=False)

    return pd.to_numeric(s_out, errors='coerce').fillna(0.0)


def _nivel_eap(codigo):
    """Retorna profundidade hierárquica pelo nº de pontos: '1'→1, '1.1'→2, '1.1.1'→3."""
    s = str(codigo).strip()
    if not s or s == "nan":
        return 1
    return len(s.split("."))


def _processar_orcamento(df, col_cod, col_desc, col_un, col_qtd, col_preco, bdi_pct=25.0):
    """
    State machine linha-a-linha para classificar ETAPA vs ITEM.
    Retorna (resultado, avisos) onde avisos é uma lista de
    {linha, tipo, mensagem} para exibir ao usuário.
    """
    bdi_fator   = 1 + (bdi_pct / 100)
    resultado   = []
    etapa_stack = {}
    avisos      = []
    tem_multiplas_abas = "_aba_origem" in df.columns

    # ── Valida se as colunas selecionadas existem no DataFrame ────────
    cols_obrig = {"Código": col_cod, "Descrição": col_desc,
                  "Unidade": col_un, "Quantidade": col_qtd, "Preço Unit.": col_preco}
    for nome, col in cols_obrig.items():
        if col != "(ignorar)" and col not in df.columns:
            avisos.append({"linha": 0, "tipo": "ERRO",
                           "mensagem": f"Coluna '{col}' selecionada para '{nome}' não existe na planilha."})

    # ── Limpeza vetorizada das colunas numéricas (uma passagem por coluna) ──
    _nan_series = pd.Series([float("nan")] * len(df), dtype=float, index=df.index)
    ser_qtd   = _limpar_col_num(df[col_qtd])   if col_qtd   != "(ignorar)" else _nan_series
    ser_preco = _limpar_col_num(df[col_preco]) if col_preco != "(ignorar)" else _nan_series

    # ── Verifica quantas células tiveram falha de conversão numérica ──
    if col_qtd != "(ignorar)":
        n_coerce_qtd = int(
            pd.to_numeric(pd.Series(df[col_qtd]), errors='coerce').isna().sum()
        )

    _aba_atual = None
    qtd_falha = 0
    preco_falha = 0
    for i, (_, row) in enumerate(df.iterrows()):
        codigo = (str(row[col_cod]).strip()
                  if col_cod != "(ignorar)" and pd.notna(row.get(col_cod, float("nan")))
                  else "")
        desc   = (str(row[col_desc]).strip()
                  if pd.notna(row.get(col_desc, float("nan"))) else "")
        un     = (str(row[col_un]).strip()
                  if col_un != "(ignorar)" and pd.notna(row.get(col_un, float("nan")))
                  else "")

        # Lê valores pré-limpos da Series vetorizada
        qtd_v   = ser_qtd.iloc[i]
        preco_v = ser_preco.iloc[i]
        qtd   = None if pd.isna(qtd_v)   else float(qtd_v)
        preco = None if pd.isna(preco_v) else float(preco_v)

        if not desc:
            continue

        # ── Troca de aba (multi-sheet "Todas as abas") ────────────────
        if tem_multiplas_abas:
            aba_row = str(row.get("_aba_origem", ""))
            if aba_row and aba_row != _aba_atual:
                _aba_atual = aba_row
                etapa_stack = {1: _aba_atual}
                resultado.append({
                    "ordem": _aba_atual, "tipo": "ETAPA", "nivel": 1,
                    "descricao": _aba_atual, "unidade": "", "quantidade": None,
                    "preco_custo": None, "preco_venda": None,
                    "total_custo": None, "total_venda": None,
                    "etapa_pai": "",
                })

        nivel   = _nivel_eap(codigo) if codigo else 1

        # ── Detecta falha de parsing numérico ───────────────────────
        if col_qtd != "(ignorar)" and pd.notna(row.get(col_qtd)) and str(row[col_qtd]).strip():
            raw_q = str(row[col_qtd]).strip()
            if qtd_v == 0.0 and raw_q not in ("0","0,0","0.0",""):
                qtd_falha += 1
        if col_preco != "(ignorar)" and pd.notna(row.get(col_preco)) and str(row[col_preco]).strip():
            raw_p = str(row[col_preco]).strip()
            if preco_v == 0.0 and raw_p not in ("0","0,0","0.0",""):
                preco_falha += 1

        is_item = qtd is not None and preco is not None and qtd > 0 and preco > 0

        if not is_item:
            # ── ETAPA / SUBETAPA ──────────────────────────────────────
            etapa_stack[nivel] = desc
            for k in [k for k in etapa_stack if k > nivel]:
                del etapa_stack[k]
            resultado.append({
                "ordem": codigo, "tipo": "ETAPA", "nivel": nivel,
                "descricao": desc, "unidade": "", "quantidade": None,
                "preco_custo": None, "preco_venda": None,
                "total_custo": None, "total_venda": None,
                "etapa_pai": etapa_stack.get(nivel - 1, ""),
            })
        else:
            # ── ITEM DE SERVIÇO ───────────────────────────────────────
            total_custo = qtd * preco
            total_venda = total_custo * bdi_fator
            pai = etapa_stack.get(max(etapa_stack.keys(), default=0), "") if etapa_stack else ""
            resultado.append({
                "ordem": codigo, "tipo": "ITEM", "nivel": nivel,
                "descricao": desc, "unidade": un, "quantidade": qtd,
                "preco_custo": preco,
                "preco_venda": round(preco * bdi_fator, 4),
                "total_custo": round(total_custo, 2),
                "total_venda": round(total_venda, 2),
                "etapa_pai": pai,
            })

    # ── Avisos consolidados ──────────────────────────────────────────
    if qtd_falha:
        avisos.append({"linha": 0, "tipo": "ADVERTÊNCIA",
                       "mensagem": f"{qtd_falha} linha(s) com quantidade não numérica (convertida para 0)."})
    if preco_falha:
        avisos.append({"linha": 0, "tipo": "ADVERTÊNCIA",
                       "mensagem": f"{preco_falha} linha(s) com preço unitário não numérico (convertido para 0)."})
    return resultado, avisos


def _normalizar_orc_data(data):
    """Garante que todo item de orçamento tenha campo 'tipo'."""
    if not data:
        return data or []
    for r in data:
        if "tipo" not in r:
            r["tipo"] = "ITEM"
    return data

def _exibir_orcamento_processado(resultado, obra_orc, bdi_pct, nome_orc):
    import plotly.express as px
    resultado = _normalizar_orc_data(resultado)
    if not resultado:
        st.info("Orçamento vazio — importe uma planilha primeiro.")
        return
    df_res = pd.DataFrame(resultado)
    itens  = df_res[df_res["tipo"] == "ITEM"].copy()

    total_custo = itens["total_custo"].sum() if len(itens) else 0
    bdi_val     = total_custo * (bdi_pct / 100)
    total_venda = total_custo + bdi_val

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Itens de Serviço",    len(itens))
    c2.metric("Total Custo Direto",  _fmt(total_custo))
    c3.metric(f"BDI ({bdi_pct:.1f}%)", _fmt(bdi_val))
    c4.metric("Total Venda",         _fmt(total_venda))
    st.markdown("---")

    if "orcamento_composicoes" not in st.session_state:
        st.session_state.orcamento_composicoes = {}

    tab_arv, tab_it, tab_res, tab_comp, tab_exp = st.tabs(
        ["🌳 Árvore EAP", "📋 Itens de Serviço", "📊 Resumo por Etapa", "🧩 Composições", "⬇️ Exportar"]
    )

    with tab_arv:
        linhas = []
        for r in resultado:
            _nv = r.get("nivel", 1)
            pad = "　" * (_nv - 1)
            if r["tipo"] == "ETAPA":
                linhas.append({"Ord": r["ordem"], "Descrição": pad+"📁 "+r["descricao"],
                                "Un":"","Qtd":"","P.Custo":"","P.Venda":"","Total Venda":""})
            else:
                linhas.append({
                    "Ord": r["ordem"],
                    "Descrição": pad+"  └ "+r["descricao"],
                    "Un": r["unidade"],
                    "Qtd": f"{r['quantidade']:,.2f}".replace(",","X").replace(".",",").replace("X","."),
                    "P.Custo": _fmt(r["preco_custo"]),
                    "P.Venda": _fmt(r["preco_venda"]),
                    "Total Venda": _fmt(r["total_venda"]),
                })
        st.dataframe(pd.DataFrame(linhas), width='stretch', hide_index=True)

    with tab_it:
        if len(itens):
            ei = itens[["ordem","descricao","etapa_pai","unidade","quantidade",
                         "preco_custo","preco_venda","total_custo","total_venda"]].copy()
            ei.columns = ["Cód","Descrição","Etapa","Un","Qtd",
                          "P.Custo","P.Venda","Total Custo","Total Venda"]
            for c in ["P.Custo","P.Venda","Total Custo","Total Venda"]:
                ei[c] = ei[c].apply(lambda v: _fmt(v) if v is not None else "")
            ei["Qtd"] = ei["Qtd"].apply(
                lambda v: f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".") if v else ""
            )
            st.dataframe(ei, width='stretch', hide_index=True)
        else:
            st.info("Nenhum item de serviço detectado com os mapeamentos informados.")

    with tab_res:
        if len(itens) and total_venda > 0:
            resumo = (itens.groupby("etapa_pai")[["total_custo","total_venda"]]
                          .sum().reset_index()
                          .sort_values("total_venda", ascending=False))
            resumo["% Total"] = (resumo["total_venda"] / total_venda * 100).round(1)
            fig = px.bar(resumo, x="etapa_pai", y="total_venda",
                         color_discrete_sequence=["#2B59C3"], text="total_venda",
                         labels={"etapa_pai":"","total_venda":"R$"})
            fig.update_traces(texttemplate="R$%{text:,.0f}", textposition="outside")
            fig.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white",
                              yaxis_tickformat=",.0f", margin=dict(t=20,b=100))
            st.plotly_chart(fig, width='stretch')
            resumo_ex = resumo.copy()
            resumo_ex["total_custo"]  = resumo_ex["total_custo"].apply(_fmt)
            resumo_ex["total_venda"]  = resumo_ex["total_venda"].apply(_fmt)
            resumo_ex["% Total"]      = resumo_ex["% Total"].astype(str) + "%"
            resumo_ex.columns = ["Etapa","Total Custo","Total Venda","% Total"]
            st.dataframe(resumo_ex, width='stretch', hide_index=True)

    with tab_comp:
        st.subheader("Gerenciar Composições")
        st.caption("Marque itens como 'Composição' para permitir o desdobramento em insumos.")
        if len(itens):
            ordens = sorted(itens["ordem"].unique())
            sel_comp = st.multiselect(
                "Selecione os itens que são composições",
                options=[(r["ordem"], r["descricao"]) for _, r in itens.iterrows()],
                format_func=lambda x: f"{x[0]} — {x[1][:60]}",
                default=[k for k in st.session_state.orcamento_composicoes if k in list(itens["ordem"])],
                key="comp_sel"
            )
            if st.button("💾 Salvar marcações de composição", key="btn_save_comp_mark"):
                st.session_state.orcamento_composicoes = {
                    r["ordem"]: {"descricao": r["descricao"], "insumos": st.session_state.orcamento_composicoes.get(r["ordem"], {}).get("insumos", [])}
                    for r in itens.to_dict("records") if r["ordem"] in [s[0] for s in sel_comp]
                }
                _notify(f"✅ {len(st.session_state.orcamento_composicoes)} composição(ões) marcada(s)!")
                st.rerun()

            if st.session_state.orcamento_composicoes:
                st.markdown("---")
                st.subheader("Desdobramento de Composições")
                for cod, comp_data in st.session_state.orcamento_composicoes.items():
                    with st.expander(f"📦 {cod} — {comp_data['descricao'][:60]}", expanded=False):
                        insumos = comp_data.get("insumos", [])
                        if insumos:
                            st.dataframe(pd.DataFrame(insumos), width='stretch', hide_index=True)
                        else:
                            st.info("Nenhum insumo cadastrado para esta composição.")
                        st.markdown("**Adicionar insumo manualmente**")
                        ic1, ic2, ic3, ic4 = st.columns(4)
                        novo_ins = {
                            "codigo": ic1.text_input("Código", key=f"comp_i_cod_{cod}"),
                            "descricao": ic2.text_input("Descrição", key=f"comp_i_desc_{cod}"),
                            "unidade": ic3.text_input("Un", value="un", key=f"comp_i_un_{cod}"),
                            "quantidade": ic4.number_input("Quantidade (por un. da comp.)", min_value=0.0, step=0.001, format="%.4f", key=f"comp_i_qtd_{cod}"),
                        }
                        if st.button("➕ Adicionar insumo", key=f"comp_add_{cod}"):
                            if novo_ins["descricao"].strip():
                                st.session_state.orcamento_composicoes[cod]["insumos"].append(novo_ins)
                                st.rerun()
                        st.markdown("---")
                        ins_up = st.file_uploader(
                            f"📤 Upload de insumos para {cod} (.xlsx, .csv)",
                            type=["xlsx", "csv"], key=f"comp_up_{cod}"
                        )
                        if ins_up is not None:
                            try:
                                if ins_up.name.endswith(".csv"):
                                    df_up = pd.read_csv(ins_up, dtype=str)
                                else:
                                    df_up = pd.read_excel(ins_up, dtype=str)
                                for _, r in df_up.iterrows():
                                    st.session_state.orcamento_composicoes[cod]["insumos"].append({
                                        "codigo": str(r.iloc[0]) if pd.notna(r.iloc[0]) else "",
                                        "descricao": str(r.iloc[1]) if len(r) > 1 and pd.notna(r.iloc[1]) else "",
                                        "unidade": str(r.iloc[2]) if len(r) > 2 and pd.notna(r.iloc[2]) else "un",
                                        "quantidade": float(str(r.iloc[3]).replace(",", ".")) if len(r) > 3 and pd.notna(r.iloc[3]) else 0.0,
                                    })
                                _notify(f"✅ {len(df_up)} insumos importados para {cod}!")
                                st.rerun()
                            except Exception as _e_up:
                                st.error(f"Erro ao ler arquivo: {_e_up}")
        else:
            st.info("Nenhum item processado para gerenciar composições.")

    with tab_exp:
        buf = io.BytesIO()
        pd.DataFrame([{
            "Ordem":           r["ordem"],       "Tipo":         r["tipo"],
            "Nível EAP":       r.get("nivel", 1),  "Etapa Pai":    r.get("etapa_pai", ""),
            "Descrição":       r["descricao"],    "Unidade":      r["unidade"],
            "Quantidade":      r["quantidade"],   "P.Unit.Custo": r["preco_custo"],
            "P.Unit.Venda":    r["preco_venda"],  "Total Custo":  r["total_custo"],
            "Total Venda":     r["total_venda"],
        } for r in resultado]).to_excel(buf, index=False)
        st.download_button(
            "⬇️ Baixar Excel estruturado (orcamento_itens)",
            data=buf.getvalue(),
            file_name=f"orcamento_{(obra_orc or 'sem_obra').replace(' ','_')}_{(nome_orc or 'orc').replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption("Estrutura compatível com a tabela `orcamento_itens` do schema Supabase/Postgres.")

        st.markdown("---")
        if st.button("📥 Gerar PDF do Orçamento", key="btn_gerar_orc_pdf", type="primary"):
            try:
                from gerar_pdf import gerar_orcamento as _gerar_orc
                ob_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_orc]
                cliente_orc = ob_row["Cliente"].iloc[0] if not ob_row.empty else "—"
                dados_orc_pdf = {
                    "obra": obra_orc, "cliente": cliente_orc, "nome": nome_orc,
                    "base_ref": st.session_state.get("orc_base", "—"),
                    "versao":   st.session_state.get("orc_versao", 1),
                    "status":   st.session_state.get("orc_status", "Rascunho"),
                    "bdi_pct":  bdi_pct if bdi_pct else (total_venda - total_custo) / total_custo * 100 if total_custo else 0,
                    "total_custo": total_custo, "total_venda": total_venda,
                }
                pdf_bytes = _gerar_orc(dados_orc_pdf, resultado)
                st.download_button(
                    label="⬇️ Baixar Orçamento em PDF",
                    data=pdf_bytes,
                    file_name=f"orcamento_{(obra_orc or 'sem_obra').replace(' ','_')}_{(nome_orc or 'orc').replace(' ','_')}.pdf",
                    mime="application/pdf",
                    key="dl_orc_pdf",
                )
            except Exception as _e_orc:
                st.error(f"Erro ao gerar PDF: {_e_orc}")


# ── Página Orçamento ──────────────────────────────────────────────────────────

def pagina_orcamento():
    st.title("📊 Orçamento")
    _init()
    _show_toast()

    tab_imp, tab_oxr = st.tabs(["📂 Importar / Processar", "📊 Orçado x Realizado"])

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1 — Importar / Processar
    # ═══════════════════════════════════════════════════════════════════════
    with tab_imp:

        # ── Parâmetros (tabela: orcamentos) ────────────────────────────────
        with st.container(border=True):
            st.markdown("**⚙️ Parâmetros do Orçamento**")
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            obra_orc    = r1c1.selectbox("Obra", _obras_nomes(), key="orc_obra")
            nome_orc    = r1c2.text_input("Nome", value="Orçamento Rev.1", key="orc_nome")
            base_ref    = r1c3.text_input("Base de Referência", value="SINAPI Mai/2026", key="orc_base")
            bdi_incluso = r1c4.checkbox("BDI já incluso na planilha", key="orc_bdi_incluso", value=True,
                                        help="Marque se os preços da planilha já incluem BDI. Desmarque para aplicar BDI adicional.")

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            r2c1.number_input("Encargos Sociais (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.5, key="orc_enc")
            r2c2.number_input("Versão", min_value=1, value=1, key="orc_versao")
            r2c3.selectbox("Status", ["Rascunho","Aprovado","Substituído"], key="orc_status")
            bdi_orc = r2c4.number_input("BDI a aplicar (%)", min_value=0.0, max_value=100.0,
                                        value=25.0, step=0.5, key="orc_bdi",
                                        disabled=bdi_incluso,
                                        help="Só ativo quando a planilha NÃO inclui BDI nos preços.")

    with st.container(border=True):
        st.markdown("**📂 Importar Planilha de Itens**")
        st.info(
            "Suba sua planilha (.xlsx ou .csv). Em seguida, mapeie as colunas e clique em **Processar**. "
            "O sistema identifica etapas/subetapas automaticamente e aplica o BDI configurado.",
            icon="📂",
        )
        arquivo = st.file_uploader("Planilha de itens (.xlsx, .xls ou .csv)", type=["xlsx","xls","csv"],
                                   label_visibility="collapsed")

    # ── Detecção de abas (multi-sheet) ──────────────────────────────────────
    if "orcamento_sheets" not in st.session_state:
        st.session_state.orcamento_sheets = []
    if "orcamento_bytes" not in st.session_state:
        st.session_state.orcamento_bytes = None

    import io as _io
    if arquivo is not None and arquivo.name != st.session_state.get("orcamento_nome"):
        raw = arquivo.read()
        st.session_state.orcamento_bytes = raw
        st.session_state.orcamento_nome  = arquivo.name
        st.session_state.orcamento_mapped = None
        st.session_state.orcamento_df_raw = None
        if arquivo.name.lower().endswith(".csv"):
            st.session_state.orcamento_sheets = []
        else:
            try:
                xls = pd.ExcelFile(_io.BytesIO(raw))
                st.session_state.orcamento_sheets = xls.sheet_names
            except Exception:
                st.session_state.orcamento_sheets = []

    sheets = st.session_state.orcamento_sheets
    if sheets:
        aba_opts = ["Todas as abas"] + sheets
        abas_visiveis = len(sheets) > 1
    else:
        aba_opts = ["Única aba"]
        abas_visiveis = False

    aba_sel = st.selectbox("Selecionar aba da planilha", aba_opts,
                           key="orc_aba", disabled=not abas_visiveis)

    # ── Carregamento bruto ──────────────────────────────────────────────────
    # Só relê (e reseta orcamento_mapped) quando o arquivo ou a aba mudar.
    _file_or_aba_mudou = (arquivo is not None and
                          arquivo.name == st.session_state.get("orcamento_nome") and
                          (st.session_state.orcamento_df_raw is None or
                           st.session_state.get("_orc_aba_anterior") != aba_sel))
    if _file_or_aba_mudou:
        try:
            raw = st.session_state.orcamento_bytes
            if raw is None:
                raise ValueError("Bytes do arquivo não disponíveis.")
            if arquivo.name.lower().endswith(".csv"):
                df_raw = pd.read_csv(_io.BytesIO(raw), sep=None, engine="python",
                                     encoding="utf-8-sig", header=None, dtype=str)
            elif aba_sel == "Todas as abas":
                dict_raw = pd.read_excel(_io.BytesIO(raw), sheet_name=None, header=None, dtype=str)
                # Empilha todas as abas, anotando a origem
                partes = []
                for nome_aba, df_aba in dict_raw.items():
                    df_aba = df_aba.copy()
                    df_aba["_aba_origem"] = nome_aba
                    partes.append(df_aba)
                df_raw = pd.concat(partes, ignore_index=True)
            else:
                df_raw = pd.read_excel(_io.BytesIO(raw), sheet_name=aba_sel,
                                       header=None, dtype=str)
            st.session_state.orcamento_df_raw  = df_raw
            st.session_state.orcamento_mapped  = None
            st.session_state._orc_aba_anterior = aba_sel
            st.success(f"'{arquivo.name}' [{aba_sel}] — {len(df_raw)} linhas × {len(df_raw.columns)} colunas brutas.")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if "orcamento_df_raw"  not in st.session_state: st.session_state.orcamento_df_raw  = None
    if "orcamento_mapped"  not in st.session_state: st.session_state.orcamento_mapped  = None

    if st.session_state.orcamento_df_raw is not None:
        df_raw = st.session_state.orcamento_df_raw

        # ── Passo 1: linha do cabeçalho ────────────────────────────────
        st.subheader("1️⃣ Linha do Cabeçalho")
        hdr_kw = ["cod","item","desc","un","qtd","quant","prec","unit","total","valor"]
        detected = 0
        for i, row in df_raw.iterrows():
            txt = " ".join(str(v).lower() for v in row.values if pd.notna(v))
            if sum(1 for kw in hdr_kw if kw in txt) >= 2:
                detected = i; break

        hdr = st.number_input("Linha do cabeçalho (0 = primeira linha)",
                               min_value=0, max_value=min(30, len(df_raw)-1),
                               value=int(detected), step=1, key="orc_hdr")
        st.caption(f"Prévia: `{list(df_raw.iloc[int(hdr)].values)}`")

        df_h = df_raw.iloc[int(hdr)+1:].copy()
        raw_cols = []
        for i, v in enumerate(df_raw.iloc[int(hdr)].values):
            name = str(v).strip() if pd.notna(v) else f"Col_{i}"
            if name in raw_cols:
                name = f"{name}_{i}"
            raw_cols.append(name)
        df_h.columns = raw_cols
        df_h = df_h.reset_index(drop=True)
        # Remove _aba_origem da interface (é metadado interno)
        _cols_visiveis = [c for c in df_h.columns if c != "_aba_origem"]
        avail = ["(ignorar)"] + _cols_visiveis

        # ── Passo 2: mapeamento de colunas ─────────────────────────────
        st.subheader("2️⃣ Mapeamento de Colunas")

        # Pré-normaliza os nomes das colunas uma única vez
        _cols_norm = {col: _norm_col(col) for col in df_h.columns}

        def _guess(kws):
            """
            Retorna a coluna com melhor correspondência.
            1. Match exato com keyword mais longa → maior pontuação
            2. Match substring com keyword >= 3 chars → pontuação menor
            Evita falsos positivos de "item" dentro de "composicao do item".
            """
            best_col = "(ignorar)"
            best_score = -1
            kws_norm = {_norm_col(k): k for k in kws}
            for col, cn in _cols_norm.items():
                for nk in kws_norm:
                    if nk == cn:
                        score = 100 + len(nk)
                    elif len(nk) >= 3 and nk in cn:
                        score = len(nk)
                    else:
                        continue
                    if score > best_score:
                        best_score = score
                        best_col = col
            return best_col

        def _idx(col):
            return avail.index(col) if col in avail else 0

        # ── Listas de keywords por campo (do mais específico ao mais genérico) ──
        KW_COD  = ["codigo", "cod.", "cod", "item", "num.", "nro.", "num", "nro", "nr."]
        KW_DESC = ["composicao do item", "composicao", "descricao", "descricoes",
                   "descr.", "descr", "desc.", "desc",
                   "servicos", "servico", "especificacao", "especif", "nome do servico", "nome"]
        KW_UN   = ["unidade", "unid.", "unid", "und.", "und", "un."]
        KW_QTD  = ["quantitativo", "quantidade", "quant.", "quant", "qtd.", "qtd", "qde"]
        KW_PU   = [
            # variantes reais de planilhas de orçamento (todas já normalizadas internamente)
            "v.unit com mat.", "v.unit com mat", "v. unit com mat",
            "custo unitario", "preco unitario", "valor unitario",
            "pr. unitario", "pr.unitario", "custo unit.", "custo unit",
            "preco unit.", "preco unit", "valor unit.", "valor unit",
            "p.unit.", "p.unit", "v.unit.", "v.unit",
            "pr. unit", "p. unit", "unit.", "pu",
        ]

        cm1,cm2,cm3,cm4,cm5 = st.columns(5)
        c_cod  = cm1.selectbox("Código / Item",  avail, index=_idx(_guess(KW_COD)),  key="mc_cod")
        c_desc = cm2.selectbox("Descrição *",    avail, index=_idx(_guess(KW_DESC)), key="mc_desc")
        c_un   = cm3.selectbox("Unidade",        avail, index=_idx(_guess(KW_UN)),   key="mc_un")
        c_qtd  = cm4.selectbox("Quantidade",     avail, index=_idx(_guess(KW_QTD)),  key="mc_qtd")
        c_pu   = cm5.selectbox("Preço Unitário", avail, index=_idx(_guess(KW_PU)),   key="mc_pu")

        # Mostra diagnóstico do mapeamento automático
        with st.expander("🔍 Diagnóstico do mapeamento automático", expanded=False):
            st.caption("Revise se as colunas foram associadas corretamente:")
            diag_data = {
                "Campo": ["Código","Descrição","Unidade","Quantidade","Preço Unitário"],
                "Coluna detectada": [c_cod, c_desc, c_un, c_qtd, c_pu],
            }
            st.dataframe(pd.DataFrame(diag_data), hide_index=True, width='stretch')

        # ── Templates de mapeamento ───────────────────────────────────
        with st.expander("📁 Templates de mapeamento", expanded=False):
            st.caption("Salve o mapeamento atual para reutilizar em futuras importações da mesma planilha.")
            tmpl_col1, tmpl_col2 = st.columns([1, 3])
            df_tmpl = db.colmap_templates_listar(st.session_state.empresa_id)
            tmpl_opts = {f"{r['nome']} ({r['created_at'][:10]})": r for _, r in df_tmpl.iterrows()} if not df_tmpl.empty else {}
            tmpl_sel = tmpl_col1.selectbox("Carregar template", ["(nenhum)"] + list(tmpl_opts.keys()), key="tmpl_sel")
            if tmpl_sel != "(nenhum)" and tmpl_sel in tmpl_opts:
                if tmpl_col1.button("📂 Aplicar", key="btn_tmpl_load"):
                    tmpl_data = tmpl_opts[tmpl_sel]["mapping"]
                    for key, widget_key in [("codigo","mc_cod"), ("descricao","mc_desc"),
                                            ("unidade","mc_un"), ("quantidade","mc_qtd"),
                                            ("preco_unitario","mc_pu")]:
                        col_name = tmpl_data.get(key, "")
                        if col_name in avail:
                            st.session_state[widget_key] = col_name
                    _notify(f"✅ Template '{tmpl_sel}' aplicado!")
                    st.rerun()
            tmpl_nome = tmpl_col2.text_input("Nome do novo template (ex: 'Planilha SINAPI padrão')", key="tmpl_nome")
            if tmpl_col2.button("💾 Salvar template", key="btn_tmpl_save"):
                if not tmpl_nome.strip():
                    st.warning("Digite um nome para o template.")
                else:
                    mapping = {
                        "codigo": c_cod if c_cod != "(ignorar)" else "",
                        "descricao": c_desc if c_desc != "(ignorar)" else "",
                        "unidade": c_un if c_un != "(ignorar)" else "",
                        "quantidade": c_qtd if c_qtd != "(ignorar)" else "",
                        "preco_unitario": c_pu if c_pu != "(ignorar)" else "",
                    }
                    db.colmap_template_criar(st.session_state.empresa_id, tmpl_nome.strip(), mapping)
                    _notify(f"✅ Template '{tmpl_nome.strip()}' salvo!")
                    st.rerun()

        st.markdown("---")

        if st.button("⚙️ Processar Orçamento", type="primary", key="btn_proc"):
            if c_desc == "(ignorar)":
                st.error("A coluna Descrição é obrigatória.")
            elif df_h.empty:
                st.error("A planilha não contém dados após o cabeçalho. Verifique a linha do cabeçalho.")
            else:
                bdi_efetivo = 0.0 if bdi_incluso else bdi_orc
                try:
                    res, avisos = _processar_orcamento(df_h, c_cod, c_desc, c_un, c_qtd, c_pu, bdi_pct=bdi_efetivo)
                except Exception as _e_proc:
                    st.error(f"Erro ao processar orçamento: {_e_proc}")
                    import traceback; traceback.print_exc()
                    res = []; avisos = []
                # Exibe avisos do processamento
                erros = [a for a in avisos if a["tipo"] == "ERRO"]
                warns = [a for a in avisos if a["tipo"] == "ADVERTÊNCIA"]
                if erros:
                    for a in erros:
                        st.error(f"{a['mensagem']}")
                if warns:
                    with st.expander("⚠️ Avisos do processamento", expanded=bool(warns)):
                        for a in warns:
                            st.warning(f"Linha {a['linha']}: {a['mensagem']}" if a['linha'] else a['mensagem'])
                st.session_state.orcamento_mapped = res
                # Vincula o orçamento à obra selecionada (usado na EAP)
                if "orcamento_por_obra" not in st.session_state:
                    st.session_state.orcamento_por_obra = {}
                st.session_state.orcamento_por_obra[obra_orc] = res
                n_etapas = sum(1 for r in res if r["tipo"]=="ETAPA")
                n_itens  = sum(1 for r in res if r["tipo"]=="ITEM")
                total_orc = sum(r["total_venda"] for r in res if r["tipo"] == "ITEM" and r.get("total_venda"))
                ob_row_orc = st.session_state.obras[st.session_state.obras["Nome"] == obra_orc]
                val_atual_orc = _parse_num_br(ob_row_orc["Valor Contrato (R$)"].iloc[0]) if not ob_row_orc.empty else 0.0
                if total_orc > 0 and abs(total_orc - val_atual_orc) > 0.01:
                    st.session_state.orc_valor_proposta = {
                        "total": total_orc, "obra": obra_orc, "atual": val_atual_orc
                    }
                _notify(f"✅ Processado: {n_etapas} etapas + {n_itens} itens. EAP vinculada à obra **{obra_orc}**.")
                st.rerun()

        if st.session_state.orcamento_mapped is not None:
            # ── Pergunta: usar valor do orçamento como Valor Contrato? ──────
            prop = st.session_state.get("orc_valor_proposta")
            if prop and prop.get("obra") == obra_orc:
                total_prop = prop["total"]
                atual_prop = prop["atual"]
                st.warning(
                    f"**Valor total do orçamento importado (com BDI):** {_fmt(total_prop)}\n\n"
                    f"**Valor Contrato atual da obra:** {_fmt(atual_prop)}\n\n"
                    f"Deseja usar o valor do orçamento como **Valor Contrato** da obra **{obra_orc}**?",
                    icon="💰",
                )
                _cs, _cn, _ = st.columns([1, 1, 4])
                if _cs.button("✅ Sim, atualizar", key="btn_orc_atualizar", type="primary"):
                    mask_u = st.session_state.obras["Nome"] == obra_orc
                    if mask_u.any():
                        # loc com máscara booleana — mais robusto que .at com índice
                        st.session_state.obras.loc[mask_u, "Valor Contrato (R$)"] = float(total_prop)
                        try:
                            import sync as _sync_orc
                            idx_u0 = st.session_state.obras.index[mask_u][0]
                            sb_id_u = str(st.session_state.obras.at[idx_u0, "SB_ID"])
                            sb_id_u = sb_id_u if sb_id_u not in ("", "nan", "None") else None
                            novo_uuid = _sync_orc.obra_save(
                                dict(st.session_state.obras.loc[idx_u0]),
                                sb_id=sb_id_u
                            )
                            if novo_uuid and not sb_id_u:
                                st.session_state.obras.at[idx_u0, "SB_ID"] = novo_uuid
                        except Exception as _e_upd:
                            st.warning(f"⚠️ Valor atualizado localmente, mas erro ao salvar no banco: {_e_upd}")
                    else:
                        st.error(f"❌ Obra '{obra_orc}' não encontrada na listagem.")
                    del st.session_state["orc_valor_proposta"]
                    _notify(f"✅ Valor Contrato da obra **{obra_orc}** atualizado para {_fmt(total_prop)}!")
                    st.rerun()
                if _cn.button("❌ Não, manter atual", key="btn_orc_manter"):
                    del st.session_state["orc_valor_proposta"]
                    st.rerun()
            _exibir_orcamento_processado(
                st.session_state.orcamento_mapped, obra_orc, bdi_orc, nome_orc
            )

            # ── Salvar no Supabase ────────────────────────────────────────────
            if _obra_valida(obra_orc):
                ob_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_orc]
                sb_id_o = str(ob_row["SB_ID"].iloc[0]) if not ob_row.empty and pd.notna(ob_row["SB_ID"].iloc[0]) else ""
                if sb_id_o:
                    st.markdown("---")
                    if st.button("💾 Salvar Orçamento", type="primary", key="btn_salvar_orc"):
                        itens_raw = st.session_state.orcamento_mapped
                        # Inclui insumos de composições
                        composicoes = st.session_state.get("orcamento_composicoes", {})
                        itens = list(itens_raw)
                        ordem_idx = 1
                        for r in itens_raw:
                            r["composicao_id"] = None
                        for cod, comp_data in composicoes.items():
                            for ins in comp_data.get("insumos", []):
                                itens.append({
                                    "tipo": "ITEM", "ordem": f"CMP_{ordem_idx:04d}",
                                    "descricao": ins.get("descricao", ""),
                                    "unidade": ins.get("unidade", "un"),
                                    "quantidade": float(ins.get("quantidade", 0)),
                                    "preco_custo": 0.0, "preco_venda": 0.0,
                                    "total_custo": 0.0, "total_venda": 0.0,
                                    "etapa_pai": comp_data.get("descricao", ""),
                                    "composicao_id": cod,
                                })
                                ordem_idx += 1
                        total_c = sum(i.get("total_custo", 0) or 0 for i in itens if i["tipo"] == "ITEM")
                        total_v = sum(i.get("total_venda", 0) or 0 for i in itens if i["tipo"] == "ITEM")
                        bdi_ef  = 0.0 if st.session_state.get("orc_bdi_incluso", True) else st.session_state.get("orc_bdi", 25.0)
                        orc_id  = sync.orcamento_save(
                            obra_sb_id=sb_id_o,
                            nome=nome_orc,
                            versao=int(st.session_state.get("orc_versao", 1)),
                            base_ref=base_ref,
                            bdi_pct=bdi_ef,
                            encargos=float(st.session_state.get("orc_enc", 80.0)),
                            total_custo=total_c,
                            total_venda=total_v,
                            status=st.session_state.get("orc_status", "Rascunho"),
                            itens=itens,
                        )
                        if orc_id:
                            sync.orcamento_load.clear()
                            _notify(f"✅ Orçamento **{nome_orc}** salvo no banco!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao salvar orçamento no Supabase.")

        if st.button("🗑️ Limpar importação", key="btn_limpar"):
            st.session_state.orcamento_df_raw = None
            st.session_state.orcamento_mapped = None
            st.session_state.orcamento_nome   = None
            st.session_state.orcamento_composicoes = {}
            st.rerun()

        # ── Orçamentos já salvos ──────────────────────────────────────────────
        if _obra_valida(obra_orc):
            st.markdown("---")
            st.subheader("📂 Orçamentos Salvos")
            try:
                orcs = sync.orcamento_load()
                ob_row_o = st.session_state.obras[st.session_state.obras["Nome"] == obra_orc]
                obra_uuid = str(ob_row_o["SB_ID"].iloc[0]) if not ob_row_o.empty and pd.notna(ob_row_o["SB_ID"].iloc[0]) else None
                orcs_filtrados = [o for o in orcs if o.get("obra_id") == obra_uuid]
                if orcs_filtrados:
                    for o in orcs_filtrados:
                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                            c1.markdown(f"**{o['nome']}**")
                            c2.caption(f"Versão {o['versao']}")
                            c3.caption(f"Status: {o['status']}")
                            c4.caption(f"Total: {_fmt(o['total_venda'])}")
                            with st.expander(f"Ver itens ({len(o.get('itens', []))} itens)"):
                                df_it = pd.DataFrame(o['itens'])[["ordem","descricao","unidade","quantidade","preco_custo"]]
                                df_it.columns = ["Cód","Descrição","Un","Qtd","P.Custo"]
                                st.dataframe(df_it, hide_index=True, width='stretch')
                else:
                    st.info("Nenhum orçamento salvo para esta obra.")
            except Exception as e:
                st.warning(f"Não foi possível carregar orçamentos salvos: {e}")

        else:
            st.markdown("---")
            st.subheader("Exemplos de formato aceito")
            st.dataframe(pd.DataFrame({
                "Código":    ["1","1.1","1.1.1","1.1.2","2","2.1"],
                "Descrição": ["SERVIÇOS PRELIMINARES","Limpeza e Terraplanagem",
                              "Limpeza manual do terreno","Locação da obra",
                              "FUNDAÇÕES","Escavação de valas"],
                "Un":        ["","","m²","m²","","m³"],
                "Qtd":       ["","",500,500,"",120],
                "Preço Unit.":["","",8.50,6.00,"",38.00],
            }), width='stretch', hide_index=True)
            st.caption(
                "Linhas sem Quantidade/Preço são calculados como Etapas da EAP. "
                "Códigos com ponto (1.1.1) definem a profundidade hierárquica automaticamente."
            )

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2 — Orçado x Realizado
    # ═══════════════════════════════════════════════════════════════════════
    with tab_oxr:
        oxr_sel = st.selectbox("Selecione a obra", _obras_nomes(), key="orc_oxr_obra")
        if not _obra_valida(oxr_sel):
            st.info("Selecione uma obra.")
        else:
            oxr_uuid = _obra_uuid(oxr_sel)
            if not oxr_uuid:
                st.warning("Obra não encontrada no Supabase.")
            else:
                _exibir_oxr(oxr_uuid, oxr_sel)


# ── DIÁRIO DE OBRA (RDO) ──────────────────────────────────────────────────────

def pagina_rdo():
    st.title("📋 Diário de Obra (RDO)")
    _init()
    _show_toast()

    obras_lista = _obras_nomes()
    if not obras_lista or obras_lista == ["(nenhuma obra — cadastre em Obras)"]:
        st.warning("Nenhuma obra cadastrada.")
        return

    tabs = st.tabs(["📝 Novo Registro", "📄 Histórico"])

    # ── ABA 1: Novo Registro ─────────────────────────────────────────────────
    with tabs[0]:
        CLIMAS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuvoso", "Tempestade"]
        STATUS = ["Normal", "Intercorrência", "Paralisação parcial", "Paralisação total"]

        c1, c2 = st.columns(2)
        obra_rdo  = c1.selectbox("Obra *", obras_lista, key="rdo_obra")
        data_rdo  = c2.date_input("Data *", value=date.today(), key="rdo_data")

        c3, c4 = st.columns(2)
        resp_rdo   = c3.text_input("Responsável / Engenheiro", key="rdo_resp")
        status_rdo = c4.selectbox("Status do Dia", STATUS, key="rdo_status")

        c5, c6, c7 = st.columns(3)
        clima_m   = c5.selectbox("Clima — Manhã",  CLIMAS, key="rdo_cm")
        clima_t   = c6.selectbox("Clima — Tarde",  CLIMAS, key="rdo_ct")
        efetivo   = c7.number_input("Efetivo Total (pessoas)", min_value=0, step=1, key="rdo_ef")

        atividades   = st.text_area("Atividades Realizadas *",
                                    placeholder="Descreva os serviços executados no dia...",
                                    height=120, key="rdo_ativ")
        ocorrencias  = st.text_area("Ocorrências / Intercorrências",
                                    placeholder="Acidentes, atrasos, problemas técnicos...",
                                    height=80, key="rdo_ocorr")
        equipamentos = st.text_area("Equipamentos Utilizados",
                                    placeholder="Betoneira, escavadeira, andaime...",
                                    height=60, key="rdo_equip")
        observacoes  = st.text_area("Observações Gerais", height=60, key="rdo_obs")

        st.markdown("---")
        st.markdown("**📷 Relatório Fotográfico**")
        fotos_upload = st.file_uploader(
            "Fotos dos serviços (.jpg, .png, .webp)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="As fotos serão incluídas no relatório fotográfico do RDO.",
            key="rdo_fotos_upload"
        )
        if fotos_upload:
            cols_prev = st.columns(min(len(fotos_upload), 4))
            for i, f in enumerate(fotos_upload):
                cols_prev[i % 4].image(f, caption=f.name, width='stretch')

        # ── RDO → Financeiro ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**💰 Financeiro**")
        gerar_cp = st.checkbox("Gerar Conta a Pagar a partir deste RDO", value=False,
                               key="rdo_gerar_cp",
                               help="Cria um lançamento em Contas a Pagar com os serviços do dia.")
        if gerar_cp:
            gf1, gf2 = st.columns(2)
            valor_cp = gf1.number_input("Valor (R$)", min_value=0.0, step=100.0,
                                         value=float(efetivo * 150), key="rdo_cp_valor")
            cat_cp   = gf2.selectbox("Categoria", ["Mão-de-obra", "Material", "Equipamento",
                                                     "Subempreiteiro", "Administrativo", "Outros"],
                                      index=0, key="rdo_cp_cat")
            gf3, gf4, gf5 = st.columns(3)
            forn_cp  = gf3.text_input("Fornecedor/Prestador", value=resp_rdo or "Mão-de-obra direta",
                                       key="rdo_cp_forn")
            venc_cp  = gf4.text_input("Vencimento", value=(date.today() + timedelta(days=30)).strftime("%d/%m/%Y"),
                                       key="rdo_cp_venc")
            forma_cp = gf5.selectbox("Forma Pag.", ["Transferência", "Boleto", "Cheque", "Dinheiro", "Cartão"],
                                      key="rdo_cp_forma")
            obra_uuid_cp = _obra_uuid(obra_rdo) if _obra_valida(obra_rdo) else None
            df_eap_cp = db.eap_itens_por_obra(obra_uuid_cp) if obra_uuid_cp else pd.DataFrame()
            if not df_eap_cp.empty:
                eap_opts_cp = [""] + [f"{r['codigo']} — {r['descricao']}" for _, r in df_eap_cp.iterrows()]
                eap_sel_cp = st.selectbox("Etapa EAP", eap_opts_cp, key="rdo_cp_eap")
                eap_id_cp = str(df_eap_cp.iloc[eap_opts_cp.index(eap_sel_cp) - 1]["id"]) if eap_sel_cp else None
            else:
                eap_id_cp = None

        # Defaults for financeiro
        valor_cp = 0.0; forn_cp = ""; cat_cp = "Mão-de-obra"; venc_cp = ""; forma_cp = "Transferência"; eap_id_cp = None
        if st.button("💾 Salvar RDO", type="primary", key="btn_salvar_rdo"):
            if not atividades.strip():
                st.error("❌ O campo **Atividades Realizadas** é obrigatório.")
            else:
                novo = {
                    "ID":            str(len(st.session_state.rdo) + 1),
                    "SB_ID":         "",
                    "Obra":          obra_rdo,
                    "Data":          str(data_rdo),
                    "Responsável":   resp_rdo,
                    "Clima Manhã":   clima_m,
                    "Clima Tarde":   clima_t,
                    "Efetivo Total": int(efetivo),
                    "Atividades":    atividades.strip(),
                    "Ocorrências":   ocorrencias.strip(),
                    "Equipamentos":  equipamentos.strip(),
                    "Status Dia":    status_rdo,
                    "Observações":   observacoes.strip(),
                    "fotos":         [],
                }
                sb_id_rdo = None
                urls_fotos = []
                try:
                    import sync as _s_rdo
                    sb_id_rdo = _s_rdo.rdo_save(novo)
                    if sb_id_rdo:
                        novo["SB_ID"] = sb_id_rdo
                        if fotos_upload:
                            for _foto in fotos_upload:
                                _url = _s_rdo.upload_rdo_foto(sb_id_rdo, _foto, _foto.name)
                                if _url:
                                    urls_fotos.append({"nome": _foto.name, "url": _url})
                            if urls_fotos:
                                _s_rdo.rdo_update_fotos(sb_id_rdo, urls_fotos)
                                novo["fotos"] = urls_fotos
                except Exception:
                    pass
                st.session_state.rdo = pd.concat(
                    [st.session_state.rdo, pd.DataFrame([novo])], ignore_index=True
                )
                # ── RDO → Financeiro: Conta a Pagar ──────────────────────────────
                if st.session_state.get("rdo_gerar_cp", False):
                    valor_cp = st.session_state.get("rdo_cp_valor", 0.0)
                    forn_cp  = st.session_state.get("rdo_cp_forn", "Mão-de-obra direta")
                    cat_cp   = st.session_state.get("rdo_cp_cat", "Mão-de-obra")
                    venc_cp  = st.session_state.get("rdo_cp_venc", "")
                    forma_cp = st.session_state.get("rdo_cp_forma", "Transferência")
                    eap_id_cp = None
                    df_eap_cp = db.eap_itens_por_obra(obra_uuid) if (obra_uuid := _obra_uuid(obra_rdo)) else pd.DataFrame()
                    if not df_eap_cp.empty:
                        eap_opts_cp = [""] + [f"{r['codigo']} — {r['descricao']}" for _, r in df_eap_cp.iterrows()]
                        eap_sel_cp = st.session_state.get("rdo_cp_eap", "")
                        if eap_sel_cp and eap_sel_cp in eap_opts_cp:
                            eap_id_cp = str(df_eap_cp.iloc[eap_opts_cp.index(eap_sel_cp) - 1]["id"])
                if st.session_state.get("rdo_gerar_cp", False) and valor_cp > 0:
                    desc_cp = f"RDO {str(data_rdo)} — {obra_rdo} ({atividades.strip()[:60]})"
                    dados_cp = {"Obra": obra_rdo, "Fornecedor": forn_cp.strip(),
                                "Descrição": desc_cp, "Categoria": cat_cp,
                                "Valor (R$)": round(valor_cp, 2), "Vencimento": venc_cp,
                                "Status": "A Pagar", "NF": f"RDO/{str(data_rdo)}",
                                "Forma Pag.": forma_cp,
                                "eap_item_id": eap_id_cp,
                                "tipo_custo": cat_cp if cat_cp != "Outros" else None}
                    uuid_cp = None
                    try:
                        uuid_cp = sync.lancamento_save(dados_cp, "PAGAR", _obra_uuid(obra_rdo))
                    except Exception:
                        pass
                    st.session_state.contas_pagar = pd.concat([
                        st.session_state.contas_pagar,
                        pd.DataFrame([{"ID": _next_id(st.session_state.contas_pagar),
                                       "SB_ID": uuid_cp or None, **dados_cp}])
                    ], ignore_index=True)
                    _msg_cp = f" + Conta a Pagar {_fmt(valor_cp)}"

                _icone_rdo = "🔴" if status_rdo != "Normal" else "✅"
                _msg_fotos = f" ({len(urls_fotos)} foto(s) anexada(s))" if urls_fotos else ""
                _msg_cp = _msg_cp if st.session_state.get("rdo_gerar_cp", False) and valor_cp > 0 else ""
                _notify(f"{_icone_rdo} RDO de **{str(data_rdo)}** — **{obra_rdo}** salvo!{_msg_cp} Status: {status_rdo}{_msg_fotos}")
                st.rerun()

    # ── ABA 2: Histórico ─────────────────────────────────────────────────────
    with tabs[1]:
        rdo_df = st.session_state.rdo.copy()
        if rdo_df.empty:
            st.info("Nenhum RDO registrado ainda.")
        else:
            col_f1, col_f2 = st.columns(2)
            obra_f   = col_f1.selectbox("Filtrar por Obra",   ["Todas"] + obras_lista, key="rdo_f_obra")
            status_f = col_f2.selectbox("Filtrar por Status", ["Todos", "Normal", "Intercorrência", "Paralisação parcial", "Paralisação total"], key="rdo_f_status")

            if obra_f != "Todas":
                rdo_df = rdo_df[rdo_df["Obra"] == obra_f]
            if status_f != "Todos":
                rdo_df = rdo_df[rdo_df["Status Dia"] == status_f]

            def _cor_rdo(s):
                return {"Normal": "🟢", "Intercorrência": "🟡",
                        "Paralisação parcial": "🔴", "Paralisação total": "🔴"}.get(s, "⚪")

            rdo_df[""] = rdo_df["Status Dia"].apply(_cor_rdo)
            st.dataframe(
                rdo_df[["", "Obra", "Data", "Responsável", "Efetivo Total", "Clima Manhã", "Clima Tarde", "Status Dia"]],
                hide_index=True, width='stretch'
            )

            # ── Garantir coluna fotos no DataFrame ──────────────────────────────
            if "fotos" not in rdo_df.columns:
                rdo_df["fotos"] = [[] for _ in range(len(rdo_df))]

            if not rdo_df.empty:
                opcoes_rdo = [f"{r['Data']} — {r['Obra']}" for _, r in rdo_df.iterrows()]
                sel_rdo = st.selectbox("Ver detalhes de:", opcoes_rdo, key="rdo_sel_det")
                if sel_rdo:
                    idx_d = opcoes_rdo.index(sel_rdo)
                    row_d = rdo_df.iloc[idx_d]

                    # ── Formulário de edição ─────────────────────────────────
                    if st.session_state.get("rdo_editando") == idx_d:
                        with st.form("form_edit_rdo"):
                            st.subheader(f"✏️ Editando RDO — {row_d['Data']} — {row_d['Obra']}")
                            CLIMAS_ED = ["Ensolarado","Parcialmente nublado","Nublado","Chuvoso","Tempestade"]
                            STATUS_ED = ["Normal","Intercorrência","Paralisação parcial","Paralisação total"]
                            _e1,_e2 = st.columns(2)
                            _resp_ed   = _e1.text_input("Responsável", value=str(row_d.get("Responsável","")))
                            _cur_st = str(row_d.get("Status Dia","Normal"))
                            _status_ed = _e2.selectbox("Status", STATUS_ED,
                                         index=STATUS_ED.index(_cur_st) if _cur_st in STATUS_ED else 0)
                            _e3,_e4,_e5 = st.columns(3)
                            _cur_cm = str(row_d.get("Clima Manhã","Ensolarado"))
                            _cur_ct = str(row_d.get("Clima Tarde","Ensolarado"))
                            _cm_ed = _e3.selectbox("Clima Manhã", CLIMAS_ED,
                                     index=CLIMAS_ED.index(_cur_cm) if _cur_cm in CLIMAS_ED else 0)
                            _ct_ed = _e4.selectbox("Clima Tarde", CLIMAS_ED,
                                     index=CLIMAS_ED.index(_cur_ct) if _cur_ct in CLIMAS_ED else 0)
                            _ef_ed = _e5.number_input("Efetivo Total", value=int(row_d.get("Efetivo Total",0) or 0), min_value=0, step=1)
                            _ativ_ed  = st.text_area("Atividades", value=str(row_d.get("Atividades","")), height=100)
                            _ocor_ed  = st.text_area("Ocorrências", value=str(row_d.get("Ocorrências","")), height=70)
                            _equip_ed = st.text_area("Equipamentos", value=str(row_d.get("Equipamentos","")), height=60)
                            _obs_ed   = st.text_area("Observações", value=str(row_d.get("Observações","")), height=60)
                            _se, _ce2 = st.columns(2)
                            _submit_ed = _se.form_submit_button("💾 Salvar alterações", type="primary")
                            _cancel_ed = _ce2.form_submit_button("❌ Cancelar")
                        if _submit_ed:
                            _dados_ed = {
                                "Obra": row_d["Obra"], "Data": row_d["Data"],
                                "Responsável": _resp_ed, "Clima Manhã": _cm_ed, "Clima Tarde": _ct_ed,
                                "Efetivo Total": int(_ef_ed), "Atividades": _ativ_ed,
                                "Ocorrências": _ocor_ed, "Equipamentos": _equip_ed,
                                "Status Dia": _status_ed, "Observações": _obs_ed,
                            }
                            try:
                                import sync as _s_ed
                                _sb_id_ed = str(row_d.get("SB_ID",""))
                                _s_ed.rdo_save(_dados_ed, sb_id=_sb_id_ed if _sb_id_ed and _sb_id_ed != "nan" else None)
                            except Exception:
                                pass
                            _orig_idx = st.session_state.rdo.index[st.session_state.rdo["ID"] == row_d["ID"]].tolist()
                            if _orig_idx:
                                for _k, _v in _dados_ed.items():
                                    st.session_state.rdo.at[_orig_idx[0], _k] = _v
                            del st.session_state["rdo_editando"]
                            _notify(f"✅ RDO de **{row_d['Data']}** atualizado com sucesso!")
                            st.rerun()
                        if _cancel_ed:
                            del st.session_state["rdo_editando"]
                            st.rerun()

                    # ── Confirmação de exclusão ──────────────────────────────
                    elif st.session_state.get("rdo_excluindo") == idx_d:
                        st.error(f"⚠️ Confirmar exclusão do RDO de **{row_d['Data']}** — **{row_d['Obra']}**?")
                        _cc1, _cc2, _ = st.columns([1,1,4])
                        if _cc1.button("✅ Sim, excluir", key="btn_conf_del_rdo"):
                            _sb_id_exc = str(row_d.get("SB_ID",""))
                            if _sb_id_exc and _sb_id_exc not in ("","nan","None"):
                                try:
                                    from db import sb as _sb_rdo
                                    _sb_rdo().table("rdo").delete().eq("id", _sb_id_exc).execute()
                                except Exception:
                                    pass
                            _mask_exc = st.session_state.rdo["ID"] != row_d["ID"]
                            st.session_state.rdo = st.session_state.rdo[_mask_exc].reset_index(drop=True)
                            del st.session_state["rdo_excluindo"]
                            _notify("✅ RDO excluído com sucesso!")
                            st.rerun()
                        if _cc2.button("❌ Cancelar", key="btn_canc_del_rdo"):
                            del st.session_state["rdo_excluindo"]
                            st.rerun()

                    else:
                        # ── Exibição normal do detalhe ───────────────────────
                        with st.expander("📄 Detalhes do RDO", expanded=True):
                            d1, d2, d3 = st.columns(3)
                            d1.metric("Obra",    row_d["Obra"])
                            d2.metric("Data",    row_d["Data"])
                            d3.metric("Efetivo", f"{row_d['Efetivo Total']} pessoas")
                            st.markdown(f"**Clima:** Manhã — {row_d['Clima Manhã']} | Tarde — {row_d['Clima Tarde']}")
                            st.markdown(f"**Atividades:** {row_d['Atividades']}")
                            if row_d.get("Ocorrências"):
                                st.warning(f"**Ocorrências:** {row_d['Ocorrências']}")
                            if row_d.get("Equipamentos"):
                                st.markdown(f"**Equipamentos:** {row_d['Equipamentos']}")
                            if row_d.get("Observações"):
                                st.markdown(f"**Observações:** {row_d['Observações']}")

                            # ── Relatório fotográfico ────────────────────────
                            import json as _json_rdo
                            _fv = row_d["fotos"] if "fotos" in row_d.index else []
                            if isinstance(_fv, str):
                                try: _fv = _json_rdo.loads(_fv)
                                except Exception: _fv = []
                            if not isinstance(_fv, list):
                                _fv = []
                            fotos_row = _fv
                            if fotos_row:
                                st.markdown("**📷 Relatório Fotográfico**")
                                _cols_f = st.columns(min(len(fotos_row), 3))
                                for _fi, _foto_item in enumerate(fotos_row):
                                    _url_f  = _foto_item.get("url","") if isinstance(_foto_item, dict) else str(_foto_item)
                                    _nome_f = _foto_item.get("nome","Foto") if isinstance(_foto_item, dict) else "Foto"
                                    if _url_f:
                                        _cols_f[_fi % 3].image(_url_f, caption=_nome_f, width='stretch')

                            # ── Exportar PDF / DOCX ──────────────────────────
                            st.markdown("---")
                            st.markdown("**📤 Exportar este RDO:**")
                            _exp1, _exp2 = st.columns(2)
                            try:
                                from gerar_pdf import gerar_rdo as _gerar_rdo_pdf
                                _pdf_bytes = _gerar_rdo_pdf(dict(row_d), fotos_row)
                                _exp1.download_button(
                                    "📄 Baixar PDF", data=_pdf_bytes,
                                    file_name=f"RDO_{str(row_d['Obra']).replace(' ','_')}_{row_d['Data']}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_pdf_rdo_{idx_d}"
                                )
                            except Exception as _ep:
                                _exp1.caption(f"PDF indisponível: {_ep}")
                            try:
                                from gerar_pdf import gerar_rdo_docx as _gerar_rdo_docx
                                _docx_bytes = _gerar_rdo_docx(dict(row_d), fotos_row)
                                _exp2.download_button(
                                    "📝 Baixar Word (.docx)", data=_docx_bytes,
                                    file_name=f"RDO_{str(row_d['Obra']).replace(' ','_')}_{row_d['Data']}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"btn_docx_rdo_{idx_d}"
                                )
                            except Exception as _ew:
                                _exp2.caption(f"Word indisponível: {_ew}")

                            # ── Ações ────────────────────────────────────────
                            st.markdown("---")
                            _ce_btn, _cd_btn = st.columns(2)
                            if _ce_btn.button("✏️ Editar este RDO", key=f"btn_edit_rdo_{idx_d}"):
                                st.session_state["rdo_editando"] = idx_d
                                st.rerun()
                            if _cd_btn.button("🗑️ Excluir este RDO", key=f"btn_del_rdo_{idx_d}", type="secondary"):
                                st.session_state["rdo_excluindo"] = idx_d
                                st.rerun()


# ── EAP ───────────────────────────────────────────────────────────────────────

def pagina_eap():
    import numpy as np
    import plotly.express as px
    st.title("📅 Planejamento — EAP")
    _init()
    _show_toast()

    obras_lista = _obras_nomes()
    obra_sel = st.selectbox("Obra", obras_lista, key="eap_obra_sel")
    obra_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_sel]
    obra_sb_id = str(obra_row["SB_ID"].iloc[0]) if not obra_row.empty and pd.notna(obra_row["SB_ID"].iloc[0]) else None

    # ── Estado sem obra ──────────────────────────────────────────────
    if obra_row.empty:
        st.warning("Nenhuma obra selecionada.")
        return

    o = obra_row.iloc[0]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Status",          o["Status"])
    c2.metric("Avanço Físico",   f"{o['% Físico']}%")
    c3.metric("Valor Contrato",  _fmt(_to_num(o["Valor Contrato (R$)"])))
    c4.metric("Responsável",     o["Responsável"])

    # ── Carregar orçamentos salvos do Supabase ───────────────────────
    orc_por_obra = st.session_state.get("orcamento_por_obra", {})
    resultado    = _normalizar_orc_data(orc_por_obra.get(obra_sel))

    if not resultado and obra_sb_id:
        orcs = sync.orcamento_load()
        orcs_filtrados = [o2 for o2 in orcs if o2.get("obra_id") == obra_sb_id]
        if orcs_filtrados:
            nomes_orc = [f"{o2['nome']} (v{o2['versao']} — R$ {o2['total_venda']:,.2f})" for o2 in orcs_filtrados]
            sel_idx = st.selectbox("Selecionar orçamento salvo", range(len(nomes_orc)), format_func=lambda i: nomes_orc[i] if i < len(nomes_orc) else "", key="eap_orc_sel")
            if st.button("📂 Carregar este orçamento como EAP", key="eap_carregar_orc"):
                o_sel = orcs_filtrados[sel_idx]
                resultado = o_sel.get("itens", [])
                if "orcamento_por_obra" not in st.session_state:
                    st.session_state.orcamento_por_obra = {}
                st.session_state.orcamento_por_obra[obra_sel] = resultado
                st.rerun()

    if not resultado:
        st.info(
            f"Nenhum orçamento carregado para **{obra_sel}**.\n\n"
            "Acesse **📊 Orçamento**, importe uma planilha e salve. "
            "Ou carregue um orçamento já salvo acima.",
            icon="ℹ️",
        )
        return

    # ── Métricas ──────────────────────────────────────────────────────
    df_res  = pd.DataFrame(resultado)
    itens   = df_res[df_res["tipo"] == "ITEM"].copy()
    etapas  = df_res[df_res["tipo"] == "ETAPA"].copy()
    tc      = itens["total_custo"].fillna(0).sum()
    tv      = itens["total_venda"].fillna(0).sum()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Etapas",              len(etapas))
    c2.metric("Itens de Serviço",    len(itens))
    c3.metric("Total Custo Direto",  _fmt(tc))
    c4.metric("Total Venda (c/ BDI)",_fmt(tv))
    st.markdown("---")

    # ── Salvar EAP no Supabase ────────────────────────────────────────
    if obra_sb_id:
        if st.button("📁 Gerar EAP no Banco", key="btn_gerar_eap", type="primary"):
            try:
                ok = sync.eap_save_from_orcamento(obra_sb_id, resultado)
            except Exception as _eap_e:
                st.error(f"Erro ao gerar EAP: {_eap_e}")
                ok = False
            if ok:
                _notify(f"✅ EAP gerada para **{obra_sel}**!")
                st.rerun()
            else:
                st.error("Erro ao gerar EAP no banco.")

    # ── Verificar se já existe EAP salva ──────────────────────────────
    eap_data = sync.eap_load(obra_sb_id) if obra_sb_id else []
    if eap_data:
        st.success(f"📌 EAP já cadastrada no banco ({len(eap_data)} itens).")
        if st.button("🔄 Recarregar estrutura salva", key="eap_reload"):
            resultado = []
            for e in eap_data:
                qtd = float(e.get("qtd_prevista", 0) or 0)
                resultado.append({
                    "ordem":      e.get("codigo", ""),
                    "descricao":  e.get("descricao", ""),
                    "unidade":    e.get("unidade", ""),
                    "quantidade": qtd,
                    "preco_custo": 0,
                    "preco_venda": 0,
                    "total_custo": 0,
                    "total_venda": float(e.get("valor_previsto", 0) or 0),
                    "tipo":       "ITEM" if qtd > 0 else "ETAPA",
                    "nivel":      1,
                    "etapa_pai":  "",
                })
            if "orcamento_por_obra" not in st.session_state:
                st.session_state.orcamento_por_obra = {}
            st.session_state.orcamento_por_obra[obra_sel] = resultado
            st.rerun()

    t_arv, t_prog, t_gantt = st.tabs(["🌳 Estrutura EAP","📊 Progresso por Etapa","📅 Cronograma"])

    # ── Aba 1: Árvore EAP ────────────────────────────────────────────
    with t_arv:
        linhas = []
        for r in resultado:
            _nivel = r.get("nivel", 1)
            pad = "　" * (_nivel - 1)
            if r["tipo"] == "ETAPA":
                linhas.append({"Cód": r["ordem"],
                                "Estrutura": pad + "📁 " + r["descricao"],
                                "Un":"","Qtd":"","Total Custo":"","Total Venda":""})
            else:
                q = r["quantidade"]
                linhas.append({
                    "Cód": r["ordem"],
                    "Estrutura": pad + "  └ " + r["descricao"],
                    "Un": r["unidade"],
                    "Qtd": f"{q:,.2f}".replace(",","X").replace(".",",").replace("X",".") if q else "",
                    "Total Custo": _fmt(r["total_custo"]) if r["total_custo"] else "",
                    "Total Venda": _fmt(r["total_venda"]) if r["total_venda"] else "",
                })
        st.dataframe(pd.DataFrame(linhas), width='stretch', hide_index=True)

    # ── Mapeamento descrição → código EAP ────────────────────────────
    _desc_to_cod = {}
    _cod_to_desc = {}
    if eap_data:
        for e in eap_data:
            desc = e.get("descricao", "")
            cod = e.get("codigo", "")
            if desc:
                _desc_to_cod[desc] = cod
                _cod_to_desc[cod] = desc

    # ── Aba 2: Progresso por Etapa ───────────────────────────────────
    with t_prog:
        if len(etapas) and tv > 0:
            custo_et = (itens.groupby("etapa_pai")[["total_custo","total_venda"]]
                             .sum().reset_index()
                             .sort_values("total_venda", ascending=False))
            custo_et["% Total"] = (custo_et["total_venda"] / tv * 100).round(1)

            if "eap_progresso" not in st.session_state:
                st.session_state.eap_progresso = {}
            if "eap_progresso_saved" not in st.session_state:
                st.session_state.eap_progresso_saved = False

            # Carrega progresso salvo do Supabase na primeira vez
            if not st.session_state.eap_progresso_saved and eap_data:
                for e in eap_data:
                    desc = e.get("descricao", "")
                    if desc:
                        k = f"eap_{obra_sel}_{desc}"
                        if k not in st.session_state.eap_progresso:
                            st.session_state.eap_progresso[k] = float(e.get("progresso", 0) or 0) * 100
                st.session_state.eap_progresso_saved = True

            st.caption("Defina o avanço físico de cada etapa:")
            _prog_payload = {}
            for _, row in custo_et.iterrows():
                nome_et = row["etapa_pai"]
                k = f"eap_{obra_sel}_{nome_et}"
                pct_at = st.session_state.eap_progresso.get(k, 0)
                cols = st.columns([4, 1, 1])
                pct_novo = cols[0].slider(nome_et[:60], 0, 100, int(pct_at), key=k)
                cols[1].metric("Custo",   _fmt(row["total_custo"]))
                cols[2].metric("% Total", f"{row['% Total']:.1f}%")
                st.session_state.eap_progresso[k] = pct_novo
                # Mapeia nome da etapa para código EAP
                cod = _desc_to_cod.get(nome_et)
                if cod:
                    _prog_payload[cod] = pct_novo

            st.markdown("---")
            if _prog_payload and obra_sb_id:
                if st.button("💾 Salvar Progresso no Banco", key="btn_salvar_prog"):
                    if sync.eap_save_all_progresso(obra_sb_id, _prog_payload):
                        _notify("Progresso salvo!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar progresso.")

            fig_p = px.bar(custo_et, x="etapa_pai", y="total_venda",
                           color_discrete_sequence=["#2B59C3"], text="% Total",
                           labels={"etapa_pai":"","total_venda":"R$"})
            fig_p.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_p.update_layout(height=340, plot_bgcolor="white", paper_bgcolor="white",
                                yaxis_tickformat=",.0f", margin=dict(t=20,b=80))
            st.plotly_chart(fig_p, width='stretch')

    # ── Aba 3: Cronograma / Gantt ────────────────────────────────────
    with t_gantt:
        if "eap_datas" not in st.session_state:
            st.session_state.eap_datas = {}
        if "eap_datas_saved" not in st.session_state:
            st.session_state.eap_datas_saved = False

        if len(etapas):
            etapas_n1 = [e["descricao"] for e in etapas if e.get("nivel") == 1]
        else:
            etapas_n1 = []

        # Carrega datas salvas do Supabase na primeira vez
        if not st.session_state.eap_datas_saved and eap_data and obra_sel:
            _loaded = {}
            for e in eap_data:
                desc = e.get("descricao", "")
                di = e.get("data_inicio")
                dt = e.get("data_termino")
                if desc and (di or dt):
                    kd = desc[:60]
                    _loaded[kd] = {
                        "ini": _iso_to_br(str(di)) if di else "",
                        "fim": _iso_to_br(str(dt)) if dt else "",
                        "desc": desc,
                    }
            if _loaded:
                st.session_state.eap_datas[obra_sel] = _loaded
            st.session_state.eap_datas_saved = True

        if not etapas_n1:
            st.info("Nenhuma etapa de nível 1 detectada. Verifique o mapeamento de colunas no Orçamento.")
        else:
            datas_obra = st.session_state.eap_datas.get(obra_sel, {})
            with st.expander("⚙️ Definir / Editar Datas das Etapas",
                             expanded=len(datas_obra) == 0):
                with st.form("form_datas_eap"):
                    st.caption(f"{len(etapas_n1)} etapa(s) principais de **{obra_sel}**")
                    novas_datas = {}
                    for etapa in etapas_n1:
                        k = etapa[:60]
                        ex = datas_obra.get(k, {})
                        c1_, c2_, c3_ = st.columns([4, 2, 2])
                        c1_.markdown(f"**{etapa[:55]}**")
                        ini_ = c2_.text_input("Início",  value=ex.get("ini",""),
                                              key=f"ini_{k}", placeholder="01/03/2026")
                        fim_ = c3_.text_input("Término", value=ex.get("fim",""),
                                              key=f"fim_{k}", placeholder="31/05/2026")
                        novas_datas[k] = {"ini": ini_, "fim": fim_, "desc": etapa}
                    ok_dt = st.form_submit_button("💾 Salvar Datas", type="primary")
                if ok_dt:
                    st.session_state.eap_datas[obra_sel] = novas_datas
                    # Salva no Supabase
                    if obra_sb_id:
                        _datas_payload = {}
                        for etapa in etapas_n1:
                            k = etapa[:60]
                            cod = _desc_to_cod.get(etapa)
                            if cod:
                                nd = novas_datas.get(k, {})
                                _datas_payload[cod] = {"ini": nd.get("ini", ""), "fim": nd.get("fim", "")}
                        if _datas_payload:
                            sync.eap_save_all_datas(obra_sb_id, _datas_payload)
                    _notify("Datas salvas!"); st.rerun()

            # Monta Gantt somente para etapas com datas preenchidas
            gantt = []
            for k, d in datas_obra.items():
                if d.get("ini") and d.get("fim"):
                    try:
                        gantt.append({
                            "Etapa":  d["desc"][:55],
                            "Início": pd.to_datetime(d["ini"], dayfirst=True),
                            "Término":pd.to_datetime(d["fim"], dayfirst=True),
                        })
                    except Exception:
                        pass

            if gantt:
                df_g = pd.DataFrame(gantt)
                fig_g = px.timeline(df_g, x_start="Início", x_end="Término", y="Etapa",
                                    color="Etapa", labels={"Etapa":""})
                fig_g.update_yaxes(autorange="reversed")
                fig_g.add_vline(x=datetime.today(), line_dash="dash", line_color="red",
                                line_width=1.5, annotation_text="Hoje",
                                annotation_position="top right")
                fig_g.update_layout(
                    height=max(300, len(gantt)*44+80),
                    showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=0,r=0,t=10,b=0),
                )
                st.plotly_chart(fig_g, width='stretch')
                # Tabela de datas
                df_g_ex = df_g.copy()
                df_g_ex["Início"]  = df_g_ex["Início"].dt.strftime("%d/%m/%Y")
                df_g_ex["Término"] = df_g_ex["Término"].dt.strftime("%d/%m/%Y")
                df_g_ex["Duração (dias)"] = (
                    pd.to_datetime(df_g["Término"]) - pd.to_datetime(df_g["Início"])
                ).dt.days
                st.dataframe(df_g_ex, width='stretch', hide_index=True)
            else:
                st.info("Preencha as datas no painel acima para visualizar o Cronograma (Gantt).")

    # ── Cronograma Físico-Financeiro ─────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 Cronograma Físico-Financeiro (Orçado x Realizado)")

    datas_cff = st.session_state.eap_datas.get(obra_sel, {})
    gantt_cff = []
    for _k_cff, _d_cff in datas_cff.items():
        if _d_cff.get("ini") and _d_cff.get("fim"):
            try:
                gantt_cff.append({
                    "desc": _d_cff["desc"],
                    "ini":  pd.to_datetime(_d_cff["ini"], dayfirst=True),
                    "fim":  pd.to_datetime(_d_cff["fim"], dayfirst=True),
                })
            except Exception:
                pass

    if not gantt_cff:
        st.info(
            "Preencha as datas das etapas na aba **Cronograma** acima "
            "para gerar o Cronograma Físico-Financeiro.",
            icon="ℹ️",
        )
    else:
        ini_global = min(g["ini"] for g in gantt_cff)
        fim_global = max(g["fim"] for g in gantt_cff)

        meses = pd.date_range(ini_global, fim_global, freq="MS")
        if len(meses) == 0:
            meses = pd.date_range(ini_global, periods=3, freq="MS")
        n = len(meses)
        mes_labels = [m.strftime("%b/%y") for m in meses]

        # ── Orçado real dos EAP itens (curva planejada) ─────────────────
        _eap_total_plan = float(eap_data[0].get("valor_previsto", tv)) if eap_data and len(eap_data) > 0 else tv
        _eap_vals = np.array([float(e.get("valor_previsto", 0) or 0) for e in eap_data])
        _eap_vals = _eap_vals[_eap_vals > 0]
        if len(_eap_vals) == 0:
            _eap_vals = np.array([tv / max(n, 1)] * n)

        # Distribui o orçado proporcionalmente no tempo (Curva S realista)
        _weights = np.ones(n)
        _w_n = len(_weights)
        _x_s = np.linspace(0, np.pi, _w_n)
        _weights = np.sin(_x_s)  # senoide: aceleração-desaceleração
        _weights = _weights / _weights.sum()
        desemb_plan = _weights * _eap_total_plan

        # ── Realizado financeiro: busca do Supabase por obra+EAP ────────
        try:
            _df_lc_r = db.lancamentos_listar("PAGAR")
            if obra_sb_id and not _df_lc_r.empty:
                _df_lo_r = _df_lc_r[_df_lc_r["obra_id"] == obra_sb_id].copy()
                if "data_vencimento" in _df_lo_r.columns:
                    _df_lo_r["_dt"] = pd.to_datetime(_df_lo_r["data_vencimento"], errors="coerce")
                    _df_lo_r["_val"] = pd.to_numeric(_df_lo_r["valor"], errors="coerce").fillna(0)
                    desemb_real = np.zeros(n)
                    for _i, _mes in enumerate(meses):
                        _fim_mes = _mes + pd.offsets.MonthEnd(0)
                        _mask = (_df_lo_r["_dt"] >= _mes) & (_df_lo_r["_dt"] <= _fim_mes)
                        desemb_real[_i] = _df_lo_r.loc[_mask, "_val"].sum()
                else:
                    desemb_real = np.zeros(n)
            else:
                desemb_real = np.zeros(n)
        except Exception:
            desemb_real = np.zeros(n)

        # ── Físico realizado dos sliders ────────────────────────────────
        _prog_cff = st.session_state.get("eap_progresso", {})
        _pcts_cff = [v for k_p, v in _prog_cff.items() if f"eap_{obra_sel}_" in k_p]
        pct_real = float(np.mean(_pcts_cff)) if _pcts_cff else 0.0

        # Curva S física: distribuição senoidal
        _weights_fis = np.sin(np.linspace(0, np.pi, n))
        _weights_fis = _weights_fis / _weights_fis.sum()
        fis_plan_cum = np.cumsum(_weights_fis * 100.0)
        fis_plan_cum = fis_plan_cum / fis_plan_cum[-1] * 100.0 if fis_plan_cum[-1] > 0 else fis_plan_cum
        fis_real_cum = np.linspace(0.0, pct_real, n)

        fin_plan_cum = np.cumsum(desemb_plan)
        fin_real_cum = np.cumsum(desemb_real)

        pct_plan_fin = float(fis_plan_cum[-1]) if n > 0 else 100.0
        desvio_fis   = pct_real - pct_plan_fin
        idp          = (pct_real / pct_plan_fin) if pct_plan_fin > 0 else 1.0

        _kc1, _kc2, _kc3, _kc4 = st.columns(4)
        _kc1.metric("Físico Planejado", f"{pct_plan_fin:.1f}%")
        _kc2.metric("Físico Realizado", f"{pct_real:.1f}%")
        _kc3.metric("Desvio Físico",    f"{desvio_fis:+.1f}%",
                    delta=f"{desvio_fis:+.1f}%",
                    delta_color="normal" if desvio_fis >= 0 else "inverse")
        _kc4.metric("IDP", f"{idp:.2f}")

        st.markdown("---")
        _tab_fis, _tab_fin = st.tabs(["📐 % Físico", "💰 Financeiro (R$)"])

        with _tab_fis:
            _df_fis = pd.DataFrame({
                "Mês":           mes_labels * 2,
                "Acumulado (%)": np.concatenate([fis_plan_cum, fis_real_cum]),
                "Tipo":          ["Planejado"] * n + ["Realizado"] * n,
            })
            _fig_fis = px.line(
                _df_fis, x="Mês", y="Acumulado (%)", color="Tipo", markers=True,
                color_discrete_map={"Planejado": "#2B59C3", "Realizado": "#E67E22"},
                title="Curva S — Avanço Físico Acumulado",
            )
            _fig_fis.add_hline(y=100, line_dash="dot", line_color="#888", line_width=1)
            _fig_fis.update_layout(
                height=370, plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(range=[0, 110], ticksuffix="%"),
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(_fig_fis, width='stretch')

        with _tab_fin:
            _df_fin = pd.DataFrame({
                "Mês":                  mes_labels * 2,
                "Valor Acumulado (R$)": np.concatenate([fin_plan_cum, fin_real_cum]),
                "Tipo":                 ["Planejado"] * n + ["Realizado"] * n,
            })
            _fig_fin = px.line(
                _df_fin, x="Mês", y="Valor Acumulado (R$)", color="Tipo", markers=True,
                color_discrete_map={"Planejado": "#2B59C3", "Realizado": "#E67E22"},
                title="Curva S — Desembolso Financeiro Acumulado",
            )
            _fig_fin.update_layout(
                height=370, plot_bgcolor="white", paper_bgcolor="white",
                yaxis_tickformat=",.0f",
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(_fig_fin, width='stretch')


# ── MEDIÇÃO ─────────────────────────────────────────────────────────────────────

def pagina_medicao():
    st.title("📏 Medição")
    _init()
    _show_toast()

    obra_sel = st.selectbox("Selecione a obra", _obras_nomes(), key="med_obra")
    if not _obra_valida(obra_sel):
        st.info("Selecione uma obra para gerenciar medições.")
        return

    obra_uuid = _obra_uuid(obra_sel)
    if not obra_uuid:
        st.warning("Obra não encontrada no Supabase. Cadastre a obra primeiro.")
        return

    ob_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_sel]
    valor_contrato = float(ob_row["Valor Contrato (R$)"].iloc[0]) if not ob_row.empty else 0

    # Carrega medições + último %
    df_med = sync.medicoes_load()
    df_med_obra = df_med[df_med["Obra"] == obra_sel].copy() if not df_med.empty else pd.DataFrame()
    ultimo_pct = sync.medicao_ultimo_pct(obra_uuid)

    tab_lista, tab_nova, tab_editar = st.tabs(["📋 Histórico", "➕ Nova Medição", "✏️ Editar / Excluir"])

    # ── Tab 1: Histórico ──────────────────────────────────────────────────
    with tab_lista:
        if df_med_obra.empty:
            st.info("Nenhuma medição registrada para esta obra.")
        else:
            for _, r in df_med_obra.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{r['Período']}** — {r.get('Observação','')}")
                    c2.metric("% Medido", f"{r['% Medido']}%")
                    c3.metric("Valor", _fmt(r['Valor Medido (R$)']))
                    c4.markdown(f"<div style='margin-top:8px;font-size:0.8rem;color:#6B7280;'>{r['Data']}</div>", unsafe_allow_html=True)
            st.markdown("---")
            c_d, c_r = st.columns(2)
            c_d.metric("Último % Medido", f"{ultimo_pct:.1f}%")
            c_r.metric("Valor Contrato", _fmt(valor_contrato))

            if st.button("📥 Gerar BM em PDF", key="med_bm_pdf"):
                _dados_bm = {
                    "obra": obra_sel, "cliente": "",
                    "periodo": "Acumulado", "num_bm": "001",
                    "pct_anterior": 0, "pct_periodo": ultimo_pct, "pct_acumulado": ultimo_pct,
                    "valor_contrato": valor_contrato,
                    "valor_anterior": 0,
                    "valor_periodo": valor_contrato * ultimo_pct / 100,
                    "valor_acumulado": valor_contrato * ultimo_pct / 100,
                }
                orc_itens = st.session_state.get("orcamento_por_obra", {}).get(obra_sel, [])
                try:
                    import gerar_pdf
                    pdf = gerar_pdf.gerar_bm(_dados_bm, itens=orc_itens)
                    st.download_button("⬇️ Baixar PDF", pdf, file_name=f"BM_{obra_sel}.pdf", mime="application/pdf")
                except Exception as _bm_e:
                    st.error(f"Erro ao gerar BM: {_bm_e}")

    # ── Tab 2: Nova Medição ───────────────────────────────────────────────
    with tab_nova:
        st.markdown(f"**Último % medido:** {ultimo_pct:.1f}%")
        competencia = st.date_input("Competência (mês/ano)", value=date.today().replace(day=1), key="med_competencia")
        pct_acum = st.number_input("% Medido Acumulado", min_value=0.0, max_value=100.0,
                                   value=min(float(ultimo_pct) + 10.0, 100.0), step=0.5, key="med_pct")
        observacao = st.text_input("Observação", key="med_obs")

        # EAP items para medição itemizada
        eap_data = sync.eap_load(obra_uuid) if obra_uuid else []
        if eap_data:
            st.markdown("#### Itens da EAP — preencha % executado de cada um")
            itens_med = []
            cols_n = st.columns([3, 1, 1, 1, 1])
            cols_n[0].markdown("**Descrição**")
            cols_n[1].markdown("**Un**")
            cols_n[2].markdown("**Qtd Prev**")
            cols_n[3].markdown("**% Exec**")
            cols_n[4].markdown("**Valor**")
            for e in eap_data:
                k = f"med_item_{e['id']}"
                pct_i = st.session_state.get(k, 0.0)
                pct_n = st.number_input(f"{e.get('descricao','')[:50]}", min_value=0.0, max_value=100.0,
                                        value=float(pct_i), step=1.0, key=k, label_visibility="collapsed",
                                        help=e.get("descricao",""))
                q_prev = float(e.get("qtd_prevista", 0) or 0)
                v_prev = float(e.get("valor_previsto", 0) or 0)
                v_exec = v_prev * pct_n / 100
                itens_med.append({
                    "eap_item_id":  e["id"],
                    "codigo":       str(e.get("codigo", "")),
                    "descricao":    e.get("descricao", ""),
                    "unidade":      e.get("unidade", ""),
                    "qtd_prevista": q_prev,
                    "qtd_periodo":  q_prev * pct_n / 100,
                    "qtd_acumulada": q_prev * pct_n / 100,
                    "preco_unitario": round(v_prev / q_prev, 2) if q_prev > 0 else 0,
                    "valor_periodo":  round(v_exec, 2),
                    "valor_acumulado": round(v_exec, 2),
                })
                cols_i = st.columns([3, 1, 1, 1, 1])
                cols_i[0].caption(e.get("descricao", "")[:60])
                cols_i[1].caption(e.get("unidade", ""))
                cols_i[2].caption(f"{q_prev:.1f}")
                cols_i[3].caption(f"{pct_n:.0f}%")
                cols_i[4].caption(_fmt(v_exec))
            total_eap = sum(it.get("valor_periodo", 0) for it in itens_med)
            st.metric("Total pela EAP", _fmt(total_eap))
        else:
            itens_med = []
            st.info("Esta obra não possui EAP. A medição será registrada apenas com % global.")

        if st.button("💾 Registrar Medição", type="primary", key="med_salvar"):
            incremento = pct_acum - ultimo_pct
            valor_periodo = incremento / 100 * valor_contrato
            dados_med = {
                "Data": competencia.strftime("%d/%m/%Y"),
                "Período": competencia.strftime("%m/%Y"),
                "% Medido": int(pct_acum),
                "Valor Medido (R$)": total_eap if itens_med else valor_periodo,
                "Observação": observacao,
            }
            mid = sync.medicao_save(dados_med, obra_sb_id=obra_uuid)
            if mid:
                if itens_med:
                    sync.medicao_itens_save(mid, itens_med)
                # Atualiza % Físico na obra
                ob_row_m = st.session_state.obras["Nome"] == obra_sel
                if ob_row_m.any():
                    st.session_state.obras.loc[ob_row_m, "% Físico"] = int(pct_acum)
                    try:
                        import sync as _sync_m
                        _sync_m.obra_save(dict(st.session_state.obras.loc[ob_row_m].iloc[0]),
                                         sb_id=obra_uuid)
                    except Exception:
                        pass
                # Cria Conta a Receber
                try:
                    from db import sb as _sb_m
                    _sb_m().table("lancamentos").insert({
                        "obra_id": obra_uuid,
                        "tipo": "RECEBER",
                        "descricao": f"BM {competencia.strftime('%m/%Y')} — {incremento:.1f}% — {obra_sel}",
                        "valor": round(total_eap if itens_med else valor_periodo, 2),
                        "data_vencimento": competencia.strftime("%Y-%m-%d"),
                        "empresa_id": st.session_state.empresa_id,
                    }).execute()
                except Exception as _le:
                    print(f"[med] erro ao criar conta a receber: {_le}")
                sync.medicoes_load.clear()
                _notify(f"✅ Medição de {pct_acum:.0f}% registrada!")
                st.rerun()
            else:
                st.error("Erro ao salvar medição no Supabase.")

    # ── Tab 3: Editar / Excluir ───────────────────────────────────────────
    with tab_editar:
        if df_med_obra.empty:
            st.info("Nenhuma medição para editar.")
        else:
            med_opts = {f"{r['Período']} — {r['% Medido']}% ({_fmt(r['Valor Medido (R$)'])})": r['SB_ID']
                       for _, r in df_med_obra.iterrows()}
            sel_label = st.selectbox("Selecionar medição", list(med_opts.keys()), key="med_edit_sel")
            if sel_label:
                mid = med_opts[sel_label]
                row_m = df_med_obra[df_med_obra["SB_ID"] == mid].iloc[0]
                if st.button("🗑️ Excluir esta medição", key="med_del", type="secondary"):
                    if sync.medicao_delete(mid):
                        sync.medicoes_load.clear()
                        st.rerun()
                    else:
                        st.error("Erro ao excluir.")


# ── Relatórios ─────────────────────────────────────────────────────────────────

def pagina_relatorios():
    st.title("📄 Relatórios")
    _init()
    _show_toast()

    tab_ger, tab_fin, tab_med, tab_rdo, tab_ncs = st.tabs(
        ["📑 Gerencial", "💰 Financeiro", "📏 Medições", "📋 RDOs", "✅ Não-Conformidades"]
    )

    obras_lista = _obras_nomes()

    # ── Tab 1: Gerencial ──────────────────────────────────────────────────
    with tab_ger:
        st.markdown("##### Relatório Gerencial Mensal — consolidado de todas as obras")
        rg_c1, rg_c2 = st.columns([3, 1])
        mes_ref = rg_c1.text_input("Mês de referência",
            value=date.today().strftime("%B/%Y"), key="rg_mes_ref2",
            placeholder="Junho/2026")
        if rg_c2.button("📥 Gerar PDF", key="btn_gerar_rg2", type="primary", width='stretch'):
            try:
                from gerar_pdf import gerar_relatorio_gerencial as _gerar_rg
                _dados_rg = {
                    "mes_ref":        mes_ref,
                    "obras":          st.session_state.obras.copy(),
                    "medicoes":       st.session_state.medicoes.copy(),
                    "contas_pagar":   st.session_state.contas_pagar.copy(),
                    "contas_receber": st.session_state.contas_receber.copy(),
                    "ncs":            st.session_state.ncs.copy(),
                    "funcionarios":   st.session_state.funcionarios.copy(),
                }
                _pdf_rg = _gerar_rg(_dados_rg)
                st.download_button("⬇️ Baixar Relatório Gerencial PDF", data=_pdf_rg,
                    file_name=f"Relatorio_Gerencial_Prumo_{mes_ref.replace('/','-')}.pdf",
                    mime="application/pdf", key="dl_rg2")
                st.success("✅ Relatório Gerencial gerado!")
            except Exception as _e_rg:
                st.error(f"❌ {_e_rg}")

        st.markdown("---")
        st.markdown("##### Prévia — Indicadores do Mês")
        ob = st.session_state.obras.copy()
        ob_ativas = ob[ob["Status"].isin(["Em andamento", "Planejamento"])]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Obras Ativas",  len(ob_ativas))
        c2.metric("Total Contratos", _fmt(ob_ativas["Valor Contrato (R$)"].sum()))
        c3.metric("Média % Físico", f"{ob_ativas['% Físico'].mean():.1f}%" if len(ob_ativas) else "—")
        c4.metric("Folha Bruta",   _fmt(st.session_state.funcionarios["Salário (R$)"].sum()) if not st.session_state.funcionarios.empty else "—")

    # ── Tab 2: Financeiro ─────────────────────────────────────────────────
    with tab_fin:
        st.markdown("##### Relatório Financeiro — Contas a Pagar / Receber")
        fin_c1, fin_c2 = st.columns(2)
        obra_fin = fin_c1.selectbox("Obra", ["Todas"] + obras_lista, key="rel_fin_obra")
        mes_fin  = fin_c2.text_input("Mês de referência", value=date.today().strftime("%m/%Y"), key="rel_fin_mes")
        cp = st.session_state.contas_pagar.copy()
        cr = st.session_state.contas_receber.copy()
        if obra_fin != "Todas":
            cp = cp[cp["Obra"] == obra_fin]
            cr = cr[cr["Obra"] == obra_fin]
        cp_venc = cp[cp["Status"].isin(["A Pagar", "Vencido"])]["Valor (R$)"].sum()
        cr_aren = cr[cr["Status"].isin(["A Receber", "Vencido"])]["Valor (R$)"].sum()
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Total a Pagar",   _fmt(cp["Valor (R$)"].sum()))
        fc2.metric("Total a Receber",  _fmt(cr["Valor (R$)"].sum()))
        fc3.metric("Saldo Líquido",   _fmt(cr["Valor (R$)"].sum() - cp["Valor (R$)"].sum()))
        st.markdown("---")
        if st.button("📥 Exportar Financeiro (Excel)", key="btn_rel_fin_xls"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                cp.drop(columns=[c for c in ["ID", "SB_ID"] if c in cp.columns], errors='ignore').to_excel(writer, sheet_name="Contas a Pagar", index=False)
                cr.drop(columns=[c for c in ["ID", "SB_ID"] if c in cr.columns], errors='ignore').to_excel(writer, sheet_name="Contas a Receber", index=False)
            st.download_button("⬇️ Baixar Excel", data=buf.getvalue(),
                file_name=f"Financeiro_{mes_fin.replace('/','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_rel_fin")
        st.dataframe(
            cp.drop(columns=[c for c in ["ID", "SB_ID"] if c in cp.columns], errors='ignore'),
            width='stretch', hide_index=True
        )

    # ── Tab 3: Medições ───────────────────────────────────────────────────
    with tab_med:
        st.markdown("##### Relatório de Medições por Obra")
        obra_med_r = st.selectbox("Obra", obras_lista, key="rel_med_obra")
        df_med_r = st.session_state.medicoes.copy()
        df_med_r = df_med_r[df_med_r["Obra"] == obra_med_r] if not df_med_r.empty else df_med_r
        if df_med_r.empty:
            st.info("Nenhuma medição para esta obra.")
        else:
            st.dataframe(df_med_r.drop(columns=[c for c in ["ID", "SB_ID"] if c in df_med_r.columns], errors='ignore'),
                width='stretch', hide_index=True)
            pct_total = df_med_r["% Medido"].max() if "% Medido" in df_med_r.columns else 0
            st.metric("% Físico Acumulado", f"{pct_total}%")
            if st.button("📥 Gerar BM PDF Consolidado", key="btn_rel_bm"):
                try:
                    from gerar_pdf import gerar_bm
                    pdf = gerar_bm({"obra": obra_med_r, "periodo": "Acumulado", "num_bm": "REL",
                        "pct_acumulado": pct_total, "valor_contrato": 0})
                    st.download_button("⬇️ Baixar BM", data=pdf,
                        file_name=f"BM_{obra_med_r}_Relatorio.pdf", mime="application/pdf", key="dl_rel_bm")
                except Exception as _e_bm:
                    st.error(f"Erro: {_e_bm}")

    # ── Tab 4: RDOs ───────────────────────────────────────────────────────
    with tab_rdo:
        st.markdown("##### Relatório de Diários de Obra")
        rdo_obra = st.selectbox("Obra", ["Todas"] + obras_lista, key="rel_rdo_obra")
        rdo_desde = st.text_input("Data inicial (dd/mm/aaaa)", key="rel_rdo_desde")
        rdo_ate   = st.text_input("Data final (dd/mm/aaaa)",   key="rel_rdo_ate")
        df_rdo_r = st.session_state.rdo.copy()
        if rdo_obra != "Todas":
            df_rdo_r = df_rdo_r[df_rdo_r["Obra"] == rdo_obra]
        if rdo_desde and rdo_ate:
            try:
                mask = (df_rdo_r["Data"] >= rdo_desde) & (df_rdo_r["Data"] <= rdo_ate)
                df_rdo_r = df_rdo_r[mask]
            except Exception:
                pass
        if df_rdo_r.empty:
            st.info("Nenhum RDO encontrado.")
        else:
            st.dataframe(df_rdo_r[["Obra", "Data", "Responsável", "Status Dia", "Efetivo Total", "Clima Manhã", "Clima Tarde"]],
                width='stretch', hide_index=True)
            st.metric("Total de RDOs", len(df_rdo_r))

    # ── Tab 5: NCs ────────────────────────────────────────────────────────
    with tab_ncs:
        st.markdown("##### Relatório de Não-Conformidades")
        obra_nc = st.selectbox("Obra", ["Todas"] + obras_lista, key="rel_nc_obra")
        df_nc_r = st.session_state.ncs.copy()
        if obra_nc != "Todas":
            df_nc_r = df_nc_r[df_nc_r["Obra"] == obra_nc]
        if df_nc_r.empty:
            st.info("Nenhuma NC registrada.")
        else:
            ab = len(df_nc_r[df_nc_r["Status"] == "Aberta"]) if "Status" in df_nc_r.columns else 0
            st.metric("NCs Abertas", ab)
            st.dataframe(df_nc_r.drop(columns=[c for c in ["ID", "SB_ID"] if c in df_nc_r.columns], errors='ignore'),
                width='stretch', hide_index=True)
            if st.button("📥 Gerar PDF de NCs", key="btn_rel_nc_pdf"):
                try:
                    from gerar_pdf import gerar_relatorio_nc
                    pdf = gerar_relatorio_nc({"obra": obra_nc}, df_nc_r.to_dict("records"))
                    st.download_button("⬇️ Baixar PDF", data=pdf,
                        file_name=f"NCs_{obra_nc.replace(' ','_')}.pdf", mime="application/pdf", key="dl_rel_nc")
                except Exception as _e_nc:
                    st.error(f"Erro: {_e_nc}")


# ── Notificações ──────────────────────────────────────────────────────────────

def pagina_notificacoes():
    st.title("🔔 Notificações")
    _init()
    _show_toast()

    _al_cache = st.session_state.get("_alertas_cache", {"vencimentos": [], "ncs_abertas": [], "estoque_critico": []})
    n_venc = len(_al_cache.get("vencimentos", []))
    n_nc   = len(_al_cache.get("ncs_abertas", []))
    n_est  = len(_al_cache.get("estoque_critico", []))
    total  = n_venc + n_nc + n_est

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Alertas", total, delta_color="inverse" if total else "normal")
    c2.metric("Contas a Vencer", n_venc, delta_color="inverse" if n_venc else "normal")
    c3.metric("NCs Abertas (+30d)", n_nc, delta_color="inverse" if n_nc else "normal")
    c4.metric("Estoque Crítico", n_est, delta_color="inverse" if n_est else "normal")

    st.markdown("---")

    tab_venc, tab_nc, tab_est, tab_config = st.tabs(["💸 Vencimentos", "🔴 NCs Abertas", "📦 Estoque", "⚙️ Config"])

    with tab_venc:
        if not _al_cache["vencimentos"]:
            st.success("Nenhuma conta a vencer nos próximos 7 dias.")
        else:
            for v in sorted(_al_cache["vencimentos"], key=lambda x: x["dias"]):
                cor = "🔴" if v["dias"] < 0 else "🟡"
                with st.container(border=True):
                    cc1, cc2 = st.columns([3, 1])
                    cc1.markdown(f"**{cor} {v['obra']}** — {v['descricao']}")
                    cc2.markdown(f"**{v['valor']}**  \n{v['status']}", help=f"Vencimento: {v['vencimento']}")

    with tab_nc:
        if not _al_cache["ncs_abertas"]:
            st.success("Nenhuma NC aberta há mais de 30 dias.")
        else:
            for nc in _al_cache["ncs_abertas"]:
                with st.container(border=True):
                    st.markdown(f"**🔴 {nc['obra']}** — {nc['descricao']}  \nGravidade: `{nc['gravidade']}` | {nc['dias']} dias em aberto")

    with tab_est:
        if not _al_cache["estoque_critico"]:
            st.success("Nenhum insumo em estoque crítico.")
        else:
            for e in _al_cache["estoque_critico"]:
                with st.container(border=True):
                    st.markdown(f"**📦 {e['insumo']}** — {e['obra']}  \nSaldo: `{e['saldo']}` / Mínimo: `{e['minimo']}`")

    with tab_config:
        st.markdown("##### Disparo de Notificações por Email")
        st.caption("Configurado via variáveis de ambiente (ALERT_EMAIL_FROM, ALERT_EMAIL_PASSWORD, ALERT_EMAIL_TO)")
        from_env = os.environ.get("ALERT_EMAIL_TO", "não configurado")
        st.code(f"Destinatário: {from_env}", language="text")
        re1, re2 = st.columns(2)
        if re1.button("📧 Enviar resumo de alertas agora", type="primary", key="notif_send"):
            try:
                import alertas as _alrt_s
                ok = _alrt_s.enviar_resumo_alertas(_al_cache)
                if ok:
                    st.success("✅ Email enviado!")
                else:
                    st.warning("Nenhum alerta ou erro no envio.")
            except Exception as _e_s:
                st.error(f"❌ {_e_s}")
        if re2.button("🔄 Re-verificar alertas", key="notif_recheck"):
            st.session_state["_alertas_verificados"] = False
            st.rerun()


# ── Portal do Contratante ────────────────────────────────────────────────────

def pagina_portal_contratante():
    import plotly.graph_objects as go
    _usr   = st.session_state.get("usuario", {})
    cliente_nome = _usr.get("nome", "Contratante")

    st.markdown(
        f'<h2 style="color:#1B3A5E;margin-bottom:4px;">🏢 Portal do Contratante</h2>'
        f'<p style="color:#6B7280;margin-top:0;">Bem-vindo(a), <b>{cliente_nome}</b> — acompanhe suas obras em tempo real.</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Obras do contratante (filtradas por usuario_obras_ids)
    obras = _obras_filtradas(st.session_state.get("obras", pd.DataFrame()))
    if obras.empty:
        st.info("Nenhuma obra vinculada à sua conta. Fale com o responsável da construtora.")
        return

    # ── Cards de obras ───────────────────────────────────────────────────────
    st.subheader("Suas Obras")
    cor_status = {"Em andamento": "#2AACA0", "Concluída": "#22c55e",
                  "Paralisada": "#f59e0b", "Planejamento": "#6366f1"}
    cols = st.columns(min(len(obras), 3))
    for i, (_, obra) in enumerate(obras.iterrows()):
        col = cols[i % 3]
        pct = float(obra.get("% Físico", 0) or 0)
        status = obra.get("Status", "")
        cor = cor_status.get(status, "#6B7280")
        val_contrato = obra.get("Valor Contrato (R$)", 0) or 0
        col.markdown(
            f'<div style="background:#fff;border-radius:12px;padding:18px 16px 14px;'
            f'border-left:4px solid {cor};box-shadow:0 2px 8px rgba(0,0,0,0.07);margin-bottom:12px;">'
            f'<div style="font-size:15px;font-weight:700;color:#1B3A5E;margin-bottom:6px;">{obra.get("Nome","")}</div>'
            f'<div style="font-size:12px;color:{cor};font-weight:600;margin-bottom:10px;">● {status}</div>'
            f'<div style="background:#EDE8DF;border-radius:4px;height:8px;margin-bottom:6px;">'
            f'<div style="background:{cor};width:{pct:.0f}%;height:8px;border-radius:4px;"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#6B7280;">'
            f'<span>Físico: <b style="color:#1B3A5E">{pct:.0f}%</b></span>'
            f'<span>Contrato: <b style="color:#1B3A5E">R$ {val_contrato:,.0f}</b></span></div>'
            f'<div style="font-size:11px;color:#9CA3AF;margin-top:6px;">'
            f'📍 {obra.get("Endereço","")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Seletor de obra para detalhes ────────────────────────────────────────
    nomes_obras = obras["Nome"].tolist()
    obra_sel_nome = st.selectbox("Ver detalhes da obra:", nomes_obras, key="portal_obra_sel")
    obra_sel = obras[obras["Nome"] == obra_sel_nome].iloc[0]
    sb_id_sel = obra_sel.get("SB_ID", None)

    tab_prog, tab_med, tab_rdo, tab_contato = st.tabs(
        ["Progresso", "Medi​ções", "Di​ário de Obra", "Contato"]
    )

    # helper: detecta coluna de valor nas medicoes
    def _col_val_med(df):
        for c in df.columns:
            if "valor" in c.lower():
                return c
        return None

    # helper: grafico moderno barras + linha acumulada
    def _grafico_medicoes(df_med, x_col, val_col):
        df = df_med.copy()
        df[val_col] = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
        df = df.sort_values(x_col)
        df["_acum"] = df[val_col].cumsum()
        n = len(df)
        cores = ["#A8DDD9" if i < n - 1 else "#2AACA0" for i in range(n)]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df[x_col], y=df[val_col],
            name="Valor medido",
            marker=dict(color=cores, cornerradius=6),
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df["_acum"],
            name="Acumulado",
            mode="lines+markers",
            line=dict(color="#1B3A5E", width=2.5),
            marker=dict(size=8, color="#1B3A5E", symbol="circle",
                        line=dict(width=2, color="#fff")),
            hovertemplate="<b>Acumulado</b><br>R$ %{y:,.0f}<extra></extra>",
            yaxis="y2",
        ))
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12, color="#374151"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11)),
            hovermode="x unified",
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis=dict(title="R$ / medição", gridcolor="#F3F4F6",
                       tickformat=",.0f", tickprefix="R$ "),
            yaxis2=dict(title="Acumulado", overlaying="y", side="right",
                        tickformat=",.0f", tickprefix="R$ ", gridcolor="rgba(0,0,0,0)"),
            bargap=0.25,
        )
        return fig

    # ── Aba Progresso ─────────────────────────────────────────────────────────
    with tab_prog:
        pct = float(obra_sel.get("% Físico", 0) or 0)
        inicio   = obra_sel.get("Início", "—")
        termino  = obra_sel.get("Término", "—")
        status   = obra_sel.get("Status", "—")
        resp     = obra_sel.get("Responsável", "—")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Progresso Fisico", f"{pct:.0f}%")
        c2.metric("Status",           status)
        c3.metric("Data Inicio",      inicio)
        c4.metric("Prev. Entrega",    termino)

        st.markdown(f"**Responsável técnico:** {resp}")

        # Barra de progresso visual
        st.markdown(
            f'<div style="margin:16px 0 4px;font-size:13px;font-weight:600;color:#1B3A5E;">'
            f'Execução física: {pct:.0f}%</div>'
            f'<div style="background:#EDE8DF;border-radius:8px;height:18px;">'
            f'<div style="background:linear-gradient(90deg,#2AACA0,#1B8A80);width:{pct:.0f}%;height:18px;'
            f'border-radius:8px;display:flex;align-items:center;padding-left:8px;">'
            f'<span style="color:#fff;font-size:11px;font-weight:700;">{pct:.0f}%</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

        # Grafico de medicoes
        meds = st.session_state.get("medicoes", pd.DataFrame())
        if not meds.empty and "Obra" in meds.columns:
            meds_obra = meds[meds["Obra"] == obra_sel_nome].copy()
        else:
            meds_obra = pd.DataFrame()

        st.markdown("**Evolução das medições**")
        if meds_obra.empty:
            st.info("Nenhuma medição registrada para esta obra ainda.")
        else:
            cv = _col_val_med(meds_obra)
            x_col = "Data" if "Data" in meds_obra.columns else meds_obra.columns[0]
            if cv:
                st.plotly_chart(_grafico_medicoes(meds_obra, x_col, cv),
                                width='stretch', key=f"chart_prog_{obra_sel_nome}")

    # ── Aba Medicoes ──────────────────────────────────────────────────────────
    with tab_med:
        meds = st.session_state.get("medicoes", pd.DataFrame())
        val_contrato = float(obra_sel.get("Valor Contrato (R$)", 0) or 0)
        if not meds.empty and "Obra" in meds.columns:
            meds_obra_m = meds[meds["Obra"] == obra_sel_nome].copy()
        else:
            meds_obra_m = pd.DataFrame()

        if meds_obra_m.empty:
            st.info("Nenhuma medição registrada para esta obra ainda.")
        else:
            col_val = _col_val_med(meds_obra_m)
            if col_val:
                meds_obra_m[col_val] = pd.to_numeric(meds_obra_m[col_val], errors="coerce").fillna(0)
                total_medido = meds_obra_m[col_val].sum()
                pct_fin = (total_medido / val_contrato * 100) if val_contrato else 0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Valor do Contrato",  f"R$ {val_contrato:,.2f}".replace(",","X").replace(".",",").replace("X","."))
                m2.metric("Total Medido",        f"R$ {total_medido:,.2f}".replace(",","X").replace(".",",").replace("X","."))
                m3.metric("% Físico",             f"{float(obra_sel.get('% Físico',0)):.0f}%")
                m4.metric("% Financeiro",         f"{pct_fin:.1f}%")

                # BM PDF
                ult_pct = float(meds_obra_m.iloc[-1].get("% Medido", pct_fin))
                if st.button("📥 Baixar BM em PDF", key=f"portal_bm_{obra_sel_nome}"):
                    try:
                        from gerar_pdf import gerar_bm as _portal_bm
                        _pdf_bm = _portal_bm({"obra": obra_sel_nome, "periodo": "Acumulado",
                            "num_bm": "001", "pct_acumulado": ult_pct, "valor_contrato": val_contrato})
                        st.download_button("⬇️ Baixar BM PDF", data=_pdf_bm,
                            file_name=f"BM_{obra_sel_nome}.pdf", mime="application/pdf",
                            key=f"dl_portal_bm_{obra_sel_nome}")
                    except Exception as _e_bm_portal:
                        st.caption(f"BM indisponível: {_e_bm_portal}")

                x_col = "Data" if "Data" in meds_obra_m.columns else meds_obra_m.columns[0]
                st.plotly_chart(_grafico_medicoes(meds_obra_m, x_col, col_val),
                                width='stretch', key=f"chart_med_{obra_sel_nome}")
                st.markdown("---")

            colunas_pub = [c for c in meds_obra_m.columns
                           if c not in ("SB_ID", "ID") and "bdi" not in c.lower()]
            st.dataframe(meds_obra_m[colunas_pub], width='stretch', hide_index=True)

    # ── Aba Diário de Obra ────────────────────────────────────────────────────
    with tab_rdo:
        rdos = st.session_state.get("rdo", pd.DataFrame())
        if not rdos.empty and "Obra" in rdos.columns:
            rdos_obra = rdos[rdos["Obra"] == obra_sel_nome].copy()
        else:
            rdos_obra = pd.DataFrame()

        if rdos_obra.empty:
            st.info("Nenhum registro diário para esta obra ainda.")
        else:
            rdos_obra = rdos_obra.sort_values("Data", ascending=False) if "Data" in rdos_obra.columns else rdos_obra
            for _, rdo_row in rdos_obra.head(5).iterrows():
                with st.expander(f"📋 {rdo_row.get('Data','—')} — {rdo_row.get('Status Dia','Normal')}"):
                    ca, cb = st.columns(2)
                    ca.markdown(f"**Clima Manhã:** {rdo_row.get('Clima Manhã','—')}")
                    cb.markdown(f"**Clima Tarde:** {rdo_row.get('Clima Tarde','—')}")
                    ca.markdown(f"**Efetivo:** {rdo_row.get('Efetivo Total', 0)} pessoas")
                    cb.markdown(f"**Responsável:** {rdo_row.get('Responsável','—')}")
                    if rdo_row.get("Atividades"):
                        st.markdown(f"**Atividades:** {rdo_row['Atividades']}")
                    if rdo_row.get("Ocorrências"):
                        st.markdown(f"**Ocorrências:** {rdo_row['Ocorrências']}")
                    # Fotos
                    fotos = rdo_row.get("fotos", []) or rdo_row.get("Fotos", [])
                    if isinstance(fotos, list) and fotos:
                        st.markdown("**Fotos:**")
                        fcols = st.columns(min(len(fotos), 4))
                        for fi, foto in enumerate(fotos[:4]):
                            url = foto.get("url", "") if isinstance(foto, dict) else str(foto)
                            if url:
                                fcols[fi].image(url, width='stretch')

    # ── Aba Contato ───────────────────────────────────────────────────────────
    with tab_contato:
        resp = obra_sel.get("Responsável", "—")
        st.markdown(f"""
**Responsável pela obra:** {resp}

**Construtora:** MBR Engenharia

Para dúvidas ou solicitações, entre em contato diretamente com o responsável técnico da sua obra.
        """)
        st.info("📧 Em breve: envio de mensagens direto pelo portal.")


# ── Layout principal ──────────────────────────────────────────────────────────

def _apply_css():
    # Define lang=pt-BR para impedir que o Chrome auto-translate sobreponha textos
    st.markdown(
        '<script>document.documentElement.lang="pt-BR";'
        'document.documentElement.setAttribute("translate","no");</script>',
        unsafe_allow_html=True,
    )
    # Paleta Prumo Modelo 3:
    # Navy Blue  #1B3A5E  — sidebar, títulos
    # Blue-Green #2AACA0  — acento, botões, valores
    # Concrete   #A0A8B0  — texto secundário
    # Background #F4F6F8  — fundo do app
    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

        /* ── Global ── */
        html, body, [class*="css"], [class*="st-"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }
        .stApp { background-color: #F4F6F8; }
        .main .block-container {
            padding-top: 1.8rem !important;
            padding-bottom: 2rem !important;
            max-width: 1400px !important;
        }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
        /* Icones Material Symbols (sidebar, expanders, uploads etc.) — o span interno
           [data-testid="stIconMaterial"] tem classe "st-emotion-cache-xxx" que casa com
           [class*="st-"] acima; mirar so o botao pai nao bastava porque o span filho
           casava com a mesma regra global e vencia por estar mais proximo do elemento.
           especificidade html+attr (0,1,1) vence [class*="st-"] (0,1,0). */
        html [data-testid="stIconMaterial"] {
            font-family: 'Material Symbols Rounded' !important;
            font-feature-settings: 'liga' 1 !important;
            -webkit-font-feature-settings: 'liga' 1 !important;
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
        }
        html [data-testid="stBaseButton-headerNoPadding"] {
            visibility: visible !important;
        }
        /* Cor padrao do icone (cinza 60%) fica quase invisivel no fundo navy da sidebar */
        html [data-testid="stBaseButton-headerNoPadding"] [data-testid="stIconMaterial"] {
            color: rgba(255,255,255,0.85) !important;
        }
        /* Botao de REABRIR a sidebar quando colapsada — fica dentro do <header>,
           que escondemos globalmente (header{visibility:hidden}); sem isso, depois
           de colapsar a sidebar nao ha como abri-la de novo. */
        html [data-testid="stExpandSidebarButton"] {
            visibility: visible !important;
            position: fixed !important;
            top: 12px !important;
            left: 12px !important;
            z-index: 999999 !important;
        }
        html [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
            color: #1B3A5E !important;
        }

        /* ── Títulos — Space Grotesk para hierarquia visual distinta do corpo/dados ── */
        h1, h2, h3, h4,
        [data-testid="stMetricValue"],
        .prumo-brand {
            font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        }
        h1 {
            color: #1B3A5E !important;
            font-weight: 700 !important;
            font-size: 1.6rem !important;
            letter-spacing: -0.4px;
            margin-bottom: 1.3rem !important;
        }
        h2, h3 { color: #1B3A5E !important; font-weight: 600 !important; letter-spacing: -0.2px; }
        h4 { color: #1B3A5E !important; font-weight: 600 !important; font-size: 1.05rem !important; }

        /* ── Métricas ── */
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: none;
            border-radius: 12px;
            padding: 20px !important;
            box-shadow: 0 2px 10px rgba(27,58,94,0.08);
            border-left: 4px solid #2AACA0;
            transition: box-shadow 0.2s, transform 0.2s;
        }
        [data-testid="stMetric"]:hover {
            box-shadow: 0 6px 20px rgba(42,172,160,0.15);
            transform: translateY(-2px);
        }
        [data-testid="stMetricValue"] { letter-spacing: -0.3px; }
        [data-testid="stMetric"] label {
            color: #A0A8B0 !important;
            font-size: 10px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        [data-testid="stMetricValue"] {
            color: #2AACA0 !important;
            font-size: 1.7rem !important;
            font-weight: 800 !important;
        }
        [data-testid="stMetricDelta"] { font-size: 12px !important; font-weight: 600 !important; }
        [data-testid="stMetricValue"] { white-space:nowrap !important; overflow:visible !important; }
        [data-testid="stMetricLabel"] { white-space:nowrap !important; overflow:visible !important; }
        div[data-testid="metric-container"] { overflow:visible !important; }

        /* ── Botões primários ── */
        button[kind="primary"] {
            background: #2AACA0 !important;
            border: none !important;
            color: #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            letter-spacing: 0.3px;
            box-shadow: 0 2px 8px rgba(42,172,160,0.30) !important;
            transition: all 0.2s !important;
        }
        button[kind="primary"]:hover {
            background: #23948A !important;
            box-shadow: 0 4px 14px rgba(42,172,160,0.40) !important;
            transform: translateY(-1px) !important;
        }

        /* ── Botões secundários ── */
        button[kind="secondary"] {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            border-color: #D0D5DC !important;
            color: #1B3A5E !important;
        }
        button[kind="secondary"]:hover {
            border-color: #2AACA0 !important;
            color: #2AACA0 !important;
            background: #F0FAF9 !important;
        }

        /* ── Abas ── */
        [data-testid="stTabs"] button[role="tab"] {
            font-weight: 600;
            font-size: 13px;
            color: #A0A8B0 !important;
            padding: 10px 18px !important;
            border-radius: 0 !important;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: #1B3A5E !important;
            border-bottom: 3px solid #2AACA0 !important;
            font-weight: 700 !important;
            background: transparent !important;
        }

        /* ── Alertas ── */
        [data-testid="stAlert"] { border-radius: 8px !important; font-size: 14px !important; }

        /* ── Tabelas ── */
        [data-testid="stDataFrameResizable"] th {
            background-color: #EEF1F5 !important;
            color: #1B3A5E !important;
            font-weight: 700 !important;
            font-size: 11px !important;
            text-transform: uppercase;
            letter-spacing: 0.7px;
            border-bottom: 2px solid #D8DDE5 !important;
        }
        [data-testid="stDataFrameResizable"] tr:hover td {
            background-color: #F0FAF9 !important;
        }

        /* ── Expanders ── */
        [data-testid="stExpander"] {
            border: 1px solid #E0E5EB !important;
            border-radius: 10px !important;
            background: #FFFFFF;
        }



        /* ── File uploader — substitui texto do botao por CSS (Chrome nao traduz content:) ── */
        [data-testid="stFileUploaderDropzone"] input[type="file"]::-webkit-file-upload-button,
        [data-testid="stFileUploaderDropzone"] input[type="file"]::file-selector-button {
            display: none !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            color: transparent !important;
            font-size: 0 !important;
            position: relative !important;
        }
        [data-testid="stFileUploaderDropzone"] button::after {
            content: "Carregar" !important;
            font-size: 14px !important;
            color: #1B3A5E !important;
            font-weight: 500 !important;
            font-family: 'Inter', sans-serif !important;
            position: absolute !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            white-space: nowrap !important;
        }

        /* ── Inputs ── */
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input {
            border-radius: 6px !important;
            border-color: #D0D5DC !important;
            font-size: 14px !important;
        }
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus {
            border-color: #2AACA0 !important;
            box-shadow: 0 0 0 3px rgba(42,172,160,0.12) !important;
        }

        /* ── Sidebar — Navy Blue do Modelo 3 ── */
        section[data-testid="stSidebar"] > div:first-child {
            background: #1B3A5E !important;
        }
        /* Itens do menu — transparentes por padrão (sem caixa/borda), só um leve
           realce no hover e um tom sutil no item ativo (referência: MBR_ERP_Prototipo.html) */
        section[data-testid="stSidebar"] button[kind="secondary"] {
            background: transparent !important;
            border: none !important;
            color: rgba(255,255,255,0.88) !important;
            border-radius: 7px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            transition: all 0.15s !important;
        }
        section[data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: rgba(255,255,255,0.08) !important;
            color: #FFFFFF !important;
        }
        section[data-testid="stSidebar"] button[kind="primary"] {
            background: rgba(42,172,160,0.18) !important;
            border: none !important;
            color: #2AACA0 !important;
            border-radius: 7px !important;
            font-weight: 600 !important;
            box-shadow: none !important;
        }
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown span,
        section[data-testid="stSidebar"] caption {
            color: #B9C6D6 !important;
            font-size: 12px !important;
        }
        hr { border-color: rgba(255,255,255,0.08) !important; }

        /* ── Dashboard cards ── */
        .dash-card {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px 20px 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(27,58,94,0.08);
            border: 1px solid #E8ECF0;
        }
        .dash-card-header {
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            font-weight: 600;
            font-size: 14px;
            color: #1B3A5E;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #EDF0F5;
            letter-spacing: -0.2px;
        }
        .dash-card-nav {
            display: flex; gap: 8px; flex-wrap: wrap;
            padding: 2px 0;
        }
        .dash-kpi-row { display: contents; }
        .dash-kpi-row [data-testid="column"]:nth-child(1) [data-testid="stMetric"] { border-left-color: #2B59C3; }
        .dash-kpi-row [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { border-left-color: #27AE60; }
        .dash-kpi-row [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-left-color: #E67E22; }
        .dash-kpi-row [data-testid="column"]:nth-child(4) [data-testid="stMetric"] { border-left-color: #2AACA0; }
        .dash-kpi-row [data-testid="column"]:nth-child(5) [data-testid="stMetric"] { border-left-color: #E74C3C; }
        .dash-empty {
            color: #A0A8B0;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 0;
            margin: 0;
        }
    </style>""", unsafe_allow_html=True)


def app():
    # ── Autenticação ─────────────────────────────────────────────────────────
    if "usuario" not in st.session_state:
        _auth_login()
        st.stop()

    # ── Pós-login: admin escolhe App ou Dev; demais vão direto pro App ────
    if "modo" not in st.session_state:
        if _role() == "admin":
            _pos_login_choice()
            st.stop()
        st.session_state.modo = "app"
        st.session_state.pagina_atual = "Principal"

    _apply_css()

    st.sidebar.markdown(
        """<style>
            section[data-testid="stSidebar"] div.st-emotion-cache-16q97a3,
            section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"],
            section[data-testid="stSidebar"] ul[data-testid="stSidebarNavItems"],
            div[data-testid="stSidebarNav"] {
                display:none !important; height:0px !important;
                opacity:0 !important; visibility:hidden !important;
            }
        </style>""",
        unsafe_allow_html=True,
    )
    _usr = st.session_state.get("usuario", {})
    st.sidebar.markdown(
        f"""<div style='padding:20px 14px 16px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:6px;'>
            <div style='margin-bottom:16px;'>
                <div class='prumo-brand' style='font-size:21px;font-weight:700;color:#FFFFFF;letter-spacing:-0.5px;line-height:1;'>
                    PRUMO<span style='font-size:11px;font-weight:600;color:#2AACA0;margin-left:3px;vertical-align:super;'>ERP</span>
                </div>
                <div style='font-size:9px;color:#B9C6D6;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;margin-top:4px;'>Software de Construção Civil</div>
                <div style='width:28px;height:2px;background:#2AACA0;border-radius:1px;margin-top:8px;'></div>
            </div>
            <div style='display:flex;align-items:center;gap:9px;background:rgba(255,255,255,0.05);
                        border-radius:8px;padding:9px 11px;border:1px solid rgba(255,255,255,0.08);'>
                <div style='width:30px;height:30px;background:#2AACA0;
                            border-radius:50%;display:flex;align-items:center;justify-content:center;
                            font-size:14px;flex-shrink:0;'>👤</div>
                <div>
                    <div style='color:#E8EFF5;font-size:13px;font-weight:600;line-height:1;'>{_usr.get('nome','Usuário')}</div>
                    <div style='color:#2AACA0;font-size:10px;margin-top:3px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;'>{_role().capitalize()}</div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Menu filtrado por role ────────────────────────────────────────────────
    if _role() == "contratante":
        _MENU = {"Minhas Obras": ("🏢", ["portal"])}
    else:
        _MENU = {
            "Principal":          ("🏠", ["dashboard"]),
            "Obras":              ("🏗️", ["obras"]),
            "Medição":            ("📏", ["obras"]),
            "Suprimentos":        ("📦", ["suprimentos"]),
            "Financeiro":         ("💰", ["financeiro"]),
            "Pessoal":            ("👥", ["pessoal", "ponto", "folha"]),
            "Qualidade":          ("✅", ["qualidade"]),
            "Diário de Obra":     ("📋", ["rdo"]),
            "Relatórios":         ("📄", ["dashboard", "obras", "financeiro", "pessoal", "qualidade", "rdo"]),
            "Notificações":       ("🔔", ["dashboard", "obras", "financeiro", "qualidade", "suprimentos"]),
            "Orçamento":          ("📊", ["orcamento"]),
            "Planejamento (EAP)": ("📅", ["obras"]),
            "Administração":      ("⚙️", ["admin"]),
        }
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = "Principal"
    if not _pode(_MENU.get(st.session_state.pagina_atual, ("", ["dashboard"]))[1]):
        st.session_state.pagina_atual = "Principal"
    for pag, (emoji, mods) in _MENU.items():
        if not _pode(mods):
            continue
        tipo = "primary" if st.session_state.pagina_atual == pag else "secondary"
        if st.sidebar.button(f"{emoji} {pag}", width='stretch', type=tipo):
            st.session_state.pagina_atual = pag
            st.rerun()
    st.sidebar.markdown("---")
    if _role() == "admin" and st.session_state.get("modo") == "dev":
        tipo_dev = "primary" if st.session_state.pagina_atual == "Desenvolvedor" else "secondary"
        if st.sidebar.button("🛠️ Desenvolvedor", width='stretch', type=tipo_dev):
            st.session_state.pagina_atual = "Desenvolvedor"
            st.rerun()
    _total_al_sb = (len(st.session_state.get("_alertas_cache", {}).get("vencimentos", [])) +
                    len(st.session_state.get("_alertas_cache", {}).get("ncs_abertas", [])) +
                    len(st.session_state.get("_alertas_cache", {}).get("estoque_critico", [])))
    if _total_al_sb > 0:
        st.sidebar.warning(f"⚠️ {_total_al_sb} alerta(s) ativo(s)")
    st.sidebar.caption("🔗 Banco de Dados: Supabase ☁️")
    st.sidebar.caption(f"📅 Hoje: {date.today().strftime('%d/%m/%Y')}")
    if st.sidebar.button("🔄 Atualizar dados", key="btn_refresh", width='stretch'):
        # Preserva autenticação mas força reload dos dados
        _auth_keys = {k: st.session_state[k] for k in ["usuario","usuario_role","usuario_obras_ids","empresa_id"] if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(_auth_keys)
        st.rerun()
    if st.sidebar.button("🚪 Sair", key="btn_logout", width='stretch'):
        for k in ["usuario", "usuario_role", "usuario_obras_ids", "_erp_init_done"]:
            st.session_state.pop(k, None)
        try:
            from db import sb
            sb().auth.sign_out()
        except Exception:
            pass
        st.rerun()

    p = st.session_state.pagina_atual
    try:
        if   p == "Minhas Obras":       pagina_portal_contratante()
        elif p == "Principal":          pagina_dashboard()
        elif p == "Obras":              pagina_obras()
        elif p == "Medição":            pagina_medicao()
        elif p == "Suprimentos":        pagina_suprimentos()
        elif p == "Financeiro":         pagina_financeiro()
        elif p == "Pessoal":            pagina_pessoal()
        elif p == "Qualidade":          pagina_qualidade()
        elif p == "Diário de Obra":     pagina_rdo()
        elif p == "Relatórios":         pagina_relatorios()
        elif p == "Notificações":       pagina_notificacoes()
        elif p == "Orçamento":          pagina_orcamento()
        elif p == "Planejamento (EAP)": pagina_eap()
        elif p == "Administração":      pagina_admin()
        elif p == "Desenvolvedor":       pagina_dev_panel()
    except st.runtime.scriptrunner.RerunException:
        raise  # deixa st.rerun() funcionar normalmente
    except Exception as _page_err:
        import traceback as _tb
        st.error(f"⚠️ Erro inesperado: {_page_err}")
        with st.expander("Detalhes técnicos"):
            st.code(_tb.format_exc())
        print(f"[app] Erro em página '{p}': {_tb.format_exc()}")

pg = st.navigation([st.Page(app, title="Prumo ERP", default=True)], position="hidden")
pg.run()
