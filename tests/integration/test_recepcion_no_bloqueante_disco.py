import hashlib
import threading
import time

import pytest
import requests
import uvicorn
from fastapi import FastAPI

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeObjectStore

pytestmark = pytest.mark.integration
TAMANO = 4 << 20
PARTES = 16


class StagingDiscoLento(DiskChunkStaging):
    """DiskChunkStaging real cuyo disco tarda en leer el manifiesto (volumen de red)."""

    def load_manifest(self, upload_id: str) -> dict:
        time.sleep(1.0)
        return super().load_manifest(upload_id)


@pytest.fixture
def servidor(tmp_path):
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(StagingDiscoLento(tmp_path), FakeObjectStore())
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    hilo = threading.Thread(target=srv.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not srv.started:
        assert time.monotonic() < limite, "uvicorn no arrancó"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{srv.servers[0].sockets[0].getsockname()[1]}", subidas, tmp_path
    srv.should_exit = True
    hilo.join(timeout=10)


def test_disco_real_lento_no_bloquea_peticiones_ligeras(servidor):
    url, subidas, raiz = servidor
    datos = bytes(range(256)) * (TAMANO // 256)
    sha = hashlib.sha256(datos).hexdigest()
    upload_id, _ = subidas.start(sha, TAMANO, TAMANO)
    parte = TAMANO // PARTES
    fin = []

    def cuerpo_lento():
        for i in range(PARTES):
            time.sleep(0.05)
            yield datos[i * parte:(i + 1) * parte]

    def subir():
        r = requests.put(f"{url}/uploads/{upload_id}/chunks/0", data=cuerpo_lento(),
                         headers={"X-Chunk-SHA256": sha}, timeout=60)
        fin.append((time.monotonic(), r.status_code))

    hilo = threading.Thread(target=subir)
    hilo.start()
    time.sleep(0.2)  # el PUT está leyendo el manifiesto lento
    latencias = []
    for _ in range(10):
        inicio = time.monotonic()
        assert requests.get(f"{url}/ping", timeout=5).status_code == 200
        latencias.append((time.monotonic(), time.monotonic() - inicio))
    hilo.join()

    (terminada, codigo), = fin
    assert codigo == 204
    assert all(t < terminada for t, _ in latencias)
    assert max(l for _, l in latencias) < 0.5
    assert subidas.status(upload_id) == ([0], [])
