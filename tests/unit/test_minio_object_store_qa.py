import io
import os

import pytest
from minio.error import S3Error

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.minio_object_store import MinioObjectStore
from tests.contratos import comprobar_object_store
from tests.dobles import FakeKeyProvider
from tests.unit.test_minio_object_store_unit import (
    BUCKET,
    ClienteMinioFalso,
    RespuestaFalsa,
    error_s3,
)


@pytest.fixture
def cliente():
    return ClienteMinioFalso()


@pytest.fixture
def almacen(cliente):
    return MinioObjectStore(cliente, BUCKET)


def _get_object_que_lanza(error):
    def get_object(bucket, nombre):
        raise error
    return get_object


@pytest.mark.parametrize("codigo", ["AccessDenied", "NoSuchBucket"])
def test_open_propaga_errores_s3_que_no_son_ausencia(almacen, cliente, codigo):
    cliente.get_object = _get_object_que_lanza(error_s3(codigo))
    with pytest.raises(S3Error) as capturado:
        almacen.open("abc")
    assert capturado.value.code == codigo


def test_put_no_sube_si_exists_falla(almacen, cliente):
    cliente.error_en_stat = error_s3("AccessDenied")
    with pytest.raises(S3Error):
        almacen.put("abc", io.BytesIO(b"x"), 1)
    assert cliente.subidas == []


def test_contenido_vacio_se_guarda_y_se_lee(almacen):
    almacen.put("vacio", io.BytesIO(b""), 0)
    with almacen.open("vacio") as flujo:
        assert flujo.read() == b""


class _RespuestaQueSeCorta(RespuestaFalsa):
    def read(self, n=-1):
        if self.tell() >= 3:
            raise ConnectionResetError("corte a mitad")
        return super().read(3)


def test_lectura_cortada_a_mitad_libera_la_conexion_al_cerrar(almacen, cliente):
    respuesta = _RespuestaQueSeCorta(b"0123456789")
    cliente.get_object = lambda bucket, nombre: respuesta
    with pytest.raises(ConnectionResetError), almacen.open("abc") as flujo:
        flujo.read()
    assert respuesta.closed and respuesta.liberada


def test_doble_close_libera_una_sola_vez(almacen, cliente):
    liberaciones = []
    respuesta = RespuestaFalsa(b"xy")
    respuesta.release_conn = lambda: liberaciones.append(1)
    cliente.get_object = lambda bucket, nombre: respuesta
    flujo = almacen.open("abc")
    flujo.close()
    flujo.close()
    assert liberaciones == [1]


class _RespuestaCuyoCloseFalla(RespuestaFalsa):
    def close(self):
        if not getattr(self, "fallo", False):
            self.fallo = True
            raise OSError("close falla")
        super().close()


def test_libera_la_conexion_aunque_close_de_la_respuesta_falle(almacen, cliente):
    respuesta = _RespuestaCuyoCloseFalla(b"xy")
    cliente.get_object = lambda bucket, nombre: respuesta
    flujo = almacen.open("abc")
    with pytest.raises(OSError):
        flujo.close()
    assert respuesta.liberada


def test_readinto_con_buffer_mayor_que_el_objeto(almacen):
    datos = os.urandom(3 << 20)
    almacen.put("grande", io.BytesIO(datos), len(datos))
    buffer = bytearray(8 << 20)
    with almacen.open("grande") as flujo:
        leidos = flujo.readinto(memoryview(buffer))
    assert bytes(buffer[:leidos]) == datos


def test_cifrado_sobre_minio_cumple_el_contrato_y_libera_conexiones(cliente):
    almacen = EncryptedObjectStore(MinioObjectStore(cliente, BUCKET),
                                   EnvelopeCipher(FakeKeyProvider(os.urandom(32)), chunk_size=64))
    comprobar_object_store(almacen)
    with almacen.open("abc") as flujo:
        flujo.read()
    assert cliente.respuestas and all(r.closed and r.liberada for r in cliente.respuestas)
