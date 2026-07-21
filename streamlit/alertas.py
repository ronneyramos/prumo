"""
Sistema de alertas por email para o ERP MBR Engenharia.
Envia notificações via Gmail SMTP sobre vencimentos, NCs e estoque crítico.
"""
import os, smtplib, traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, timedelta
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_FROM  = os.environ.get("ALERT_EMAIL_FROM", "")
_PASS  = os.environ.get("ALERT_EMAIL_PASSWORD", "")
_TO    = os.environ.get("ALERT_EMAIL_TO", "")


def _enviar_email(assunto: str, corpo_html: str) -> bool:
    """Envia email via Gmail SMTP. Retorna True se enviou com sucesso."""
    if not _FROM or not _PASS or not _TO:
        print("[alertas] Credenciais de email não configuradas.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = f"ERP MBR <{_FROM}>"
        msg["To"]      = _TO
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(_FROM, _PASS)
            srv.sendmail(_FROM, _TO, msg.as_string())
        return True
    except Exception:
        print(f"[alertas] Erro ao enviar email:\n{traceback.format_exc()}")
        return False


def _to_num(v) -> float:
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace("R$","").replace(" ","").replace(".","").replace(",",".")
    try: return float(s)
    except Exception: return 0.0


def _fmt(v) -> str:
    try: return f"R$ {_to_num(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception: return "R$ 0,00"


def verificar_alertas(contas_pagar: pd.DataFrame,
                      nao_conformidades: pd.DataFrame,
                      estoque: pd.DataFrame = None) -> dict:
    """
    Verifica todos os alertas e retorna dict com listas de itens críticos.
    Não envia email — apenas classifica.
    """
    hoje = date.today()
    em_7_dias = hoje + timedelta(days=7)
    alertas = {"vencimentos": [], "ncs_abertas": [], "estoque_critico": []}

    # ── Vencimentos próximos (≤ 7 dias) e vencidos ───────────────────────────
    if not contas_pagar.empty and "Vencimento" in contas_pagar.columns:
        cp = contas_pagar.copy()
        cp["_venc_dt"] = pd.to_datetime(cp["Vencimento"], dayfirst=True, errors="coerce").dt.date
        cp["_valor"]   = cp["Valor (R$)"].apply(_to_num) if "Valor (R$)" in cp.columns else 0.0
        status_col = cp["Status"].fillna("Pendente").str.lower() if "Status" in cp.columns else pd.Series(["pendente"]*len(cp))
        pendentes = cp[status_col.isin(["pendente","a pagar","a vencer",""])]
        criticos  = pendentes[pendentes["_venc_dt"].notna() & (pendentes["_venc_dt"] <= em_7_dias)]
        for _, r in criticos.iterrows():
            venc = r["_venc_dt"]
            dias = (venc - hoje).days
            alertas["vencimentos"].append({
                "obra":       r.get("Obra", "—"),
                "descricao":  r.get("Descrição", r.get("Fornecedor", "—")),
                "valor":      _fmt(r["_valor"]),
                "vencimento": str(venc),
                "dias":       dias,
                "status":     "VENCIDO" if dias < 0 else f"vence em {dias}d",
            })

    # ── NCs abertas há mais de 30 dias ───────────────────────────────────────
    if not nao_conformidades.empty:
        nc = nao_conformidades.copy()
        col_data = next((c for c in ["Data Abertura", "Data", "created_at"] if c in nc.columns), None)
        if col_data:
            nc["_dt"] = pd.to_datetime(nc[col_data], dayfirst=True, errors="coerce").dt.date
            status_nc = nc["Status"].fillna("Aberta").str.lower() if "Status" in nc.columns else pd.Series(["aberta"]*len(nc))
            abertas = nc[status_nc.isin(["aberta", "em análise", "pendente", ""])]
            for _, r in abertas.iterrows():
                if pd.isna(r["_dt"]):
                    continue
                dias_aberta = (hoje - r["_dt"]).days
                if dias_aberta > 30:
                    alertas["ncs_abertas"].append({
                        "obra":      r.get("Obra", "—"),
                        "descricao": r.get("Descrição", "NC sem descrição"),
                        "gravidade": r.get("Gravidade", "—"),
                        "dias":      dias_aberta,
                    })

    # ── Estoque crítico (saldo ≤ mínimo) ─────────────────────────────────────
    if estoque is not None and not estoque.empty:
        col_saldo = next((c for c in ["Saldo Atual", "Quantidade", "saldo_atual"] if c in estoque.columns), None)
        col_min   = next((c for c in ["Saldo Mínimo", "Mínimo", "estoque_minimo"] if c in estoque.columns), None)
        if col_saldo and col_min:
            est = estoque.copy()
            est["_saldo"] = est[col_saldo].apply(_to_num)
            est["_min"]   = est[col_min].apply(_to_num)
            criticos_est  = est[(est["_min"] > 0) & (est["_saldo"] <= est["_min"])]
            for _, r in criticos_est.iterrows():
                alertas["estoque_critico"].append({
                    "insumo": r.get("Insumo", r.get("Descrição", "—")),
                    "obra":   r.get("Obra", "—"),
                    "saldo":  r["_saldo"],
                    "minimo": r["_min"],
                })

    return alertas


def enviar_resumo_alertas(alertas: dict) -> bool:
    """Monta o HTML e envia o email de resumo de alertas."""
    total = sum(len(v) for v in alertas.values())
    if total == 0:
        return False

    hoje_str = date.today().strftime("%d/%m/%Y")

    def _row(cols, header=False):
        tag = "th" if header else "td"
        style = "background:#2B59C3;color:white;font-weight:bold;" if header else "border-bottom:1px solid #eee;"
        cells = "".join(f"<{tag} style='padding:8px 12px;{style}'>{c}</{tag}>" for c in cols)
        return f"<tr>{cells}</tr>"

    html = f"""
    <html><body style='font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto'>
    <div style='background:#2B59C3;padding:20px;border-radius:8px 8px 0 0'>
      <h1 style='color:white;margin:0;font-size:22px'>&#9888;&#65039; ERP MBR &mdash; Alertas do dia {hoje_str}</h1>
      <p style='color:#c8d8f8;margin:4px 0 0'>{total} item(ns) requer(em) aten&ccedil;&atilde;o</p>
    </div>
    <div style='background:#f8f9fa;padding:20px;border-radius:0 0 8px 8px'>
    """

    if alertas["vencimentos"]:
        venc = alertas["vencimentos"]
        vencidos = [v for v in venc if v["dias"] < 0]
        html += f"<h2 style='color:#E74C3C'>&#128184; Contas a Pagar ({len(venc)} item(s))</h2>"
        if vencidos:
            html += f"<p style='color:#E74C3C;font-weight:bold'>&#128308; {len(vencidos)} conta(s) VENCIDA(S)</p>"
        html += "<table style='width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden'>"
        html += _row(["Obra", "Descri&ccedil;&atilde;o", "Valor", "Vencimento", "Situa&ccedil;&atilde;o"], header=True)
        for v in sorted(venc, key=lambda x: x["dias"]):
            cor = "#FDECEA" if v["dias"] < 0 else "#FFF9E6" if v["dias"] <= 3 else "white"
            cor_txt = "#E74C3C" if v["dias"] < 0 else "#E67E22"
            html += (f"<tr style='background:{cor}'>"
                     f"<td style='padding:8px 12px'>{v['obra']}</td>"
                     f"<td style='padding:8px 12px'>{v['descricao']}</td>"
                     f"<td style='padding:8px 12px;font-weight:bold'>{v['valor']}</td>"
                     f"<td style='padding:8px 12px'>{v['vencimento']}</td>"
                     f"<td style='padding:8px 12px;font-weight:bold;color:{cor_txt}'>{v['status']}</td>"
                     f"</tr>")
        html += "</table><br>"

    if alertas["ncs_abertas"]:
        html += f"<h2 style='color:#E67E22'>&#128308; N&atilde;o-Conformidades Abertas ({len(alertas['ncs_abertas'])} item(s) h&aacute; +30 dias)</h2>"
        html += "<table style='width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden'>"
        html += _row(["Obra", "Descri&ccedil;&atilde;o", "Gravidade", "Dias em aberto"], header=True)
        for nc in alertas["ncs_abertas"]:
            html += _row([nc["obra"], nc["descricao"], nc["gravidade"], f"{nc['dias']} dias"])
        html += "</table><br>"

    if alertas["estoque_critico"]:
        html += f"<h2 style='color:#8E44AD'>&#128230; Estoque Cr&iacute;tico ({len(alertas['estoque_critico'])} insumo(s))</h2>"
        html += "<table style='width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden'>"
        html += _row(["Insumo", "Obra", "Saldo Atual", "Estoque M&iacute;nimo"], header=True)
        for e in alertas["estoque_critico"]:
            html += _row([e["insumo"], e["obra"], str(e["saldo"]), str(e["minimo"])])
        html += "</table><br>"

    html += """
    <p style='color:#888;font-size:12px;margin-top:20px;border-top:1px solid #ddd;padding-top:12px'>
      Este email foi gerado automaticamente pelo ERP MBR Engenharia.<br>
      Acesse o sistema para tomar as provid&ecirc;ncias necess&aacute;rias.
    </p>
    </div></body></html>
    """

    assunto = f"ERP MBR - {total} alerta(s) em {date.today().strftime('%d/%m/%Y')}"
    return _enviar_email(assunto, html)
