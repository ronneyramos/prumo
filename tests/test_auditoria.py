"""Regressões dos problemas encontrados na auditoria de 28/09/2026."""
from datetime import date, timedelta

import pytest

import db
import sync


# ── Status "Vencido" calculado pela data ────────────────────────────────────

def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def test_conta_em_aberto_com_vencimento_passado_fica_vencida():
    ontem = _br(date.today() - timedelta(days=1))
    assert sync.status_com_vencimento("A Pagar", ontem) == "Vencido"
    assert sync.status_com_vencimento("A Receber", ontem) == "Vencido"


def test_conta_paga_ou_futura_nao_vira_vencida():
    ontem = _br(date.today() - timedelta(days=1))
    assert sync.status_com_vencimento("Pago", ontem) == "Pago"
    assert sync.status_com_vencimento("Cancelado", ontem) == "Cancelado"
    assert sync.status_com_vencimento("A Pagar", _br(date.today())) == "A Pagar"
    assert sync.status_com_vencimento("A Pagar", "") == "A Pagar"


# ── Conciliação: leitura do extrato ─────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("1500.50", 1500.50),      # antes virava 150050
    ("1.500,50", 1500.50),
    ("1500,50", 1500.50),
    ("1,500.50", 1500.50),
    ("1.500", 1500.0),
    ("-R$ 10,00", -10.0),
    ("10,00-", -10.0),
])
def test_valor_extrato(texto, esperado):
    assert sync._valor_extrato(texto) == pytest.approx(esperado)


def test_extrato_com_ponto_e_virgula_e_cabecalho():
    csv = "Data;Descrição;Valor\n10/09/2026;PIX recebido;1.234,56\n11/09/2026;Boleto;-99,90\nSaldo;;5000\n"
    t = sync._parse_csv_extrato(csv)
    assert [(x["data"], x["valor"], x["tipo"]) for x in t] == [
        ("2026-09-10", 1234.56, "Credito"),
        ("2026-09-11", 99.90, "Debito"),
    ]


def test_extrato_com_virgula_e_decimal_com_ponto():
    t = sync._parse_csv_extrato("Data,Descricao,Valor\n10/09/2026,PIX,1500.50\n")
    assert t[0]["valor"] == pytest.approx(1500.50)


# ── Ordenação dos códigos de orçamento/EAP ──────────────────────────────────

def test_ordem_natural_dos_codigos():
    codigos = ["10", "2", "1.10", "1.2", "1", "2.1"]
    assert sorted(codigos, key=sync._chave_ordem) == ["1", "1.2", "1.10", "2", "2.1", "10"]


# ── Colaborador: edição parcial não apaga dados ─────────────────────────────

def test_salvar_so_a_situacao_nao_zera_o_resto(monkeypatch):
    enviado = {}
    monkeypatch.setattr(db, "colaborador_atualizar", lambda cid, d: enviado.update(d) or {"id": cid})
    assert sync.colaborador_save({"Situação": "Férias"}, sb_id="col-1") == "col-1"
    assert enviado == {"situacao": "Férias"}


def test_ferias_nao_desativa_o_colaborador(monkeypatch):
    enviado = {}
    monkeypatch.setattr(db, "colaborador_atualizar", lambda cid, d: enviado.update(d) or {"id": cid})
    sync.colaborador_save({"Nome": "João", "Situação": "Afastado", "Salário (R$)": 3000}, sb_id="col-1")
    assert "ativo" not in enviado and enviado["situacao"] == "Afastado"


# ── NC: responsável é gravado ───────────────────────────────────────────────

def test_nc_grava_responsavel(monkeypatch):
    enviado = {}
    monkeypatch.setattr(db, "nc_criar", lambda d: enviado.update(d) or {"id": "nc-1"})
    sync.nc_save({"Descrição": "Trinca", "Gravidade": "Alta", "Responsável": "Carlos"}, obra_sb_id="o1")
    assert enviado["responsavel_nome"] == "Carlos"


