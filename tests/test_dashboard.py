import pytest
import pandas as pd
from datetime import date, timedelta


class TestDashboardCalculations:
    """Testes para cálculos usados no dashboard."""

    def test_total_contratado(self, sample_obras_df):
        from main import _to_num
        total = sample_obras_df["Valor Contrato (R$)"].sum()
        assert total == 150000.0

    def test_total_medido(self, sample_obras_df):
        obras = sample_obras_df.copy()
        obras["_val_medido"] = obras["Valor Contrato (R$)"] * obras["% Físico"] / 100
        total = obras["_val_medido"].sum()
        # Obra A: 100000 * 0.45 = 45000, Obra B: 50000 * 1.0 = 50000
        assert total == 95000.0

    def test_pct_medido(self, sample_obras_df):
        obras = sample_obras_df.copy()
        total_contratado = obras["Valor Contrato (R$)"].sum()
        obras["_val_medido"] = obras["Valor Contrato (R$)"] * obras["% Físico"] / 100
        total_medido = obras["_val_medido"].sum()
        pct = (total_medido / total_contratado * 100) if total_contratado else 0
        assert abs(pct - 63.33) < 0.01

    def test_obras_ativas_count(self, sample_obras_df):
        n_ativas = len(sample_obras_df[sample_obras_df["Status"] == "Em andamento"])
        assert n_ativas == 1

    def test_total_folha(self, sample_func_df):
        from main import _to_num
        total = sample_func_df["Salário (R$)"].apply(_to_num).sum() * 1.31
        assert abs(total - (8500.0 * 1.31)) < 0.01

    def test_alertas_vencidos(self, sample_contas_df):
        hoje = date.today()
        df = sample_contas_df.copy()
        from datetime import datetime
        df["venc_dt"] = pd.to_datetime(df["Vencimento"], dayfirst=True, errors="coerce").dt.date
        mask = (df["Status"] == "Vencido") | (
            (df["Status"] == "A Pagar") & (df["venc_dt"] <= hoje + timedelta(days=7))
        )
        n_alertas = int(mask.sum())
        assert n_alertas >= 1


class TestToNumWithDataFrame:
    """Testes para _to_num aplicado em colunas de DataFrame."""

    def test_currency_column_conversion(self):
        from main import _to_num
        df = pd.DataFrame({"Valor": ["R$ 1.500,00", "R$ 2.300,50", "R$ 0,00"]})
        result = df["Valor"].apply(_to_num)
        assert list(result) == [1500.00, 2300.50, 0.00]

    def test_mixed_column_conversion(self):
        from main import _to_num
        df = pd.DataFrame({"Valor": [1000.0, "R$ 500,00", None]})
        result = df["Valor"].apply(_to_num)
        assert list(result) == [1000.0, 500.0, 0.0]