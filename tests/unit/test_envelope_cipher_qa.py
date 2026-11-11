import hashlib
import io
import os
import struct
import traceback
import tracemalloc

import pytest

from src.adapters import envelope_cipher
from src.adapters.envelope_cipher import FIXED_HEADER, EnvelopeCipher
from src.application.ports import DecryptionError, KeyUnavailable

CHUNK = 64
HEADER = EnvelopeCipher.HEADER_SIZE
FIXED = FIXED_HEADER.size


class _Kek:
    def __init__(self, kek):
        self._kek = kek

    def kek(self):
        return self._kek


def _cipher(kek=None, chunk_size=CHUNK) -> EnvelopeCipher:
    return EnvelopeCipher(_Kek(os.urandom(32) if kek is None else kek), chunk_size=chunk_size)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seal(cipher, data: bytes) -> bytes:
    return b"".join(cipher.encrypt(io.BytesIO(data), _sha(data)))


def _open(cipher, blob: bytes, sha: str) -> bytes:
    return b"".join(cipher.decrypt(io.BytesIO(blob), sha))


def _fails_closed(cipher, blob: bytes, sha: str) -> None:
    with pytest.raises(DecryptionError):
        _open(cipher, blob, sha)


class _Trickle:
    def __init__(self, data: bytes, step):
        self._data, self._pos, self._step = data, 0, step

    def read(self, size=-1):
        take = min(size, self._step(self._pos)) if size >= 0 else self._step(self._pos)
        part = self._data[self._pos : self._pos + take]
        self._pos += len(part)
        return part


@pytest.mark.parametrize("step", [lambda p: 1, lambda p: 1 + (p * 7) % 13, lambda p: 1000])
def test_stream_de_trozos_irregulares_da_el_mismo_resultado_que_uno_regular(step):
    data = os.urandom(5 * CHUNK + 3)
    cipher = _cipher()
    blob = b"".join(cipher.encrypt(_Trickle(data, step), _sha(data)))
    assert _open(cipher, blob, _sha(data)) == data
    assert b"".join(cipher.decrypt(_Trickle(blob, step), _sha(data))) == data


def test_objeto_vacio_va_y_vuelve_y_ocupa_cabecera_mas_una_etiqueta():
    cipher = _cipher()
    blob = _seal(cipher, b"")
    assert len(blob) == HEADER + EnvelopeCipher.TAG_SIZE
    assert _open(cipher, blob, _sha(b"")) == b""


@pytest.mark.parametrize("size", [0, 1, CHUNK, 3 * CHUNK + 1])
def test_solo_la_cabecera_sin_chunks_falla_cerrado(size):
    data = os.urandom(size)
    cipher = _cipher()
    _fails_closed(cipher, _seal(cipher, data)[:HEADER], _sha(data))


@pytest.mark.parametrize("extra", [1, 5, 15])
def test_chunk_final_mas_corto_que_la_etiqueta_falla_cerrado(extra):
    cipher = _cipher()
    blob = _seal(cipher, b"")[:HEADER] + os.urandom(extra)
    _fails_closed(cipher, blob, _sha(b""))


@pytest.mark.parametrize("chunks", [1, 2, 3, 4])
def test_truncado_exacto_en_frontera_de_chunk_falla_cerrado(chunks):
    data = os.urandom(5 * CHUNK)
    cipher = _cipher()
    blob = _seal(cipher, data)
    cut = HEADER + chunks * (CHUNK + EnvelopeCipher.TAG_SIZE)
    _fails_closed(cipher, blob[:cut], _sha(data))


def test_dos_objetos_concatenados_fallan_cerrado():
    a, b = os.urandom(2 * CHUNK), os.urandom(2 * CHUNK)
    cipher = _cipher()
    _fails_closed(cipher, _seal(cipher, a) + _seal(cipher, b), _sha(a))


def test_objeto_con_basura_al_final_falla_cerrado():
    data = os.urandom(2 * CHUNK)
    cipher = _cipher()
    _fails_closed(cipher, _seal(cipher, data) + b"\x00", _sha(data))


def test_cuerpo_de_otro_objeto_con_el_mismo_claro_y_otra_cabecera_falla():
    data = os.urandom(3 * CHUNK)
    cipher = _cipher(os.urandom(32))
    one, two = _seal(cipher, data), _seal(cipher, data)
    _fails_closed(cipher, one[:HEADER] + two[HEADER:], _sha(data))


