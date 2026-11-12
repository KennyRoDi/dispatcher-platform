import hashlib
import threading
import time

import pytest
import requests
import uvicorn
from fastapi import FastAPI

from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeChunkStaging, FakeObjectStore

pytestmark = pytest.mark.integration

MIB = 1 << 20
TAMANO = 16 * MIB
PARTES = 32
PETICIONES = 20


@pytest.fixture
def servidor():
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(FakeChunkStaging(), FakeObjectStore())
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas

    @app.get("/ping")
    def ping():
        return {"ok": True}

    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        assert time.monotonic() < limite, "uvicorn no arrancó"
        time.sleep(0.05)
    puerto = servidor.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{puerto}", subidas
    servidor.should_exit = True
    hilo.join(timeout=10)


def test_la_api_responde_durante_una_subida_lenta_de_16_mib(servidor):
    url, subidas = servidor
    datos = bytes(range(256)) * (TAMANO // 256)
    upload_id, _ = subidas.start(hashlib.sha256(datos).hexdigest(), TAMANO, TAMANO)
    parte = TAMANO // PARTES
    fin_subida = []

    def cuerpo_lento():
        for i in range(PARTES):
            time.sleep(0.05)
            yield datos[i * parte:(i + 1) * parte]

    def subir():
        respuesta = requests.put(f"{url}/uploads/{upload_id}/chunks/0", data=cuerpo_lento(),
                                 headers={"X-Chunk-SHA256": hashlib.sha256(datos).hexdigest()}, timeout=60)
        fin_subida.append((time.monotonic(), respuesta.status_code))

    hilo = threading.Thread(target=subir)
    hilo.start()
    time.sleep(0.2)
    respuestas = []
    for _ in range(PETICIONES):
        inicio = time.monotonic()
        codigo = requests.get(f"{url}/ping", timeout=5).status_code
        respuestas.append((time.monotonic(), codigo, time.monotonic() - inicio))
    hilo.join()

    (terminada, codigo_subida), = fin_subida
    assert codigo_subida == 204
    assert all(codigo == 200 for _, codigo, _ in respuestas)
    assert all(instante < terminada for instante, _, _ in respuestas)
    assert max(latencia for _, _, latencia in respuestas) < 0.5
