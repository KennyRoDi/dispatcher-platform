import gc
import hashlib
import io
import os
import time
import tracemalloc

import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.application.ports import DecryptionError, KeyUnavailable
from tests.dobles import FakeKeyProvider, FakeObjectStore

CHUNK = 16
MIB = 1024 * 1024


def _almacen(inner=None, kek=None, chunk_size=CHUNK):
    kek = os.urandom(32) if kek is None else kek
    inner = FakeObjectStore() if inner is None else inner
    cipher = EnvelopeCipher(FakeKeyProvider(kek), chunk_size=chunk_size)
    return EncryptedObjectStore(inner, cipher), inner


def _guardar(almacen, contenido: bytes) -> str:
    sha = hashlib.sha256(contenido).hexdigest()
    almacen.put(sha, io.BytesIO(contenido), len(contenido))
    return sha


def _alterar(inner, sha, posicion=-5):
    alterado = bytearray(inner.objetos[sha])
    alterado[posicion] ^= 0x01
    inner.objetos[sha] = bytes(alterado)


def _locales_con_llaves(error, minimo=31):
    # Solo `dek` y `kek`: la cabecera y la DEK envuelta son públicas por diseño.
    encontrados, traza = [], error.__traceback__
    while traza:
        for nombre, valor in list(traza.tb_frame.f_locals.items()):
            if nombre in {"dek", "kek"} and isinstance(valor, (bytes, bytearray)) and len(valor) >= minimo:
                encontrados.append((traza.tb_frame.f_code.co_name, nombre))
        traza = traza.tb_next
    return encontrados


class FlujoQueFalla(io.BytesIO):
    def read(self, size=-1):
        if self.tell() > 0:
            raise OSError("fallo a mitad del flujo")
        return super().read(size)


class FlujoSintetico(io.RawIOBase):
    def __init__(self, total):
        self.restante = total

    def readable(self):
        return True

    def read(self, size=-1):
        tomar = min(self.restante, 65536 if size is None or size < 0 else size)
        self.restante -= tomar
        return b"\0" * tomar


class AlmacenExacto(FakeObjectStore):
    """Como MinIO: lee exactamente `size` bytes y descarta el resto."""

    def put(self, sha256, content, size):
        self.objetos[sha256] = content.read(size)


class AlmacenEnArchivo(FakeObjectStore):
    def __init__(self, ruta):
        super().__init__()
        self.ruta = ruta

    def put(self, sha256, content, size):
        with open(self.ruta, "wb") as destino:
            while bloque := content.read(65536):
                destino.write(bloque)

    def open(self, sha256):
        return open(self.ruta, "rb")


class FlujoQueSeCierra(io.BytesIO):
    def __init__(self, datos):
        super().__init__(datos)
        self.cierres = 0

    def close(self):
        self.cierres += 1
        super().close()


class AlmacenConFlujo(FakeObjectStore):
    def open(self, sha256):
        self.flujo = FlujoQueSeCierra(self.objetos[sha256])
        return self.flujo


def test_un_error_de_autenticacion_no_se_convierte_en_lectura_parcial_valida():
    almacen, inner = _almacen()
    sha = _guardar(almacen, os.urandom(4 * CHUNK))
    _alterar(inner, sha, -5)
    lector = almacen.open(sha)
    with pytest.raises(DecryptionError):
        lector.read(100)
    with pytest.raises(Exception):
        lector.read(100)


def test_el_lector_sirve_para_file_digest_y_bufferedreader():
    almacen, _ = _almacen()
    contenido = os.urandom(5 * CHUNK + 3)
    sha = _guardar(almacen, contenido)
    assert hashlib.file_digest(almacen.open(sha), "sha256").hexdigest() == sha
    assert io.BufferedReader(almacen.open(sha)).read() == contenido


def test_read_tras_close_falla():
    almacen, _ = _almacen()
    sha = _guardar(almacen, os.urandom(3 * CHUNK))
    lector = almacen.open(sha)
    lector.close()
    with pytest.raises(ValueError):
        lector.read(5)


def test_close_con_fallo_del_flujo_interno_deja_el_lector_cerrado():
    class Roto(AlmacenConFlujo):
        def open(self, sha256):
            flujo = super().open(sha256)
            cerrar = flujo.close
            fallos = []

            def cerrar_con_fallo():
                if not fallos:
                    fallos.append(1)
                    raise OSError("cierre fallido")
                cerrar()

            flujo.close = cerrar_con_fallo
            return flujo

    almacen, _ = _almacen(Roto())
    sha = _guardar(almacen, os.urandom(3 * CHUNK))
    lector = almacen.open(sha)
    with pytest.raises(OSError):
        lector.close()
    assert lector.closed


def test_leer_en_bloques_pequenos_cuesta_lo_mismo_que_leer_todo(tmp_path):
    chunk = 4 * MIB
    almacen, _ = _almacen(chunk_size=chunk)
    sha = _guardar(almacen, os.urandom(4 * chunk))

    def medir(leer):
        tiempos = []
        for _ in range(2):
            lector = almacen.open(sha)
            inicio = time.perf_counter()
            leer(lector)
            tiempos.append(time.perf_counter() - inicio)
        return min(tiempos)

    def bloques(lector):
        while lector.read(8192):
            pass

    assert medir(bloques) < 5 * medir(lambda lector: lector.read())


