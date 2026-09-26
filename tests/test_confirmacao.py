"""Exclusão em dois passos: o 1º clique nunca apaga nada."""
from streamlit.testing.v1 import AppTest


def _app():
    import streamlit as st
    from confirmacao import pedir_confirmacao, confirmou_exclusao
    st.session_state.setdefault("apagados", 0)
    if st.button("🗑️ Excluir", key="del"):
        pedir_confirmacao("item")
    if confirmou_exclusao("item", "o item X"):
        st.session_state.apagados += 1


def _rodar():
    return AppTest.from_function(_app, default_timeout=60).run()


def test_primeiro_clique_so_pede_confirmacao():
    at = _rodar()
    at.button(key="del").click().run()
    assert at.session_state["apagados"] == 0
    assert "o item X" in at.warning[0].value


def test_sim_apaga_uma_vez():
    at = _rodar()
    at.button(key="del").click().run()
    at.button(key="_confirma_item_sim").click().run()
    assert at.session_state["apagados"] == 1
    at.run()  # no app, os handlers de exclusão fazem st.rerun()
    assert not at.warning                     # aviso some
    assert at.session_state["apagados"] == 1  # e não apaga de novo


def test_cancelar_nao_apaga():
    at = _rodar()
    at.button(key="del").click().run()
    at.button(key="_confirma_item_nao").click().run()
    assert at.session_state["apagados"] == 0
    assert not at.warning
