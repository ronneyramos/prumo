"""Alertas: detecção correta e envio só para os destinatários informados."""
from datetime import date, timedelta
import pandas as pd
import alertas


def test_estoque_critico_usa_colunas_do_app():
    est = pd.DataFrame([{"Insumo": "Cimento", "Obra": "A", "Estoque Atual": 2.0, "Estoque Mínimo": 10.0},
                        {"Insumo": "Areia",   "Obra": "A", "Estoque Atual": 50.0, "Estoque Mínimo": 10.0}])
    r = alertas.verificar_alertas(pd.DataFrame(), pd.DataFrame(), est)
    assert [e["insumo"] for e in r["estoque_critico"]] == ["Cimento"]


def test_conta_com_status_vencido_gera_alerta():
    ontem = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
    cp = pd.DataFrame([{"Obra": "A", "Descrição": "Aço", "Valor (R$)": 100.0,
                        "Vencimento": ontem, "Status": "Vencido"}])
    r = alertas.verificar_alertas(cp, pd.DataFrame())
    assert len(r["vencimentos"]) == 1 and r["vencimentos"][0]["status"] == "VENCIDO"


def test_envio_vai_so_para_destinatarios(monkeypatch):
    enviados = {}

    class _SMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, *a): pass
        def sendmail(self, de, para, msg): enviados["para"] = para

    monkeypatch.setattr(alertas, "_FROM", "plataforma@x.com")
    monkeypatch.setattr(alertas, "_PASS", "senha")
    monkeypatch.setattr(alertas.smtplib, "SMTP_SSL", _SMTP)
    ok = alertas._enviar_email("assunto", "<p>x</p>", ["admin@construtora.com", "admin@construtora.com", ""])
    assert ok and enviados["para"] == ["admin@construtora.com"]


def test_sem_destinatario_nao_envia(monkeypatch):
    monkeypatch.setattr(alertas, "_FROM", "plataforma@x.com")
    monkeypatch.setattr(alertas, "_PASS", "senha")
    assert alertas._enviar_email("assunto", "<p>x</p>", []) is False
