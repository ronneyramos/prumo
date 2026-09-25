"""Garante que o cache de leituras nunca serve dados de uma empresa para outra."""
import sync


def test_cache_separa_empresas(monkeypatch):
    chamadas = []

    @sync._cache_por_empresa(ttl=60)
    def carregar():
        chamadas.append(sync._empresa_id())
        return f"dados-{sync._empresa_id()}"

    monkeypatch.setattr(sync, "_empresa_id", lambda: "empresa-A")
    assert carregar() == "dados-empresa-A"
    monkeypatch.setattr(sync, "_empresa_id", lambda: "empresa-B")
    assert carregar() == "dados-empresa-B"
    monkeypatch.setattr(sync, "_empresa_id", lambda: "empresa-A")
    assert carregar() == "dados-empresa-A"  # veio do cache da A
    assert chamadas == ["empresa-A", "empresa-B"]


def test_funcoes_diferentes_nao_dividem_cache(monkeypatch):
    monkeypatch.setattr(sync, "_empresa_id", lambda: "empresa-A")

    @sync._cache_por_empresa(ttl=60)
    def obras():
        return "obras"

    @sync._cache_por_empresa(ttl=60)
    def colaboradores():
        return "colaboradores"

    assert obras() == "obras"
    assert colaboradores() == "colaboradores"


def test_parametro_ignorado_nao_muda_empresa(monkeypatch):
    """O argumento legado (_empresa_ignorado) não pode escolher a empresa."""
    monkeypatch.setattr(sync, "_empresa_id", lambda: "empresa-B")

    @sync._cache_por_empresa(ttl=60)
    def carregar(_empresa_ignorado: str = ""):
        return sync._empresa_id()

    assert carregar("empresa-A") == "empresa-B"


def test_sem_sessao_nao_cai_na_mbr():
    assert sync._empresa_id() is None
