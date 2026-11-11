import hashlib
import io
import os

import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.minio_object_store import MinioObjectStore
from tests.contratos import comprobar_object_store
from tests.dobles import FakeKeyProvider
from tests.integration.test_minio_object_store_real import (  # noqa: F401
    MIB,
    _objetos,
    bucket,
    cliente,
)

pytestmark = pytest.mark.integration


class _FallaEn(io.RawIOBase):
    def __init__(self, falla_en):
        self._restantes = falla_en

    def readable(self):
        return True

    def readinto(self, buffer):
        if self._restantes == 0:
            raise RuntimeError("lectura interrumpida")
        leidos = min(len(buffer), self._restantes)
        buffer[:leidos] = b"b" * leidos
        self._restantes -= leidos
        return leidos


def test_put_que_falla_en_la_segunda_parte_no_deja_objeto_ni_multipart(cliente, bucket):  # noqa: F811
    almacen = MinioObjectStore(cliente, bucket)
    with pytest.raises(RuntimeError):
        almacen.put("e" * 64, io.BufferedReader(_FallaEn(7 * MIB)), 15 * MIB)
    assert _objetos(cliente, bucket) == []
    assert cliente._list_multipart_uploads(bucket).uploads == []


def test_objeto_multipart_se_lee_integro_por_partes(cliente, bucket):  # noqa: F811
    almacen = MinioObjectStore(cliente, bucket)
    datos = os.urandom(12 * MIB + 123)
    clave = hashlib.sha256(datos).hexdigest()
    almacen.put(clave, io.BytesIO(datos), len(datos))
    for _ in range(20):
        with almacen.open(clave) as flujo:
            assert flujo.read(10) == datos[:10]
    with almacen.open(clave) as flujo:
        assert hashlib.sha256(flujo.read()).hexdigest() == clave


def test_contenido_vacio(cliente, bucket):  # noqa: F811
    almacen = MinioObjectStore(cliente, bucket)
    clave = hashlib.sha256(b"").hexdigest()
    almacen.put(clave, io.BytesIO(b""), 0)
    with almacen.open(clave) as flujo:
        assert flujo.read() == b""


def test_cifrado_sobre_minio_cumple_el_contrato(cliente, bucket):  # noqa: F811
    comprobar_object_store(EncryptedObjectStore(MinioObjectStore(cliente, bucket),
                                                EnvelopeCipher(FakeKeyProvider(os.urandom(32)))))
