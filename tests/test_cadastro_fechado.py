"""Cadastro público fechado por padrão (piloto) e reaberto pela config."""
import os
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "streamlit", "main.py")


def _tela_login(monkeypatch, valor_config):
    # main.py faz importlib.reload(db), que desfaria um patch em db; por isso o
    # cliente falso entra em supabase.create_client (db o reimporta no reload).
    import supabase

    class _Res:
        data = [{"value": valor_config}] if valor_config is not None else []

    class _Q:
        def __getattr__(self, _):
            return lambda *a, **k: self
        def execute(self):
            return _Res()

    class _Admin:
        def table(self, _):
            return _Q()

    monkeypatch.setattr(supabase, "create_client", lambda *a, **k: _Admin())
    import streamlit as st
    st.cache_data.clear()  # _config_global fica em cache entre execuções
    return AppTest.from_file(APP, default_timeout=120).run()


def test_sem_config_cadastro_fica_fechado(monkeypatch):
    at = _tela_login(monkeypatch, None)
    labels = [b.label for b in at.button]
    assert "Criar conta gratuita →" not in labels
    assert "ENTRAR" in labels and "Esqueci minha senha" in labels


def test_config_true_reabre_cadastro(monkeypatch):
    at = _tela_login(monkeypatch, "true")
    assert "Criar conta gratuita →" in [b.label for b in at.button]
