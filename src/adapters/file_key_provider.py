import base64
import binascii
import os
import stat
from collections.abc import Callable, Mapping
from pathlib import Path

from src.application.ports import KeyUnavailable

KEK_SIZE = 32


class FileKeyProvider:
    """KEK de 32 bytes desde un archivo `0400`/`0600` o, solo en desarrollo, de base64 (AD-16, SUP-30).

    La fuente se guarda como función para que ni `repr` ni `vars` muestren la llave.
    """

    def __init__(self, path: str | Path | None = None, *, _source: Callable[[], bytes] | None = None):
        self._source = _source or (lambda: _read_file(path))

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "FileKeyProvider":
        environ = os.environ if environ is None else environ
        path, encoded = environ.get("KEK_FILE", "").strip(), environ.get("KEK", "").strip()
        if path:
            return cls(path)
        if encoded:
            return cls(_source=lambda: _decode_base64(encoded))
        return cls(_source=_missing)

    def kek(self) -> bytes:
        return _checked(self._source())


def _missing() -> bytes:
    raise KeyUnavailable("falta KEK_FILE o KEK")


def _checked(kek: bytes) -> bytes:
    if len(kek) != KEK_SIZE:
        raise KeyUnavailable(f"la KEK debe tener {KEK_SIZE} bytes")
    return kek


def _decode_base64(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise KeyUnavailable("KEK no es base64 valido") from None


def _read_file(path: str | Path | None) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise KeyUnavailable("KEK_FILE debe ser un archivo regular")
            if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise KeyUnavailable("KEK_FILE no debe tener permisos para grupo ni otros")
            return handle.read(KEK_SIZE + 1)
    except (OSError, TypeError):
        raise KeyUnavailable("KEK_FILE no se pudo leer") from None
