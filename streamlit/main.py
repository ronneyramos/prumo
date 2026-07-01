import os
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import io
import unicodedata
import importlib
import sync
importlib.reload(sync)  # garante versão atualizada a cada reload do Streamlit

st.set_page_config(page_title="Prumo ERP", layout="wide", page_icon="🏗️")

# ── Inicialização do estado ───────────────────────────────────────────────────

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
    rows = st.session_state.obras[st.session_state.obras["Nome"] == obra_nome]
    return _sb_id(st.session_state.obras, rows["ID"].iloc[0]) if len(rows) else None


def _init():
    # ── Carrega do Supabase na primeira vez que a sessão é aberta ──────────────
    if not st.session_state.get("_erp_init_done"):
        if _supabase_ok():
            try:
                st.session_state.obras          = sync.obras_load()
                st.session_state.contas_pagar   = sync.lancamentos_load("PAGAR")
                st.session_state.contas_receber = sync.lancamentos_load("RECEBER")
                st.session_state.funcionarios   = sync.colaboradores_load()
                st.session_state.ncs            = sync.ncs_load()
                st.session_state.medicoes       = sync.medicoes_load()
                st.session_state.ponto          = sync.faltas_load()
                st.session_state.rdo            = sync.rdo_load()
            except Exception as _e:
                print(f"[_init] Erro ao carregar dados do Supabase: {_e}")
        st.session_state._erp_init_done = True

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

    # ── Módulos ainda em memória (sem Supabase por ora) ───────────────────────
    if "estoque" not in st.session_state:
        st.session_state.estoque = pd.DataFrame({
            "ID": [1,2,3,4,5,6],
            "Insumo": ["Cimento CP-II (sc 50kg)","Aço CA-50 Ø10mm","Areia lavada média","Brita nº 1","Tijolo cerâmico 9x19x19","Piso porcelanato 60x60"],
            "Unidade": ["sc","kg","m³","m³","mil","m²"],
            "Estoque Atual": [120.0,3500.0,45.0,30.0,8.5,200.0],
            "Estoque Mínimo": [50.0,1000.0,15.0,10.0,2.0,50.0],
            "Obra": ["Residencial Beira Mar","Residencial Beira Mar","Comercial Centro","Comercial Centro","Condomínio Sol Nascente","Condomínio Sol Nascente"],
        })
    if "movimentacoes" not in st.session_state:
        st.session_state.movimentacoes = pd.DataFrame({
            "ID": [1,2,3,4,5],
            "Data": ["10/06/2026","12/06/2026","15/06/2026","18/06/2026","20/06/2026"],
            "Tipo": ["Entrada","Saída","Entrada","Saída","Entrada"],
            "Insumo": ["Cimento CP-II (sc 50kg)","Aço CA-50 Ø10mm","Brita nº 1","Areia lavada média","Tijolo cerâmico 9x19x19"],
            "Quantidade": [100.0,500.0,20.0,10.0,3.0],
            "Obra": ["Residencial Beira Mar","Residencial Beira Mar","Comercial Centro","Comercial Centro","Condomínio Sol Nascente"],
            "Responsável": ["Almoxarife João","Mestre Paulo","Almoxarife João","Mestre Paulo","Almoxarife João"],
            "NF/Doc": ["NF-0821","RM-014","NF-0834","RM-015","NF-0843"],
        })
    if "requisicoes" not in st.session_state:
        try:
            from sync import requisicoes_load
            st.session_state.requisicoes = requisicoes_load()
        except Exception:
            st.session_state.requisicoes = pd.DataFrame(columns=[
                "ID","SB_ID","Data","Obra","Insumo","Quantidade",
                "Unidade","Status","Solicitante","Observação","Aprovado Por","Data Aprovação"
            ])
    if "ponto" not in st.session_state:
        st.session_state.ponto = pd.DataFrame(columns=["ID","Data","Funcionário","Obra","Tipo","Observação"])
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
    # Migração: colunas adicionadas em versões posteriores
    if "Tipo Contrato" not in st.session_state.funcionarios.columns:
        st.session_state.funcionarios.insert(3, "Tipo Contrato", "CLT")
    if "Forma Pag." not in st.session_state.contas_pagar.columns:
        st.session_state.contas_pagar["Forma Pag."] = "—"
    if "Categoria" not in st.session_state.contas_pagar.columns:
        st.session_state.contas_pagar["Categoria"] = "Materiais"

    # ── Verificação de alertas (uma vez por sessão) ───────────────────────────
    if not st.session_state.get("_alertas_verificados"):
        try:
            import alertas as _alrt
            _nc_df = st.session_state.get("ncs", pd.DataFrame())
            # ncs usa coluna "Data Abertura"; nao_conformidades é alias
            _al = _alrt.verificar_alertas(
                st.session_state.get("contas_pagar", pd.DataFrame()),
                _nc_df,
                st.session_state.get("estoque", pd.DataFrame()),
            )
            st.session_state["_alertas_cache"] = _al
        except Exception:
            st.session_state["_alertas_cache"] = {"vencimentos": [], "ncs_abertas": [], "estoque_critico": []}
        st.session_state["_alertas_verificados"] = True


def _obras_nomes(extra: list | None = None) -> list:
    """Retorna lista de nomes de obras visíveis ao usuário; nunca vazia (evita crash em selectbox)."""
    df = st.session_state.get("obras", pd.DataFrame())
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

def _to_num(v) -> float:
    """Converte para float aceitando strings R$ 58.000,00 ou numéricos."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def _next_id(df):
    return int(df["ID"].max()) + 1 if len(df) > 0 else 1

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

def _auth_login():
    """Tela de login fiel ao mockup: fundo bege, split, guindaste SVG."""
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background: #EDE8DF !important; }
        .main .block-container {
            max-width: 1080px !important; padding-top: 5vh !important;
            padding-left: 2rem !important; padding-right: 2rem !important;
        }
        /* Inputs com borda teal — igual ao mockup */
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
        /* Botão laranja pill — igual ao mockup */
        button[kind="primary"] {
            background: #F07820 !important; border: none !important;
            border-radius: 8px !important; font-weight: 800 !important;
            font-size: 15px !important; letter-spacing: 2px; text-transform: uppercase;
            box-shadow: 0 4px 14px rgba(240,120,32,0.30) !important;
            transition: background 0.2s !important; height: 48px !important;
        }
        button[kind="primary"]:hover { background: #D9660E !important; }
        /* Card branco do formulário */
        [data-testid="stForm"] {
            background: #FFFFFF !important; border: none !important;
            border-radius: 12px !important; padding: 28px 28px 20px !important;
            box-shadow: 0 2px 24px rgba(27,58,94,0.09) !important;
            margin-bottom: 14px !important;
        }
        /* Remove label nativo do text_input (usamos labels HTML customizados) */
        [data-testid="stTextInput"] label { display: none !important; }
        [data-testid="stTextInput"] { margin-bottom: 2px !important; }
        /* Labels do selectbox no cadastro */
        [data-testid="stSelectbox"] label { font-size: 12px !important; color: #6B7280 !important; }
    </style>""", unsafe_allow_html=True)

    col_form, col_illus = st.columns([1.1, 0.9], gap="large")

    # ─── COLUNA ESQUERDA — Logo + Form ───────────────────────────────────────
    with col_form:
        # Logo com monograma geométrico P
        st.markdown(
        '<div style="display:flex;align-items:center;gap:16px;margin-bottom:2.4rem;">'
        '<svg width="58" height="58" viewBox="0 0 58 58" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 7,52 L 7,7 L 28,7 A 10.5,10.5 0 0 1 28,28 L 7,28"'
        ' stroke="#1B3A5E" stroke-width="6" stroke-linejoin="miter"/>'
        '<path d="M 18,52 L 18,18 L 38,18 A 10,10 0 0 1 38,38 L 18,38"'
        ' stroke="#2AACA0" stroke-width="5" stroke-linejoin="miter"/>'
        '</svg>'
        '<div>'
        '<div style="line-height:1;"><span style="font-size:1.9rem;font-weight:900;color:#1B3A5E;letter-spacing:2px;">PRUMO</span></div>'
        '<div style="font-size:1rem;font-weight:700;color:#2AACA0;letter-spacing:2px;margin-top:1px;">ERP</div>'
        '<div style="font-size:8.5px;color:#A0A8B0;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin-top:3px;">Software de Construção Civil</div>'
        '</div></div>',
        unsafe_allow_html=True)

        if st.session_state.auth_mode == "login":
            # Saudação
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
                entrar = st.form_submit_button("ENTRAR", use_container_width=True, type="primary")

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

            if st.button("Criar conta gratuita →", key="btn_ir_cadastro", use_container_width=False):
                st.session_state.auth_mode = "cadastro"
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
                        role_res = sb().table("user_roles").select("role").eq("user_id", res.user.id).execute()
                        role = role_res.data[0]["role"] if role_res.data else None
                    except Exception:
                        pass
                    if not role:
                        role = meta.get("role") or "admin"
                    st.session_state.usuario_role  = role
                    st.session_state.empresa_id    = meta.get("empresa_id") or "00000000-0000-0000-0000-000000000001"
                    if role in ("engenheiro", "adm_obra", "suprimentos", "qualidade"):
                        try:
                            obras_res = sb().table("usuario_obras").select("obra_id").eq("user_id", res.user.id).execute()
                            st.session_state.usuario_obras_ids = [r["obra_id"] for r in (obras_res.data or [])]
                        except Exception:
                            st.session_state.usuario_obras_ids = []
                    else:
                        st.session_state.usuario_obras_ids = []
                    st.rerun()
                except Exception as e:
                    st.error("Login inválido. Verifique e-mail e senha.")
                    print(f"[auth] erro login: {e}")

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
                nome_usuario = st.text_input("Nome completo")
                email_cad    = st.text_input("E-mail")
                senha_cad    = st.text_input("Senha (mín. 6 caracteres)", type="password")
                nome_empresa = st.text_input("Nome da empresa / construtora")
                cidade_cad   = st.text_input("Cidade", value="Fortaleza")
                estado_cad   = st.selectbox("Estado", ["CE","SP","RJ","MG","BA","PE","RS","SC","PR","GO","DF","AM","PA","MA","PI","RN","PB","AL","SE","ES","MT","MS","RO","AC","RR","AP","TO"])
                cadastrar    = st.form_submit_button("CRIAR CONTA", use_container_width=True, type="primary")
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
                            sb().auth.sign_in_with_password({"email": email_cad, "password": senha_cad})
                            try:
                                rpc_res    = sb().rpc("registrar_empresa", {"p_nome_empresa": nome_empresa, "p_user_id": user_id}).execute()
                                empresa_id = rpc_res.data
                            except Exception as _e_rpc:
                                print(f"[cadastro] RPC: {_e_rpc}")
                                emp_res    = sb().table("empresas").insert({"nome": nome_empresa, "cidade": cidade_cad, "estado": estado_cad}).execute()
                                empresa_id = (emp_res.data[0] if emp_res.data else {}).get("id")
                            st.session_state.usuario           = {"id": user_id, "email": email_cad, "nome": nome_usuario}
                            st.session_state.usuario_role      = "admin"
                            st.session_state.usuario_obras_ids = []
                            st.session_state.empresa_id        = str(empresa_id) if empresa_id else "00000000-0000-0000-0000-000000000001"
                            st.success(f"✅ Bem-vindo(a) à {nome_empresa}!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")
                        print(f"[cadastro] erro: {e}")

    with col_illus:
        import os as _os
        _img_path = _os.path.join(_os.path.dirname(__file__), "static", "building.png")
        st.image(_img_path, use_container_width=True)


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