@pytest.mark.xfail(strict=True, reason="size menor que el real: el interno guarda un objeto truncado e ilegible sin error en put")
@pytest.mark.parametrize("declarado", [0, 10, -1])
def test_size_menor_al_real_no_deja_un_objeto_ilegible(declarado):
    almacen, _ = _almacen(AlmacenExacto())
    contenido = os.urandom(40)
    sha = hashlib.sha256(contenido).hexdigest()
    try:
        almacen.put(sha, io.BytesIO(contenido), declarado)
    except ValueError:
        return
    assert almacen.open(sha).read() == contenido


@pytest.mark.xfail(strict=True, reason="la DEK queda en los locales de la traza cuando falla el flujo de entrada")
def test_la_dek_no_queda_en_la_traza_si_falla_el_flujo_de_put():
    almacen, _ = _almacen()
    with pytest.raises(OSError) as info:
        almacen.put("a" * 64, FlujoQueFalla(os.urandom(4 * CHUNK)), 4 * CHUNK)
    assert _locales_con_llaves(info.value, 32) == []


@pytest.mark.xfail(strict=True, reason="la DEK queda en los locales de la traza cuando un chunk no autentica")
def test_la_dek_no_queda_en_la_traza_si_un_chunk_no_autentica():
    almacen, inner = _almacen()
    sha = _guardar(almacen, os.urandom(4 * CHUNK))
    _alterar(inner, sha, -3)
    with pytest.raises(DecryptionError) as info:
        almacen.open(sha).read()
    assert _locales_con_llaves(info.value, 32) == []


@pytest.mark.xfail(strict=True, reason="una KEK de largo invalido queda en los locales de la traza (FileKeyProvider si la borra)")
def test_una_kek_de_largo_invalido_no_queda_en_la_traza():
    almacen, _ = _almacen(kek=b"S" * 31)
    with pytest.raises(KeyUnavailable) as info:
        almacen.put("a" * 64, io.BytesIO(b"x"), 1)
    assert _locales_con_llaves(info.value, 31) == []


def test_un_put_cuyo_flujo_falla_no_deja_objeto_en_el_interno():
    almacen, inner = _almacen()
    with pytest.raises(OSError):
        almacen.put("a" * 64, FlujoQueFalla(os.urandom(4 * CHUNK)), 4 * CHUNK)
    assert inner.objetos == {}


@pytest.mark.parametrize("basura", [b"", b"EVC1", b"EVC1\x01", os.urandom(200)], ids=["vacio", "solo_magia", "magia_y_version", "aleatorio"])
def test_un_objeto_interno_vacio_o_con_basura_falla_y_cierra_el_flujo(basura):
    inner = AlmacenConFlujo()
    almacen, _ = _almacen(inner)
    inner.objetos["a" * 64] = basura
    with pytest.raises(DecryptionError):
        almacen.open("a" * 64)
    assert inner.flujo.closed


def test_con_la_kek_rotada_falla_sin_filtrar_la_llave_en_el_mensaje():
    inner = FakeObjectStore()
    antigua, nueva = b"A" * 32, b"N" * 32
    sha = _guardar(_almacen(inner, kek=antigua)[0], os.urandom(40))
    with pytest.raises(DecryptionError) as info:
        _almacen(inner, kek=nueva)[0].open(sha)
    texto = repr(info.value) + str(info.value.__cause__)
    assert "AAAA" not in texto and "NNNN" not in texto


def test_exists_con_objeto_corrupto_delega_y_open_falla():
    almacen, inner = _almacen()
    sha = _guardar(almacen, os.urandom(40))
    inner.objetos[sha] = b"basura"
    assert almacen.exists(sha)
    with pytest.raises(DecryptionError):
        almacen.open(sha)


def test_un_open_sin_leer_ni_cerrar_libera_el_flujo_interno_al_descartarlo():
    inner = AlmacenConFlujo()
    almacen, _ = _almacen(inner)
    sha = _guardar(almacen, os.urandom(3 * CHUNK))
    lector = almacen.open(sha)
    del lector
    gc.collect()
    assert inner.flujo.closed


@pytest.mark.parametrize("tamano", [1, 3, CHUNK - 1, CHUNK, CHUNK + 1, 7 * CHUNK])
def test_lecturas_parciales_pequenas_reconstruyen_el_claro(tamano):
    almacen, _ = _almacen()
    contenido = os.urandom(5 * CHUNK + 3)
    lector = almacen.open(_guardar(almacen, contenido))
    partes = []
    while bloque := lector.read(tamano):
        assert len(bloque) <= tamano
        partes.append(bloque)
    assert b"".join(partes) == contenido


def test_read_cero_y_none_en_el_lector():
    almacen, _ = _almacen()
    lector = almacen.open(_guardar(almacen, b"hola mundo"))
    assert (lector.read(0), lector.read(None), lector.read(3)) == (b"", b"hola mundo", b"")


def test_put_y_open_de_un_objeto_grande_usan_memoria_acotada(tmp_path):
    total, chunk = 24 * MIB, MIB
    almacen, _ = _almacen(AlmacenEnArchivo(tmp_path / "objeto"), chunk_size=chunk)
    tracemalloc.start()
    try:
        almacen.put("a" * 64, FlujoSintetico(total), total)
        pico_put = tracemalloc.get_traced_memory()[1]
        tracemalloc.reset_peak()
        lector, leidos = almacen.open("a" * 64), 0
        while bloque := lector.read(65536):
            leidos += len(bloque)
        pico_open = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert leidos == total
    assert pico_put < 8 * chunk and pico_open < 8 * chunk
