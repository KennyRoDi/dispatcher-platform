import hashlib
import io
import os

import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.application.ports import DecryptionError, KeyUnavailable, ObjectStore
from tests.contratos import comprobar_object_store
from tests.dobles import FakeKeyProvider, FakeObjectStore

MARCADOR = b"MARCADOR-SINTETICO-F28-ca5e0b1a"
CHUNK = 16


class AlmacenRegistrador(FakeObjectStore):
    def __init__(self):
        super().__init__()
        self.tamanos = []
        self.llamadas = 0

    def put(self, sha256, content, size):
        self.llamadas += 1
        self.tamanos.append(size)
        super().put(sha256, content, size)


def _sha(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _almacen(inner=None, kek=None, chunk_size=CHUNK):
    kek = os.urandom(32) if kek is None else kek
    inner = FakeObjectStore() if inner is None else inner
    return EncryptedObjectStore(inner, EnvelopeCipher(FakeKeyProvider(kek), chunk_size=chunk_size)), inner, kek


def _guardar(almacen, contenido: bytes) -> str:
    sha = _sha(contenido)
    almacen.put(sha, io.BytesIO(contenido), len(contenido))
    return sha


def _contenidos():
    return {
        "vacio": b"",
        "un_chunk": MARCADOR[:10],
        "limite_exacto": os.urandom(CHUNK),
        "dos_chunks_exactos": os.urandom(2 * CHUNK),
        "varios_chunks": MARCADOR + os.urandom(5 * CHUNK + 3),
    }


@pytest.mark.parametrize("contenido", _contenidos().values(), ids=_contenidos().keys())
def test_ida_y_vuelta_devuelve_el_claro(contenido):
    almacen, _, _ = _almacen()
    sha = _guardar(almacen, contenido)
    assert almacen.open(sha).read() == contenido


def test_cumple_el_puerto_objectstore():
    almacen, _, _ = _almacen()
    assert isinstance(almacen, ObjectStore)


def test_cumple_el_contrato_objectstore():
    almacen, _, _ = _almacen()
    comprobar_object_store(almacen)


def test_el_almacen_interno_no_contiene_el_marcador():
    almacen, inner, _ = _almacen()
    contenido = b"cabecera " + MARCADOR + b" cola " + MARCADOR * 4
    sha = _guardar(almacen, contenido)
    guardado = inner.objetos[sha]
    assert MARCADOR not in guardado
    assert MARCADOR[:8] not in guardado
    assert guardado != contenido


def test_la_clave_del_objeto_no_cambia():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, b"evidencia " + MARCADOR)
    assert list(inner.objetos) == [sha]
    assert almacen.exists(sha)
    assert not almacen.exists(_sha(b"otra cosa"))


@pytest.mark.parametrize("contenido", _contenidos().values(), ids=_contenidos().keys())
def test_el_tamano_entregado_al_interno_es_el_del_objeto_cifrado(contenido):
    inner = AlmacenRegistrador()
    almacen, _, _ = _almacen(inner)
    sha = _guardar(almacen, contenido)
    assert inner.tamanos == [len(inner.objetos[sha])]
    assert inner.tamanos[0] > len(contenido)


def test_dos_cifrados_del_mismo_claro_difieren():
    a, inner_a, _ = _almacen()
    b, inner_b, _ = _almacen()
    sha = _guardar(a, MARCADOR)
    _guardar(b, MARCADOR)
    assert inner_a.objetos[sha] != inner_b.objetos[sha]


def test_un_byte_alterado_en_el_interno_falla_el_descifrado():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, MARCADOR + os.urandom(3 * CHUNK))
    bruto = bytearray(inner.objetos[sha])
    for posicion in (0, EnvelopeCipher.HEADER_SIZE - 1, EnvelopeCipher.HEADER_SIZE + 5, len(bruto) - 1):
        alterado = bytearray(bruto)
        alterado[posicion] ^= 0x01
        inner.objetos[sha] = bytes(alterado)
        with pytest.raises(DecryptionError):
            almacen.open(sha).read()


def test_un_objeto_truncado_en_el_interno_falla():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, os.urandom(4 * CHUNK))
    inner.objetos[sha] = inner.objetos[sha][: -(CHUNK + EnvelopeCipher.TAG_SIZE)]
    with pytest.raises(DecryptionError):
        almacen.open(sha).read()


def test_un_objeto_copiado_bajo_otra_clave_falla():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, MARCADOR)
    otra = _sha(b"otra clave")
    inner.objetos[otra] = inner.objetos[sha]
    with pytest.raises(DecryptionError):
        almacen.open(otra).read()


def test_con_otra_kek_no_se_descifra():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, MARCADOR)
    ajeno, _, _ = _almacen(inner)
    with pytest.raises(DecryptionError):
        ajeno.open(sha).read()


def test_sin_kek_put_falla_cerrado_y_no_escribe_nada():
    inner = AlmacenRegistrador()
    almacen = EncryptedObjectStore(inner, EnvelopeCipher(FakeKeyProvider(None), chunk_size=CHUNK))
    with pytest.raises(KeyUnavailable):
        almacen.put(_sha(MARCADOR), io.BytesIO(MARCADOR), len(MARCADOR))
    assert inner.objetos == {}
    assert not almacen.exists(_sha(MARCADOR))


def test_sin_kek_open_falla_cerrado_sin_entregar_datos():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, MARCADOR)
    sin_kek = EncryptedObjectStore(inner, EnvelopeCipher(FakeKeyProvider(None), chunk_size=CHUNK))
    with pytest.raises(KeyUnavailable):
        sin_kek.open(sha).read()


def test_sin_kek_exists_no_la_necesita():
    almacen, inner, _ = _almacen()
    sha = _guardar(almacen, MARCADOR)
    sin_kek = EncryptedObjectStore(inner, EnvelopeCipher(FakeKeyProvider(None), chunk_size=CHUNK))
    assert sin_kek.exists(sha)


def test_kek_de_largo_invalido_no_guarda_en_claro():
    inner = AlmacenRegistrador()
    almacen = EncryptedObjectStore(inner, EnvelopeCipher(FakeKeyProvider(b"corta"), chunk_size=CHUNK))
    with pytest.raises(KeyUnavailable):
        almacen.put(_sha(MARCADOR), io.BytesIO(MARCADOR), len(MARCADOR))
    assert inner.objetos == {}
