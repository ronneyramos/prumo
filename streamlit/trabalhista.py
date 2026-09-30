"""Estimativas trabalhistas (rescisão, férias, encargos) para o ERP.

NÃO substituem o cálculo da contabilidade: servem para prever custo por obra e
sugerir valores que o usuário confere. Não calculam INSS/IRRF do empregado
(tabelas progressivas mudam todo ano) nem médias de variáveis.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

# Encargos da empresa sobre a folha CLT: INSS patronal 20% + RAT 3% + FGTS 8%
ENCARGOS_CLT = 0.31
TIPOS_COM_ENCARGOS = ("CLT",)

TIPOS_RESCISAO = ["Sem justa causa", "Com justa causa", "Pedido demissão", "Término contrato", "Acordo"]
AVISOS = ["Indenizado", "Trabalhado", "Dispensado"]


def custo_empresa(salario: float, tipo_contrato: str | None) -> float:
    """Custo mensal estimado: CLT leva encargos; MEI, autônomo, diarista etc. custam o valor pago."""
    salario = float(salario or 0)
    if (tipo_contrato or "CLT") in TIPOS_COM_ENCARGOS:
        return salario * (1 + ENCARGOS_CLT)
    return salario


def _somar_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def avos(inicio: date, fim: date) -> int:
    """Meses (1/12) entre inicio e fim contando mês com 15 dias ou mais trabalhados. Máximo 12."""
    if fim < inicio:
        return 0
    n, cursor = 0, inicio
    while cursor <= fim and n < 12:
        proximo = _somar_meses(cursor, 1)
        ultimo_dia = min(proximo - timedelta(days=1), fim)
        if (ultimo_dia - cursor).days + 1 >= 15:
            n += 1
        cursor = proximo
    return n


def dias_aviso_previo(admissao: date | None, desligamento: date) -> int:
    """30 dias + 3 por ano completo de casa, até 90 (Lei 12.506/2011)."""
    if not admissao:
        return 30
    anos = desligamento.year - admissao.year - ((desligamento.month, desligamento.day) < (admissao.month, admissao.day))
    return min(30 + 3 * max(anos, 0), 90)


def sugestao_rescisao(salario: float, admissao: date | None, desligamento: date,
                      tipo: str, aviso: str, saldo_fgts: float = 0.0) -> dict:
    """Verbas sugeridas. Férias vencidas não são conhecidas pelo sistema: entram zeradas."""
    sal = float(salario or 0)
    admissao = admissao if admissao and admissao <= desligamento else None
    justa_causa = tipo == "Com justa causa"
    dias_av = dias_aviso_previo(admissao, desligamento)

    # Aviso indenizado conta como tempo de serviço (projeta 13º e férias)
    indenizado = aviso == "Indenizado" and tipo in ("Sem justa causa", "Acordo")
    fim_projetado = desligamento + timedelta(days=dias_av if indenizado else 0)

    saldo = round(sal / 30 * min(desligamento.day, 30), 2)

    inicio_ano = date(fim_projetado.year, 1, 1)
    avos_13 = 0 if justa_causa else avos(max(inicio_ano, admissao or inicio_ano), fim_projetado)

    # Período aquisitivo atual: último aniversário da admissão
    if admissao:
        inicio_aq = admissao
        while _somar_meses(inicio_aq, 12) <= fim_projetado:
            inicio_aq = _somar_meses(inicio_aq, 12)
    else:
        inicio_aq = inicio_ano
    avos_ferias = 0 if justa_causa else avos(inicio_aq, fim_projetado)

    ferias_prop = round(sal / 12 * avos_ferias, 2)
    decimo = round(sal / 12 * avos_13, 2)

    if indenizado:
        aviso_valor = round(sal / 30 * dias_av * (0.5 if tipo == "Acordo" else 1), 2)
    else:
        aviso_valor = 0.0

    multa = {"Sem justa causa": 0.40, "Acordo": 0.20}.get(tipo, 0.0)
    return {
        "saldo_salario":        saldo,
        "ferias_vencidas":      0.0,
        "ferias_proporcionais": ferias_prop,
        "decimo_terceiro":      decimo,
        "aviso_previo":         aviso_valor,
        "multa_fgts":           round(float(saldo_fgts or 0) * multa, 2),
        "dias_aviso":           dias_av if indenizado else 0,
        "avos_13":              avos_13,
        "avos_ferias":          avos_ferias,
        "pct_multa":            multa,
    }


def saldo_fgts_estimado(salario: float, admissao: date | None, desligamento: date) -> float:
    """8% do salário por mês de casa. Só uma referência: o valor certo é o do extrato do FGTS."""
    if not admissao or admissao > desligamento:
        return 0.0
    meses = (desligamento.year - admissao.year) * 12 + desligamento.month - admissao.month
    return round(float(salario or 0) * 0.08 * max(meses, 0), 2)


def fim_ferias(inicio: date, dias: int) -> date:
    """Último dia de férias (30 dias a partir de 01/07 terminam em 30/07)."""
    return inicio + timedelta(days=int(dias) - 1)
