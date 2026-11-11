import hashlib
import io

import pytest
from minio.error import S3Error

from src.adapters.minio_object_store import MinioObjectStore
from tests.contratos import comprobar_object_store

BUCKET = "objetos"


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def error_s3(codigo):
    return S3Error(None, codigo, codigo, "/", "req", "host")


class RespuestaFalsa(io.BytesIO):
    def __init__(self, datos):
        super().__init__(datos)
        self.liberada = False

    def release_conn(self):
        self.liberada = True


class ClienteMinioFalso:
    """Imita lo que usa el adaptador de `minio.Minio`: lee `data` por partes y no guarda si la lectura falla."""

    def __init__(self):
        self.objetos = {}
        self.subidas = []
        self.respuestas = []
        self.error_en_stat = None

    def stat_object(self, bucket, nombre):
        assert bucket == BUCKET
        if self.error_en_stat:
            raise self.error_en_stat
        if nombre not in self.objetos:
            raise error_s3("NoSuchKey")
        return object()

    def put_object(self, bucket, nombre, data, length, **_):
        assert bucket == BUCKET
        self.subidas.append((nombre, data, length))
        partes = []
        while parte := data.read(4):
            partes.append(parte)
        self.objetos[nombre] = b"".join(partes)

    def get_object(self, bucket, nombre):
        assert bucket == BUCKET
        if nombre not in self.objetos:
            raise error_s3("NoSuchKey")
        respuesta = RespuestaFalsa(self.objetos[nombre])
        self.respuestas.append(respuesta)
        return respuesta


@pytest.fixture
def cliente():
    return ClienteMinioFalso()


@pytest.fixture
def almacen(cliente):
    return MinioObjectStore(cliente, BUCKET)


def test_cumple_el_contrato_de_object_store(almacen):
    comprobar_object_store(almacen)


def test_clave_es_sha256_del_contenido(almacen, cliente):
    datos = b"evidencia sintetica"
    almacen.put(sha(datos), io.BytesIO(datos), len(datos))
    assert cliente.objetos == {sha(datos): datos}


def test_mismo_contenido_guarda_un_objeto(almacen, cliente):
    datos = b"mismo contenido"
    for _ in range(3):
        almacen.put(sha(datos), io.BytesIO(datos), len(datos))
    assert len(cliente.subidas) == 1
    assert list(cliente.objetos) == [sha(datos)]


def test_put_entrega_el_flujo_con_su_tamano_sin_leerlo_antes(almacen, cliente):
    flujo = io.BytesIO(b"x" * 100)
    almacen.put(sha(b"x" * 100), flujo, 100)
    (_, entregado, longitud), = cliente.subidas
    assert entregado is flujo
    assert longitud == 100


def test_exists_es_falso_si_no_existe(almacen):
    assert almacen.exists(sha(b"nada")) is False


@pytest.mark.parametrize("error", [error_s3("AccessDenied"), ConnectionError("sin red")])
def test_exists_propaga_errores_que_no_son_ausencia(almacen, cliente, error):
    cliente.error_en_stat = error
    with pytest.raises(type(error)):
        almacen.exists(sha(b"nada"))


def test_open_inexistente_lanza_keyerror(almacen):
    with pytest.raises(KeyError):
        almacen.open(sha(b"nada"))


def test_open_libera_la_conexion_al_cerrar(almacen, cliente):
    datos = b"contenido"
    almacen.put(sha(datos), io.BytesIO(datos), len(datos))
    with almacen.open(sha(datos)) as flujo:
        assert flujo.read() == datos
    respuesta, = cliente.respuestas
    assert respuesta.closed and respuesta.liberada


@pytest.mark.parametrize("clave", ["", "a/b", "../x", "x/", "."])
def test_clave_insegura_se_rechaza_sin_tocar_minio(almacen, cliente, clave):
    for operacion in (lambda: almacen.exists(clave), lambda: almacen.open(clave),
                      lambda: almacen.put(clave, io.BytesIO(b"x"), 1)):
        with pytest.raises(ValueError):
            operacion()
    assert cliente.subidas == [] and cliente.objetos == {}
