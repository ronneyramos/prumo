"""Fotos do RDO: bucket privado com links assinados; fotos antigas continuam."""
import sync


class _BucketFake:
    def create_signed_url(self, path, expira):
        assert expira == 3600
        return {"signedURL": f"https://assinado/{path}"}


class _ClienteFake:
    class storage:
        @staticmethod
        def from_(bucket):
            assert bucket == "rdo-fotos"
            return _BucketFake()


def test_resolver_fotos_gera_link_assinado(monkeypatch):
    import db
    monkeypatch.setattr(db, "sb", lambda: _ClienteFake())
    fotos = [{"nome": "laje.jpg", "path": "emp-1/rdo/r1/a.jpg"}]
    assert sync.resolver_fotos(fotos) == [{"nome": "laje.jpg", "url": "https://assinado/emp-1/rdo/r1/a.jpg"}]


def test_resolver_fotos_mantem_formato_antigo():
    antigas = [{"nome": "x", "url": "https://publico/x.jpg"}, "https://publico/y.jpg"]
    assert sync.resolver_fotos(antigas) == [
        {"nome": "x", "url": "https://publico/x.jpg"},
        {"nome": "Foto", "url": "https://publico/y.jpg"},
    ]


def test_upload_sem_empresa_nao_envia(monkeypatch):
    monkeypatch.setattr(sync, "_empresa_id", lambda: None)
    assert sync.upload_rdo_foto("r1", b"bytes", "a.jpg") is None