# ── EAP: atualizar não apaga o que já existe ────────────────────────────────

class _Consulta:
    def __init__(self, banco, tabela):
        self.banco, self.tabela, self.op, self.dados, self.filtros = banco, tabela, "select", None, []

    def select(self, *_):
        return self

    def update(self, d):
        self.op, self.dados = "update", d
        return self

    def insert(self, d):
        self.op, self.dados = "insert", d
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, v):
        self.filtros.append((col, [v]))
        return self

    def in_(self, col, vs):
        self.filtros.append((col, list(vs)))
        return self

    def execute(self):
        linhas = self.banco.setdefault(self.tabela, [])
        casa = [r for r in linhas if all(r.get(c) in vs for c, vs in self.filtros)]
        if self.op == "insert":
            for r in self.dados:
                linhas.append({**r, "id": f"novo-{r['codigo']}"})
        elif self.op == "update":
            for r in casa:
                r.update(self.dados)
        elif self.op == "delete":
            self.banco[self.tabela] = [r for r in linhas if r not in casa]
        return type("R", (), {"data": casa})()


def test_atualizar_eap_mantem_ids_e_nao_apaga_etapa_com_custo(monkeypatch):
    banco = {
        "eap_itens": [
            {"id": "e1", "obra_id": "o1", "codigo": "1", "descricao": "Fundação", "progresso": 0.4},
            {"id": "e2", "obra_id": "o1", "codigo": "2", "descricao": "Antiga com custo"},
            {"id": "e3", "obra_id": "o1", "codigo": "3", "descricao": "Antiga sem nada"},
        ],
        "lancamentos": [{"id": "l1", "eap_item_id": "e2"}],
    }
    cliente = type("C", (), {"table": lambda self, t: _Consulta(banco, t)})()
    monkeypatch.setattr(db, "sb", lambda: cliente)
    monkeypatch.setattr(sync, "_empresa_id", lambda: "emp")

    r = sync.eap_save_from_orcamento("o1", [
        {"ordem": "1", "descricao": "Fundação (rev)", "total_venda": 100},
        {"ordem": "4", "descricao": "Nova", "total_venda": 50},
    ])

    eap = {e["codigo"]: e for e in banco["eap_itens"]}
    assert r == {"novos": 1, "atualizados": 1, "removidos": 1, "mantidos": 1}
    assert eap["1"]["id"] == "e1" and eap["1"]["progresso"] == 0.4   # progresso preservado
    assert eap["1"]["descricao"] == "Fundação (rev)"
    assert "2" in eap        # tem lançamento ligado: fica
    assert "3" not in eap    # sem vínculo: removida
    assert "4" in eap


# ── 2ª leva ─────────────────────────────────────────────────────────────────

def test_falta_grava_tipo_e_limpa_horarios(monkeypatch):
    enviado = {}

    class _T:
        def upsert(self, d, on_conflict=None):
            enviado.update(d)
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "p1"}]})()

    monkeypatch.setattr(sync, "_colaborador_uuid_por_nome", lambda n: "col-1")
    monkeypatch.setattr(db, "sb", lambda: type("C", (), {"table": lambda self, t: _T()})())
    assert sync.falta_save({"Funcionário": "João", "Data": "10/09/2026", "Tipo": "Atestado"}) == "p1"
    assert enviado["tipo_falta"] == "Atestado" and enviado["falta"] is True
    assert enviado["entrada"] is None and enviado["horas_normais"] == 0


def test_marcar_vencedora_nao_zera_a_cotacao(monkeypatch):
    enviado = {}
    monkeypatch.setattr(db, "cotacao_atualizar", lambda cid, d: enviado.update(d) or {"id": cid})
    assert sync.cotacao_save({"Vencedora": "Sim"}, sb_id="cot-1") == "cot-1"
    assert enviado == {"vencedora": True}
