import io
import os
import uuid

import minio
import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.application.ports import DecryptionError
from tests.dobles import FakeKeyProvider

pytestmark = pytest.mark.integration

MARCADOR = b"MARCADOR-SINTETICO-F28-ca5e0b1a"


class MinioParaPrueba:
    """Adaptador mínimo solo de prueba: el de producción es F-23 (Melany), no este."""

    def __init__(self, client: minio.Minio, bucket: str):
        self.client, self.bucket = client, bucket

    def exists(self, sha256):
        try:
            self.client.stat_object(self.bucket, sha256)
            return True
        except minio.S3Error:
            return False

    def put(self, sha256, content, size):
        self.client.put_object(self.bucket, sha256, content, length=size)

    def open(self, sha256):
        respuesta = self.client.get_object(self.bucket, sha256)
        try:
            return io.BytesIO(respuesta.read())
        finally:
            respuesta.close()
            respuesta.release_conn()


@pytest.fixture
def cliente():
    endpoint = os.environ.get("MINIO_ENDPOINT")
    acceso, secreto = os.environ.get("MINIO_ACCESS_KEY"), os.environ.get("MINIO_SECRET_KEY")
    if not (endpoint and acceso and secreto):
        pytest.skip("define MINIO_ENDPOINT, MINIO_ACCESS_KEY y MINIO_SECRET_KEY de un MinIO real")
    conexion = minio.Minio(endpoint, access_key=acceso, secret_key=secreto, secure=False)
    try:
        conexion.list_buckets()
    except Exception as error:
        pytest.skip(f"MinIO no responde en {endpoint}: {type(error).__name__}")
    return conexion


@pytest.fixture
def almacen_real(cliente):
    bucket = f"f28-prueba-{uuid.uuid4().hex[:12]}"
    cliente.make_bucket(bucket)
    crudo = MinioParaPrueba(cliente, bucket)
    yield EncryptedObjectStore(crudo, EnvelopeCipher(FakeKeyProvider(os.urandom(32)))), crudo
    for objeto in cliente.list_objects(bucket):
        cliente.remove_object(bucket, objeto.object_name)
    cliente.remove_bucket(bucket)


def _guardar(almacen, contenido):
    import hashlib

    sha = hashlib.sha256(contenido).hexdigest()
    almacen.put(sha, io.BytesIO(contenido), len(contenido))
    return sha


def test_objeto_real_en_minio_no_contiene_marcador(almacen_real):
    almacen, crudo = almacen_real
    contenido = b"inicio " + MARCADOR + os.urandom(1024) + MARCADOR
    sha = _guardar(almacen, contenido)
    directo = crudo.open(sha).read()
    assert MARCADOR not in directo
    assert almacen.open(sha).read() == contenido


def test_byte_alterado_en_minio_falla(almacen_real):
    almacen, crudo = almacen_real
    sha = _guardar(almacen, MARCADOR + os.urandom(512))
    alterado = bytearray(crudo.open(sha).read())
    alterado[-1] ^= 0x01
    crudo.put(sha, io.BytesIO(bytes(alterado)), len(alterado))
    with pytest.raises(DecryptionError):
        almacen.open(sha).read()
