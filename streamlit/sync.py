"""
Adaptador entre o formato do app Streamlit (DataFrames em português)
e o Supabase (tabelas snake_case, UUIDs, datas ISO).
"""
from __future__ import annotations

import traceback
import pandas as pd
from datetime import datetime

_MBR_EMPRESA_ID = "00000000-0000-0000-0000-000000000001"


def _empresa_id() -> str:
    """Obtém empresa_id da sessão Streamlit ou retorna o padrão MBR."""
    try:
        import streamlit as _st
        return _st.session_state.get("empresa_id") or _MBR_EMPRESA_ID
    except Exception:
        return _MBR_EMPRESA_ID


def _iso_to_br(val) -> str:
    if not val:
        return ""
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(val)[:10]


def _br_to_iso(val) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def _attr(row, *keys, default=""):
    for k in keys:
        v = getattr(row, k, None)
        if v is not None:
            return v
    return default


# ─────────────────────────────────────────────────────────────────────────────
# OBRAS
# ─────────────────────────────────────────────────────────────────────────────

_OBRAS_COLS = ["ID","SB_ID","Nome","Tipo","Cliente","CNPJ Cliente",
               "Endereço","Valor Contrato (R$)","BDI (%)","Início",
               "Término","% Físico","Status","Responsável"]