@pytest.mark.parametrize("campo", ["version", "chunk_size", "prefijo"])
def test_cabecera_fija_alterada_falla_aunque_la_dek_sea_valida(campo):
    data = os.urandom(3 * CHUNK)
    cipher = _cipher()
    blob = bytearray(_seal(cipher, data))
    magic, version, chunk_size, prefix = FIXED_HEADER.unpack(bytes(blob[:FIXED]))
    nuevo = {
        "version": (magic, version + 1, chunk_size, prefix),
        "chunk_size": (magic, version, chunk_size * 2, prefix),
        "prefijo": (magic, version, chunk_size, bytes(b ^ 1 for b in prefix)),
    }[campo]
    blob[:FIXED] = FIXED_HEADER.pack(*nuevo)
    _fails_closed(cipher, bytes(blob), _sha(data))


@pytest.mark.parametrize("chunk_size", [0, 2**26 + 1, 2**32 - 1])
def test_chunk_size_invalido_en_la_cabecera_falla_sin_leer_mas(chunk_size):
    data = os.urandom(CHUNK)
    cipher = _cipher()
    blob = bytearray(_seal(cipher, data))
    blob[5:9] = struct.pack(">I", chunk_size)
    _fails_closed(cipher, bytes(blob), _sha(data))


def test_chunk_size_enorme_valido_no_reserva_memoria_por_adelantado():
    data = os.urandom(CHUNK)
    cipher = _cipher()
    blob = bytearray(_seal(cipher, data))
    blob[5:9] = struct.pack(">I", 2**26)
    tracemalloc.start()
    try:
        with pytest.raises(DecryptionError):
            _open(cipher, bytes(blob), _sha(data))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 2**22


def test_dek_envuelta_con_otro_sha_falla():
    data = os.urandom(CHUNK)
    cipher = _cipher()
    _fails_closed(cipher, _seal(cipher, data), _sha(data + b"x"))


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: el SHA-256 hex es sensible a mayusculas porque se usa tal cual como AAD; "
    "un llamador que lo normalice distinto no puede descifrar (la clave deberia normalizarse)",
)
def test_sha_en_mayusculas_equivale_al_de_minusculas():
    data = os.urandom(CHUNK)
    cipher = _cipher()
    blob = _seal(cipher, data)
    assert _open(cipher, blob, _sha(data).upper()) == data


def test_dek_y_nonce_de_envoltura_no_se_repiten_entre_objetos():
    data = os.urandom(CHUNK)
    cipher = _cipher()
    cabeceras = {_seal(cipher, data)[:HEADER] for _ in range(200)}
    assert len(cabeceras) == 200
    envueltas = {h[FIXED:] for h in cabeceras}
    assert len(envueltas) == 200


def test_el_mismo_claro_cifrado_dos_veces_no_comparte_chunks():
    data = os.urandom(3 * CHUNK)
    cipher = _cipher()
    a, b = _seal(cipher, data)[HEADER:], _seal(cipher, data)[HEADER:]
    width = CHUNK + EnvelopeCipher.TAG_SIZE
    assert not {a[i : i + width] for i in range(0, len(a), width)} & {
        b[i : i + width] for i in range(0, len(b), width)
    }


def test_consumo_parcial_del_iterador_no_deja_error_ni_estado():
    data = os.urandom(6 * CHUNK)
    cipher = _cipher()
    blob = _seal(cipher, data)
    gen = cipher.decrypt(io.BytesIO(blob), _sha(data))
    assert next(gen) == data[:CHUNK]
    gen.close()
    assert _open(cipher, blob, _sha(data)) == data
    gen = cipher.encrypt(io.BytesIO(data), _sha(data))
    next(gen)
    gen.close()


def test_los_errores_no_filtran_kek_ni_dek_en_el_texto_de_la_traza(monkeypatch):
    registro = []
    real = os.urandom
    monkeypatch.setattr(
        envelope_cipher.os, "urandom", lambda n: registro.append(real(n)) or registro[-1]
    )
    kek = real(32)
    data = os.urandom(3 * CHUNK)
    cipher = _cipher(kek)
    blob = bytearray(_seal(cipher, data))
    secretos = [kek, *registro]
    blob[-1] ^= 1
    with pytest.raises(DecryptionError) as info:
        _open(cipher, bytes(blob), _sha(data))
    texto = "".join(traceback.format_exception(info.value))
    for secreto in secretos:
        assert secreto.hex() not in texto and repr(secreto) not in texto


@pytest.mark.parametrize("tamano_kek", [0, 16, 31, 33, 64])
def test_kek_de_tamano_incorrecto_no_aparece_en_el_mensaje(tamano_kek):
    kek = os.urandom(tamano_kek)
    with pytest.raises(KeyUnavailable) as info:
        b"".join(_cipher(kek or b"").encrypt(io.BytesIO(b"x"), "0" * 64))
    assert kek.hex() not in str(info.value) or tamano_kek == 0


