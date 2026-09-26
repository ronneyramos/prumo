"""Exclusão em dois passos: o 1º clique só pede confirmação, nada é apagado.

Uso:
    if st.button("🗑️ Excluir"): pedir_confirmacao("obra_12")
    if confirmou_exclusao("obra_12", "a obra Residencial X"): <apaga>
"""
import streamlit as st


def pedir_confirmacao(chave: str):
    """1º passo: só marca o pedido."""
    st.session_state[f"_confirma_{chave}"] = True
    st.rerun()


def confirmou_exclusao(chave: str, descricao: str) -> bool:
    """2º passo: mostra o aviso e devolve True só quando o usuário clica em "Sim, excluir"."""
    flag = f"_confirma_{chave}"
    if not st.session_state.get(flag):
        return False
    st.warning(f"⚠️ Confirma a exclusão de **{descricao}**? Esta ação não pode ser desfeita.")
    c_sim, c_nao, _ = st.columns([1, 1, 3])
    if c_sim.button("Sim, excluir", key=f"{flag}_sim", type="primary"):
        st.session_state.pop(flag, None)
        return True
    if c_nao.button("Cancelar", key=f"{flag}_nao"):
        st.session_state.pop(flag, None)
        st.rerun()
    return False
