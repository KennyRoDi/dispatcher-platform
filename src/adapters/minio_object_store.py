import io
from typing import BinaryIO

from minio.error import S3Error

_AUSENTE = {"NoSuchKey", "NoSuchObject"}


class MinioObjectStore:
    """`ObjectStore` sobre MinIO: la clave del objeto es el SHA-256 de su contenido (AD-11)."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def exists(self, sha256: str) -> bool:
        try:
            self._client.stat_object(self._bucket, _clave(sha256))
        except S3Error as error:
            if error.code in _AUSENTE:
                return False
            raise
        return True

    def put(self, sha256: str, content: BinaryIO, size: int) -> None:
        # Mismo contenido, misma clave: si ya existe no se vuelve a subir.
        if self.exists(sha256):
            return
        self._client.put_object(self._bucket, sha256, content, length=size)

    def open(self, sha256: str) -> BinaryIO:
        try:
            respuesta = self._client.get_object(self._bucket, _clave(sha256))
        except S3Error as error:
            if error.code in _AUSENTE:
                raise KeyError(sha256) from None
            raise
        return io.BufferedReader(_Respuesta(respuesta))


def _clave(sha256: str) -> str:
    if not sha256 or "/" in sha256 or sha256 in {".", ".."}:
        raise ValueError(f"clave de objeto inválida: {sha256!r}")
    return sha256


class _Respuesta(io.RawIOBase):
    def __init__(self, respuesta) -> None:
        self._respuesta = respuesta

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        datos = self._respuesta.read(len(buffer))
        buffer[:len(datos)] = datos
        return len(datos)

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._respuesta.close()
        finally:
            self._respuesta.release_conn()
            super().close()