def test_memoria_acotada_con_objeto_grande_en_flujo():
    chunk = 1 << 20
    total = 32 * chunk
    cipher = EnvelopeCipher(_Kek(os.urandom(32)), chunk_size=chunk)

    class Ceros:
        def __init__(self):
            self.left = total

        def read(self, size):
            take = min(size, self.left)
            self.left -= take
            return bytes(take)

    class Lector:
        def __init__(self, partes):
            self.partes, self.resto = partes, b""

        def read(self, size):
            while len(self.resto) < size:
                try:
                    self.resto += next(self.partes)
                except StopIteration:
                    break
            salida, self.resto = self.resto[:size], self.resto[size:]
            return salida

    sha = "0" * 64
    tracemalloc.start()
    try:
        cifrado = Lector(cipher.encrypt(Ceros(), sha))
        visto = sum(len(p) for p in cipher.decrypt(cifrado, sha))
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert visto == total
    assert pico < 8 * chunk


class _Raw:
    """Flujo no bloqueante: read devuelve None cuando aun no hay datos (io.RawIOBase)."""

    def __init__(self, data: bytes, corte: int):
        self._data, self._pos, self._corte, self._visto_corte = data, 0, corte, False

    def read(self, size=-1):
        if self._pos == self._corte and not self._visto_corte:
            self._visto_corte = True
            return None
        part = self._data[self._pos : self._pos + size]
        self._pos += len(part)
        return part


@pytest.mark.xfail(
    strict=True,
    reason="QA media: read() devuelve None en un flujo no bloqueante y _read_exact lo toma "
    "como fin de datos: encrypt cifra un objeto truncado sin error (fuga silenciosa de datos)",
)
def test_flujo_que_devuelve_none_no_trunca_en_silencio():
    data = os.urandom(5 * CHUNK)
    cipher = _cipher()
    try:
        blob = b"".join(cipher.encrypt(_Raw(data, 2 * CHUNK), _sha(data)))
    except Exception:
        return
    assert _open(cipher, blob, _sha(data)) == data


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: decrypt entrega los chunks previos autenticados antes de fallar por "
    "truncado; el SPEC dice que nunca devuelve datos parciales (desviacion ya declarada en AD-34)",
)
def test_un_objeto_truncado_no_entrega_ningun_byte_antes_de_fallar():
    data = os.urandom(5 * CHUNK)
    cipher = _cipher()
    blob = _seal(cipher, data)
    cut = HEADER + 4 * (CHUNK + EnvelopeCipher.TAG_SIZE)
    entregado = []
    with pytest.raises(DecryptionError):
        for parte in cipher.decrypt(io.BytesIO(blob[:cut]), _sha(data)):
            entregado.append(parte)
    assert entregado == []


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: una KEK que no es bytes pero mide 32 (str) pasa la validacion y AESGCM "
    "lanza TypeError en vez de KeyUnavailable",
)
@pytest.mark.parametrize("kek", ["k" * 32, None])
def test_kek_que_no_es_bytes_lanza_key_unavailable(kek):
    with pytest.raises(KeyUnavailable):
        b"".join(_cipher_con(kek).encrypt(io.BytesIO(b"x"), "0" * 64))


def _cipher_con(kek) -> EnvelopeCipher:
    return EnvelopeCipher(_Kek(kek), chunk_size=CHUNK)


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: chunk_size float o bool pasa el rango y falla despues con TypeError "
    "opaco al leer (o se acepta True como 1 byte)",
)
@pytest.mark.parametrize("chunk_size", [1.5, True])
def test_chunk_size_que_no_es_entero_se_rechaza_al_construir(chunk_size):
    with pytest.raises((ValueError, TypeError)):
        EnvelopeCipher(_Kek(os.urandom(32)), chunk_size=chunk_size)


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: encrypt es generador; KeyUnavailable (KEK ausente) no se lanza al llamar "
    "sino en el primer next(), cuando el almacen ya pudo abrir el destino",
)
def test_kek_ausente_falla_al_llamar_encrypt_no_al_iterar():
    class SinKek:
        def kek(self):
            raise KeyUnavailable("sin KEK")

    cipher = EnvelopeCipher(SinKek(), chunk_size=CHUNK)
    with pytest.raises(KeyUnavailable):
        cipher.encrypt(io.BytesIO(b"x"), "0" * 64)
