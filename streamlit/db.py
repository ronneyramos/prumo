"""
Camada de acesso ao Supabase para o ERP MBR.
Todas as leituras e escritas do banco passam por aqui.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd

load_dotenv()

# ── Cliente ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_client() -> Client:
    url  = os.environ.get("SUPABASE_URL", "")
    key  = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key or "SEU_PROJETO" in url:
        raise RuntimeError(
            "⚠️ Credenciais do Supabase não configuradas.\n"
            "Edite o arquivo .env com SUPABASE_URL e SUPABASE_ANON_KEY."
        )
    return create_client(url, key)


def sb() -> Client:
    return get_client()


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


# ── MEDIÇÕES ─────────────────────────────────────────────────────────────────

def medicoes_listar(obra_id: str) -> pd.DataFrame:
    res = sb().table("medicoes").select("*").eq("obra_id", obra_id).order("numero").execute()
    return _df(res.data)

def medicao_criar(dados: dict) -> dict:
    res = sb().table("medicoes").insert(dados).execute()
    return res.data[0] if res.data else {}


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
