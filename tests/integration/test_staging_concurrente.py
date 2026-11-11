import hashlib
import threading

import pytest

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.domain.chunks import UploadNotFound
from tests.dobles import FakeObjectStore

pytestmark = pytest.mark.integration

RONDAS = 200


def test_chunks_concurrentes_con_discard_no_dejan_carpetas(tmp_path):
    staging = DiskChunkStaging(tmp_path / "staging")
    caso = ChunkedUpload(staging, FakeObjectStore(), max_chunk_size=64)
    datos = b"a" * 100
    chunk = datos[:50]
    for _ in range(RONDAS):
        upload_id, _ = caso.start(hashlib.sha256(datos).hexdigest(), len(datos), 50)
        descarte = threading.Thread(target=staging.discard, args=(upload_id,))
        descarte.start()
        try:
            caso.receive(upload_id, 0, chunk, hashlib.sha256(chunk).hexdigest())
        except UploadNotFound:
            pass
        descarte.join()
    assert list((tmp_path / "staging").iterdir()) == []
