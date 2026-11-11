import os
import struct
from itertools import count
from collections.abc import Iterator
from typing import BinaryIO, Protocol

# Tercero: cryptography (Apache-2.0 o BSD-3-Clause), https://github.com/pyca/cryptography
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.application.ports import DecryptionError, KeyUnavailable

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024
MAGIC = b"EVC1"
VERSION = 1
KEY_SIZE = 32
NONCE_SIZE = 12
PREFIX_SIZE = 4
TAG_SIZE = 16
PREFIX_START = 9
FIXED_HEADER = struct.Struct(">4sBI4s")


class _KeyProvider(Protocol):
    def kek(self) -> bytes: ...


class EnvelopeCipher:
    """Cifrado de sobre AES-256-GCM por chunks (AD-34).

    Cabecera: magia, versión, tamaño de chunk, prefijo de nonce y la DEK del
    objeto envuelta por la KEK con el SHA-256 del claro como AAD. Cada chunk lleva
    como AAD la cabecera fija, el SHA-256, su índice y la marca de último, y su
    nonce es prefijo aleatorio más contador, único por objeto.
    """

    TAG_SIZE = TAG_SIZE
    HEADER_SIZE = FIXED_HEADER.size + NONCE_SIZE + KEY_SIZE + TAG_SIZE

    def __init__(self, key_provider: _KeyProvider, chunk_size: int = DEFAULT_CHUNK_SIZE):
        if not 0 < chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size fuera de rango: {chunk_size}")
        self._keys = key_provider
        self.chunk_size = chunk_size

    def encrypt(self, stream: BinaryIO, sha256_hex: str) -> Iterator[bytes]:
        wrapper = self._kek_cipher()
        dek = os.urandom(KEY_SIZE)
        wrap_nonce = os.urandom(NONCE_SIZE)
        fixed = FIXED_HEADER.pack(MAGIC, VERSION, self.chunk_size, os.urandom(PREFIX_SIZE))
        wrapped = wrap_nonce + wrapper.encrypt(wrap_nonce, dek, sha256_hex.encode())
        yield fixed + wrapped
        yield from self._seal_chunks(stream, AESGCM(dek), fixed, sha256_hex)

    def decrypt(self, stream: BinaryIO, sha256_hex: str) -> Iterator[bytes]:
        wrapper = self._kek_cipher()
        header = _read_exact(stream, self.HEADER_SIZE)
        if len(header) < self.HEADER_SIZE:
            raise DecryptionError("cabecera truncada")
        fixed = header[: FIXED_HEADER.size]
        chunk_size = self._parse_fixed(fixed)
        wrapped = header[FIXED_HEADER.size :]
        try:
            dek = wrapper.decrypt(wrapped[:NONCE_SIZE], wrapped[NONCE_SIZE:], sha256_hex.encode())
        except InvalidTag as error:
            raise DecryptionError("llave del objeto no autentica") from error
        yield from self._open_chunks(stream, AESGCM(dek), fixed, sha256_hex, chunk_size)

    def _kek_cipher(self) -> AESGCM:
        kek = self._keys.kek()
        if len(kek) != KEY_SIZE:
            raise KeyUnavailable(f"la KEK debe tener {KEY_SIZE} bytes")
        return AESGCM(kek)

    @staticmethod
    def _parse_fixed(fixed: bytes) -> int:
        magic, version, chunk_size, _ = FIXED_HEADER.unpack(fixed)
        if magic != MAGIC or version != VERSION:
            raise DecryptionError("formato desconocido")
        if not 0 < chunk_size <= MAX_CHUNK_SIZE:
            raise DecryptionError("tamaño de chunk inválido")
        return chunk_size

    def _seal_chunks(
        self, stream: BinaryIO, aead: AESGCM, fixed: bytes, sha256_hex: str
    ) -> Iterator[bytes]:
        current = _read_exact(stream, self.chunk_size)
        for index in count():
            following = _read_exact(stream, self.chunk_size)
            last = not following
            nonce, aad = _chunk_context(fixed, sha256_hex, index, last)
            yield aead.encrypt(nonce, current, aad)
            if last:
                return
            current = following

    @staticmethod
    def _open_chunks(
        stream: BinaryIO, aead: AESGCM, fixed: bytes, sha256_hex: str, chunk_size: int
    ) -> Iterator[bytes]:
        width = chunk_size + TAG_SIZE
        current = _read_exact(stream, width)
        for index in count():
            following = _read_exact(stream, width)
            last = not following
            nonce, aad = _chunk_context(fixed, sha256_hex, index, last)
            try:
                yield aead.decrypt(nonce, current, aad)
            except InvalidTag as error:
                raise DecryptionError(f"chunk {index} no autentica") from error
            if last:
                return
            current = following


def _chunk_context(fixed: bytes, sha256_hex: str, index: int, last: bool) -> tuple[bytes, bytes]:
    nonce = fixed[PREFIX_START : PREFIX_START + PREFIX_SIZE] + index.to_bytes(8, "big")
    aad = fixed + sha256_hex.encode() + index.to_bytes(8, "big") + (b"\x01" if last else b"\x00")
    return nonce, aad


def count() -> Iterator[int]:
    index = 0
    while True:
        yield index
        index += 1


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    parts: list[bytes] = []
    remaining = size
    while remaining:
        part = stream.read(remaining)
        if not part:
            break
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)
