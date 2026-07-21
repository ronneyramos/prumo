"""
Importa planilhas "Controle Custo - *.xlsm" para o Supabase (MBR ERP).
Faz a importacao completa: obras, lancamentos, suprimentos/insumos,
colaboradores, folha de pagamento e orcamento.

Uso: python scripts/import_planilhas.py
"""
import os, sys, warnings
from datetime import datetime
warnings.filterwarnings("ignore")

_env_path = os.path.join(os.path.dirname(__file__), "..", "streamlit", ".env")
from dotenv import load_dotenv; load_dotenv(_env_path)
from supabase import create_client
import pandas as pd

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_ANON_KEY"]
EMPRESA_ID = "00000000-0000-0000-0000-000000000001"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

ARQUIVOS = [
    (r"D:\Ronney\Mbr\Crduarte\Controle Custo - CrDuarte.xlsm",   "CR Duarte",     "SÃO JOSE PACATUBA"),
    (r"D:\Ronney\Mbr\Colmeia\Controle Custo - Colmeia.xlsm",     "Colmeia",        None),
    (r"D:\Ronney\Mbr\Victa Joquei\Controle Custo - Joquei.xlsm", "Victa Joquei",   "VICTA JOQUEI"),
]

MATERIAL_TIPOS = {"MAT. CONSTRUÇÃO", "FERRAMENTAS", "EQUIP. PROPRIO",
                  "COMBUST. EQUIPAM.", "COMBUST. VEICULO", "AGUA POTÁVEL",
                  "ENERGIA/AGUA/ESGOTO/IPTU", "LOCAÇÃO EQUIP."}

# ─── helpers ───────────────────────────────────────────────────

