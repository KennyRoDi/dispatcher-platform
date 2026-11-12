from unittest.mock import Mock

import pytest
import urllib3
from minio.error import S3Error

from src.adapters.parser_por_extension import ExtensionSinParser
from src.application.ports import DecryptionError, KeyUnavailable
from src.domain.chat_export import FormatoDeChatInvalido
from src.workers.fallos import es_transitorio
from src.workers.multimedia_processor import CorruptInputError, ProcessingError, ProcessingTimeoutError


def s3(estado):
    respuesta = Mock(status=estado)
    return S3Error(respuesta, "Error", "mensaje", "recurso", "req", "host")


@pytest.mark.parametrize("error", [
    TimeoutError(), MemoryError(), BlockingIOError(), InterruptedError(), PermissionError(),
    ConnectionError(), ConnectionResetError(), urllib3.exceptions.HTTPError("red"),
    urllib3.exceptions.MaxRetryError(None, "http://minio"), s3(503), KeyUnavailable("sin KEK"),
])
def test_transitorios(error):
    assert es_transitorio(error) is True


@pytest.mark.parametrize("error", [
    ValueError("ilegible"), FormatoDeChatInvalido("f", "mal"), ExtensionSinParser("csv"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "mal"), KeyError("sha"), DecryptionError("mal"),
    ProcessingError("ffmpeg"), CorruptInputError("roto"), ProcessingTimeoutError("lento"),
    s3(404), RuntimeError("desconocido"), OSError("disco"),
])
def test_permanentes(error):
    assert es_transitorio(error) is False


def test_clasificacion_de_fallos_separa_transitorios_y_permanentes():
    assert es_transitorio(TimeoutError()) and not es_transitorio(ValueError())
    assert not es_transitorio(Exception("lo desconocido es permanente"))
