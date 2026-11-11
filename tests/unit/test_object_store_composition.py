import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.application.chunked_upload import ChunkedUpload
from src.infrastructure import object_store
from src.infrastructure.tls import TlsConfigError


def test_crea_composicion_cifrada_y_staging_en_disco(tmp_path, monkeypatch):
    cliente = object()
    monkeypatch.setattr(object_store.minio, "Minio", lambda *args, **kwargs: cliente)
    staging = tmp_path / "chunks"
    env = {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_ACCESS_KEY": "access",
        "MINIO_SECRET_KEY": "secret",
        "MINIO_SECURE": "false",
        "OBJECTS_BUCKET": "objetos",
        "STAGING_DIR": str(staging),
        "TLS_ENABLED": "false",
    }
    subidas = object_store.crear_subidas(env)
    assert isinstance(subidas, ChunkedUpload)
    assert staging.is_dir()
    assert isinstance(subidas._object_store, EncryptedObjectStore)
    assert subidas._object_store._inner._client is cliente


def test_tls_activo_rechaza_minio_inseguro(tmp_path):
    env = {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_ACCESS_KEY": "access",
        "MINIO_SECRET_KEY": "secret",
        "MINIO_SECURE": "false",
        "OBJECTS_BUCKET": "objetos",
        "STAGING_DIR": str(tmp_path / "chunks"),
        "TLS_ENABLED": "true",
    }
    with pytest.raises(TlsConfigError):
        object_store.crear_subidas(env)


def test_faltan_variables_de_minio():
    with pytest.raises(ValueError, match="faltan variables"):
        object_store.crear_subidas({})