# ── Dashboard ────────────────────────────────────────────────────────────────

def _dados_obras_dash():
    return pd.DataFrame({
        "obra":           ["Residencial Beira Mar","Comercial Centro","Industrial Lagoa","Condomínio Sol Nascente"],
        "status":         ["Em andamento","Em andamento","Paralisada","Em andamento"],
        "valor_contrato": [2_800_000,1_900_000,950_000,1_750_000],
        "valor_medido":   [1_540_000,760_000,380_000,420_000],
        "pct_fisico":     [55,40,40,24],
    })

def pagina_dashboard():
    st.title("🏠 Dashboard")
    _init()

    # ── Banner de alertas ─────────────────────────────────────────────────────
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
    # ─────────────────────────────────────────────────────────────────────────

    CATS      = ["Materiais", "Folha de Pagamento", "Impostos", "Outros"]
    CAT_CORES = {"Materiais": "#2B59C3", "Folha de Pagamento": "#E67E22",
                 "Impostos": "#E74C3C",  "Outros": "#95A5A6"}
    STATUS_CORES = {"Em andamento": "#2B59C3", "Paralisada": "#E74C3C",
                    "Concluída": "#27AE60", "Planejamento": "#F39C12", "Cancelada": "#95A5A6"}

    obras_df  = st.session_state.obras.copy()
    contas_df = st.session_state.contas_pagar.copy()
    func_df   = st.session_state.funcionarios.copy()
    est_df    = st.session_state.estoque.copy()
    hoje      = date.today()

    # garante coluna numérica de valor e vencimento
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

    tab_geral, tab_obra = st.tabs(["🏢 Visão Geral — Diretoria / Sócios",
                                   "🏗️ Por Obra — Engenharia / Administrativo"])

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1 — VISÃO GERAL
    # ═══════════════════════════════════════════════════════════════════════
    with tab_geral:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Obras Ativas",        str(n_ativas))
        k2.metric("Portfólio Total",     f"R$ {total_contratado/1_000_000:.2f}M")
        k3.metric("Estimativa Medida",   f"R$ {total_medido/1_000:.0f}k",
                  delta=f"{pct_med:.1f}% do portfólio")
        k4.metric("Saldo a Medir",       _fmt(saldo_a_medir),
                  help="Valor Contrato − Total Medido Acumulado (medições registradas)")
        k5.metric("Alertas Financeiros", str(n_alertas),
                  delta="Ação necessária" if n_alertas else "Em dia",
                  delta_color="inverse" if n_alertas else "normal")

        st.markdown("---")
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
                st.info("Nenhuma obra cadastrada.")
        with cb:
            st.subheader("Distribuição do Portfólio")
            if len(obras_df):
                fig_pie = px.pie(obras_df, values="Valor Contrato (R$)", names="Nome",
                                 hole=0.42, color_discrete_sequence=px.colors.qualitative.Set2)
                fig_pie.update_traces(textinfo="percent+label", textposition="outside")
                fig_pie.update_layout(height=max(240, len(obras_df)*50),
                                      showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_pie, width='stretch')

        st.markdown("---")
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
                st.info("Nenhum lançamento financeiro categorizado.")

        st.markdown("---")
        st.subheader("📊 Status das Obras")

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
            st.info("Nenhuma obra cadastrada.")

        st.markdown("---")
        st.subheader("💰 Fluxo de Caixa Mensal")
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
            st.info("Sem lançamentos financeiros para exibir o fluxo de caixa.")

        st.markdown("---")
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

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2 — POR OBRA
    # ═══════════════════════════════════════════════════════════════════════
    with tab_obra:
        obras_lista = obras_df["Nome"].tolist()
        if not obras_lista:
            st.info("Nenhuma obra cadastrada.")
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

        st.markdown("---")
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
                st.info("Sem lançamentos financeiros nesta obra.")

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
                st.info("Nenhum colaborador alocado nesta obra.")

        st.markdown("---")
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
                st.info("Sem contas registradas nesta obra.")

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
                st.info("Sem insumos registrados nesta obra.")

        # Orçamento importado — resumo executivo
        orc = st.session_state.get("orcamento_por_obra", {}).get(obra_sel)
        if orc:
            itens = [r for r in orc if r["tipo"] == "ITEM"]
            if itens:
                st.markdown("---")
                st.subheader("Orçamento Importado — Resumo Executivo")
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

    # ── RELATÓRIO GERENCIAL PDF ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📑 Relatório Gerencial Mensal")
    _rg_c1, _rg_c2 = st.columns([3, 1])
    _mes_ref = _rg_c1.text_input(
        "Mês de referência",
        value=__import__("datetime").date.today().strftime("%B/%Y"),
        key="rg_mes_ref",
        placeholder="Junho/2026",
    )
    if _rg_c2.button("📥 Gerar PDF", key="btn_gerar_rg", type="primary", use_container_width=True):
        try:
            from gerar_pdf import gerar_relatorio_gerencial as _gerar_rg
            _dados_rg = {
                "mes_ref":        _mes_ref,
                "obras":          st.session_state.obras.copy(),
                "medicoes":       st.session_state.medicoes.copy(),
                "contas_pagar":   st.session_state.contas_pagar.copy(),
                "contas_receber": st.session_state.contas_receber.copy(),
                "ncs":            st.session_state.nao_conformidades.copy(),
                "funcionarios":   st.session_state.colaboradores.copy(),
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


# ── Obras ────────────────────────────────────────────────────────────────────

def pagina_obras():
    st.title("🏗️ Obras")
    _init()
    aba = st.radio("Ação",["📋 Listagem","📏 Medições","➕ Nova Obra"],horizontal=True,label_visibility="collapsed")

    if aba == "📋 Listagem":
        obras = st.session_state.obras.copy()
        cf1,cf2 = st.columns(2)
        fs = cf1.selectbox("Status",["Todos"]+sorted(obras["Status"].unique().tolist()))
        fr = cf2.selectbox("Responsável",["Todos"]+sorted(obras["Responsável"].unique().tolist()))
        if fs != "Todos": obras = obras[obras["Status"]==fs]
        if fr != "Todos": obras = obras[obras["Responsável"]==fr]
        st.markdown(f"**{len(obras)} obra(s)**")
        exib = obras.drop(columns=[c for c in ["ID","SB_ID"] if c in obras.columns]).copy()
        exib["Valor Contrato (R$)"] = exib["Valor Contrato (R$)"].apply(_fmt)
        st.dataframe(exib,width='stretch',hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(exib), file_name="obras.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_obras")

        st.markdown("---")
        st.subheader("Editar / Excluir")
        opc = {f"[{r.ID}] {r.Nome}": r.ID for r in st.session_state.obras.itertuples()}
        if not opc:
            st.info("Nenhuma obra cadastrada. Use a aba ➕ Nova Obra.")
            st.stop()
        sel = st.selectbox("Selecione",list(opc.keys()))
        id_sel = opc[sel]
        L = st.session_state.obras[st.session_state.obras["ID"]==id_sel].iloc[0]
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
            except Exception: pass
            st.success(f"✅ Obra **{nome}** atualizada com sucesso!"); st.rerun()
        if excluir:
            _nome_exc = L["Nome"]
            uuid_exc = _sb_id(st.session_state.obras, id_sel)
            st.session_state.obras = st.session_state.obras[st.session_state.obras["ID"]!=id_sel].reset_index(drop=True)
            if uuid_exc: sync.obra_delete(uuid_exc)
            st.success(f"✅ Obra **{_nome_exc}** removida!"); st.rerun()
    elif aba == "📏 Medições":
        st.subheader("Histórico de Medições")
        med_df = st.session_state.medicoes.copy()
        if not med_df.empty:
            obra_f_med = st.selectbox("Filtrar por Obra", ["Todas"] + sorted(med_df["Obra"].unique().tolist()), key="med_filtro_obra")
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
            obras_com_med = sorted(med_df["Obra"].unique().tolist())
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
                        except Exception: pass
                # 3. Conta a Receber
                if valor_med > 0:
                    dados_bm = {"Obra": obra_med, "Cliente": ob_row["Cliente"].iloc[0] if not ob_row.empty else "",
                                "Descrição": f"BM {periodo_med} — {pct_incremento:.1f}% — {obra_med}",
                                "Valor (R$)": valor_med, "Vencimento": venc_med, "Status": "A Receber"}
                    uuid_bm = sync.lancamento_save(dados_bm, "RECEBER", _obra_uuid(obra_med))
                    st.session_state.contas_receber = pd.concat([
                        st.session_state.contas_receber,
                        pd.DataFrame([{"ID": _next_id(st.session_state.contas_receber),
                                       "SB_ID": uuid_bm or "", **dados_bm}])
                    ], ignore_index=True)
                st.success(f"✅ Medição registrada! {obra_med} avançou para **{pct_med_inp:.0f}%** físico. "
                           + (f"Conta a Receber de **{_fmt(valor_med)}** gerada." if valor_med > 0 else ""))
                st.rerun()
    else:
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
            if not nome or not cliente: st.error("Nome e Cliente obrigatórios.")
            else:
                dados_nova = {"Nome":nome,"Tipo":tipo,"Cliente":cliente,"CNPJ Cliente":cnpj,"Endereço":end,"Valor Contrato (R$)":valor,"BDI (%)":bdi,"Início":ini,"Término":term,"% Físico":pct,"Status":stat,"Responsável":resp}
                try:
                    uuid_nova = sync.obra_save(dados_nova)
                except Exception:
                    uuid_nova = None
                st.session_state.obras = pd.concat([st.session_state.obras,pd.DataFrame([{"ID":_next_id(st.session_state.obras),"SB_ID":uuid_nova or "","Nome":nome,"Tipo":tipo,"Cliente":cliente,"CNPJ Cliente":cnpj,"Endereço":end,"Valor Contrato (R$)":valor,"BDI (%)":bdi,"Início":ini,"Término":term,"% Físico":pct,"Status":stat,"Responsável":resp}])],ignore_index=True)
                st.success(f"✅ Obra **{nome}** cadastrada com sucesso!"); st.rerun()


# ── Suprimentos ──────────────────────────────────────────────────────────────

def pagina_suprimentos():
    st.title("📦 Suprimentos")
    _init()
    aba = st.radio("Ação",["📦 Estoque","🔄 Movimentações","📝 Requisições","➕ Movimentar","📋 Entrada de NF"],horizontal=True,label_visibility="collapsed")

    if aba == "📦 Estoque":
        est = st.session_state.estoque.copy()
        est["Situação"] = est.apply(lambda r:"🔴 Abaixo do mínimo" if r["Estoque Atual"]<r["Estoque Mínimo"] else "🟢 OK",axis=1)
        c1,c2,c3 = st.columns(3)
        c1.metric("Insumos Cadastrados",len(est))
        c2.metric("Itens em Alerta",len(est[est["Estoque Atual"]<est["Estoque Mínimo"]]))
        c3.metric("Obras Abastecidas",est["Obra"].nunique())
        st.markdown("---")
        fo = st.selectbox("Obra",["Todas"]+sorted(est["Obra"].unique().tolist()))
        if fo != "Todas": est = est[est["Obra"]==fo]
        _est_exib = est.drop(columns=[c for c in ["ID","SB_ID"] if c in est.columns])
        st.dataframe(_est_exib, width='stretch', hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(_est_exib), file_name="estoque.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_estoque")

    elif aba == "🔄 Movimentações":
        mov = st.session_state.movimentacoes.copy()
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
        obras_req  = ["Todas"] + sorted(req["Obra"].dropna().unique().tolist()) if not req.empty else ["Todas"]
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
        st.dataframe(req_disp[colunas_vis], use_container_width=True, hide_index=True)

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
                    _enviar_email(
                        assunto=f"[Prumo ERP] Requisição Aprovada — {row_req.Insumo}",
                        corpo=(f"Requisição aprovada por {usuario}.\n\n"
                               f"Insumo: {row_req.Insumo}\nQuantidade: {row_req.Quantidade} {row_req.Unidade}\n"
                               f"Obra: {row_req.Obra}\nSolicitante: {row_req.Solicitante}")
                    )
                except Exception:
                    pass
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
        insumos_opcoes = sorted(st.session_state.estoque["Insumo"].dropna().unique().tolist()) if not st.session_state.estoque.empty else []
        with st.form("form_req"):
            c1, c2 = st.columns(2)
            obra_r    = c1.selectbox("Obra",      _obras_nomes(), key="req_obra")
            insumo_r  = c2.selectbox("Insumo",    insumos_opcoes if insumos_opcoes else [""], key="req_insumo")
            qtd_r     = c1.number_input("Quantidade",  min_value=0.01, step=1.0,  value=1.0, key="req_qtd")
            un_r      = c2.text_input("Unidade",  value="un", key="req_un")
            sol_r     = c1.text_input("Solicitante", key="req_sol")
            obs_r     = c2.text_input("Observação",  key="req_obs")
            ok_r      = st.form_submit_button("📝 Enviar Requisição", type="primary")
        if ok_r:
            dados_req = {"Data": date.today().strftime("%d/%m/%Y"), "Obra": obra_r,
                         "Insumo": insumo_r, "Quantidade": qtd_r, "Unidade": un_r,
                         "Solicitante": sol_r, "Observação": obs_r}
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
            st.success(f"✅ Requisição de **{qtd_r} {un_r}** de **{insumo_r}** enviada para aprovação!")
            st.rerun()
    elif aba == "➕ Movimentar":
        st.subheader("Registrar Movimentação")
        with st.form("form_mov"):
            c1,c2 = st.columns(2)
            tipo_m   = c1.radio("Tipo", ["Entrada","Saída"])
            obra_m   = c2.selectbox("Obra", _obras_nomes())
            insumo_m = c1.selectbox("Insumo", st.session_state.estoque["Insumo"].tolist())
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
                    except Exception: pass
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
                except Exception: pass
                st.rerun()

    else:  # Entrada de NF
        st.subheader("📋 Entrada de Nota Fiscal")
        st.caption("Registra a NF, atualiza o estoque e gera automaticamente uma Conta a Pagar no Financeiro.")

        # Obra (fora do form para manter estado ao adicionar insumo)
        obra_nf = st.selectbox("Obra *", _obras_nomes(), key="nf_obra_sel")

        # ── Seleção de insumo com cadastro dinâmico ───────────────────
        st.markdown("**Insumo ***")
        NOVA_OPCAO = "➕ Cadastrar novo insumo..."
        insumos_base = sorted(st.session_state.estoque["Insumo"].unique().tolist())
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
                    st.success(f"'{nome_novo}' cadastrado! Agora selecione-o no campo acima.")
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
                                   "SB_ID": uuid_cp_nf or "", **dados_cp_nf}])
                ], ignore_index=True)
                st.success(
                    f"✅ Entrada registrada! Conta a Pagar de **{_fmt(val_nf)}** "
                    f"gerada para **{forn_nf.strip()}** — venc. {venc_nf} via {forma_nf}."
                )
                st.rerun()


