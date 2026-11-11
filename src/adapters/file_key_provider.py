import base64
import binascii
import os
import stat
from collections.abc import Callable, Mapping
from pathlib import Path

from src.application.ports import KeyUnavailable

KEK_SIZE = 32
PERMITTED_MODES = (0o400, 0o600)


class FileKeyProvider:
    """KEK de 32 bytes desde un archivo `0400`/`0600` o, solo en desarrollo, de base64 (AD-16, SUP-30).

    La fuente se guarda como función para que ni `repr` ni `vars` muestren la llave.
    """

    def __init__(self, path: str | Path | None = None, *, _source: Callable[[], bytes | None] | None = None):
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
        kek = self._source()
        if kek is not None and len(kek) == KEK_SIZE:
            return kek
        # Sin la variable, la llave de largo incorrecto no queda en los locales de la traza.
        del kek
        raise KeyUnavailable(f"la KEK debe ser de {KEK_SIZE} bytes y estar bien codificada")


def _missing() -> bytes:
    raise KeyUnavailable("falta KEK_FILE o KEK")


def _decode_base64(encoded: str) -> bytes | None:
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None


def _read_file(path: str | Path | None) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise KeyUnavailable("KEK_FILE debe ser un archivo regular")
            if stat.S_IMODE(info.st_mode) not in PERMITTED_MODES:
                raise KeyUnavailable("KEK_FILE debe tener permisos 0400 o 0600")
            return os.read(descriptor, KEK_SIZE + 1)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, TypeError):
        raise KeyUnavailable("KEK_FILE no se pudo leer") from None
