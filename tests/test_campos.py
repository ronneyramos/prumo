"""Seletores de data/mês devolvem texto no formato que as telas já usam."""
from datetime import date
from streamlit.testing.v1 import AppTest
import campos


def test_para_date_aceita_formatos_do_app():
    assert campos._para_date("05/03/2026") == date(2026, 3, 5)
    assert campos._para_date("2026-03-05") == date(2026, 3, 5)
    assert campos._para_date("2026-03-05T10:00:00") == date(2026, 3, 5)
    for vazio in (None, "", "nan", "None", "texto qualquer"):
        assert campos._para_date(vazio) is None


def _app():
    import streamlit as st
    from datetime import date
    from campos import campo_data, campo_mes, ISO
    st.session_state["r_br"] = campo_data("BR", "05/03/2026", key="br")
    st.session_state["r_iso"] = campo_data("ISO", "05/03/2026", fmt=ISO, key="iso")
    st.session_state["r_opc"] = campo_data("Opcional", None, opcional=True, key="opc")
    st.session_state["r_mes"] = campo_mes("Mês", date(2026, 9, 1), key="m")
    st.session_state["r_ext"] = campo_mes("Mês", date(2026, 9, 1), extenso=True, key="e")


def test_formatos_de_saida():
    at = AppTest.from_function(_app, default_timeout=60).run()
    assert at.session_state["r_br"] == "05/03/2026"
    assert at.session_state["r_iso"] == "2026-03-05"
    assert at.session_state["r_opc"] == ""
    assert at.session_state["r_mes"] == "09/2026"
    assert at.session_state["r_ext"] == "Setembro/2026"


def test_usuario_escolhe_data():
    at = AppTest.from_function(_app, default_timeout=60).run()
    at.date_input(key="br").set_value(date(2026, 12, 31)).run()
    assert at.session_state["r_br"] == "31/12/2026"
