"""Clasificación de fallos del worker tipado (SUP-50, provisional)."""
from minio.error import S3Error
from urllib3.exceptions import HTTPError

from src.application.ports import KeyUnavailable

TRANSITORIOS = (
    TimeoutError, MemoryError, BlockingIOError, InterruptedError, PermissionError,
    ConnectionError, HTTPError, KeyUnavailable,
)


def es_transitorio(error: BaseException) -> bool:
    if isinstance(error, S3Error):
        return getattr(error.response, "status", 0) >= 500
    return isinstance(error, TRANSITORIOS)