# ── Financeiro ────────────────────────────────────────────────────────────────

def pagina_financeiro():
    st.title("💰 Financeiro")
    _init()

    CATS     = ["Materiais", "Folha de Pagamento", "Impostos", "Outros"]
    CAT_CORES = {"Materiais":"#2B59C3", "Folha de Pagamento":"#E67E22",
                 "Impostos":"#E74C3C",  "Outros":"#95A5A6"}

    tab_pg, tab_rc, tab_novo, tab_custo = st.tabs(
        ["💸 Contas a Pagar","💵 Contas a Receber","➕ Novo Lançamento","📊 Custos por Obra"]
    )

    def _tabela_financ(df_key):
        df = st.session_state[df_key].copy()
        todas_obras = sorted(_obras_nomes())
        c1,c2 = st.columns(2)
        f_ob = c1.selectbox("Obra", ["Todas"] + todas_obras, key=f"fo_{df_key}")
        f_st = c2.selectbox("Status",["Todos"]+sorted(df["Status"].unique().tolist()), key=f"fs_{df_key}")
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
        drop_cols = [c for c in ["ID","SB_ID"] if c in df.columns]
        ex = df.drop(columns=drop_cols).copy()
        ex["Valor (R$)"] = ex["Valor (R$)"].apply(_fmt)
        ex["Status"]     = ex["Status"].apply(lambda s: f"{badges.get(s,'⚪')} {s}")
        st.dataframe(ex, width='stretch', hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex), file_name="contas_pagar.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_cp")
        st.markdown("---")

        st.subheader("Ações")
        opc_p = {f"[{r.ID}] {r.Fornecedor} — {getattr(r,'Descrição','')}": r.ID
                 for r in st.session_state.contas_pagar.itertuples()}
        if not opc_p:
            st.info("Nenhum lançamento a pagar. Use a aba ➕ Novo Lançamento.")
        else:
            ca, cb = st.columns(2)
            with ca:
                sel_p = st.selectbox("Lançamento", list(opc_p.keys()), key="sel_cp")
                ns_p  = st.selectbox("Novo Status", ["Pago","A Pagar","Vencido","Cancelado"], key="ns_cp")
                if st.button("✅ Atualizar", key="btn_cp", type="primary"):
                    ix = st.session_state.contas_pagar[st.session_state.contas_pagar["ID"]==opc_p[sel_p]].index[0]
                    st.session_state.contas_pagar.loc[ix,"Status"] = ns_p
                    uuid_cp = _sb_id(st.session_state.contas_pagar, opc_p[sel_p])
                    if uuid_cp: sync.lancamento_status_update(uuid_cp, ns_p)
                    st.success(f"✅ Status atualizado para **{ns_p}**!"); st.rerun()
            with cb:
                if st.button("🗑️ Excluir Lançamento", key="del_cp"):
                    _desc_cp = sel_p
                    uuid_cp_del = _sb_id(st.session_state.contas_pagar, opc_p[sel_p])
                    st.session_state.contas_pagar = st.session_state.contas_pagar[
                        st.session_state.contas_pagar["ID"] != opc_p[sel_p]
                    ].reset_index(drop=True)
                    if uuid_cp_del: sync.lancamento_delete(uuid_cp_del)
                    st.success(f"✅ Lançamento excluído com sucesso!"); st.rerun()

    # ── Contas a Receber ──────────────────────────────────────────────
    with tab_rc:
        df_r = _tabela_financ("contas_receber")
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Previsto", _fmt(df_r["Valor (R$)"].sum()))
        c2.metric("Recebido",       _fmt(df_r[df_r["Status"]=="Recebido"]["Valor (R$)"].sum()))
        c3.metric("A Receber",      _fmt(df_r[df_r["Status"]=="A Receber"]["Valor (R$)"].sum()))
        st.markdown("---")
        badges_r = {"Recebido":"🟢","A Receber":"🟡","Vencido":"🔴"}
        ex_r = df_r.drop(columns=[c for c in ["ID","SB_ID"] if c in df_r.columns]).copy()
        ex_r["Valor (R$)"] = ex_r["Valor (R$)"].apply(_fmt)
        ex_r["Status"]     = ex_r["Status"].apply(lambda s: f"{badges_r.get(s,'⚪')} {s}")
        st.dataframe(ex_r, width='stretch', hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_r), file_name="contas_receber.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_cr")
        st.markdown("---")
        opc_r = {f"[{r.ID}] {r.Cliente} — {r.Descrição}": r.ID
                 for r in st.session_state.contas_receber.itertuples()}
        if not opc_r:
            st.info("Nenhum lançamento a receber. Use a aba ➕ Novo Lançamento.")
        else:
            ca_r, cb_r = st.columns(2)
            with ca_r:
                sel_r = st.selectbox("Lançamento", list(opc_r.keys()), key="sel_cr")
                ns_r  = st.selectbox("Novo Status", ["Recebido","A Receber","Vencido","Cancelado"], key="ns_cr")
                if st.button("✅ Atualizar", key="btn_cr", type="primary"):
                    ix_r = st.session_state.contas_receber[
                        st.session_state.contas_receber["ID"] == opc_r[sel_r]
                    ].index[0]
                    st.session_state.contas_receber.loc[ix_r,"Status"] = ns_r
                    uuid_cr = _sb_id(st.session_state.contas_receber, opc_r[sel_r])
                    if uuid_cr: sync.lancamento_status_update(uuid_cr, ns_r)
                    st.success(f"✅ Status atualizado para **{ns_r}**!"); st.rerun()
            with cb_r:
                if st.button("🗑️ Excluir", key="del_cr"):
                    uuid_cr_del = _sb_id(st.session_state.contas_receber, opc_r[sel_r])
                    st.session_state.contas_receber = st.session_state.contas_receber[
                        st.session_state.contas_receber["ID"] != opc_r[sel_r]
                    ].reset_index(drop=True)
                    if uuid_cr_del: sync.lancamento_delete(uuid_cr_del)
                    st.success(f"✅ Lançamento excluído com sucesso!"); st.rerun()

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
            if tipo_l == "Conta a Pagar":
                c3,c4 = st.columns(2)
                cat_l   = c3.selectbox("Categoria", CATS)
                forma_l = c4.selectbox("Forma de Pagamento",
                                        ["Boleto","PIX","Transferência","Cartão","Cheque","A definir"])
            ok_l = st.form_submit_button("➕ Adicionar", type="primary")
        if ok_l:
            obra_uuid_l = _obra_uuid(obra_l)
            if tipo_l == "Conta a Pagar":
                dados_cp = {"Obra": obra_l, "Fornecedor": contra, "Descrição": desc_l,
                            "Categoria": cat_l, "Valor (R$)": val_l, "Vencimento": venc_l,
                            "Status": "A Pagar", "NF": nf_l, "Forma Pag.": forma_l}
                uuid_l = sync.lancamento_save(dados_cp, "PAGAR", obra_uuid_l)
                st.session_state.contas_pagar = pd.concat([
                    st.session_state.contas_pagar,
                    pd.DataFrame([{"ID": _next_id(st.session_state.contas_pagar),
                                   "SB_ID": uuid_l or "", **dados_cp}])
                ], ignore_index=True)
            else:
                dados_cr = {"Obra": obra_l, "Cliente": contra, "Descrição": desc_l,
                            "Valor (R$)": val_l, "Vencimento": venc_l, "Status": "A Receber"}
                uuid_l = sync.lancamento_save(dados_cr, "RECEBER", obra_uuid_l)
                st.session_state.contas_receber = pd.concat([
                    st.session_state.contas_receber,
                    pd.DataFrame([{"ID": _next_id(st.session_state.contas_receber),
                                   "SB_ID": uuid_l or "", **dados_cr}])
                ], ignore_index=True)
            _tipo_msg = "Conta a Pagar" if tipo_l == "Conta a Pagar" else "Conta a Receber"
            st.success(f"✅ {_tipo_msg} de **{_fmt(val_l)}** para **{obra_l}** adicionada!"); st.rerun()

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


