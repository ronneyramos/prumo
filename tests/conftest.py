import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit"))

import pytest
import pandas as pd


@pytest.fixture
def sample_obras_df():
    return pd.DataFrame({
        "ID": [1, 2],
        "SB_ID": ["uuid-1", "uuid-2"],
        "Nome": ["Obra A", "Obra B"],
        "Status": ["Em andamento", "Concluída"],
        "Valor Contrato (R$)": [100000.0, 50000.0],
        "% Físico": [45.0, 100.0],
        "BDI (%)": [25.0, 20.0],
    })


@pytest.fixture
def sample_contas_df():
    return pd.DataFrame({
        "ID": [1, 2, 3],
        "Valor (R$)": [1500.0, 3000.0, 800.0],
        "Status": ["A Pagar", "Vencido", "Pago"],
        "Vencimento": ["15/07/2026", "01/07/2026", "20/06/2026"],
        "Categoria": ["Materiais", "Folha de Pagamento", "Outros"],
    })


@pytest.fixture
def sample_func_df():
    return pd.DataFrame({
        "ID": [1, 2],
        "Nome": ["João", "Maria"],
        "Salário (R$)": [3500.0, 5000.0],
        "Obra": ["Obra A", "Obra B"],
    })


@pytest.fixture
def empty_df():
    return pd.DataFrame()