def obras_load() -> pd.DataFrame:
    """Carrega obras do Supabase → formato app."""
    empty = pd.DataFrame(columns=_OBRAS_COLS)
    try:
        from db import obras_listar
        df = obras_listar()
        if df.empty:
            return empty

        rows = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            rows.append({
                "ID":                  i,
                "SB_ID":               _attr(row, "id"),
                "Nome":                _attr(row, "nome"),
                "Tipo":                _attr(row, "tipo"),
                "Cliente":             _attr(row, "cliente"),
                "CNPJ Cliente":        _attr(row, "cnpj_cliente"),
                "Endereço":            _attr(row, "endereco"),
                "Valor Contrato (R$)": float(_attr(row, "valor_contrato", default=0) or 0),
                "BDI (%)":             round(float(_attr(row, "bdi", default=0.25) or 0.25) * 100, 2),
                "Início":              _iso_to_br(_attr(row, "data_inicio")),
                "Término":             _iso_to_br(_attr(row, "data_termino")),
                "% Físico":            int(float(_attr(row, "pct_fisico", default=0) or 0)),
                "Status":              _attr(row, "status", default="Planejamento"),
                "Responsável":         _attr(row, "responsavel"),
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.obras_load] ERRO:\n", traceback.format_exc())
        return empty


def obra_save(dados: dict, sb_id: str | None = None) -> str | None:
    """Cria ou atualiza uma obra. Retorna UUID ou None."""
    try:
        from db import obra_criar, obra_atualizar
        payload = {
            "nome":           dados.get("Nome", ""),
            "tipo":           dados.get("Tipo") or None,
            "cliente":        dados.get("Cliente") or None,
            "cnpj_cliente":   dados.get("CNPJ Cliente") or None,
            "endereco":       dados.get("Endereço") or None,
            "responsavel":    dados.get("Responsável") or None,
            "valor_contrato": float(dados.get("Valor Contrato (R$)", 0) or 0),
            "bdi":            round(float(dados.get("BDI (%)", 25) or 25) / 100, 6),
            "data_inicio":    _br_to_iso(dados.get("Início")),
            "data_termino":   _br_to_iso(dados.get("Término")),
            "pct_fisico":     int(float(dados.get("% Físico", 0) or 0)),
            "status":         dados.get("Status", "Planejamento"),
            "empresa_id":     _empresa_id(),
        }
        res = obra_atualizar(sb_id, payload) if sb_id else obra_criar(payload)
        return (res or {}).get("id")
    except Exception:
        print("[sync.obra_save] ERRO:\n", traceback.format_exc())
        return None


def obra_delete(sb_id: str):
    try:
        from db import obra_excluir
        obra_excluir(sb_id)
    except Exception:
        print("[sync.obra_delete] ERRO:\n", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# LANÇAMENTOS  →  contas_pagar / contas_receber
# ─────────────────────────────────────────────────────────────────────────────

_PAGAR_COLS   = ["ID","SB_ID","Obra","Fornecedor","Descrição","Categoria",
                 "Valor (R$)","Vencimento","Status","NF","Forma Pag.",
                 "eap_item_id","tipo_custo"]
_RECEBER_COLS = ["ID","SB_ID","Obra","Cliente","Descrição",
                 "Valor (R$)","Vencimento","Status",
                 "eap_item_id","tipo_custo"]

_STATUS_SB = {
    "A Pagar":   "Previsto", "A Receber": "Previsto",
    "Pago":      "Pago",     "Recebido":  "Pago",
    "Vencido":   "Previsto", "Cancelado": "Cancelado",
    "Aprovado":  "Aprovado", "Previsto":  "Previsto",
}
_STATUS_APP_PAGAR   = {"Previsto": "A Pagar",  "Pago": "Pago",     "Cancelado": "Cancelado", "Aprovado": "A Pagar"}
_STATUS_APP_RECEBER = {"Previsto": "A Receber", "Pago": "Recebido", "Cancelado": "Cancelado", "Aprovado": "A Receber"}


def lancamentos_load(tipo: str) -> pd.DataFrame:
    """tipo: 'PAGAR' | 'RECEBER'. Retorna DataFrame vazio se falhar."""
    empty = pd.DataFrame(columns=_PAGAR_COLS if tipo == "PAGAR" else _RECEBER_COLS)
    try:
        from db import lancamentos_listar
        df = lancamentos_listar(tipo)
        if df.empty:
            return empty

        rows = []
        status_map = _STATUS_APP_PAGAR if tipo == "PAGAR" else _STATUS_APP_RECEBER
        for i, row in enumerate(df.itertuples(index=False), start=1):
            obras_nested = _attr(row, "obras", default={}) or {}
            obra_nome    = obras_nested.get("nome", "") if isinstance(obras_nested, dict) else ""
            status_sb    = _attr(row, "status", default="Previsto")
            base = {
                "ID":         i,
                "SB_ID":      _attr(row, "id"),
                "Obra":       obra_nome,
                "Descrição":  _attr(row, "descricao"),
                "Valor (R$)": float(_attr(row, "valor", default=0) or 0),
                "Vencimento": _iso_to_br(_attr(row, "data_vencimento")),
                "Status":     status_map.get(status_sb, status_sb),
                "eap_item_id": _attr(row, "eap_item_id", default=None),
                "tipo_custo":  _attr(row, "tipo_custo", default=None),
            }
            if tipo == "PAGAR":
                base.update({
                    "Fornecedor": _attr(row, "cliente_nome"),
                    "Categoria":  _attr(row, "categoria", default="Materiais"),
                    "NF":         _attr(row, "documento", default="—"),
                    "Forma Pag.": _attr(row, "forma_pagamento", default="Boleto"),
                })
            else:
                base["Cliente"] = _attr(row, "cliente_nome")
            rows.append(base)
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.lancamentos_load] ERRO:\n", traceback.format_exc())
        return empty


def lancamento_save(dados: dict, tipo: str,
                    obra_sb_id: str | None = None,
                    sb_id: str | None = None) -> str | None:
    """Cria ou atualiza um lançamento. Retorna UUID ou None."""
    try:
        from db import lancamento_criar, lancamento_atualizar
        payload = {
            "tipo":            tipo,
            "status":          _STATUS_SB.get(dados.get("Status", ""), "Previsto"),
            "obra_id":         obra_sb_id,
            "cliente_nome":    dados.get("Fornecedor") or dados.get("Cliente") or None,
            "descricao":       dados.get("Descrição", ""),
            "valor":           float(dados.get("Valor (R$)", 0) or 0),
            "categoria":       dados.get("Categoria") or ("Materiais" if tipo == "PAGAR" else None),
            "data_emissao":    datetime.now().strftime("%Y-%m-%d"),
            "data_vencimento": _br_to_iso(dados.get("Vencimento")),
            "documento":       dados.get("NF") or None,
            "forma_pagamento": dados.get("Forma Pag.") or None,
            "empresa_id":      _empresa_id(),
            "eap_item_id":     dados.get("eap_item_id") or None,
            "tipo_custo":      dados.get("tipo_custo") or None,
        }
        res = lancamento_atualizar(sb_id, payload) if sb_id else lancamento_criar(payload)
        return (res or {}).get("id")
    except Exception:
        print("[sync.lancamento_save] ERRO:\n", traceback.format_exc())
        return None


def lancamento_status_update(sb_id: str, status_app: str):
    """Atualiza apenas o status de um lançamento."""
    try:
        from db import lancamento_atualizar
        lancamento_atualizar(sb_id, {"status": _STATUS_SB.get(status_app, "Previsto")})
    except Exception:
        print("[sync.lancamento_status_update] ERRO:\n", traceback.format_exc())


def lancamento_delete(sb_id: str):
    try:
        from db import sb
        sb().table("lancamentos").delete().eq("id", sb_id).execute()
    except Exception:
        print("[sync.lancamento_delete] ERRO:\n", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# COLABORADORES / FUNCIONÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

_FUNC_COLS = ["ID","SB_ID","Nome","Cargo","Tipo Contrato","Obra",
              "Salário (R$)","Admissão","Situação"]


def colaboradores_load() -> pd.DataFrame:
    empty = pd.DataFrame(columns=_FUNC_COLS)
    try:
        from db import colaboradores_listar
        df = colaboradores_listar()
        if df.empty:
            return empty

        rows = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            # Tenta obra_alocada (coluna direta após migração 01_MIGRATION_OBRA_ALOCADA.sql)
            obra_nome = _attr(row, "obra_alocada", default="") or ""
            # Fallback: alocacoes join
            if not obra_nome:
                aloc = _attr(row, "alocacoes", default=[]) or []
                if isinstance(aloc, list) and aloc:
                    first = aloc[0]
                    if isinstance(first, dict):
                        obras_n = first.get("obras", {}) or {}
                        obra_nome = obras_n.get("nome", "") if isinstance(obras_n, dict) else ""

            rows.append({
                "ID":           i,
                "SB_ID":        _attr(row, "id"),
                "Nome":         _attr(row, "nome"),
                "Cargo":        _attr(row, "funcao"),
                "Tipo Contrato":_attr(row, "tipo_contrato", default="CLT"),
                "Obra":         obra_nome,
                "Salário (R$)": float(_attr(row, "salario", default=0) or 0),
                "Admissão":     _iso_to_br(_attr(row, "admissao")),
                "Situação":     "Ativo" if _attr(row, "ativo", default=True) else "Inativo",
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.colaboradores_load] ERRO:\n", traceback.format_exc())
        return empty


def colaborador_save(dados: dict, sb_id: str | None = None) -> str | None:
    try:
        from db import colaborador_criar, colaborador_atualizar
        payload = {
            "nome":          dados.get("Nome", ""),
            "funcao":        dados.get("Cargo") or None,
            "tipo_contrato": dados.get("Tipo Contrato", "CLT"),
            "salario":       float(dados.get("Salário (R$)", 0) or 0),
            "admissao":      _br_to_iso(dados.get("Admissão")),
            "ativo":         dados.get("Situação", "Ativo") == "Ativo",
            "empresa_id":    _empresa_id(),
        }
        # Salva obra_alocada se informada e válida
        obra = dados.get("Obra") or ""
        if obra and not obra.startswith("("):
            payload["obra_alocada"] = obra
        elif sb_id:
            payload["obra_alocada"] = obra or None

        res = colaborador_atualizar(sb_id, payload) if sb_id else colaborador_criar(payload)
        return (res or {}).get("id")
    except Exception:
        print("[sync.colaborador_save] ERRO:\n", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# NÃO CONFORMIDADES
# ─────────────────────────────────────────────────────────────────────────────

_SEV_TO_APP = {"Baixa": "Baixa", "Média": "Moderada", "Alta": "Alta", "Crítica": "Crítica"}
_SEV_TO_SB  = {"Baixa": "Baixa", "Moderada": "Média", "Alta": "Alta", "Crítica": "Crítica"}

_NC_COLS = ["ID","SB_ID","Data Abertura","Obra","Descrição","Gravidade",
            "Responsável","Status","Prazo","Ação Corretiva"]


def ncs_load() -> pd.DataFrame:
    empty = pd.DataFrame(columns=_NC_COLS)
    try:
        from db import ncs_listar
        df = ncs_listar()
        if df.empty:
            return empty

        rows = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            obras_n = _attr(row, "obras", default={}) or {}
            obra_nome = obras_n.get("nome", "") if isinstance(obras_n, dict) else ""
            rows.append({
                "ID":             _attr(row, "numero", default=f"NC-{i:03d}"),
                "SB_ID":          _attr(row, "id"),
                "Data Abertura":  _iso_to_br(str(_attr(row, "created_at"))[:10]),
                "Obra":           obra_nome,
                "Descrição":      _attr(row, "descricao") or _attr(row, "titulo"),
                "Gravidade":      _SEV_TO_APP.get(_attr(row, "severidade", default="Alta"), "Alta"),
                "Responsável":    _attr(row, "responsavel_id", default=""),
                "Status":         _attr(row, "status", default="Aberta"),
                "Prazo":          _iso_to_br(_attr(row, "prazo")),
                "Ação Corretiva": _attr(row, "acao_corretiva"),
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.ncs_load] ERRO:\n", traceback.format_exc())
        return empty


def nc_save(dados: dict, obra_sb_id: str | None = None,
            sb_id: str | None = None) -> str | None:
    try:
        from db import nc_criar, nc_atualizar
        titulo = (dados.get("Descrição", "") or "")[:200]
        payload = {
            "obra_id":        obra_sb_id,
            "titulo":         titulo,
            "descricao":      dados.get("Descrição") or None,
            "severidade":     _SEV_TO_SB.get(dados.get("Gravidade", "Alta"), "Alta"),
            "status":         dados.get("Status", "Aberta"),
            "prazo":          _br_to_iso(dados.get("Prazo")),
            "acao_corretiva": dados.get("Ação Corretiva") or None,
            "empresa_id":     _empresa_id(),
        }
        res = nc_atualizar(sb_id, payload) if sb_id else nc_criar(payload)
        return (res or {}).get("id")
    except Exception:
        print("[sync.nc_save] ERRO:\n", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MEDIÇÕES
# ─────────────────────────────────────────────────────────────────────────────

_MED_COLS = ["ID","SB_ID","Data","Obra","Período","% Medido","Valor Medido (R$)","Observação"]


def medicoes_load() -> pd.DataFrame:
    """Carrega todas as medições de todas as obras."""
    empty = pd.DataFrame(columns=_MED_COLS)
    try:
        from db import sb as _sb
        res = _sb().table("medicoes").select("*, obras(nome)").order("competencia", desc=True).execute()
        if not res.data:
            return empty

        rows = []
        for i, row in enumerate(res.data, start=1):
            obras_n   = row.get("obras", {}) or {}
            obra_nome = obras_n.get("nome", "") if isinstance(obras_n, dict) else ""
            obs_raw   = row.get("observacoes", "") or ""
            # Recupera campos extras do campo observacoes: "PCT:XX|PERIODO:YY|OBS:ZZ"
            pct, periodo, obs_limpa = 0, "", obs_raw
            if obs_raw.startswith("PCT:"):
                for parte in obs_raw.split("|"):
                    if parte.startswith("PCT:"):
                        try: pct = int(parte[4:])
                        except: pass
                    elif parte.startswith("PERIODO:"):
                        periodo = parte[8:]
                    elif parte.startswith("OBS:"):
                        obs_limpa = parte[4:]
            rows.append({
                "ID":               i,
                "SB_ID":            row.get("id", ""),
                "Data":             _iso_to_br(row.get("competencia", "")),
                "Obra":             obra_nome,
                "Período":          periodo,
                "% Medido":         pct,
                "Valor Medido (R$)":float(row.get("valor_total", 0) or 0),
                "Observação":       obs_limpa,
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.medicoes_load] ERRO:\n", traceback.format_exc())
        return empty


def medicao_save(dados: dict, obra_sb_id: str | None = None) -> str | None:
    """Cria uma nova medição. Retorna UUID ou None."""
    try:
        from db import sb as _sb
        pct  = int(dados.get("% Medido", 0) or 0)
        per  = str(dados.get("Período", "") or "")
        obs  = str(dados.get("Observação", "") or "")
        obs_sb = f"PCT:{pct}|PERIODO:{per}|OBS:{obs}"

        # Próximo número desta obra
        num = 1
        if obra_sb_id:
            try:
                r = _sb().table("medicoes").select("numero").eq("obra_id", obra_sb_id)\
                         .order("numero", desc=True).limit(1).execute()
                if r.data:
                    num = (r.data[0].get("numero") or 0) + 1
            except Exception:
                pass

        payload = {
            "obra_id":      obra_sb_id,
            "numero":       num,
            "competencia":  _br_to_iso(dados.get("Data")) or datetime.now().strftime("%Y-%m-%d"),
            "data_emissao": datetime.now().strftime("%Y-%m-%d"),
            "status":       "Aprovado",
            "valor_total":  float(dados.get("Valor Medido (R$)", 0) or 0),
            "observacoes":  obs_sb,
            "empresa_id":   _empresa_id(),
        }
        res = _sb().table("medicoes").insert(payload).execute()
        return (res.data[0] if res.data else {}).get("id")
    except Exception:
        print("[sync.medicao_save] ERRO:\n", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PONTO (FALTAS)
# ─────────────────────────────────────────────────────────────────────────────

_PONTO_COLS = ["ID","SB_ID","Data","Funcionário","Obra","Tipo","Observação"]


def _colaborador_uuid_por_nome(nome: str) -> str | None:
    """Busca UUID do colaborador pelo nome."""
    try:
        from db import sb as _sb
        res = _sb().table("colaboradores").select("id").eq("nome", nome).limit(1).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        print("[sync._colaborador_uuid_por_nome] ERRO:\n", traceback.format_exc())
        return None


def faltas_load() -> pd.DataFrame:
    """Carrega registros de ponto onde falta=True."""
    empty = pd.DataFrame(columns=_PONTO_COLS)
    try:
        from db import sb as _sb
        res = _sb().table("ponto").select("*, colaboradores(nome), obras(nome)")\
                   .eq("falta", True).order("data", desc=True).execute()
        if not res.data:
            return empty

        rows = []
        for i, row in enumerate(res.data, start=1):
            col_n  = (row.get("colaboradores") or {}).get("nome", "")
            obra_n = (row.get("obras") or {}).get("nome", "")
            obs    = row.get("observacao") or ""
            tipo   = "Abono" if obs.startswith("ABONO:") else "Falta"
            obs    = obs.removeprefix("ABONO:").strip()
            rows.append({
                "ID":          i,
                "SB_ID":       row.get("id", ""),
                "Data":        _iso_to_br(row.get("data", "")),
                "Funcionário": col_n,
                "Obra":        obra_n,
                "Tipo":        tipo,
                "Observação":  obs,
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.faltas_load] ERRO:\n", traceback.format_exc())
        return empty


def falta_save(dados: dict, obra_sb_id: str | None = None) -> str | None:
    """Registra uma falta/abono no ponto. Retorna UUID ou None."""
    try:
        from db import sb as _sb
        func_nome = dados.get("Funcionário", "")
        col_id = _colaborador_uuid_por_nome(func_nome)
        if not col_id:
            print(f"[sync.falta_save] Colaborador não encontrado: {func_nome}")
            return None

        tipo   = dados.get("Tipo", "Falta")
        obs    = dados.get("Observação", "") or ""
        obs_sb = f"ABONO:{obs}" if tipo == "Abono" else obs

        payload = {
            "colaborador_id": col_id,
            "obra_id":        obra_sb_id,
            "data":           _br_to_iso(dados.get("Data")) or datetime.now().strftime("%Y-%m-%d"),
            "falta":          True,
            "observacao":     obs_sb,
            "empresa_id":     _empresa_id(),
        }
        res = _sb().table("ponto").upsert(payload, on_conflict="colaborador_id,data").execute()
        return (res.data[0] if res.data else {}).get("id")
    except Exception:
        print("[sync.falta_save] ERRO:\n", traceback.format_exc())
        return None


_PONTO_REGISTRO_COLS = ["ID","SB_ID","Data","Funcionário","Obra","Entrada","Saída Almoço",
                         "Retorno Almoço","Saída","Horas Normais","Horas Extras","Observação"]


def ponto_registro_load() -> pd.DataFrame:
    """Carrega registros de ponto com horário batido (falta=False)."""
    empty = pd.DataFrame(columns=_PONTO_REGISTRO_COLS)
    try:
        from db import sb as _sb
        res = _sb().table("ponto").select("*, colaboradores(nome), obras(nome)")\
                   .eq("falta", False).order("data", desc=True).execute()
        if not res.data:
            return empty

        rows = []
        for i, row in enumerate(res.data, start=1):
            col_n  = (row.get("colaboradores") or {}).get("nome", "")
            obra_n = (row.get("obras") or {}).get("nome", "")
            rows.append({
                "ID":              i,
                "SB_ID":           row.get("id", ""),
                "Data":            _iso_to_br(row.get("data", "")),
                "Funcionário":     col_n,
                "Obra":            obra_n,
                "Entrada":         (row.get("entrada") or "")[:5],
                "Saída Almoço":    (row.get("saida_almoco") or "")[:5],
                "Retorno Almoço":  (row.get("retorno_almoco") or "")[:5],
                "Saída":           (row.get("saida") or "")[:5],
                "Horas Normais":   row.get("horas_normais") or 0,
                "Horas Extras":    row.get("horas_extras") or 0,
                "Observação":      row.get("observacao") or "",
            })
        return pd.DataFrame(rows)
    except Exception:
        print("[sync.ponto_registro_load] ERRO:\n", traceback.format_exc())
        return empty


def ponto_registro_save(dados: dict, obra_sb_id: str | None = None) -> str | None:
    """Registra o ponto batido do dia (entrada/almoço/saída) de um colaborador. Retorna UUID ou None."""
    try:
        from db import sb as _sb
        func_nome = dados.get("Funcionário", "")
        col_id = _colaborador_uuid_por_nome(func_nome)
        if not col_id:
            print(f"[sync.ponto_registro_save] Colaborador não encontrado: {func_nome}")
            return None

        payload = {
            "colaborador_id":  col_id,
            "obra_id":         obra_sb_id,
            "data":            _br_to_iso(dados.get("Data")) or datetime.now().strftime("%Y-%m-%d"),
            "entrada":         dados.get("Entrada") or None,
            "saida_almoco":    dados.get("Saída Almoço") or None,
            "retorno_almoco":  dados.get("Retorno Almoço") or None,
            "saida":           dados.get("Saída") or None,
            "horas_normais":   dados.get("Horas Normais"),
            "horas_extras":    dados.get("Horas Extras"),
            "falta":           False,
            "observacao":      dados.get("Observação", "") or "",
            "empresa_id":      _empresa_id(),
        }
        res = _sb().table("ponto").upsert(payload, on_conflict="colaborador_id,data").execute()
        return (res.data[0] if res.data else {}).get("id")
    except Exception:
        print("[sync.ponto_registro_save] ERRO:\n", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ESTOQUE / INSUMOS
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_insumo(descricao: str, unidade: str = "un") -> str | None:
    """Retorna UUID do insumo pelo nome, criando se não existir."""
    try:
        from db import sb as _sb
        desc = descricao.strip()
        res = _sb().table("insumos").select("id").ilike("descricao", desc).limit(1).execute()
        if res.data:
            return res.data[0]["id"]
        codigo = desc[:6].upper().replace(" ", "_")
        novo = _sb().table("insumos").insert({
            "codigo":     codigo,
            "descricao":  desc,
            "unidade":    unidade,
            "empresa_id": _empresa_id(),
        }).execute()
        return (novo.data[0] if novo.data else {}).get("id")
    except Exception:
        print("[sync._get_or_create_insumo] ERRO:\n", traceback.format_exc())
        return None


def estoque_movimento_save(dados: dict, obra_sb_id: str | None = None) -> bool:
    """
    Salva movimento de estoque (ENTRADA ou SAIDA).
    dados: Insumo, Unidade, Tipo ('Entrada'|'Saída'), Quantidade, Observação
    Retorna True se salvou com sucesso.
    """
    try:
        from db import estoque_entrada, estoque_saida
        desc  = dados.get("Insumo", "")
        unid  = dados.get("Unidade", "un")
        qtd   = float(dados.get("Quantidade", 0) or 0)
        tipo  = dados.get("Tipo", "Entrada")
        obs   = dados.get("Observação", "") or None

        insumo_id = _get_or_create_insumo(desc, unid)
        if not insumo_id:
            return False

        payload = {
            "insumo_id":  insumo_id,
            "obra_id":    obra_sb_id,
            "quantidade": qtd,
            "observacao": obs,
            "empresa_id": _empresa_id(),
        }
        if tipo == "Entrada":
            estoque_entrada(payload)
        else:
            estoque_saida(payload)
        return True
    except Exception:
        print("[sync.estoque_movimento_save] ERRO:\n", traceback.format_exc())
        return False


# ── RDO ──────────────────────────────────────────────────────────────────────

_RDO_COLS = ["ID", "SB_ID", "Obra", "Data", "Responsável", "Clima Manhã", "Clima Tarde",
             "Efetivo Total", "Atividades", "Ocorrências", "Equipamentos", "Status Dia", "Observações", "fotos"]


def _parse_fotos(v):
    import json as _j
    if not v:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            return _j.loads(v)
        except Exception:
            return []
    return []


def rdo_load() -> pd.DataFrame:
    try:
        from db import sb
        res = sb().table("rdo").select("*, obras(nome)").order("data", desc=True).execute()
        rows = []
        for r in (res.data or []):
            obra_nome = (r.get("obras") or {}).get("nome", "") if isinstance(r.get("obras"), dict) else ""
            rows.append({
                "ID":            str(r.get("id", "")),
                "SB_ID":         str(r.get("id", "")),
                "Obra":          obra_nome,
                "Data":          r.get("data", ""),
                "Responsável":   r.get("responsavel", ""),
                "Clima Manhã":   r.get("clima_manha", "Ensolarado"),
                "Clima Tarde":   r.get("clima_tarde", "Ensolarado"),
                "Efetivo Total": int(r.get("efetivo_total") or 0),
                "Atividades":    r.get("atividades", ""),
                "Ocorrências":   r.get("ocorrencias", ""),
                "Equipamentos":  r.get("equipamentos", ""),
                "Status Dia":    r.get("status_dia", "Normal"),
                "Observações":   r.get("observacoes", ""),
                "fotos":         _parse_fotos(r.get("fotos")),
            })
        return pd.DataFrame(rows, columns=_RDO_COLS) if rows else pd.DataFrame(columns=_RDO_COLS)
    except Exception:
        print("[sync.rdo_load] ERRO:\n", traceback.format_exc())
        return pd.DataFrame(columns=_RDO_COLS)


def rdo_save(dados: dict, sb_id: str | None = None) -> str | None:
    try:
        from db import sb
        payload = {
            "data":          dados.get("Data"),
            "responsavel":   dados.get("Responsável") or None,
            "clima_manha":   dados.get("Clima Manhã", "Ensolarado"),
            "clima_tarde":   dados.get("Clima Tarde", "Ensolarado"),
            "efetivo_total": int(dados.get("Efetivo Total") or 0),
            "atividades":    dados.get("Atividades") or None,
            "ocorrencias":   dados.get("Ocorrências") or None,
            "equipamentos":  dados.get("Equipamentos") or None,
            "status_dia":    dados.get("Status Dia", "Normal"),
            "observacoes":   dados.get("Observações") or None,
            "empresa_id":    _empresa_id(),
        }
        obra_nome = dados.get("Obra", "")
        if obra_nome:
            try:
                ob = sb().table("obras").select("id").eq("nome", obra_nome).execute()
                if ob.data:
                    payload["obra_id"] = ob.data[0]["id"]
            except Exception:
                pass
        if sb_id:
            res = sb().table("rdo").update(payload).eq("id", sb_id).execute()
        else:
            res = sb().table("rdo").insert(payload).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        print("[sync.rdo_save] ERRO:\n", traceback.format_exc())
        return None


def upload_rdo_foto(rdo_id: str, arquivo, filename: str) -> str | None:
    """Faz upload de uma foto para o bucket rdo-fotos e retorna a URL pública."""
    import uuid as _uuid
    try:
        from db import sb
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        path = f"rdo/{rdo_id}/{_uuid.uuid4().hex}.{ext}"
        content = arquivo.read() if hasattr(arquivo, "read") else arquivo
        content_type = getattr(arquivo, "type", None) or f"image/{ext}"
        sb().storage.from_("rdo-fotos").upload(
            path, content,
            file_options={"content-type": content_type, "upsert": "false"}
        )
        url = sb().storage.from_("rdo-fotos").get_public_url(path)
        return url
    except Exception:
        print("[sync.upload_rdo_foto] ERRO:\n", traceback.format_exc())
        return None


def rdo_update_fotos(rdo_id: str, fotos: list) -> bool:
    """Atualiza o campo fotos (lista de dicts {nome, url}) de um registro RDO."""
    try:
        from db import sb
        sb().table("rdo").update({"fotos": fotos}).eq("id", rdo_id).execute()
        return True
    except Exception:
        print("[sync.rdo_update_fotos] ERRO:\n", traceback.format_exc())
        return False


# ─────────────────────────────────────────────────────────────────────────────
# REQUISIÇÕES DE MATERIAIS
# ─────────────────────────────────────────────────────────────────────────────

_REQ_COLS = ["ID", "SB_ID", "Data", "Obra", "Insumo", "Quantidade",
             "Unidade", "Status", "Solicitante", "Observação",
             "Aprovado Por", "Data Aprovação"]


def requisicoes_load() -> pd.DataFrame:
    empty = pd.DataFrame(columns=_REQ_COLS)
    try:
        from db import sb
        rows = (
            sb().table("requisicoes")
            .select("*")
            .eq("empresa_id", _empresa_id())
            .order("data_solicitacao", desc=True)
            .execute()
        ).data or []
        if not rows:
            return empty
        records = []
        for i, r in enumerate(rows, 1):
            records.append({
                "ID":             i,
                "SB_ID":          r["id"],
                "Data":           _iso_to_br(r.get("data_solicitacao")),
                "Obra":           r.get("obra_nome") or "",
                "Insumo":         r.get("insumo_nome") or "",
                "Quantidade":     float(r.get("quantidade") or 0),
                "Unidade":        r.get("unidade") or "un",
                "Status":         r.get("status") or "Pendente",
                "Solicitante":    r.get("solicitante") or "",
                "Observação":     r.get("observacao") or "",
                "Aprovado Por":   r.get("aprovado_por") or "",
                "Data Aprovação": _iso_to_br(r.get("data_aprovacao")),
            })
        return pd.DataFrame(records)
    except Exception:
        print("[sync.requisicoes_load] ERRO:\n", traceback.format_exc())
        return empty


def requisicao_save(dados: dict) -> str | None:
    try:
        from db import sb
        payload = {
            "empresa_id":       _empresa_id(),
            "obra_nome":        dados.get("Obra") or None,
            "insumo_nome":      dados.get("Insumo") or "",
            "quantidade":       float(dados.get("Quantidade") or 1),
            "unidade":          dados.get("Unidade") or "un",
            "status":           "Pendente",
            "solicitante":      dados.get("Solicitante") or None,
            "observacao":       dados.get("Observação") or None,
            "data_solicitacao": _br_to_iso(dados.get("Data")) or None,
            "eap_item_id":      dados.get("eap_item_id") or None,
            "tipo_custo":       dados.get("tipo_custo") or None,
        }
        obra_nome = dados.get("Obra", "")
        if obra_nome:
            try:
                ob = sb().table("obras").select("id").eq("nome", obra_nome).execute()
                if ob.data:
                    payload["obra_id"] = ob.data[0]["id"]
            except Exception:
                pass
        res = sb().table("requisicoes").insert(payload).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        print("[sync.requisicao_save] ERRO:\n", traceback.format_exc())
        return None


# ── ORÇAMENTO ────────────────────────────────────────────────────────────────


def orcamento_save(obra_sb_id: str, nome: str, versao: int,
                   base_ref: str, bdi_pct: float, encargos: float,
                   total_custo: float, total_venda: float,
                   status: str, itens: list[dict]) -> str | None:
    """Salva orçamento (header + itens) no Supabase.

    itens = [
        {"ordem": "1.1", "descricao": "...", "unidade": "m³",
         "quantidade": 120.0, "preco_unit": 38.0,
         "tipo": "ETAPA"|"ITEM", "nivel": 1, ...}
    ]
    """
    try:
        from db import sb
        from datetime import date
        user = sb().auth.get_user()
        user_id = user.user.id if user and user.user else None

        eid = _empresa_id()

        # Header
        header = {
            "obra_id":  obra_sb_id,
            "nome":     nome,
            "versao":   versao,
            "base_referencia": base_ref,
            "bdi":              bdi_pct / 100.0,
            "encargos_sociais": encargos / 100.0,
            "total_custo":      round(total_custo, 2),
            "total_venda":      round(total_venda, 2),
            "status": status,
            "created_by": user_id,
            "empresa_id": eid,
        }
        res = sb().table("orcamentos").insert(header).execute()
        if not res.data:
            return None
        orc_id = res.data[0]["id"]

        # Itens — salva em duas etapas para resolver composicao_id FK
        parent_rows = []
        child_rows = []
        ordem_to_parent_id = {}
        for it in itens:
            if it.get("tipo") != "ITEM":
                continue
            composicao_ref = it.get("composicao_id") or None
            if composicao_ref:
                child_rows.append(it)
            else:
                parent_rows.append(it)

        # 1. Salva pais (sem composicao_id) e captura IDs
        if parent_rows:
            parent_payload = [{
                "orcamento_id": orc_id,
                "ordem":        str(it.get("ordem", "")),
                "descricao":    it.get("descricao", ""),
                "unidade":      it.get("unidade", ""),
                "quantidade":   float(it.get("quantidade", 0) or 0),
                "preco_unit":   float(it.get("preco_custo", 0) or 0),
                "empresa_id":   eid,
            } for it in parent_rows]
            parent_res = sb().table("orcamento_itens").insert(parent_payload).execute()
            if parent_res.data:
                for saved, orig in zip(parent_res.data, parent_rows):
                    ordem_to_parent_id[orig.get("ordem", "")] = saved["id"]

        # 2. Salva filhos com composicao_id resolvido
        if child_rows:
            child_payload = [{
                "orcamento_id":  orc_id,
                "ordem":         str(it.get("ordem", "")),
                "descricao":     it.get("descricao", ""),
                "unidade":       it.get("unidade", ""),
                "quantidade":    float(it.get("quantidade", 0) or 0),
                "preco_unit":    float(it.get("preco_custo", 0) or 0),
                "empresa_id":    eid,
                "composicao_id": ordem_to_parent_id.get(it.get("composicao_id")),
            } for it in child_rows]
            sb().table("orcamento_itens").insert(child_payload).execute()

        return orc_id
    except Exception:
        print("[sync.orcamento_save] ERRO:\n", traceback.format_exc())
        return None


def orcamento_load() -> list[dict]:
    """Carrega todos os orçamentos com itens."""
    try:
        from db import sb
        orcs = sb().table("orcamentos").select("*, obras(id, nome)").eq("empresa_id", _empresa_id()).order("created_at", desc=True).execute()
        result = []
        for o in orcs.data or []:
            bdi_dec = float(o.get("bdi", 0) or 0)
            bdi_fator = 1.0 + bdi_dec
            itens_raw = sb().table("orcamento_itens").select("*").eq("orcamento_id", o["id"]).order("ordem").execute()
            itens = []
            for i in itens_raw.data or []:
                qtd = float(i.get("quantidade", 0) or 0)
                pu_custo = float(i.get("preco_unit", 0) or 0)
                pu_venda = round(pu_custo * bdi_fator, 4)
                tot_custo = round(qtd * pu_custo, 2)
                tot_venda = round(qtd * pu_venda, 2)
                itens.append({
                    "ordem":        i.get("ordem", ""),
                    "descricao":    i.get("descricao", ""),
                    "unidade":      i.get("unidade", ""),
                    "quantidade":   qtd,
                    "preco_custo":  pu_custo,
                    "preco_venda":  pu_venda,
                    "total_custo":  tot_custo,
                    "total_venda":  tot_venda,
                    "tipo":         "ITEM",
                })
            result.append({
                "id":             o["id"],
                "obra_id":        o.get("obra_id"),
                "obra_nome":      o.get("obras", {}).get("nome") if o.get("obras") else None,
                "nome":           o.get("nome"),
                "versao":         o.get("versao"),
                "base_referencia": o.get("base_referencia"),
                "bdi":            o.get("bdi", 0) * 100,
                "total_custo":    o.get("total_custo", 0),
                "total_venda":    o.get("total_venda", 0),
                "status":         o.get("status"),
                "itens":          itens,
            })
        return result
    except Exception:
        print("[sync.orcamento_load] ERRO:\n", traceback.format_exc())
        return []


# ── EAP ──────────────────────────────────────────────────────────────────────


def eap_save_from_orcamento(obra_sb_id: str, itens: list[dict]) -> bool:
    """Gera/atualiza a EAP de uma obra a partir dos itens de orçamento."""
    try:
        from db import sb
        eid = _empresa_id()
        # Remove EAP existente
        sb().table("eap_itens").delete().eq("obra_id", obra_sb_id).execute()
        # Insere itens
        rows = []
        ordem = 0
        for it in itens:
            _desc = it.get("descricao", "")
            if not _desc:
                continue
            rows.append({
                "obra_id":       obra_sb_id,
                "codigo":        str(it.get("ordem", "")),
                "descricao":     _desc,
                "unidade":       it.get("unidade", ""),
                "qtd_prevista":  float(it.get("quantidade", 0) or 0),
                "valor_previsto": float(it.get("total_venda", 0) or 0),
                "ordem":         ordem,
                "empresa_id":    eid,
            })
            ordem += 1
        if rows:
            sb().table("eap_itens").insert(rows).execute()
        return True
    except Exception:
        print("[sync.eap_save_from_orcamento] ERRO:\n", traceback.format_exc())
        return False


def eap_load(obra_sb_id: str) -> list[dict]:
    """Carrega EAP de uma obra."""
    try:
        from db import sb
        res = sb().table("eap_itens").select("*").eq("obra_id", obra_sb_id).eq("empresa_id", _empresa_id()).order("ordem").execute()
        return res.data or []
    except Exception:
        print("[sync.eap_load] ERRO:\n", traceback.format_exc())
        return []


def eap_update_progresso(obra_sb_id: str, codigo: str, progresso: float) -> bool:
    """Salva o % de avanço de uma etapa EAP."""
    try:
        from db import sb
        sb().table("eap_itens").update({"progresso": round(progresso / 100, 4)}).eq("obra_id", obra_sb_id).eq("codigo", codigo).execute()
        return True
    except Exception:
        print("[sync.eap_update_progresso] ERRO:\n", traceback.format_exc())
        return False


def eap_update_datas(obra_sb_id: str, codigo: str, data_inicio: str, data_termino: str) -> bool:
    """Salva datas de uma etapa EAP. Recebe strings dd/mm/YYYY."""
    try:
        from db import sb
        payload = {}
        if data_inicio:
            payload["data_inicio"] = _br_to_iso(data_inicio)
        if data_termino:
            payload["data_termino"] = _br_to_iso(data_termino)
        if payload:
            sb().table("eap_itens").update(payload).eq("obra_id", obra_sb_id).eq("codigo", codigo).execute()
        return True
    except Exception:
        print("[sync.eap_update_datas] ERRO:\n", traceback.format_exc())
        return False


def eap_save_all_progresso(obra_sb_id: str, progressos: dict[str, float]) -> bool:
    """Salva múltiplos progressos de uma vez. progressos = {codigo: pct}"""
    try:
        from db import sb
        for codigo, pct in progressos.items():
            sb().table("eap_itens").update({"progresso": round(pct / 100, 4)}).eq("obra_id", obra_sb_id).eq("codigo", codigo).execute()
        return True
    except Exception:
        print("[sync.eap_save_all_progresso] ERRO:\n", traceback.format_exc())
        return False


def eap_save_all_datas(obra_sb_id: str, datas: dict[str, dict]) -> bool:
    """Salva múltiplas datas de uma vez. datas = {codigo: {ini: ..., fim: ...}}"""
    try:
        from db import sb
        for codigo, d in datas.items():
            payload = {}
            if d.get("ini"):
                payload["data_inicio"] = _br_to_iso(d["ini"])
            if d.get("fim"):
                payload["data_termino"] = _br_to_iso(d["fim"])
            if payload:
                sb().table("eap_itens").update(payload).eq("obra_id", obra_sb_id).eq("codigo", codigo).execute()
        return True
    except Exception:
        print("[sync.eap_save_all_datas] ERRO:\n", traceback.format_exc())
        return False


def requisicao_status_update(sb_id: str, status: str, aprovado_por: str = "") -> bool:
    try:
        from db import sb
        from datetime import date
        payload: dict = {"status": status}
        if status == "Aprovada":
            payload["aprovado_por"]   = aprovado_por or None
            payload["data_aprovacao"] = date.today().isoformat()
        sb().table("requisicoes").update(payload).eq("id", sb_id).execute()
        return True
    except Exception:
        print("[sync.requisicao_status_update] ERRO:\n", traceback.format_exc())
        return False

