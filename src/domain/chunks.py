import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

_HEX = frozenset("0123456789abcdef")


class ChunkRejected(Exception):
    pass


class IntegrityMismatch(Exception):
    pass


class UploadNotFound(Exception):
    pass


class MissingChunks(Exception):
    def __init__(self, missing: list[int]) -> None:
        super().__init__(f"faltan los chunks {missing}")
        self.missing = missing


def _entero_positivo(valor: object) -> bool:
    # bool es subclase de int: sin excluirlo, True pasaría como 1.
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def normalizar_sha256(valor: object) -> str:
    texto = valor.lower() if isinstance(valor, str) else ""
    if len(texto) != 64 or not set(texto) <= _HEX:
        raise ValueError(f"sha256 inválido: {valor!r}")
    return texto


@dataclass(frozen=True)
class UploadManifest:
    sha256: str
    size: int
    chunk_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "sha256", normalizar_sha256(self.sha256))
        if not _entero_positivo(self.size):
            raise ValueError(f"size debe ser un entero positivo: {self.size!r}")
        if not _entero_positivo(self.chunk_size):
            raise ValueError(f"chunk_size debe ser un entero positivo: {self.chunk_size!r}")

    @property
    def chunk_count(self) -> int:
        return -(-self.size // self.chunk_size)

    def expected_size(self, index: int) -> int:
        if not 0 <= index < self.chunk_count:
            raise ChunkRejected(f"índice fuera de rango: {index}")
        return min(self.chunk_size, self.size - index * self.chunk_size)

    def to_dict(self) -> dict:
        return {"sha256": self.sha256, "size": self.size, "chunk_size": self.chunk_size}

    @classmethod
    def from_dict(cls, data: dict) -> "UploadManifest":
        return cls(data["sha256"], data["size"], data["chunk_size"])


def verify_chunk(manifest: UploadManifest, index: int, data: bytes, sha256: str) -> None:
    if not isinstance(index, int) or isinstance(index, bool):
        raise ChunkRejected(f"índice inválido: {index!r}")
    esperado = manifest.expected_size(index)
    if len(data) != esperado:
        raise ChunkRejected(f"el chunk {index} mide {len(data)} bytes; se esperaban {esperado}")
    if hashlib.sha256(data).hexdigest() != str(sha256).lower():
        raise ChunkRejected(f"el sha256 del chunk {index} no coincide")


def missing_chunks(manifest: UploadManifest, received: Iterable[int]) -> list[int]:
    return sorted(set(range(manifest.chunk_count)) - set(received))