# ── Pessoal ───────────────────────────────────────────────────────────────────

def pagina_pessoal():
    st.title("👥 Pessoal")
    _init()
    t1,t2,t3,t4 = st.tabs(["👤 Funcionários","🕐 Ponto","💰 Folha","➕ Novo Funcionário"])

    with t1:
        funcs = st.session_state.funcionarios.copy()
        cf1,cf2 = st.columns(2)
        fo_f = cf1.selectbox("Obra",    ["Todas"]+sorted(funcs["Obra"].unique().tolist()),   key="ff_ob")
        fs_f = cf2.selectbox("Situação",["Todos"]+sorted(funcs["Situação"].unique().tolist()),key="ff_sit")
        if fo_f != "Todas": funcs = funcs[funcs["Obra"]==fo_f]
        if fs_f != "Todos": funcs = funcs[funcs["Situação"]==fs_f]
        c1,c2,c3 = st.columns(3)
        c1.metric("Total",   len(st.session_state.funcionarios))
        c2.metric("Ativos",  len(st.session_state.funcionarios[st.session_state.funcionarios["Situação"]=="Ativo"]))
        if _role() == "admin":
            c3.metric("Folha Bruta", _fmt(st.session_state.funcionarios["Salário (R$)"].sum()))
        st.markdown("---")
        ex_f = funcs.drop(columns=[c for c in ["ID","SB_ID"] if c in funcs.columns]).copy()
        if _role() == "admin":
            ex_f["Salário (R$)"] = ex_f["Salário (R$)"].apply(_fmt)
        else:
            ex_f = ex_f.drop(columns=["Salário (R$)"], errors="ignore")
        st.dataframe(ex_f,width='stretch',hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_f), file_name="funcionarios.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_func")
        st.markdown("---")
        st.subheader("Editar / Excluir")
        opc_f = {f"[{r.ID}] {r.Nome} — {r.Cargo}":r.ID for r in st.session_state.funcionarios.itertuples()}
        if not opc_f:
            st.info("Nenhum colaborador cadastrado. Use a aba ➕ Novo Colaborador.")
        else:
            sel_f = st.selectbox("Funcionário",list(opc_f.keys()))
            id_f  = opc_f[sel_f]
            LF    = st.session_state.funcionarios[st.session_state.funcionarios["ID"]==id_f].iloc[0]
            obras_lista = _obras_nomes(["Sede","Todas"])
            contrato_opts = ["CLT","MEI","Empreiteiro"]
            with st.form("form_edit_func"):
                c1,c2 = st.columns(2)
                nome_f  = c1.text_input("Nome",  value=LF["Nome"])
                cargo_f = c2.text_input("Cargo", value=LF["Cargo"])
                tc_idx  = contrato_opts.index(LF.get("Tipo Contrato","CLT")) if LF.get("Tipo Contrato","CLT") in contrato_opts else 0
                cont_f  = c1.selectbox("Tipo de Contrato", contrato_opts, index=tc_idx)
                ob_val  = str(LF.get("Obra","") or "")
                ob_idx  = obras_lista.index(ob_val) if ob_val in obras_lista else 0
                obra_f  = c2.selectbox("Obra Alocada", obras_lista, index=ob_idx)
                if _role() == "admin":
                    sal_f = c1.number_input("Salário / Valor (R$)", value=_to_num(LF["Salário (R$)"]),step=100.0)
                else:
                    sal_f = _to_num(LF["Salário (R$)"])
                adm_f   = c2.text_input("Admissão", value=str(LF.get("Admissão","") or ""))
                sit_opts = ["Ativo","Férias","Afastado","Demitido"]
                sit_val = str(LF.get("Situação","Ativo") or "Ativo")
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
                sync.colaborador_save({"Nome":nome_f,"Cargo":cargo_f,"Tipo Contrato":cont_f,
                                       "Salário (R$)":sal_f,"Admissão":adm_f,"Situação":sit_f}, sb_id=sb_uuid)
                st.success(f"✅ Dados de **{nome_f}** atualizados com sucesso!"); st.rerun()
            if del_f:
                _nome_del_f = nome_f
                uuid_f_del = _sb_id(st.session_state.funcionarios, id_f)
                st.session_state.funcionarios = st.session_state.funcionarios[st.session_state.funcionarios["ID"]!=id_f].reset_index(drop=True)
                if uuid_f_del:
                    try:
                        from db import sb
                        sb().table("colaboradores").update({"ativo": False}).eq("id", uuid_f_del).execute()
                    except Exception: pass
                st.success(f"✅ **{_nome_del_f}** removido do sistema!"); st.rerun()

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
                               "SB_ID": _uuid_pt or "", **_dado_pt}])
            ], ignore_index=True)
            st.success(f"Falta de **{func_p}** em {data_p} registrada."); st.rerun()

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
                todas_ob = ["Todas"] + sorted(ff_all["Obra"].unique().tolist())
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
                ob_pdf_folha = st.selectbox("Obra para exportar", ["Todas as Obras"] + sorted(ff_all["Obra"].unique().tolist()), key="folha_pdf_obra")
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
                        }
                        uuid_folha = sync.lancamento_save(dados_folha, "PAGAR", _obra_uuid(ob_lanc))
                        st.session_state.contas_pagar = pd.concat([
                            st.session_state.contas_pagar,
                            pd.DataFrame([{
                                "ID":    _next_id(st.session_state.contas_pagar),
                                "SB_ID": uuid_folha or "",
                                **dados_folha,
                            }])
                        ], ignore_index=True)
                        st.success(
                            f"✅ Folha lançada no Financeiro! Custo Empresa {_fmt(custo_emp)} "
                            f"registrado em Contas a Pagar — {ob_lanc} ref. {ref_mes}."
                        )
                        st.rerun()

    with t4:
        with st.form("form_novo_func"):
            c1,c2 = st.columns(2)
            nome_nf  = c1.text_input("Nome *")
            cargo_nf = c2.text_input("Cargo *")
            cont_nf  = c1.selectbox("Tipo de Contrato *", ["CLT","MEI","Empreiteiro"])
            obra_nf  = c2.selectbox("Obra Alocada", _obras_nomes(["Sede","Todas"]))
            sal_nf   = c1.number_input("Salário / Valor (R$)", min_value=0.0, step=100.0)
            adm_nf   = c2.text_input("Admissão", value=date.today().strftime("%d/%m/%Y"))
            sit_nf   = c1.selectbox("Situação", ["Ativo","Férias","Afastado"])
            ok_nf    = st.form_submit_button("➕ Cadastrar", type="primary")
        if ok_nf:
            if not nome_nf or not cargo_nf: st.error("Nome e Cargo obrigatórios.")
            else:
                dados_col = {"Nome": nome_nf, "Cargo": cargo_nf, "Tipo Contrato": cont_nf,
                             "Obra": obra_nf, "Salário (R$)": sal_nf, "Admissão": adm_nf, "Situação": sit_nf}
                uuid_col = sync.colaborador_save(dados_col)
                st.session_state.funcionarios = pd.concat([
                    st.session_state.funcionarios,
                    pd.DataFrame([{"ID": _next_id(st.session_state.funcionarios),
                                   "SB_ID": uuid_col or "", **dados_col}])
                ], ignore_index=True)
                st.success(f"✅ Colaborador **{nome_nf}** ({cargo_nf}) cadastrado com sucesso!"); st.rerun()


