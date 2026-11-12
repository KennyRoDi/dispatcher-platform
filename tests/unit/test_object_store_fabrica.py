import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.minio_object_store import MinioObjectStore
from src.infrastructure import object_store
from src.infrastructure.tls import TlsConfigError

ENV = {
    "MINIO_ENDPOINT": "minio:9000",
    "MINIO_ACCESS_KEY": "access",
    "MINIO_SECRET_KEY": "secret",
    "MINIO_SECURE": "false",
    "OBJECTS_BUCKET": "objetos",
    "TLS_ENABLED": "false",
}


class Cliente:
    def __init__(self):
        self.buckets = []

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.append(bucket)


@pytest.fixture
def cliente(monkeypatch):
    falso = Cliente()
    monkeypatch.setattr(object_store.minio, "Minio", lambda *args, **kwargs: falso)
    return falso


def test_crear_almacen_lectura_arma_el_almacen_cifrado_sin_staging(cliente):
    almacen = object_store.crear_almacen_lectura(ENV)
    assert isinstance(almacen, EncryptedObjectStore)
    assert isinstance(almacen._inner, MinioObjectStore)
    assert almacen._inner._client is cliente
    assert cliente.buckets == ["objetos"]


@pytest.mark.parametrize("faltante", ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"])
def test_crear_almacen_lectura_exige_variables_y_tls(cliente, faltante):
    env = {clave: valor for clave, valor in ENV.items() if clave != faltante}
    with pytest.raises(ValueError, match="faltan variables"):
        object_store.crear_almacen_lectura(env)
    with pytest.raises(TlsConfigError):
        object_store.crear_almacen_lectura({**ENV, "TLS_ENABLED": "true"})


def test_crear_subidas_sigue_igual_tras_extraer_la_fabrica(cliente, tmp_path, monkeypatch):
    llamadas = []
    original = object_store.crear_almacen_lectura
    monkeypatch.setattr(object_store, "crear_almacen_lectura", lambda env: llamadas.append(env) or original(env))
    env = {**ENV, "STAGING_DIR": str(tmp_path / "chunks")}
    subidas = object_store.crear_subidas(env)
    assert llamadas == [env]
    assert (tmp_path / "chunks").is_dir()
    assert isinstance(subidas._object_store, EncryptedObjectStore)
    with pytest.raises(ValueError, match="faltan variables"):
        object_store.crear_subidas({})
