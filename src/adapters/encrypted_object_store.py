import io
from collections.abc import Iterator
from itertools import chain
from typing import BinaryIO, Protocol

from src.application.ports import ObjectStore


class _Cipher(Protocol):
    chunk_size: int
    TAG_SIZE: int
    HEADER_SIZE: int

    def encrypt(self, stream: BinaryIO, sha256_hex: str) -> Iterator[bytes]: ...
    def decrypt(self, stream: BinaryIO, sha256_hex: str) -> Iterator[bytes]: ...


class EncryptedObjectStore:
    """Decorador de `ObjectStore` que cifra en `put` y descifra en `open` (F-28, AD-34).

    La clave del objeto sigue siendo el SHA-256 del claro (AD-11), por eso `exists` se delega.
    """

    def __init__(self, inner: ObjectStore, cipher: _Cipher):
        self._inner = inner
        self._cipher = cipher

    def exists(self, sha256: str) -> bool:
        return self._inner.exists(sha256)

    def put(self, sha256: str, content: BinaryIO, size: int) -> None:
        # Se obtiene la cabecera antes de tocar el interno: sin KEK no se escribe nada.
        sealed = self._cipher.encrypt(content, sha256)
        header = next(sealed)
        self._inner.put(sha256, _IteratorReader(chain([header], sealed)), self._sealed_size(size))

    def open(self, sha256: str) -> BinaryIO:
        source = self._inner.open(sha256)
        try:
            opened = self._cipher.decrypt(source, sha256)
            first = next(opened)
        except BaseException:
            source.close()
            raise
        return _IteratorReader(chain([first], opened), source)

    def _sealed_size(self, size: int) -> int:
        chunk_size = self._cipher.chunk_size
        chunks = max(1, -(-size // chunk_size))
        return self._cipher.HEADER_SIZE + size + chunks * self._cipher.TAG_SIZE


class _IteratorReader(io.RawIOBase):
    def __init__(self, parts: Iterator[bytes], source: BinaryIO | None = None):
        self._parts = iter(parts)
        self._source = source
        self._current = memoryview(b"")
        self._failure: Exception | None = None

    def readable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        if size is None or size < 0:
            return b"".join(self._drain())
        buffer = bytearray(size)
        return bytes(buffer[: self.readinto(buffer)])

    def readinto(self, buffer) -> int:
        self._check_usable()
        target = memoryview(buffer).cast("B")
        filled = 0
        while filled < len(target):
            if not self._current and not self._advance():
                break
            taken = min(len(target) - filled, len(self._current))
            target[filled : filled + taken] = self._current[:taken]
            self._current = self._current[taken:]
            filled += taken
        return filled

    def close(self) -> None:
        if self.closed:
            return
        try:
            if self._source is not None:
                self._source.close()
        finally:
            super().close()

    def _drain(self) -> Iterator[bytes]:
        self._check_usable()
        yield bytes(self._current)
        self._current = memoryview(b"")
        while self._advance():
            yield bytes(self._current)
            self._current = memoryview(b"")

    def _advance(self) -> bool:
        try:
            part = next(self._parts, None)
        except Exception as error:
            self._failure = error
            raise
        if part is None:
            return False
        self._current = memoryview(part)
        return True

    def _check_usable(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        if self._failure is not None:
            raise self._failure
