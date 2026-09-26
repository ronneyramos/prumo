"""Campos de formulário reutilizáveis."""
from datetime import date, datetime

import streamlit as st

BR = "%d/%m/%Y"
ISO = "%Y-%m-%d"


def _para_date(valor) -> date | None:
    """Aceita date, datetime, 'dd/mm/aaaa' ou 'aaaa-mm-dd' (com ou sem hora)."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    for fmt in (BR, ISO):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def campo_data(label: str, valor=None, *, fmt: str = BR, opcional: bool = False,
               container=None, **kwargs) -> str:
    """Seletor de data (calendário) que devolve texto no formato que a tela já usa.

    - fmt: formato do texto devolvido (BR = dd/mm/aaaa, ISO = aaaa-mm-dd).
    - opcional=True permite deixar em branco (devolve "").
    Valor inicial inválido ou vazio vira "hoje" (ou vazio, se opcional).
    """
    alvo = container or st
    inicial = _para_date(valor)
    if inicial is None and not opcional:
        inicial = date.today()
    escolhido = alvo.date_input(label, value=inicial, format="DD/MM/YYYY",
                                min_value=date(1990, 1, 1), max_value=date(2100, 12, 31),
                                **kwargs)
    return escolhido.strftime(fmt) if escolhido else ""


MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def campo_mes(label: str, valor: date | None = None, *, extenso: bool = False,
              key: str, container=None) -> str:
    """Mês/ano com dois seletores. Devolve "mm/aaaa" ou, com extenso=True,
    "Setembro/2026" (sempre em português, sem depender do locale do servidor)."""
    alvo = container or st
    ref = valor or date.today()
    c_mes, c_ano = alvo.columns([3, 2])
    mes = c_mes.selectbox(label, range(1, 13), index=ref.month - 1,
                          format_func=lambda m: MESES[m - 1], key=f"{key}_mes")
    anos = list(range(ref.year - 5, ref.year + 3))
    ano = c_ano.selectbox("Ano", anos, index=anos.index(ref.year), key=f"{key}_ano")
    return f"{MESES[mes - 1]}/{ano}" if extenso else f"{mes:02d}/{ano}"