def parse_valor(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try: return float(s)
    except: return 0.0

def parse_data(v):
    if v is None: return None
    if isinstance(v, datetime): return v.date().isoformat()
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try: return datetime.strptime(s[:10], fmt).date().isoformat()
        except: continue
    return None

# ─── cache helpers (Supabase) ──────────────────────────────────

_obra_cache = {}
_forn_cache = {}
_insumo_cache = {}

def get_or_create_obra(nome: str, cliente: str = "") -> str | None:
    nome = nome.strip().upper()
    if nome in _obra_cache:
        return _obra_cache[nome]
    res = sb.table("obras").select("id").ilike("nome", nome).execute()
    if res.data:
        _obra_cache[nome] = res.data[0]["id"]
        return res.data[0]["id"]
    payload = {
        "empresa_id": EMPRESA_ID,
        "nome": nome.title(),
        "cliente": cliente,
        "status": "Em andamento",
        "tipo": "residencial",
    }
    res = sb.table("obras").insert(payload).execute()
    if res.data:
        oid = res.data[0]["id"]
        _obra_cache[nome] = oid
        print(f"  [+] Obra criada: {nome.title()}")
        return oid
    return None

def get_or_create_fornecedor(nome: str) -> str | None:
    if not nome or nome in ("Não informado", ""):
        return None
    if nome in _forn_cache:
        return _forn_cache[nome]
    res = sb.table("fornecedores").select("id").eq("razao_social", nome).execute()
    if res.data:
        _forn_cache[nome] = res.data[0]["id"]
        return res.data[0]["id"]
    payload = {"empresa_id": EMPRESA_ID, "razao_social": nome}
    res = sb.table("fornecedores").insert(payload).execute()
    if res.data:
        fid = res.data[0]["id"]
        _forn_cache[nome] = fid
        return fid
    return None

def get_or_create_insumo(descricao: str, unidade: str = "un") -> str | None:
    key = descricao.strip().upper()
    if key in _insumo_cache:
        return _insumo_cache[key]
    res = sb.table("insumos").select("id").ilike("descricao", descricao.strip()).limit(1).execute()
    if res.data:
        _insumo_cache[key] = res.data[0]["id"]
        return res.data[0]["id"]
    codigo = descricao.strip()[:6].upper().replace(" ", "_")
    payload = {
        "codigo": codigo,
        "descricao": descricao.strip(),
        "unidade": unidade,
        "empresa_id": EMPRESA_ID,
    }
    res = sb.table("insumos").insert(payload).execute()
    if res.data:
        iid = res.data[0]["id"]
        _insumo_cache[key] = iid
        return iid
    return None

# ─── extrair metadata ─────────────────────────────────────────

def extrair_metadata(df: pd.DataFrame) -> dict:
    meta = {"cliente": "", "obra": "", "total": 0.0}
    for i in range(5):
        linha = df.iloc[i]
        vals = [str(v).strip() for v in linha if pd.notna(v)]
        for j, v in enumerate(vals):
            if v == "CLIENTE:" and j + 1 < len(vals):
                meta["cliente"] = vals[j + 1]
            elif v == "OBRA:" and j + 1 < len(vals):
                meta["obra"] = vals[j + 1]
            elif "TOTAL:" in v and j + 1 < len(vals):
                try: meta["total"] = float(vals[j + 1])
                except: pass
    return meta

# ─── extrair lancamentos ──────────────────────────────────────

def extrair_lancamentos(df: pd.DataFrame) -> list[dict]:
    lancamentos = []
    for i in range(6, len(df)):
        row = df.iloc[i]
        contrato   = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        emissao    = row.iloc[1] if pd.notna(row.iloc[1]) else None
        fantasia   = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        razao      = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        documento  = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        competencia = row.iloc[5] if pd.notna(row.iloc[5]) else None
        tipo_custo = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else ""
        unidade    = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else ""
        quant      = row.iloc[8] if pd.notna(row.iloc[8]) else None
        preco_unit = row.iloc[9] if pd.notna(row.iloc[9]) else None
        valor      = row.iloc[10] if pd.notna(row.iloc[10]) else None
        vencimento = row.iloc[11] if pd.notna(row.iloc[11]) else None
        descricao  = str(row.iloc[12]).strip() if pd.notna(row.iloc[12]) else ""
        aplicacao  = str(row.iloc[13]).strip() if pd.notna(row.iloc[13]) else ""
        envio      = str(row.iloc[14]).strip() if pd.notna(row.iloc[14]) else ""

        if not contrato and not descricao and not valor:
            continue

        fornecedor = razao or fantasia or "Não informado"
        v = parse_valor(valor)
        tc = tipo_custo.upper() if tipo_custo else "OUTROS"

        desc = descricao or contrato

        lancamentos.append({
            "contrato": contrato,
            "fornecedor": fornecedor,
            "fantasia": fantasia,
            "documento": documento,
            "tipo_custo": tc,
            "unidade": unidade,
            "quantidade": parse_valor(quant),
            "preco_unit": parse_valor(preco_unit),
            "valor": v,
            "emissao": parse_data(emissao),
            "vencimento": parse_data(vencimento),
            "descricao": desc,
            "aplicacao": aplicacao,
            "envio": envio,
        })
    return lancamentos

# ─── importar lancamentos ─────────────────────────────────────

def category_from_tipo(tc: str) -> str:
    if "FOLHA" in tc: return "Mão de Obra"
    if "ALIMENTA" in tc: return "Alimentação"
    if "ALOJAMENTO" in tc: return "Alojamento"
    if "TRANSPORTE" in tc: return "Transporte"
    if "LOCAÇÃO" in tc or "LOCACAO" in tc: return "Equipamentos"
    if "FERRAMENTA" in tc: return "Ferramentas"
    if "EXAME" in tc: return "Exames"
    if "MAT." in tc or "MATERIAL" in tc: return "Materiais"
    if "EQUIP" in tc: return "Equipamentos"
    if "COMBUST" in tc: return "Combustível"
    if "ENERGIA" in tc or "AGUA" in tc: return "Utilidades"
    if "OUTROS" in tc: return "Outros"
    return "Outros"

def is_material_type(tc: str) -> bool:
    for t in MATERIAL_TIPOS:
        if t in tc:
            return True
    return False

def importar_lancamentos(obra_uuid: str, lancamentos: list[dict]) -> tuple:
    inseridos = 0
    erros = 0
    materiais_insumo = []
    for lanc in lancamentos:
        fn = lanc["fornecedor"]
        fornecedor_uuid = get_or_create_fornecedor(fn) if fn and fn != "Não informado" else None

        tc = lanc["tipo_custo"]
        categoria = category_from_tipo(tc)
        desc = lanc["descricao"][:200] if lanc["descricao"] else f"{lanc['contrato']} - {tc}"

        payload = {
            "empresa_id": EMPRESA_ID,
            "tipo": "PAGAR",
            "status": "Previsto",
            "obra_id": obra_uuid,
            "fornecedor_id": fornecedor_uuid,
            "cliente_nome": lanc["fornecedor"],
            "descricao": desc,
            "valor": lanc["valor"],
            "data_emissao": lanc["emissao"] or datetime.now().date().isoformat(),
            "data_vencimento": lanc["vencimento"] or lanc["emissao"] or datetime.now().date().isoformat(),
            "documento": lanc["documento"][:50] if lanc["documento"] else None,
            "tipo_custo": tc,
            "categoria": categoria,
            "origem": "importacao_planilha",
        }

        try:
            res = sb.table("lancamentos").insert(payload).execute()
            if res.data:
                inseridos += 1
                if is_material_type(tc) and lanc["valor"] > 0:
                    materiais_insumo.append({
                        "descricao": desc,
                        "unidade": lanc["unidade"] or "un",
                        "valor": lanc["valor"],
                        "quantidade": lanc["quantidade"] if lanc["quantidade"] > 0 else 1,
                        "obra_id": obra_uuid,
                        "fornecedor": lanc["fornecedor"],
                    })
            else:
                erros += 1
        except Exception as e:
            print(f"  [!] Erro lancamento: {desc[:60]}... -> {e}")
            erros += 1

    return inseridos, erros, materiais_insumo

# ─── importar insumos / estoque ───────────────────────────────

def importar_insumos(materiais: list[dict]):
    if not materiais:
        return 0, 0
    print(f"  Importando {len(materiais)} materiais para insumos/estoque...")
    ok = 0
    err = 0
    for mat in materiais:
        desc = mat["descricao"][:100]
        unid = mat["unidade"] or "un"
        insumo_id = get_or_create_insumo(desc, unid)
        if not insumo_id:
            err += 1
            continue
        payload = {
            "empresa_id": EMPRESA_ID,
            "insumo_id": insumo_id,
            "obra_id": mat["obra_id"],
            "quantidade": mat["quantidade"],
        }
        try:
            sb.table("estoque_movimentos").insert({**payload, "tipo": "ENTRADA"}).execute()
            ok += 1
        except Exception as e:
            err += 1
    return ok, err

# ─── importar colaboradores ───────────────────────────────────

def importar_colaboradores(obra_ids: dict):
    """Extrai funcionarios das abas RESULTADO (Cerâmica) e FP_*."""
    criados = 0
    visitados = set()

    for caminho, rotulo, obra_forcada in ARQUIVOS:
        xl = pd.ExcelFile(caminho, engine="openpyxl")
        obra_info = obra_ids.get(rotulo, {})
        obra_nome = obra_info.get("nome", "") or (obra_forcada or "")
        obra_uuid = obra_info.get("id", None)

        # RESULTADO (Ceramica) - only for CR Duarte & Victa Joquei (Colmeia tem orcamento)
        if rotulo != "Colmeia" and "RESULTADO" in xl.sheet_names:
            df = pd.read_excel(caminho, sheet_name="RESULTADO", header=None, engine="openpyxl")
            for i in range(len(df)):
                row = df.iloc[i]
                nome = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                cargo = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                if nome and nome not in visitados and nome != "Funcionário" and nome != "Cerâmica":
                    visitados.add(nome)
                    if criar_colaborador(nome, cargo, obra_uuid, obra_nome):
                        criados += 1

        # FP_* sheets - tem Nome + Função nas linhas (header na linha 6)
        for sheet in xl.sheet_names:
            if sheet.startswith("FP_"):
                df_fp = pd.read_excel(caminho, sheet_name=sheet, header=None, engine="openpyxl")
                for i in range(7, len(df_fp)):
                    nome_fp = str(df_fp.iloc[i, 1]).strip() if pd.notna(df_fp.iloc[i, 1]) else ""
                    funcao_fp = str(df_fp.iloc[i, 2]).strip() if pd.notna(df_fp.iloc[i, 2]) else ""
                    if nome_fp and nome_fp not in visitados and nome_fp != "Nome":
                        visitados.add(nome_fp)
                        if criar_colaborador(nome_fp, funcao_fp, obra_uuid, obra_nome):
                            criados += 1
    return criados

def _is_person_name(nome: str) -> bool:
    """Filtra nomes que parecem ser de pessoas (nao codigos/rotulos de planilha)."""
    if not nome or len(nome) < 3:
        return False
    # Ignora codigos como "1", "1.1", "ITEM", "VALOR ORCAMENTO", etc
    if nome[0].isdigit():
        return False
    upper_stop = {"ITEM", "DESCRIÇÃO", "VALOR ORÇAMENTO", "VALOR TOTAL", "TOTAL", "UND", "VB", "M", "M2", "M3"}
    if nome.upper().strip() in upper_stop:
        return False
    return True

def criar_colaborador(nome: str, funcao: str, obra_uuid: str | None = None, obra_nome: str = "") -> bool:
    if not _is_person_name(nome):
        return False
    try:
        res = sb.table("colaboradores").select("id").eq("nome", nome).limit(1).execute()
        if res.data:
            # Ja existe — se tiver obra_uuid e nao tiver alocacao ativa, cria
            cid = res.data[0]["id"]
            if obra_uuid:
                aloc = sb.table("alocacoes").select("id").eq("colaborador_id", cid).is_("data_fim", None).limit(1).execute()
                if not aloc.data:
                    sb.table("alocacoes").insert({
                        "colaborador_id": cid,
                        "obra_id": obra_uuid,
                        "data_inicio": datetime.now().strftime("%Y-%m-%d"),
                        "empresa_id": EMPRESA_ID,
                    }).execute()
                    sb.table("colaboradores").update({"obra_alocada": obra_nome}).eq("id", cid).execute()
            return False
        sb.table("colaboradores").insert({
            "empresa_id": EMPRESA_ID,
            "nome": nome,
            "funcao": funcao or "Pedreiro",
            "obra_alocada": obra_nome or None,
        }).execute()
        # Cria alocacao inicial
        if obra_uuid:
            cid2 = sb.table("colaboradores").select("id").eq("nome", nome).limit(1).execute().data[0]["id"]
            sb.table("alocacoes").insert({
                "colaborador_id": cid2,
                "obra_id": obra_uuid,
                "data_inicio": datetime.now().strftime("%Y-%m-%d"),
                "empresa_id": EMPRESA_ID,
            }).execute()
        return True
    except:
        return False

# ─── importar folha pagamento ──────────────────────────────────

def importar_folha():
    """Importa registros das abas FP_* para folha_pagamento."""
    total = 0
    _col_cache = {}

    MES_MAP = {
        "FP_JAN": "01", "FP_FEV": "02", "FP_MAR": "03", "FP_ABR": "04",
        "FP_MAI": "05", "FP_JUN": "06", "FP_JUL": "07", "FP_AGO": "08",
        "FP_SET": "09", "FP_OUT": "10", "FP_NOV": "11", "FP_DEZ": "12",
    }

    def col_id(nome: str) -> str | None:
        if nome in _col_cache:
            return _col_cache[nome]
        res = sb.table("colaboradores").select("id").eq("nome", nome).limit(1).execute()
        if res.data:
            _col_cache[nome] = res.data[0]["id"]
            return res.data[0]["id"]
        return None

    for caminho, rotulo, _ in ARQUIVOS:
        xl = pd.ExcelFile(caminho, engine="openpyxl")
        for sheet in xl.sheet_names:
            if not sheet.startswith("FP_"):
                continue
            df = pd.read_excel(caminho, sheet_name=sheet, header=None, engine="openpyxl")

            # Determina competencia: usa mes do nome da aba + ano do cabecalho
            mes = MES_MAP.get(sheet.upper(), "01")
            ano = "2026"
            for i in range(4):
                linha = df.iloc[i]
                vals = [str(v).strip() for v in linha if pd.notna(v)]
                for j, v in enumerate(vals):
                    if "COMP.:" in v and j + 1 < len(vals):
                        comp_val = vals[j + 1][:10]
                        if "-" in comp_val:
                            ano = comp_val[:4]
                        break
            competencia = f"{ano}-{mes}-01"

            registros = []
            for i in range(7, len(df)):
                nome  = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ""
                funcao = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ""
                sal   = parse_valor(df.iloc[i, 7]) if pd.notna(df.iloc[i, 7]) else 0.0
                cesta = parse_valor(df.iloc[i, 8]) if pd.notna(df.iloc[i, 8]) else 0.0
                prod  = parse_valor(df.iloc[i, 16]) if len(df.columns) > 16 and pd.notna(df.iloc[i, 16]) else 0.0
                total_row = parse_valor(df.iloc[i, 17]) if len(df.columns) > 17 and pd.notna(df.iloc[i, 17]) else 0.0

                if not nome or nome == "Nome":
                    continue

                cid = col_id(nome)
                if not cid or not competencia:
                    continue

                prov = total_row if total_row > 0 else sal + cesta + prod
                registros.append({
                    "empresa_id": EMPRESA_ID,
                    "colaborador_id": cid,
                    "competencia": competencia,
                    "proventos": prov,
                    "descontos": 0.0,
                    "status": "Aprovado",
                    "detalhes": f"salario={sal}|cesta={cesta}|producao={prod}",
                })

            if registros:
                try:
                    sb.table("folha_pagamento").upsert(registros, on_conflict="competencia,colaborador_id").execute()
                    total += len(registros)
                except Exception as e:
                    print(f"  [!] Erro folha {sheet}: {e}")
    return total

# ─── importar orcamento (Colmeia) ──────────────────────────────

def importar_orcamento_colmeia():
    """Importa orcamento da aba RESULTADO da Colmeia."""
    caminho = r"D:\Ronney\Mbr\Colmeia\Controle Custo - Colmeia.xlsm"
    xl = pd.ExcelFile(caminho, engine="openpyxl")
    df = pd.read_excel(caminho, sheet_name="RESULTADO", header=None, engine="openpyxl")

    obra_id = get_or_create_obra("SKY RESIDENCIAL", "COLMEIA")
    if not obra_id:
        print("  [!] Obra Sky Residencial nao encontrada/criada")
        return

    # Cria header do orcamento
    total_orc = 76060.29
    payload = {
        "empresa_id": EMPRESA_ID,
        "obra_id": obra_id,
        "nome": "Orçamento Colmeia",
        "versao": 1,
        "base_referencia": "Planilha RESULTADO",
        "total_custo": total_orc,
        "total_venda": total_orc,
        "status": "Aprovado",
    }
    res = sb.table("orcamentos").insert(payload).execute()
    if not res.data:
        print("  [!] Erro ao criar orcamento")
        return
    orc_id = res.data[0]["id"]
    print(f"  [+] Orcamento criado: {orc_id}")

    itens = []
    ordem = 0

    def parse_item(row, prefix=""):
        nonlocal ordem
        item   = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        desc   = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        unid   = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        qtde   = parse_valor(row.iloc[3]) if pd.notna(row.iloc[3]) else 0.0
        pu     = parse_valor(row.iloc[4]) if pd.notna(row.iloc[4]) else 0.0
        total  = parse_valor(row.iloc[5]) if pd.notna(row.iloc[5]) else 0.0

        if not desc or total == 0:
            return
        if any(v in desc.upper() for v in ("VALOR ORÇAMENTO", "VALOR TOTAL", "ITEM", "DESCRIÇÃO")):
            return

        cod = f"{prefix}{item}" if item else f"ORD_{ordem:04d}"
        ordem += 1
        itens.append({
            "orcamento_id": orc_id,
            "ordem": cod,
            "descricao": desc,
            "unidade": unid,
            "quantidade": qtde if qtde > 0 else 1,
            "preco_unit": pu if pu > 0 else total,
            "empresa_id": EMPRESA_ID,
        })

    # Section 1: Budget (linhas 6-22)
    for i in range(6, 23):
        parse_item(df.iloc[i])

    # Section 2: Complementar (linhas 30-38) - prefix with 'C' to avoid key dupe
    for i in range(30, 39):
        parse_item(df.iloc[i], prefix="C")

    if itens:
        sb.table("orcamento_itens").insert(itens).execute()
        print(f"  [+] {len(itens)} itens de orcamento inseridos")

        # Gera EAP para obra
        eap_rows = []
        eap_ordem = 0
        for it in itens:
            eap_rows.append({
                "obra_id": obra_id,
                "codigo": it["ordem"],
                "descricao": it["descricao"],
                "unidade": it["unidade"],
                "qtd_prevista": it["quantidade"],
                "valor_previsto": it["quantidade"] * it["preco_unit"],
                "ordem": eap_ordem,
                "empresa_id": EMPRESA_ID,
            })
            eap_ordem += 1
        if eap_rows:
            # Remove EAP existente para evitar duplicatas
            try:
                sb.table("eap_itens").delete().eq("obra_id", obra_id).execute()
            except:
                pass
            sb.table("eap_itens").insert(eap_rows).execute()
            print(f"  [+] {len(eap_rows)} itens EAP gerados")

# ─── importar medicoes ─────────────────────────────────────────

def importar_medicoes(obra_ids: dict):
    total = 0
    for caminho, rotulo, obra_forcada in ARQUIVOS:
        if not os.path.exists(caminho):
            continue
        if rotulo not in obra_ids:
            continue
        xl = pd.ExcelFile(caminho, engine="openpyxl")
        if "Medições" not in xl.sheet_names:
            continue

        df = pd.read_excel(caminho, sheet_name="Medições", header=None, engine="openpyxl")
        obra_id = obra_ids[rotulo]["id"]

        inseridas = 0
        next_num = 1
        for i in range(4, len(df)):
            row = df.iloc[i]
            contrato = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            numero   = row.iloc[1] if pd.notna(row.iloc[1]) else None
            data      = row.iloc[2] if pd.notna(row.iloc[2]) else None
            mes_ref  = row.iloc[3] if pd.notna(row.iloc[3]) else None
            descricao = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
            servico  = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
            valor_bruto = parse_valor(row.iloc[6]) if pd.notna(row.iloc[6]) else 0.0
            ret_pct = parse_valor(row.iloc[7]) if pd.notna(row.iloc[7]) else 0.0

            if not numero or valor_bruto == 0:
                continue

            comp_data = parse_data(mes_ref) or parse_data(data)
            emissao = parse_data(data)
            if not comp_data:
                continue

            valor_liquido = valor_bruto * (1 - ret_pct)
            payload = {
                "obra_id": obra_id,
                "numero": next_num,
                "competencia": comp_data,
                "data_emissao": emissao or comp_data,
                "status": "Aprovado",
                "valor_total": round(valor_bruto, 2),
                "valor_liquido": round(valor_liquido, 2),
                "observacoes": f"PCT:0|PERIODO:{comp_data[:7]}|OBS:{descricao[:100]}",
                "retencao_ir": round(valor_bruto * ret_pct, 2),
                "workflow_status": "Aprovado",
                "empresa_id": EMPRESA_ID,
            }
            try:
                sb.table("medicoes").insert(payload).execute()
                inseridas += 1
                next_num += 1
            except Exception as e:
                print(f"  [!] Erro medicao {rotulo}#{num}: {e}")

        if inseridas:
            print(f"  {rotulo}: {inseridas} medicoes importadas")
            total += inseridas
    return total

# ─── main ──────────────────────────────────────────────────────

def main():
    print("="*60)
    print("IMPORTACAO COMPLETA DE PLANILHAS")
    print(f"Supabase: {SUPABASE_URL}")
    print("="*60)

    # ── 0) Limpa dados anteriores ──
    print("\n[0] Limpando dados de importacao anterior...")
    try:
        sb.table("lancamentos").delete().eq("origem", "importacao_planilha").execute()
        print("  Lancamentos antigos removidos")
    except Exception as e:
        print(f"  Aviso: {e}")

    # ── 1) Obras ──
    print("\n[1] Criando/verificando obras...")
    obra_ids = {}
    for caminho, rotulo, obra_forcada in ARQUIVOS:
        if not os.path.exists(caminho):
            print(f"  [!] Arquivo nao encontrado: {caminho}")
            continue
        df = pd.read_excel(caminho, sheet_name="Lançamento", header=None, engine="openpyxl")
        meta = extrair_metadata(df)

        if obra_forcada:
            nome_obra = obra_forcada
            cliente = meta["cliente"]
        else:
            nome_obra = meta["obra"]
            cliente = meta["cliente"]

        oid = get_or_create_obra(nome_obra, cliente)
        if oid:
            obra_ids[rotulo] = {"id": oid, "nome": nome_obra, "cliente": cliente, "total": meta["total"]}
            print(f"  {rotulo}: {nome_obra} (cliente={cliente})")

    # ── 2) Lancamentos ──
    print("\n[2] Importando lancamentos financeiros...")
    total_lanc = 0
    total_mat = []
    for caminho, rotulo, obra_forcada in ARQUIVOS:
        if rotulo not in obra_ids:
            continue
        df = pd.read_excel(caminho, sheet_name="Lançamento", header=None, engine="openpyxl")
        lancs = extrair_lancamentos(df)
        oid = obra_ids[rotulo]["id"]
        ins, err, mats = importar_lancamentos(oid, lancs)
        total_lanc += ins
        total_mat.extend(mats)
        print(f"  {rotulo}: {ins} lancamentos, {err} erros")

    print(f"\n  Total lancamentos: {total_lanc}")
    print(f"  Materiais p/ insumos: {len(total_mat)}")

    # ── 3) Insumos / Estoque ──
    print("\n[3] Importando insumos e movimentos de estoque...")
    if total_mat:
        ok, err = importar_insumos(total_mat)
        print(f"  {ok} insumos/estoque criados, {err} erros")
    else:
        print("  Nenhum material para importar")

    # ── 4) Colaboradores ──
    print("\n[4] Importando colaboradores...")
    criados = importar_colaboradores(obra_ids)
    print(f"  {criados} novos colaboradores criados")

    # ── 5) Folha de Pagamento ──
    print("\n[5] Importando folha de pagamento...")
    folhas = importar_folha()
    print(f"  {folhas} registros de folha importados")

    # ── 6) Medições ──
    print("\n[6] Importando medicoes...")
    meds = importar_medicoes(obra_ids)
    print(f"  {meds} medicoes importadas")

    # ── 7) Orcamento Colmeia ──
    print("\n[7] Importando orcamento da Colmeia...")
    importar_orcamento_colmeia()

    print(f"\n{'='*60}")
    print("IMPORTACAO FINALIZADA!")
    print(f"  Obras: {len(obra_ids)}")
    print(f"  Lancamentos: {total_lanc}")
    print(f"  Insumos: {len(total_mat)}")
    print(f"  Colaboradores: +{criados}")
    print(f"  Folha: {folhas}")
    print(f"  Medicoes: {meds}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
