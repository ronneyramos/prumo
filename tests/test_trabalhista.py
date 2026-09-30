"""Estimativas trabalhistas (trabalhista.py)."""
from datetime import date

import pytest

import trabalhista as tb


def test_encargos_so_para_clt():
    assert tb.custo_empresa(1000, "CLT") == pytest.approx(1310)
    for tipo in ("MEI", "Autônomo", "Diarista", "Empreiteiro", "Estagiário"):
        assert tb.custo_empresa(1000, tipo) == pytest.approx(1000)


def test_avos_conta_mes_com_15_dias():
    assert tb.avos(date(2026, 1, 1), date(2026, 3, 14)) == 2   # março com 14 dias não conta
    assert tb.avos(date(2026, 1, 1), date(2026, 3, 15)) == 3
    assert tb.avos(date(2026, 1, 1), date(2026, 12, 31)) == 12
    assert tb.avos(date(2026, 5, 1), date(2026, 4, 1)) == 0


def test_aviso_previo_proporcional():
    assert tb.dias_aviso_previo(None, date(2026, 9, 29)) == 30
    assert tb.dias_aviso_previo(date(2020, 9, 29), date(2026, 9, 29)) == 48   # 6 anos
    assert tb.dias_aviso_previo(date(1990, 1, 1), date(2026, 9, 29)) == 90    # teto


def test_sem_justa_causa_com_aviso_indenizado():
    # Admitido 01/03/2025, dispensado 20/09/2026, salário 3.000, FGTS 4.000
    s = tb.sugestao_rescisao(3000, date(2025, 3, 1), date(2026, 9, 20), "Sem justa causa", "Indenizado", 4000)
    assert s["saldo_salario"] == pytest.approx(2000)          # 20 dias
    assert s["dias_aviso"] == 33                               # 1 ano completo
    assert s["aviso_previo"] == pytest.approx(3300)
    # Aviso projeta até 23/10: 13º = 10/12; férias do período iniciado em 01/03/2026 = 8/12
    assert s["avos_13"] == 10 and s["avos_ferias"] == 8
    assert s["multa_fgts"] == pytest.approx(1600)              # 40% do saldo, não do salário


def test_justa_causa_so_saldo():
    s = tb.sugestao_rescisao(3000, date(2025, 3, 1), date(2026, 9, 20), "Com justa causa", "Indenizado", 4000)
    assert s["decimo_terceiro"] == 0 and s["ferias_proporcionais"] == 0
    assert s["aviso_previo"] == 0 and s["multa_fgts"] == 0
    assert s["saldo_salario"] == pytest.approx(2000)


def test_acordo_metade_do_aviso_e_20_por_cento():
    s = tb.sugestao_rescisao(3000, date(2025, 3, 1), date(2026, 9, 20), "Acordo", "Indenizado", 4000)
    assert s["aviso_previo"] == pytest.approx(1650)
    assert s["multa_fgts"] == pytest.approx(800)


def test_pedido_de_demissao_sem_aviso_e_sem_multa():
    s = tb.sugestao_rescisao(3000, date(2025, 3, 1), date(2026, 9, 20), "Pedido demissão", "Indenizado", 4000)
    assert s["aviso_previo"] == 0 and s["multa_fgts"] == 0 and s["dias_aviso"] == 0
    assert s["avos_13"] == 9


def test_fim_das_ferias_inclui_o_primeiro_dia():
    assert tb.fim_ferias(date(2026, 7, 1), 30) == date(2026, 7, 30)
