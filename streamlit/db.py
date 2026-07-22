"""
Camada de acesso ao Supabase para o ERP MBR.
Todas as leituras e escritas do banco passam por aqui.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions
import pandas as pd

load_dotenv()

# ── Cliente anon (leitura/escrita normal) ────────────────────────────────────

@lru_cache(maxsize=1)
def get_client() -> Client:
    url  = os.environ.get("SUPABASE_URL", "")
    key  = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key or "SEU_PROJETO" in url:
        raise RuntimeError(
            "⚠️ Credenciais do Supabase não configuradas.\n"
            "Edite o arquivo .env com SUPABASE_URL e SUPABASE_ANON_KEY."
        )
    opts = ClientOptions(postgrest_client_timeout=10)
    return create_client(url, key, options=opts)


def sb() -> Client:
    """Retorna cliente Supabase — usa service_role se disponível (bypassa RLS)."""
    admin = get_admin_client()
    if admin:
        return admin
    return get_client()


# ── Cliente admin (service_role — apenas operações administrativas) ───────────

def get_admin_client() -> Client | None:
    url  = os.environ.get("SUPABASE_URL", "")
    key  = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None
    opts = ClientOptions(postgrest_client_timeout=10)
    return create_client(url, key, options=opts)


def sb_admin() -> Client | None:
    return get_admin_client()


# ── Utilitários ──────────────────────────────────────────────────────────────

def _df(rows: list) -> pd.DataFrame:
    """Converte lista de dicts retornada pelo Supabase em DataFrame."""
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── OBRAS ────────────────────────────────────────────────────────────────────

def obras_listar() -> pd.DataFrame:
    res = sb().table("obras").select("*").is_("deleted_at", None).order("created_at").execute()
    return _df(res.data)

def obra_criar(dados: dict) -> dict:
    res = sb().table("obras").insert(dados).execute()
    return res.data[0] if res.data else {}

def obra_atualizar(obra_id: str, dados: dict) -> dict:
    res = sb().table("obras").update(dados).eq("id", obra_id).execute()
    return res.data[0] if res.data else {}

def obra_patch(obra_id: str, campos: dict) -> dict:
    """Atualiza apenas os campos informados, sem sobrescrever os demais."""
    res = sb().table("obras").update(campos).eq("id", obra_id).execute()
    return res.data[0] if res.data else {}

def obra_excluir(obra_id: str):
    from datetime import datetime
    sb().table("obras").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", obra_id).execute()


# ── COLABORADORES / PESSOAL ──────────────────────────────────────────────────

def colaboradores_listar() -> pd.DataFrame:
    res = sb().table("colaboradores").select("*, alocacoes(obra_id, obras(nome))").eq("ativo", True).execute()
    return _df(res.data)

def colaborador_criar(dados: dict) -> dict:
    res = sb().table("colaboradores").insert(dados).execute()
    return res.data[0] if res.data else {}

def colaborador_atualizar(col_id: str, dados: dict) -> dict:
    res = sb().table("colaboradores").update(dados).eq("id", col_id).execute()
    return res.data[0] if res.data else {}


# ── ALOCAÇÕES / TRANSFERÊNCIAS ───────────────────────────────────────────────

def alocacao_ativa(colaborador_id: str) -> dict | None:
    """Retorna a alocação ativa (sem data_fim) de um colaborador, ou None."""
    res = sb().table("alocacoes") \
        .select("*, obras(id, nome)") \
        .eq("colaborador_id", colaborador_id) \
        .is_("data_fim", None) \
        .limit(1) \
        .execute()
    return res.data[0] if res.data else None


def alocacoes_listar(colaborador_id: str) -> list:
    """Retorna todo o histórico de alocações de um colaborador."""
    res = sb().table("alocacoes") \
        .select("*, obras(id, nome)") \
        .eq("colaborador_id", colaborador_id) \
        .order("data_inicio", desc=True) \
        .execute()
    return res.data or []


def alocacao_criar(dados: dict) -> dict:
    """Cria uma nova alocação (transferência)."""
    res = sb().table("alocacoes").insert(dados).execute()
    return res.data[0] if res.data else {}


def alocacao_finalizar(alocacao_id: str, data_fim: str):
    """Encerra uma alocação (data_fim = data da transferência)."""
    sb().table("alocacoes").update({"data_fim": data_fim}).eq("id", alocacao_id).execute()


# ── FINANCEIRO — LANÇAMENTOS ─────────────────────────────────────────────────

def lancamentos_listar(tipo: str = None) -> pd.DataFrame:
    q = sb().table("lancamentos").select("*, obras(nome)").order("data_vencimento")
    if tipo:
        q = q.eq("tipo", tipo)
    res = q.execute()
    return _df(res.data)

def lancamento_criar(dados: dict) -> dict:
    res = sb().table("lancamentos").insert(dados).execute()
    return res.data[0] if res.data else {}

def lancamento_atualizar(lanc_id: str, dados: dict) -> dict:
    res = sb().table("lancamentos").update(dados).eq("id", lanc_id).execute()
    return res.data[0] if res.data else {}


# ── SUPRIMENTOS — ESTOQUE ────────────────────────────────────────────────────

def estoque_saldo(obra_id: str = None) -> pd.DataFrame:
    q = sb().table("estoque_saldo").select("*, insumos(codigo, descricao, unidade), obras(nome)")
    if obra_id:
        q = q.eq("obra_id", obra_id)
    res = q.execute()
    return _df(res.data)

def estoque_entrada(dados: dict) -> dict:
    res = sb().table("estoque_movimentos").insert({**dados, "tipo": "ENTRADA"}).execute()
    return res.data[0] if res.data else {}

def estoque_saida(dados: dict) -> dict:
    res = sb().table("estoque_movimentos").insert({**dados, "tipo": "SAIDA"}).execute()
    return res.data[0] if res.data else {}


# ── INSUMOS ──────────────────────────────────────────────────────────────────

def insumos_listar() -> pd.DataFrame:
    res = sb().table("insumos").select("*").order("descricao").execute()
    return _df(res.data)

def insumo_criar(dados: dict) -> dict:
    res = sb().table("insumos").insert(dados).execute()
    return res.data[0] if res.data else {}


# ── QUALIDADE ────────────────────────────────────────────────────────────────

def inspecoes_listar(obra_id: str = None) -> pd.DataFrame:
    q = sb().table("inspecoes").select("*, obras(nome)").order("data", desc=True)
    if obra_id:
        q = q.eq("obra_id", obra_id)
    res = q.execute()
    return _df(res.data)

def ncs_listar(obra_id: str = None) -> pd.DataFrame:
    q = sb().table("nao_conformidades").select("*, obras(nome)").order("created_at", desc=True)
    if obra_id:
        q = q.eq("obra_id", obra_id)
    res = q.execute()
    return _df(res.data)

def nc_criar(dados: dict) -> dict:
    res = sb().table("nao_conformidades").insert(dados).execute()
    return res.data[0] if res.data else {}

def nc_atualizar(nc_id: str, dados: dict) -> dict:
    res = sb().table("nao_conformidades").update(dados).eq("id", nc_id).execute()
    return res.data[0] if res.data else {}


# ── ORÇAMENTO ────────────────────────────────────────────────────────────────

def orcamentos_listar(obra_id: str = None) -> pd.DataFrame:
    q = sb().table("orcamentos").select("*, obras(nome)").order("created_at", desc=True)
    if obra_id:
        q = q.eq("obra_id", obra_id)
    res = q.execute()
    return _df(res.data)

def orcamento_criar(dados: dict) -> dict:
    res = sb().table("orcamentos").insert(dados).execute()
    return res.data[0] if res.data else {}

def orcamento_itens_inserir(itens: list) -> list:
    if not itens:
        return []
    res = sb().table("orcamento_itens").insert(itens).execute()
    return res.data or []

def orcamento_itens_listar(orcamento_id: str) -> pd.DataFrame:
    res = sb().table("orcamento_itens").select("*").eq("orcamento_id", orcamento_id).order("ordem").execute()
    return _df(res.data)


# ── EAP ──────────────────────────────────────────────────────────────────────

def eap_listar(obra_id: str) -> pd.DataFrame:
    res = sb().table("eap_itens").select("*").eq("obra_id", obra_id).order("ordem").execute()
    return _df(res.data)

def eap_upsert(itens: list) -> list:
    if not itens:
        return []
    res = sb().table("eap_itens").upsert(itens, on_conflict="obra_id,codigo").execute()
    return res.data or []

def eap_itens_por_obra(obra_id: str) -> pd.DataFrame:
    q = sb().table("eap_itens").select("id,codigo,descricao,valor_previsto,qtd_prevista,unidade").eq("obra_id", obra_id).order("ordem").execute()
    return _df(q.data)


# ── MEDIÇÕES ─────────────────────────────────────────────────────────────────

def medicoes_listar(obra_id: str) -> pd.DataFrame:
    res = sb().table("medicoes").select("*").eq("obra_id", obra_id).order("numero").execute()
    return _df(res.data)

def medicao_criar(dados: dict) -> dict:
    res = sb().table("medicoes").insert(dados).execute()
    return res.data[0] if res.data else {}

def medicao_atualizar(medicao_id: str, dados: dict) -> dict:
    res = sb().table("medicoes").update(dados).eq("id", medicao_id).execute()
    return res.data[0] if res.data else {}

def medicao_deletar(medicao_id: str):
    sb().table("medicoes").delete().eq("id", medicao_id).execute()

def medicao_itens_listar(medicao_id: str) -> list:
    res = sb().table("medicao_itens").select("*").eq("medicao_id", medicao_id).order("codigo").execute()
    return res.data or []

def medicao_itens_salvar(medicao_id: str, itens: list):
    """Substitui todos os itens de uma medição (delete + insert)."""
    sb().table("medicao_itens").delete().eq("medicao_id", medicao_id).execute()
    if itens:
        sb().table("medicao_itens").insert(itens).execute()


# ── PONTO ────────────────────────────────────────────────────────────────────

def ponto_listar(obra_id: str = None, data: str = None) -> pd.DataFrame:
    q = sb().table("ponto").select("*, colaboradores(nome)").order("data", desc=True)
    if obra_id:
        q = q.eq("obra_id", obra_id)
    if data:
        q = q.eq("data", data)
    res = q.execute()
    return _df(res.data)

def ponto_registrar(dados: dict) -> dict:
    res = sb().table("ponto").upsert(dados, on_conflict="colaborador_id,data").execute()
    return res.data[0] if res.data else {}


# ── FOLHA DE PAGAMENTO ───────────────────────────────────────────────────────

def folha_listar(competencia: str = None) -> pd.DataFrame:
    q = sb().table("folha_pagamento").select("*, colaboradores(nome, funcao)").order("competencia", desc=True)
    if competencia:
        q = q.eq("competencia", competencia)
    res = q.execute()
    return _df(res.data)

def folha_criar(registros: list) -> list:
    if not registros:
        return []
    res = sb().table("folha_pagamento").upsert(registros, on_conflict="competencia,colaborador_id").execute()
    return res.data or []


# ── ORÇADO x REALIZADO ───────────────────────────────────────────────────────

def orcado_realizado_listar() -> pd.DataFrame:
    q = sb().table("vw_orcado_realizado").select("*").order("obra_nome").execute()
    return _df(q.data)

def orcado_realizado_por_obra(obra_id: str) -> pd.DataFrame:
    q = sb().table("vw_orcado_realizado").select("*").eq("obra_id", obra_id).order("eap_codigo").execute()
    return _df(q.data)

def resumo_obras_listar() -> pd.DataFrame:
    q = sb().table("vw_resumo_obra").select("*").order("obra_nome").execute()
    return _df(q.data)


# ── COLUNAS (templates de mapeamento) ──────────────────────────────────────

def colmap_templates_listar(empresa_id: str) -> pd.DataFrame:
    res = sb().table("orcamento_colmap_templates").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
    return _df(res.data)

def colmap_template_criar(empresa_id: str, nome: str, mapping: dict) -> dict:
    res = sb().table("orcamento_colmap_templates").insert({
        "empresa_id": empresa_id,
        "nome": nome,
        "mapping": mapping,
    }).execute()
    return res.data[0] if res.data else {}

def colmap_template_atualizar(template_id: str, nome: str, mapping: dict) -> dict:
    res = sb().table("orcamento_colmap_templates").update({
        "nome": nome,
        "mapping": mapping,
        "updated_at": "now()",
    }).eq("id", template_id).execute()
    return res.data[0] if res.data else {}

def colmap_template_deletar(template_id: str):
    sb().table("orcamento_colmap_templates").delete().eq("id", template_id).execute()


# ── FORNECEDORES ─────────────────────────────────────────────────────────────

def fornecedores_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("fornecedores").select("*").order("razao_social").execute()
    return _df(q.data)

def fornecedor_criar(dados: dict) -> dict:
    res = sb().table("fornecedores").insert(dados).execute()
    return res.data[0] if res.data else {}

def fornecedor_atualizar(forn_id: str, dados: dict) -> dict:
    res = sb().table("fornecedores").update(dados).eq("id", forn_id).execute()
    return res.data[0] if res.data else {}

def fornecedor_deletar(forn_id: str):
    sb().table("fornecedores").delete().eq("id", forn_id).execute()


# ── COTAÇÕES ──────────────────────────────────────────────────────────────────

def cotacoes_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("cotacoes").select("*, fornecedores(razao_social, nome_fantasia), obras(nome)").order("data", desc=True).execute()
    return _df(q.data)

def cotacao_criar(dados: dict) -> dict:
    res = sb().table("cotacoes").insert(dados).execute()
    return res.data[0] if res.data else {}

def cotacao_atualizar(cot_id: str, dados: dict) -> dict:
    res = sb().table("cotacoes").update(dados).eq("id", cot_id).execute()
    return res.data[0] if res.data else {}

def cotacao_deletar(cot_id: str):
    sb().table("cotacoes").delete().eq("id", cot_id).execute()

def cotacao_itens_listar(cotacao_id: str) -> list:
    res = sb().table("cotacao_itens").select("*").eq("cotacao_id", cotacao_id).order("id").execute()
    return res.data or []

def cotacao_itens_inserir(itens: list) -> list:
    if not itens: return []
    res = sb().table("cotacao_itens").insert(itens).execute()
    return res.data or []

def cotacao_itens_deletar(cotacao_id: str):
    sb().table("cotacao_itens").delete().eq("cotacao_id", cotacao_id).execute()


# ── CONCILIAÇÃO BANCÁRIA ──────────────────────────────────────────────────────

def conciliacao_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("conciliacao").select("*").order("data_importacao", desc=True).execute()
    return _df(q.data)

def conciliacao_criar(dados: dict) -> dict:
    res = sb().table("conciliacao").insert(dados).execute()
    return res.data[0] if res.data else {}

def conciliacao_atualizar(con_id: str, dados: dict) -> dict:
    res = sb().table("conciliacao").update(dados).eq("id", con_id).execute()
    return res.data[0] if res.data else {}

def conciliacao_deletar(con_id: str):
    sb().table("conciliacao").delete().eq("id", con_id).execute()

def conciliacao_itens_listar(conciliacao_id: str) -> pd.DataFrame:
    res = sb().table("conciliacao_itens").select("*").eq("conciliacao_id", conciliacao_id).order("data").execute()
    return _df(res.data)

def conciliacao_itens_inserir(itens: list) -> list:
    if not itens: return []
    res = sb().table("conciliacao_itens").insert(itens).execute()
    return res.data or []

def conciliacao_item_atualizar(item_id: str, dados: dict) -> dict:
    res = sb().table("conciliacao_itens").update(dados).eq("id", item_id).execute()
    return res.data[0] if res.data else {}


# ── FÉRIAS ────────────────────────────────────────────────────────────────────

def ferias_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("ferias").select("*, colaboradores(nome)").order("data_inicio", desc=True).execute()
    return _df(q.data)

def ferias_criar(dados: dict) -> dict:
    res = sb().table("ferias").insert(dados).execute()
    return res.data[0] if res.data else {}

def ferias_atualizar(ferias_id: str, dados: dict) -> dict:
    res = sb().table("ferias").update(dados).eq("id", ferias_id).execute()
    return res.data[0] if res.data else {}


# ── ADICIONAIS ────────────────────────────────────────────────────────────────

def adicionais_listar(colaborador_id: str = None) -> pd.DataFrame:
    q = sb().table("adicionais_funcionario").select("*")
    if colaborador_id:
        q = q.eq("colaborador_id", colaborador_id)
    res = q.order("created_at", desc=True).execute()
    return _df(res.data)

def adicional_criar(dados: dict) -> dict:
    res = sb().table("adicionais_funcionario").insert(dados).execute()
    return res.data[0] if res.data else {}

def adicional_atualizar(adicional_id: str, dados: dict) -> dict:
    res = sb().table("adicionais_funcionario").update(dados).eq("id", adicional_id).execute()
    return res.data[0] if res.data else {}

def adicional_deletar(adicional_id: str):
    sb().table("adicionais_funcionario").delete().eq("id", adicional_id).execute()


# ── RESCISÃO ──────────────────────────────────────────────────────────────────

def rescisoes_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("rescisoes").select("*, colaboradores(nome)").order("data_rescisao", desc=True).execute()
    return _df(q.data)

def rescicao_criar(dados: dict) -> dict:
    res = sb().table("rescisoes").insert(dados).execute()
    return res.data[0] if res.data else {}

def rescicao_atualizar(resc_id: str, dados: dict) -> dict:
    res = sb().table("rescisoes").update(dados).eq("id", resc_id).execute()
    return res.data[0] if res.data else {}


# ── SUBEMPREITEIROS ────────────────────────────────────────────────────────────

def subempreiteiros_listar(empresa_id: str = None) -> pd.DataFrame:
    q = sb().table("subempreiteiros").select("*").order("razao_social").execute()
    return _df(q.data)

def subempreiteiro_criar(dados: dict) -> dict:
    res = sb().table("subempreiteiros").insert(dados).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_atualizar(sub_id: str, dados: dict) -> dict:
    res = sb().table("subempreiteiros").update(dados).eq("id", sub_id).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_deletar(sub_id: str):
    sb().table("subempreiteiros").delete().eq("id", sub_id).execute()

def subempreiteiro_contratos_listar(subempreiteiro_id: str = None, obra_id: str = None) -> pd.DataFrame:
    q = sb().table("subempreiteiro_contratos").select("*, obras(nome)")
    if subempreiteiro_id:
        q = q.eq("subempreiteiro_id", subempreiteiro_id)
    if obra_id:
        q = q.eq("obra_id", obra_id)
    res = q.order("data_inicio", desc=True).execute()
    return _df(res.data)

def subempreiteiro_contrato_criar(dados: dict) -> dict:
    res = sb().table("subempreiteiro_contratos").insert(dados).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_contrato_atualizar(cont_id: str, dados: dict) -> dict:
    res = sb().table("subempreiteiro_contratos").update(dados).eq("id", cont_id).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_contrato_deletar(cont_id: str):
    sb().table("subempreiteiro_contratos").delete().eq("id", cont_id).execute()

def subempreiteiro_medicoes_listar(contrato_id: str = None) -> pd.DataFrame:
    q = sb().table("subempreiteiro_medicoes").select("*")
    if contrato_id:
        q = q.eq("contrato_id", contrato_id)
    res = q.order("mes_referencia", desc=True).execute()
    return _df(res.data)

def subempreiteiro_medicao_criar(dados: dict) -> dict:
    res = sb().table("subempreiteiro_medicoes").insert(dados).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_medicao_atualizar(med_id: str, dados: dict) -> dict:
    res = sb().table("subempreiteiro_medicoes").update(dados).eq("id", med_id).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_medicao_deletar(med_id: str):
    sb().table("subempreiteiro_medicoes").delete().eq("id", med_id).execute()

def subempreiteiro_documentos_listar(subempreiteiro_id: str = None) -> pd.DataFrame:
    q = sb().table("subempreiteiro_documentos").select("*")
    if subempreiteiro_id:
        q = q.eq("subempreiteiro_id", subempreiteiro_id)
    res = q.order("data_validade").execute()
    return _df(res.data)

def subempreiteiro_documento_criar(dados: dict) -> dict:
    res = sb().table("subempreiteiro_documentos").insert(dados).execute()
    return res.data[0] if res.data else {}

def subempreiteiro_documento_deletar(doc_id: str):
    sb().table("subempreiteiro_documentos").delete().eq("id", doc_id).execute()
