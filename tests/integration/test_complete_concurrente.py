import hashlib
import os
import threading

import pytest

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.domain.chunks import MissingChunks, UploadNotFound
from tests.dobles import FakeObjectStore

pytestmark = pytest.mark.integration

RONDAS = 100
CHUNK = 4096


def test_dos_complete_simultaneos_solo_fallan_con_errores_de_dominio(tmp_path):
    staging = DiskChunkStaging(tmp_path / "staging")
    caso = ChunkedUpload(staging, FakeObjectStore(), max_chunk_size=CHUNK)
    datos = os.urandom(64 * CHUNK)
    inesperados = []

    def completar(upload_id, barrera):
        barrera.wait()
        try:
            caso.complete(upload_id)
        except (UploadNotFound, MissingChunks):
            pass
        except Exception as error:  # noqa: BLE001 — se reporta cualquier otro fallo (sería un 500)
            inesperados.append(repr(error))

    for _ in range(RONDAS):
        upload_id, cantidad = caso.start(hashlib.sha256(datos).hexdigest(), len(datos), CHUNK)
        for i in range(cantidad):
            parte = datos[i * CHUNK:(i + 1) * CHUNK]
            caso.receive(upload_id, i, parte, hashlib.sha256(parte).hexdigest())
        barrera = threading.Barrier(2)
        hilos = [threading.Thread(target=completar, args=(upload_id, barrera)) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

    assert inesperados == []
    assert list((tmp_path / "staging").iterdir()) == []
