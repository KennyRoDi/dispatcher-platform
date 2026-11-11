import hashlib
import io
import os

import pytest

from src.adapters.envelope_cipher import EnvelopeCipher
from src.application.ports import DecryptionError, KeyUnavailable

CHUNK = 64
MARCADOR = b"MARCADOR-SINTETICO-F28-" + os.urandom(8).hex().encode()


class _Kek:
    def __init__(self, kek: bytes | None):
        self._kek = kek

    def kek(self) -> bytes:
        if self._kek is None:
            raise KeyUnavailable("sin KEK")
        return self._kek


def _cipher(kek: bytes | None = ...) -> EnvelopeCipher:
    kek = os.urandom(32) if kek is ... else kek
    return EnvelopeCipher(_Kek(kek), chunk_size=CHUNK)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seal(cipher: EnvelopeCipher, data: bytes) -> bytes:
    return b"".join(cipher.encrypt(io.BytesIO(data), _sha(data)))


def _open(cipher: EnvelopeCipher, blob: bytes, sha: str) -> bytes:
    return b"".join(cipher.decrypt(io.BytesIO(blob), sha))


@pytest.mark.parametrize(
    "size",
    [0, 1, CHUNK - 1, CHUNK, CHUNK + 1, 2 * CHUNK, 3 * CHUNK + 5, 10 * CHUNK],
)
def test_ida_y_vuelta_aes_gcm(size):
    data = os.urandom(size)
    cipher = _cipher()
    assert _open(cipher, _seal(cipher, data), _sha(data)) == data


def test_el_marcador_no_aparece_en_el_cifrado():
    data = b"x" * 10 + MARCADOR + b"y" * 200
    assert MARCADOR not in _seal(_cipher(), data)


def _posiciones(blob_len: int) -> dict[str, int]:
    h = EnvelopeCipher.HEADER_SIZE
    return {
        "magia": 0,
        "version": 4,
        "tamano_chunk": 5,
        "prefijo_nonce": 9,
        "dek_envuelta": h - 10,
        "cuerpo": h + 3,
        "etiqueta": blob_len - 1,
    }


@pytest.mark.parametrize(
    "zona", ["magia", "version", "tamano_chunk", "prefijo_nonce", "dek_envuelta", "cuerpo", "etiqueta"]
)
def test_chunk_alterado_falla_autenticacion(zona):
    data = os.urandom(3 * CHUNK + 7)
    cipher = _cipher()
    blob = bytearray(_seal(cipher, data))
    blob[_posiciones(len(blob))[zona]] ^= 0x01
    with pytest.raises(DecryptionError):
        _open(cipher, bytes(blob), _sha(data))


def test_cualquier_byte_alterado_falla():
    data = os.urandom(2 * CHUNK + 1)
    cipher = _cipher()
    blob = _seal(cipher, data)
    for i in range(len(blob)):
        alterado = bytearray(blob)
        alterado[i] ^= 0x80
        with pytest.raises(DecryptionError):
            _open(cipher, bytes(alterado), _sha(data))


def test_chunks_reordenados_o_truncados_fallan():
    data = os.urandom(4 * CHUNK)
    cipher = _cipher()
    blob = _seal(cipher, data)
    h, w = EnvelopeCipher.HEADER_SIZE, CHUNK + EnvelopeCipher.TAG_SIZE
    chunks = [blob[h + i * w : h + (i + 1) * w] for i in range(4)]
    assert b"".join(chunks) == blob[h:h + 4 * w]
    variantes = {
        "intercambiados": chunks[1] + chunks[0] + chunks[2] + chunks[3],
        "duplicado": chunks[0] + chunks[0] + chunks[2] + chunks[3],
        "sin_ultimo": b"".join(chunks[:3]),
        "sin_primero": b"".join(chunks[1:]),
        "sin_medio": chunks[0] + chunks[2] + chunks[3],
        "cola_cortada": b"".join(chunks)[:-1],
        "sin_cuerpo": b"",
    }
    for nombre, cuerpo in variantes.items():
        with pytest.raises(DecryptionError):
            _open(cipher, blob[:h] + cuerpo, _sha(data))


def test_flujo_truncado_en_cualquier_largo_falla():
    data = os.urandom(2 * CHUNK + 9)
    cipher = _cipher()
    blob = _seal(cipher, data)
    for n in range(len(blob)):
        with pytest.raises(DecryptionError):
            _open(cipher, blob[:n], _sha(data))


def test_nonce_no_se_repite():
    cipher = _cipher()
    bloque = os.urandom(CHUNK)
    data = bloque * 6
    h, w = EnvelopeCipher.HEADER_SIZE, CHUNK + EnvelopeCipher.TAG_SIZE
    a, b = _seal(cipher, data), _seal(cipher, data)
    cuerpos = [x[h + i * w : h + (i + 1) * w] for x in (a, b) for i in range(6)]
    assert len(set(cuerpos)) == 12
    assert a[:h] != b[:h]


def test_kek_distinta_falla():
    data = os.urandom(CHUNK + 3)
    blob = _seal(_cipher(), data)
    with pytest.raises(DecryptionError):
        _open(_cipher(), blob, _sha(data))


def test_falla_si_falta_kek():
    cipher = _cipher(None)
    data = b"abc"
    with pytest.raises(KeyUnavailable):
        _seal(cipher, data)
    with pytest.raises(KeyUnavailable):
        _open(cipher, b"\x00" * 200, _sha(data))


@pytest.mark.parametrize("largo", [0, 16, 31, 33, 64])
def test_kek_de_largo_invalido(largo):
    cipher = _cipher(os.urandom(largo))
    with pytest.raises(KeyUnavailable):
        _seal(cipher, b"abc")


def test_objeto_copiado_bajo_otra_clave_falla():
    data = os.urandom(CHUNK + 1)
    cipher = _cipher()
    blob = _seal(cipher, data)
    with pytest.raises(DecryptionError):
        _open(cipher, blob, _sha(data + b"otro"))


def test_el_tamano_de_chunk_por_defecto_es_4_mib():
    assert EnvelopeCipher(_Kek(os.urandom(32))).chunk_size == 4 * 1024 * 1024
