import pytest
import pandas as pd


class TestToNum:
    """Testes para _to_num() - conversão de valores para float."""

    def test_none_returns_zero(self):
        from main import _to_num
        assert _to_num(None) == 0.0

    def test_int_returns_float(self):
        from main import _to_num
        assert _to_num(42) == 42.0

    def test_float_returns_float(self):
        from main import _to_num
        assert _to_num(3.14) == 3.14

    def test_br_currency_string(self):
        from main import _to_num
        assert _to_num("R$ 1.500,50") == 1500.50

    def test_empty_string_returns_zero(self):
        from main import _to_num
        assert _to_num("") == 0.0

    def test_invalid_string_returns_zero(self):
        from main import _to_num
        assert _to_num("abc") == 0.0

    def test_dot_as_thousand_separator(self):
        from main import _to_num
        assert _to_num("1.234,56") == 1234.56


class TestFmt:
    """Testes para _fmt() - formatação de valores monetários."""

    def test_format_brl(self):
        from main import _fmt
        assert _fmt(1500.50) == "R$ 1.500,50"

    def test_format_large_number(self):
        from main import _fmt
        assert _fmt(1000000.00) == "R$ 1.000.000,00"

    def test_format_zero(self):
        from main import _fmt
        assert _fmt(0) == "R$ 0,00"

    def test_format_none(self):
        from main import _fmt
        assert _fmt(None) == "R$ 0,00"


class TestUniq:
    """Testes para _uniq() - valores únicos de Series."""

    def test_basic_unique(self):
        from main import _uniq
        s = pd.Series(["a", "b", "a", "c"])
        assert _uniq(s) == ["a", "b", "c"]

    def test_ignores_nan(self):
        from main import _uniq
        s = pd.Series(["a", None, "b"])
        result = _uniq(s)
        assert None not in result
        assert result == ["a", "b"]

    def test_ignores_empty_string(self):
        from main import _uniq
        s = pd.Series(["a", "", "b"])
        assert _uniq(s) == ["a", "b"]

    def test_empty_series(self):
        from main import _uniq
        s = pd.Series([], dtype=str)
        assert _uniq(s) == []


class TestNextId:
    """Testes para _next_id() - próximo ID incremental."""

    def test_empty_df_returns_1(self):
        from main import _next_id
        df = pd.DataFrame(columns=["ID"])
        assert _next_id(df) == 1

    def test_increments(self):
        from main import _next_id
        df = pd.DataFrame({"ID": [1, 2, 3]})
        assert _next_id(df) == 4

    def test_single_row(self):
        from main import _next_id
        df = pd.DataFrame({"ID": [5]})
        assert _next_id(df) == 6


class TestTabelaClicavel:
    """Testes para _tabela_clicavel() - seleção em tabela."""

    def test_returns_none_if_no_selection(self):
        from main import _tabela_clicavel
        df = pd.DataFrame({"Nome": ["A", "B"]})
        # Simula que nada foi selecionado
        result = _tabela_clicavel(df, key="test_no_sel")
        assert result is None


class TestFormatSync:
    """Testes para funções de formatação do sync.py."""

    def test_iso_to_br(self):
        from sync import _iso_to_br
        assert _iso_to_br("2026-07-09") == "09/07/2026"

    def test_iso_to_br_empty(self):
        from sync import _iso_to_br
        assert _iso_to_br(None) == ""
        assert _iso_to_br("") == ""

    def test_br_to_iso(self):
        from sync import _br_to_iso
        assert _br_to_iso("09/07/2026") == "2026-07-09"

    def test_br_to_iso_empty(self):
        from sync import _br_to_iso
        assert _br_to_iso(None) is None
        assert _br_to_iso("") is None

    def test_attr_with_valid_key(self):
        from sync import _attr
        class Row:
            nome = "Teste"
            id = "abc-123"
        row = Row()
        assert _attr(row, "nome") == "Teste"
        assert _attr(row, "id") == "abc-123"

    def test_attr_fallback(self):
        from sync import _attr
        class Row:
            nome = "Teste"
        row = Row()
        assert _attr(row, "nao_existe", "outra_chave", default="fallback") == "fallback"