"""Leitura do XML da NF-e (modelo 55, layout 4.00).

Só lê e valida o arquivo; quem grava no banco é a tela de Entrada de NF.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime

NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
TAMANHO_MAXIMO = 2 * 1024 * 1024  # 2 MB: XML de NF-e real raramente passa de 500 KB

# Tabela tPag da SEFAZ (as mais comuns)
FORMAS_PAGAMENTO = {
    "01": "Dinheiro", "02": "Cheque", "03": "Cartão", "04": "Cartão",
    "05": "Crédito Loja", "15": "Boleto", "16": "Transferência", "17": "PIX",
    "18": "Transferência", "90": "Sem pagamento", "99": "Outros",
}


class NFeInvalida(ValueError):
    """Arquivo não é uma NF-e que o sistema consegue importar."""


@dataclass
class ItemNFe:
    codigo: str
    descricao: str
    ncm: str
    cfop: str
    unidade: str
    quantidade: float
    valor_unitario: float
    valor_total: float


@dataclass
class Parcela:
    numero: str
    vencimento: date
    valor: float


@dataclass
class NFe:
    chave: str
    numero: str
    serie: str
    emissao: date
    emitente_cnpj: str
    emitente_nome: str
    emitente_fantasia: str
    emitente_endereco: str
    emitente_telefone: str
    destinatario_cnpj: str
    valor_total: float
    autorizada: bool
    forma_pagamento: str
    itens: list[ItemNFe] = field(default_factory=list)
    parcelas: list[Parcela] = field(default_factory=list)


def somente_digitos(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def formatar_cnpj(v: str | None) -> str:
    d = somente_digitos(v)
    if len(d) != 14:
        return d
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def _txt(no, caminho: str, padrao: str = "") -> str:
    if no is None:
        return padrao
    el = no.find(caminho, NS)
    return el.text.strip() if el is not None and el.text else padrao


def _num(no, caminho: str) -> float:
    try:
        return float(_txt(no, caminho, "0"))
    except ValueError:
        return 0.0


def _data(valor: str) -> date | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor).date()   # dhEmi: 2026-09-20T10:15:00-03:00
    except ValueError:
        try:
            return datetime.strptime(valor[:10], "%Y-%m-%d").date()  # dEmi / dVenc
        except ValueError:
            return None


def ler_nfe(conteudo: bytes) -> NFe:
    """Converte o XML (nfeProc ou NFe) em NFe. Levanta NFeInvalida com mensagem amigável."""
    if not conteudo:
        raise NFeInvalida("Arquivo vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise NFeInvalida("Arquivo grande demais para ser uma NF-e.")
    if b"<!DOCTYPE" in conteudo[:2000] or b"<!ENTITY" in conteudo:
        raise NFeInvalida("XML com declarações não permitidas.")
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        raise NFeInvalida("O arquivo não é um XML válido.")

    tag = raiz.tag.split("}")[-1]
    if tag in ("procEventoNFe", "evento", "retEvento"):
        raise NFeInvalida("Este XML é um evento (cancelamento/carta de correção), não a nota.")
    if tag in ("cteProc", "CTe"):
        raise NFeInvalida("Este XML é um CT-e (conhecimento de transporte). Importe o XML da NF-e.")

    inf = raiz.find(".//n:infNFe", NS)
    if inf is None:
        raise NFeInvalida("Não encontrei os dados da NF-e neste XML. Confira se é o XML da nota (modelo 55).")

    ide, emit, dest = inf.find("n:ide", NS), inf.find("n:emit", NS), inf.find("n:dest", NS)
    if _txt(ide, "n:mod") not in ("", "55"):
        raise NFeInvalida("Somente NF-e modelo 55 é suportada (NFC-e/cupom não).")

    chave = (inf.get("Id") or "").removeprefix("NFe") or _txt(raiz, ".//n:protNFe/n:infProt/n:chNFe")
    emissao = _data(_txt(ide, "n:dhEmi") or _txt(ide, "n:dEmi"))
    if not chave or not emissao:
        raise NFeInvalida("NF-e sem chave de acesso ou data de emissão.")

    end = emit.find("n:enderEmit", NS) if emit is not None else None
    endereco = ", ".join(p for p in (
        _txt(end, "n:xLgr"), _txt(end, "n:nro"), _txt(end, "n:xBairro"),
        f"{_txt(end, 'n:xMun')}/{_txt(end, 'n:UF')}".strip("/"),
    ) if p)

    itens = []
    for det in inf.findall("n:det", NS):
        prod = det.find("n:prod", NS)
        itens.append(ItemNFe(
            codigo=_txt(prod, "n:cProd"),
            descricao=_txt(prod, "n:xProd"),
            ncm=_txt(prod, "n:NCM"),
            cfop=_txt(prod, "n:CFOP"),
            unidade=_txt(prod, "n:uCom", "un"),
            quantidade=_num(prod, "n:qCom"),
            valor_unitario=_num(prod, "n:vUnCom"),
            valor_total=_num(prod, "n:vProd") - _num(prod, "n:vDesc"),
        ))
    if not itens:
        raise NFeInvalida("A NF-e não tem itens.")

    parcelas = []
    for dup in inf.findall("n:cobr/n:dup", NS):
        venc = _data(_txt(dup, "n:dVenc"))
        if venc:
            parcelas.append(Parcela(_txt(dup, "n:nDup"), venc, _num(dup, "n:vDup")))

    tpag = _txt(inf, "n:pag/n:detPag/n:tPag")
    cstat = _txt(raiz, ".//n:protNFe/n:infProt/n:cStat")

    return NFe(
        chave=chave,
        numero=_txt(ide, "n:nNF"),
        serie=_txt(ide, "n:serie"),
        emissao=emissao,
        emitente_cnpj=somente_digitos(_txt(emit, "n:CNPJ") or _txt(emit, "n:CPF")),
        emitente_nome=_txt(emit, "n:xNome"),
        emitente_fantasia=_txt(emit, "n:xFant"),
        emitente_endereco=endereco,
        emitente_telefone=_txt(end, "n:fone"),
        destinatario_cnpj=somente_digitos(_txt(dest, "n:CNPJ") or _txt(dest, "n:CPF")),
        valor_total=_num(inf, "n:total/n:ICMSTot/n:vNF"),
        autorizada=cstat in ("100", "150"),  # 100 = autorizada; 150 = autorizada fora do prazo
        forma_pagamento=FORMAS_PAGAMENTO.get(tpag, "A definir"),
        itens=itens,
        parcelas=parcelas,
    )


def parcelas_para_pagar(nota: NFe) -> list[Parcela]:
    """Duplicatas da nota; sem duplicata, uma parcela única no valor total, vencendo na emissão."""
    return nota.parcelas or [Parcela("1", nota.emissao, nota.valor_total)]