# ── Qualidade ─────────────────────────────────────────────────────────────────

def pagina_qualidade():
    st.title("✅ Qualidade")
    _init()
    t1,t2,t3,t4 = st.tabs(["📋 Checklists","⚠️ Não-Conformidades","➕ Nova Inspeção","➕ Abrir NC"])

    with t1:
        chk = st.session_state.checklists.copy()
        cf1,cf2 = st.columns(2)
        fo_q = cf1.selectbox("Obra",      ["Todas"]+sorted(chk["Obra"].unique().tolist()),      key="fq_ob")
        fr_q = cf2.selectbox("Resultado", ["Todos"]+sorted(chk["Resultado"].unique().tolist()),  key="fq_res")
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
        fo_nc = cf3.selectbox("Obra",  ["Todas"]+sorted(ncs["Obra"].unique().tolist()),   key="fnc_ob")
        fs_nc = cf4.selectbox("Status",["Todos"]+sorted(ncs["Status"].unique().tolist()),  key="fnc_st")
        if fo_nc != "Todas": ncs = ncs[ncs["Obra"]==fo_nc]
        if fs_nc != "Todos": ncs = ncs[ncs["Status"]==fs_nc]
        bdg_nc = {"Aberta":"🔴","Em tratamento":"🟡","Encerrada":"🟢"}
        ex_nc = ncs.copy()
        ex_nc["Gravidade"] = ex_nc["Gravidade"].apply(lambda g:("🔴 " if g=="Alta" else "🟡 " if g=="Moderada" else "🟢 ")+g)
        ex_nc["Status"]    = ex_nc["Status"].apply(lambda s:f"{bdg_nc.get(s,'⚪')} {s}")
        st.dataframe(ex_nc,width='stretch',hide_index=True)
        st.download_button("⬇️ Exportar Excel", data=_export_excel(ex_nc), file_name="nao_conformidades.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="btn_xls_nc")
        st.markdown("---")
        st.subheader("Atualizar Status")
        opc_nc = {f"{r.ID} — {r.Obra}":r.ID for r in st.session_state.ncs.itertuples()}
        if not opc_nc:
            st.info("Nenhuma NC registrada.")
        else:
            sel_nc = st.selectbox("NC",list(opc_nc.keys()))
            ns_nc  = st.selectbox("Novo Status",["Aberta","Em tratamento","Encerrada"],key="ns_nc")
            if st.button("✅ Atualizar NC",type="primary"):
                ix_nc = st.session_state.ncs[st.session_state.ncs["ID"]==opc_nc[sel_nc]].index[0]
                st.session_state.ncs.loc[ix_nc,"Status"]=ns_nc
                st.success(f"✅ **{sel_nc}** atualizada para status **{ns_nc}**!"); st.rerun()

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
            st.success(f"✅ Inspeção de **{item_chk}** registrada! Resultado: {_res_icon} {res_chk}"); st.rerun()

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
            st.success(f"✅ NC **{novo_id_nc}** aberta em **{obra_nc}** (Gravidade: {grav_nc})!"); st.rerun()


# ── Orçamento (importação) ───────────────────────────────────────────────────

# ── Helpers de importação de orçamento ───────────────────────────────────────

def _norm_col(s):
    """
    Normaliza um nome de coluna para comparação insensível a maiúsculas e acentos.
    Ex.: 'Preço Unitário' → 'preco unitario' | 'V.Unit com Mat.' → 'v.unit com mat.'
    """
    s = str(s).lower().strip()
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')


def _to_num(val):
    """
    Converte célula de planilha para float, respeitando o padrão BR.
    - float/int vindos do pandas  → retorna direto (sem manipulação de string)
    - string BR com ponto+vírgula → "1.234,56"  → 1234.56  (remove . e troca ,)
    - string BR só com vírgula   → "1234,56"   → 1234.56  (troca , por .)
    - string US/Python só ponto  → "1234.56"   → 1234.56  (sem alteração)
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
    As colunas numéricas (Qtd e Preço) são limpas de forma vetorizada
    por _limpar_col_num() antes do loop — sem chamar _to_num por linha.
    """
    bdi_fator   = 1 + (bdi_pct / 100)
    resultado   = []
    etapa_stack = {}

    # ── Limpeza vetorizada das colunas numéricas (uma passagem por coluna) ──
    _nan_series = pd.Series([float("nan")] * len(df), dtype=float, index=df.index)
    ser_qtd   = _limpar_col_num(df[col_qtd])   if col_qtd   != "(ignorar)" else _nan_series
    ser_preco = _limpar_col_num(df[col_preco]) if col_preco != "(ignorar)" else _nan_series

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

        nivel   = _nivel_eap(codigo) if codigo else 1
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
    return resultado


def _exibir_orcamento_processado(resultado, obra_orc, bdi_pct, nome_orc):
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

    tab_arv, tab_it, tab_res, tab_exp = st.tabs(
        ["🌳 Árvore EAP", "📋 Itens de Serviço", "📊 Resumo por Etapa", "⬇️ Exportar"]
    )

    with tab_arv:
        linhas = []
        for r in resultado:
            pad = "　" * (r["nivel"] - 1)
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

    with tab_exp:
        buf = io.BytesIO()
        pd.DataFrame([{
            "Ordem":           r["ordem"],       "Tipo":         r["tipo"],
            "Nível EAP":       r["nivel"],        "Etapa Pai":    r["etapa_pai"],
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


# ── Página Orçamento ──────────────────────────────────────────────────────────

def pagina_orcamento():
    st.title("📊 Orçamento")
    _init()

    # ── Parâmetros (tabela: orcamentos) ────────────────────────────────────
    with st.expander("⚙️ Parâmetros do Orçamento", expanded=True):
        c1,c2,c3,c4 = st.columns(4)
        obra_orc    = c1.selectbox("Obra", _obras_nomes(), key="orc_obra")
        nome_orc    = c2.text_input("Nome", value="Orçamento Rev.1", key="orc_nome")
        base_ref    = c3.text_input("Base de Referência", value="SINAPI Mai/2026", key="orc_base")
        bdi_incluso = c4.checkbox("Planilha já inclui BDI", key="orc_bdi_incluso", value=True,
                                  help="Marque se os preços da planilha já incluem BDI. Desmarque para aplicar BDI adicional.")
        bdi_orc     = c4.number_input("BDI a aplicar (%)", min_value=0.0, max_value=100.0,
                                      value=25.0, step=0.5, key="orc_bdi",
                                      disabled=bdi_incluso,
                                      help="Só ativo quando a planilha NÃO inclui BDI nos preços.")
        c1.number_input("Encargos Sociais (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.5, key="orc_enc")
        c2.number_input("Versão", min_value=1, value=1, key="orc_versao")
        c3.selectbox("Status", ["Rascunho","Aprovado","Substituído"], key="orc_status")

    st.markdown("---")
    st.subheader("📂 Importar Planilha de Itens")
    st.info(
        "Suba sua planilha (.xlsx ou .csv). Em seguida, mapeie as colunas e clique em **Processar**. "
        "O sistema identifica etapas/subetapas automaticamente e aplica o BDI configurado.",
        icon="📂",
    )

    arquivo = st.file_uploader("Selecione o arquivo", type=["xlsx","xls","csv"])

    # ── Carregamento bruto ──────────────────────────────────────────────────
    # Só relê (e reseta orcamento_mapped) quando o arquivo for diferente do anterior.
    # Se simplesmente comparar `arquivo is not None` em todo render, o resultado
    # processado seria apagado imediatamente após cada st.rerun().
    if arquivo is not None and arquivo.name != st.session_state.get("orcamento_nome"):
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_raw = pd.read_csv(arquivo, sep=None, engine="python",
                                     encoding="utf-8-sig", header=None,
                                     dtype=str)
            else:
                df_raw = pd.read_excel(arquivo, header=None, dtype=str)
            st.session_state.orcamento_df_raw = df_raw
            st.session_state.orcamento_nome   = arquivo.name
            st.session_state.orcamento_mapped = None
            st.success(f"'{arquivo.name}' carregado — {len(df_raw)} linhas × {len(df_raw.columns)} colunas brutas.")
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
        df_h.columns = [str(v).strip() if pd.notna(v) else f"Col_{i}"
                        for i, v in enumerate(df_raw.iloc[int(hdr)].values)]
        df_h = df_h.reset_index(drop=True)
        avail = ["(ignorar)"] + list(df_h.columns)

        # ── Passo 2: mapeamento de colunas ─────────────────────────────
        st.subheader("2️⃣ Mapeamento de Colunas")

        # Pré-normaliza os nomes das colunas uma única vez
        _cols_norm = {col: _norm_col(col) for col in df_h.columns}

        def _guess(kws):
            """
            Retorna a primeira coluna cujo nome normalizado contém alguma
            das palavras-chave (também normalizadas).
            Testa as keywords mais longas primeiro para evitar falsos positivos.
            Para keywords < 3 chars aceita apenas match EXATO (evita "un" em "fundacao").
            """
            kws_n = sorted([_norm_col(k) for k in kws], key=len, reverse=True)
            for kw in kws_n:
                for col, cn in _cols_norm.items():
                    if kw == cn:                        # match exato (qualquer tamanho)
                        return col
                    if len(kw) >= 3 and kw in cn:       # substring apenas se kw >= 3 chars
                        return col
            return "(ignorar)"

        def _idx(col):
            return avail.index(col) if col in avail else 0

        # ── Listas de keywords por campo (do mais específico ao mais genérico) ──
        KW_COD  = ["codigo", "cod.", "cod", "item", "num.", "nro.", "num", "nro", "nr."]
        KW_DESC = ["descricao", "descricoes", "descr.", "descr", "desc.", "desc",
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

        st.markdown("---")

        if st.button("⚙️ Processar Orçamento", type="primary", key="btn_proc"):
            if c_desc == "(ignorar)":
                st.error("A coluna Descrição é obrigatória.")
            else:
                bdi_efetivo = 0.0 if bdi_incluso else bdi_orc
                res = _processar_orcamento(df_h, c_cod, c_desc, c_un, c_qtd, c_pu, bdi_pct=bdi_efetivo)
                st.session_state.orcamento_mapped = res
                # Vincula o orçamento à obra selecionada (usado na EAP)
                if "orcamento_por_obra" not in st.session_state:
                    st.session_state.orcamento_por_obra = {}
                st.session_state.orcamento_por_obra[obra_orc] = res
                n_etapas = sum(1 for r in res if r["tipo"]=="ETAPA")
                n_itens  = sum(1 for r in res if r["tipo"]=="ITEM")
                total_orc = sum(r["total_venda"] for r in res if r["tipo"] == "ITEM" and r.get("total_venda"))
                ob_row_orc = st.session_state.obras[st.session_state.obras["Nome"] == obra_orc]
                val_atual_orc = _to_num(ob_row_orc["Valor Contrato (R$)"].iloc[0]) if not ob_row_orc.empty else 0.0
                if total_orc > 0 and abs(total_orc - val_atual_orc) > 0.01:
                    st.session_state.orc_valor_proposta = {
                        "total": total_orc, "obra": obra_orc, "atual": val_atual_orc
                    }
                st.success(f"✅ Processado: {n_etapas} etapas + {n_itens} itens. EAP vinculada à obra **{obra_orc}**.")
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
                    st.success(f"✅ Valor Contrato da obra **{obra_orc}** atualizado para {_fmt(total_prop)}!")
                    st.rerun()
                if _cn.button("❌ Não, manter atual", key="btn_orc_manter"):
                    del st.session_state["orc_valor_proposta"]
                    st.rerun()
            # ────────────────────────────────────────────────────────────────
            _exibir_orcamento_processado(
                st.session_state.orcamento_mapped, obra_orc, bdi_orc, nome_orc
            )

        if st.button("🗑️ Limpar importação", key="btn_limpar"):
            st.session_state.orcamento_df_raw = None
            st.session_state.orcamento_mapped = None
            st.session_state.orcamento_nome   = None
            st.rerun()

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
            "Linhas sem Quantidade/Preço são detectadas como Etapas da EAP. "
            "Códigos com ponto (1.1.1) definem a profundidade hierárquica automaticamente."
        )


# ── DIÁRIO DE OBRA (RDO) ──────────────────────────────────────────────────────

def pagina_rdo():
    st.title("📋 Diário de Obra (RDO)")
    _init()

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
            "Adicione fotos dos serviços executados",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="As fotos serão incluídas no relatório fotográfico do RDO.",
            key="rdo_fotos_upload"
        )
        if fotos_upload:
            cols_prev = st.columns(min(len(fotos_upload), 4))
            for i, f in enumerate(fotos_upload):
                cols_prev[i % 4].image(f, caption=f.name, use_container_width=True)

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
                _icone_rdo = "🔴" if status_rdo != "Normal" else "✅"
                _msg_fotos = f" ({len(urls_fotos)} foto(s) anexada(s))" if urls_fotos else ""
                st.success(f"{_icone_rdo} RDO de **{str(data_rdo)}** — **{obra_rdo}** salvo! Status: {status_rdo}{_msg_fotos}")
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
                            st.success(f"✅ RDO de **{row_d['Data']}** atualizado com sucesso!")
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
                            st.success("✅ RDO excluído com sucesso!")
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
                                        _cols_f[_fi % 3].image(_url_f, caption=_nome_f, use_container_width=True)

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
    st.title("📅 Planejamento — EAP")
    _init()

    obras_lista = _obras_nomes()
    obra_sel = st.selectbox("Obra", obras_lista, key="eap_obra_sel")

    orc_por_obra = st.session_state.get("orcamento_por_obra", {})
    resultado    = orc_por_obra.get(obra_sel)

    # ── Estado sem orçamento importado ───────────────────────────────
    if not resultado:
        obra_row = st.session_state.obras[st.session_state.obras["Nome"] == obra_sel]
        if len(obra_row):
            o = obra_row.iloc[0]
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Status",          o["Status"])
            c2.metric("Avanço Físico",   f"{o['% Físico']}%")
            c3.metric("Valor Contrato",  _fmt(_to_num(o["Valor Contrato (R$)"])))
            c4.metric("Responsável",     o["Responsável"])
        st.info(
            f"Nenhum orçamento importado para **{obra_sel}**.\n\n"
            "Acesse **Orçamento → Importar Planilha**, selecione esta obra, "
            "processe o arquivo e clique em **⚙️ Processar Orçamento** para gerar a EAP aqui.",
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

    t_arv, t_prog, t_gantt = st.tabs(["🌳 Estrutura EAP","📊 Progresso por Etapa","📅 Cronograma"])

    # ── Aba 1: Árvore EAP ────────────────────────────────────────────
    with t_arv:
        linhas = []
        for r in resultado:
            pad = "　" * (r["nivel"] - 1)
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

    # ── Aba 2: Progresso por Etapa ───────────────────────────────────
    with t_prog:
        if len(etapas) and tv > 0:
            custo_et = (itens.groupby("etapa_pai")[["total_custo","total_venda"]]
                             .sum().reset_index()
                             .sort_values("total_venda", ascending=False))
            custo_et["% Total"] = (custo_et["total_venda"] / tv * 100).round(1)

            if "eap_progresso" not in st.session_state:
                st.session_state.eap_progresso = {}

            st.caption("Defina o avanço físico de cada etapa:")
            for _, row in custo_et.iterrows():
                nome_et = row["etapa_pai"]
                k = f"eap_{obra_sel}_{nome_et}"
                pct_at = st.session_state.eap_progresso.get(k, 0)
                cols = st.columns([4, 1, 1])
                pct_novo = cols[0].slider(nome_et[:60], 0, 100, pct_at, key=k)
                cols[1].metric("Custo",   _fmt(row["total_custo"]))
                cols[2].metric("% Total", f"{row['% Total']:.1f}%")
                st.session_state.eap_progresso[k] = pct_novo

            st.markdown("---")
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

        etapas_n1 = etapas[etapas["nivel"] == 1]["descricao"].tolist() if len(etapas) else []

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
                    st.success("Datas salvas!"); st.rerun()

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
    st.subheader("📈 Cronograma Físico-Financeiro")

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
        import numpy as np
        from scipy.special import erf as _erf

        ini_global = min(g["ini"] for g in gantt_cff)
        fim_global = max(g["fim"] for g in gantt_cff)

        meses = pd.date_range(ini_global, fim_global, freq="MS")
        if len(meses) == 0:
            meses = pd.date_range(ini_global, periods=3, freq="MS")
        n = len(meses)
        mes_labels = [m.strftime("%b/%y") for m in meses]

        # Curva S planejada via erf
        _x = np.linspace(-2.0, 2.0, n)
        _s_cum = (_erf(_x) + 1.0) / 2.0
        _s_men = np.diff(np.concatenate([[0.0], _s_cum]))
        _s_men = _s_men / _s_men.sum() * 100.0

        desemb_plan = _s_men * tv / 100.0

        # Realizado financeiro: lançamentos filtrados pela obra
        df_lanc_cff = st.session_state.get("lancamentos", pd.DataFrame())
        desemb_real = np.zeros(n)
        try:
            if len(df_lanc_cff) > 0 and "Data" in df_lanc_cff.columns and "Valor (R$)" in df_lanc_cff.columns:
                _obra_col = next((c for c in df_lanc_cff.columns if "obra" in c.lower()), None)
                _df_lo = df_lanc_cff[df_lanc_cff[_obra_col] == obra_sel].copy() if _obra_col else df_lanc_cff.copy()
                _df_lo["_dt"]  = pd.to_datetime(_df_lo["Data"], dayfirst=True, errors="coerce")
                _df_lo["_val"] = _df_lo["Valor (R$)"].apply(lambda v: _to_num(str(v)))
                for _i, _mes in enumerate(meses):
                    _fim_mes = _mes + pd.offsets.MonthEnd(0)
                    _mask = (_df_lo["_dt"] >= _mes) & (_df_lo["_dt"] <= _fim_mes)
                    desemb_real[_i] = _df_lo.loc[_mask, "_val"].sum()
        except Exception:
            pass

        # Físico realizado: média dos sliders de progresso
        _prog_cff = st.session_state.get("eap_progresso", {})
        _pcts_cff = [v for k_p, v in _prog_cff.items() if f"eap_{obra_sel}_" in k_p]
        pct_real = float(np.mean(_pcts_cff)) if _pcts_cff else 0.0

        fis_plan_cum = _s_cum * 100.0
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
            st.plotly_chart(_fig_fis, use_container_width=True)

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
            st.plotly_chart(_fig_fin, use_container_width=True)

        _df_tab_cff = pd.DataFrame({
            "Mês":               mes_labels,
            "% Físico Mensal":   [f"{v:.1f}%" for v in _s_men],
            "% Físico Acum.":    [f"{v:.1f}%" for v in fis_plan_cum],
            "Desembolso Mensal": [_fmt(v) for v in desemb_plan],
            "Desembolso Acum.":  [_fmt(v) for v in fin_plan_cum],
        })
        st.caption("Cronograma Físico-Financeiro — Planejado (Curva S)")
        st.dataframe(_df_tab_cff, hide_index=True, use_container_width=True)
        _col_cff, _ = st.columns([1, 4])
        _col_cff.download_button(
            "📥 Exportar Excel", _export_excel(_df_tab_cff),
            f"cronograma_{obra_sel}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_cronograma_cff",
        )


# ── Portal do Contratante ────────────────────────────────────────────────────

def pagina_portal_contratante():
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
        import plotly.graph_objects as go
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
                                use_container_width=True, key=f"chart_prog_{obra_sel_nome}")

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

                m1, m2, m3 = st.columns(3)
                m1.metric("Valor do Contrato",  f"R$ {val_contrato:,.2f}".replace(",","X").replace(".",",").replace("X","."))
                m2.metric("Total Medido",        f"R$ {total_medido:,.2f}".replace(",","X").replace(".",",").replace("X","."))
                m3.metric("% Fin. Medido",       f"{pct_fin:.1f}%")

                x_col = "Data" if "Data" in meds_obra_m.columns else meds_obra_m.columns[0]
                st.plotly_chart(_grafico_medicoes(meds_obra_m, x_col, col_val),
                                use_container_width=True, key=f"chart_med_{obra_sel_nome}")
                st.markdown("---")

            colunas_pub = [c for c in meds_obra_m.columns
                           if c not in ("SB_ID", "ID") and "bdi" not in c.lower()]
            st.dataframe(meds_obra_m[colunas_pub], use_container_width=True, hide_index=True)

    # ── Aba Diário de Obra ────────────────────────────────────────────────────
    with tab_rdo:
        rdos = st.session_state.get("rdos", pd.DataFrame())
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
                    fotos = rdo_row.get("Fotos", [])
                    if isinstance(fotos, list) and fotos:
                        st.markdown("**Fotos:**")
                        fcols = st.columns(min(len(fotos), 4))
                        for fi, foto in enumerate(fotos[:4]):
                            url = foto.get("url", "") if isinstance(foto, dict) else str(foto)
                            if url:
                                fcols[fi].image(url, use_container_width=True)

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
    # Paleta Prumo Modelo 3:
    # Navy Blue  #1B3A5E  — sidebar, títulos
    # Blue-Green #2AACA0  — acento, botões, valores
    # Concrete   #A0A8B0  — texto secundário
    # Background #F4F6F8  — fundo do app
    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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

        /* ── Títulos ── */
        h1 {
            color: #1B3A5E !important;
            font-weight: 800 !important;
            font-size: 1.55rem !important;
            letter-spacing: -0.3px;
            margin-bottom: 1.2rem !important;
        }
        h2, h3 { color: #1B3A5E !important; font-weight: 700 !important; }

        /* ── Métricas ── */
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 20px !important;
            box-shadow: 0 2px 10px rgba(27,58,94,0.08);
            border-left: 4px solid #2AACA0;
            transition: box-shadow 0.2s, transform 0.2s;
        }
        [data-testid="stMetric"]:hover {
            box-shadow: 0 6px 20px rgba(42,172,160,0.15);
            transform: translateY(-2px);
        }
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
        section[data-testid="stSidebar"] button[kind="secondary"] {
            background-color: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            color: #A0B4C8 !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            transition: all 0.2s !important;
        }
        section[data-testid="stSidebar"] button[kind="secondary"]:hover {
            background-color: rgba(42,172,160,0.18) !important;
            border-color: rgba(42,172,160,0.5) !important;
            color: #2AACA0 !important;
        }
        section[data-testid="stSidebar"] button[kind="primary"] {
            background: #2AACA0 !important;
            border: none !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown span,
        section[data-testid="stSidebar"] caption {
            color: #7A9AB8 !important;
            font-size: 12px !important;
        }
        hr { border-color: rgba(255,255,255,0.08) !important; }
    </style>""", unsafe_allow_html=True)


def app():
    # ── Autenticação ─────────────────────────────────────────────────────────
    if "usuario" not in st.session_state:
        _auth_login()
        st.stop()

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
                <div style='font-size:20px;font-weight:900;color:#FFFFFF;letter-spacing:-0.5px;line-height:1;'>
                    PRUMO<span style='font-size:11px;font-weight:700;color:#2AACA0;margin-left:3px;vertical-align:super;'>ERP</span>
                </div>
                <div style='font-size:9px;color:#7A9AB8;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;margin-top:4px;'>Software de Construção Civil</div>
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
            "Suprimentos":        ("📦", ["suprimentos"]),
            "Financeiro":         ("💰", ["financeiro"]),
            "Pessoal":            ("👥", ["pessoal", "ponto", "folha"]),
            "Qualidade":          ("✅", ["qualidade"]),
            "Diário de Obra":     ("📋", ["rdo"]),
            "Orçamento":          ("📊", ["orcamento"]),
            "Planejamento (EAP)": ("📅", ["obras"]),
        }
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = "Principal"
    # Redireciona se a página atual não for acessível com o role atual
    if not _pode(_MENU.get(st.session_state.pagina_atual, ("", ["dashboard"]))[1]):
        st.session_state.pagina_atual = "Principal"
    for pag, (emoji, mods) in _MENU.items():
        if not _pode(mods):
            continue
        tipo = "primary" if st.session_state.pagina_atual == pag else "secondary"
        if st.sidebar.button(f"{emoji} {pag}", use_container_width=True, type=tipo):
            st.session_state.pagina_atual = pag
            st.rerun()

    st.sidebar.markdown("---")
    _total_al_sb = (len(st.session_state.get("_alertas_cache", {}).get("vencimentos", [])) +
                    len(st.session_state.get("_alertas_cache", {}).get("ncs_abertas", [])) +
                    len(st.session_state.get("_alertas_cache", {}).get("estoque_critico", [])))
    if _total_al_sb > 0:
        st.sidebar.warning(f"⚠️ {_total_al_sb} alerta(s) ativo(s)")
    st.sidebar.caption("🔗 Banco de Dados: Supabase ☁️")
    st.sidebar.caption(f"📅 Hoje: {date.today().strftime('%d/%m/%Y')}")
    if st.sidebar.button("🔄 Atualizar dados", key="btn_refresh", use_container_width=True):
        # Preserva autenticação mas força reload dos dados
        _auth_keys = {k: st.session_state[k] for k in ["usuario","usuario_role","usuario_obras_ids","empresa_id"] if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(_auth_keys)
        st.rerun()
    if st.sidebar.button("🚪 Sair", key="btn_logout", use_container_width=True):
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
        elif p == "Suprimentos":        pagina_suprimentos()
        elif p == "Financeiro":         pagina_financeiro()
        elif p == "Pessoal":            pagina_pessoal()
        elif p == "Qualidade":          pagina_qualidade()
        elif p == "Diário de Obra":     pagina_rdo()
        elif p == "Orçamento":          pagina_orcamento()
        elif p == "Planejamento (EAP)": pagina_eap()
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
