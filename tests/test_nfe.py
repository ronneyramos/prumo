"""Leitura do XML da NF-e."""
import os
from datetime import date

import pytest

import nfe

XML = open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe_exemplo.xml"), "rb").read()


def test_le_cabecalho_emitente_e_totais():
    n = nfe.ler_nfe(XML)
    assert n.chave == "23260912345678000190550010000045671000045678"
    assert (n.numero, n.serie) == ("4567", "1")
    assert n.emissao == date(2026, 9, 20)
    assert n.emitente_cnpj == "12345678000190"
    assert n.emitente_nome == "DEPOSITO DE MATERIAIS FICTICIO LTDA"
    assert n.emitente_endereco == "Rua das Pedras, 100, Centro, Fortaleza/CE"
    assert n.destinatario_cnpj == "98765432000110"
    assert n.valor_total == 5850.00
    assert n.autorizada is True
    assert n.forma_pagamento == "Boleto"


def test_le_itens_com_desconto():
    itens = nfe.ler_nfe(XML).itens
    assert [i.descricao for i in itens] == ["CIMENTO CP II 50KG", "VERGALHAO CA-50 10MM"]
    assert (itens[0].unidade, itens[0].quantidade, itens[0].valor_unitario) == ("SC", 100.0, 38.5)
    assert itens[1].valor_total == 2000.00  # vProd 2080 - vDesc 80


def test_parcelas():
    n = nfe.ler_nfe(XML)
    assert [(p.numero, p.vencimento, p.valor) for p in nfe.parcelas_para_pagar(n)] == [
        ("001", date(2026, 10, 20), 2925.0), ("002", date(2026, 11, 19), 2925.0)]


def test_sem_duplicata_vira_parcela_unica_na_emissao():
    sem_cobr = XML.replace(XML[XML.index(b"<cobr>"):XML.index(b"</cobr>") + 7], b"")
    n = nfe.ler_nfe(sem_cobr)
    assert [(p.vencimento, p.valor) for p in nfe.parcelas_para_pagar(n)] == [(date(2026, 9, 20), 5850.0)]


def test_nota_sem_protocolo_nao_esta_autorizada():
    sem_prot = XML.replace(b"<cStat>100</cStat>", b"")
    assert nfe.ler_nfe(sem_prot).autorizada is False


@pytest.mark.parametrize("conteudo, trecho", [
    (b"", "vazio"),
    (b"isso nao e xml", "XML válido"),
    (b'<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"/>', "evento"),
    (b'<cteProc xmlns="http://www.portalfiscal.inf.br/cte"/>', "CT-e"),
    (b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]><x>&a;</x>", "não permitidas"),
    (b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"/>', "Não encontrei"),
])
def test_arquivos_invalidos_tem_mensagem_clara(conteudo, trecho):
    with pytest.raises(nfe.NFeInvalida, match=trecho):
        nfe.ler_nfe(conteudo)


def test_nfce_nao_e_aceita():
    with pytest.raises(nfe.NFeInvalida, match="modelo 55"):
        nfe.ler_nfe(XML.replace(b"<mod>55</mod>", b"<mod>65</mod>"))


def test_formatar_cnpj():
    assert nfe.formatar_cnpj("12345678000190") == "12.345.678/0001-90"
