import asyncio
import hashlib
import threading

import httpx
from fastapi import FastAPI

from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeChunkStaging, FakeObjectStore

DATOS = b"abcdefgh"
ESPERA_MAXIMA = 5


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def app_con(staging, al_atender_otra):
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(staging, FakeObjectStore(), max_chunk_size=64)
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas

    @app.get("/otra")
    async def otra():
        al_atender_otra()
        return {"ok": True}

    return app, subidas


def test_subida_lenta_no_bloquea_otra_peticion():
    cuerpo_abierto = asyncio.Event()
    otra_atendida = asyncio.Event()
    app, subidas = app_con(FakeChunkStaging(), otra_atendida.set)
    upload_id, _ = subidas.start(sha(DATOS), len(DATOS), 8)

    async def cuerpo_lento():
        yield DATOS[:4]
        cuerpo_abierto.set()
        await otra_atendida.wait()
        yield DATOS[4:]

    async def escenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as cliente:
            subida = asyncio.create_task(cliente.put(
                f"/uploads/{upload_id}/chunks/0", content=cuerpo_lento(), headers={"X-Chunk-SHA256": sha(DATOS)}))
            await asyncio.wait_for(cuerpo_abierto.wait(), ESPERA_MAXIMA)
            otra = await cliente.get("/otra")
            assert not subida.done()
            return otra.status_code, (await asyncio.wait_for(subida, ESPERA_MAXIMA)).status_code

    assert asyncio.run(escenario()) == (200, 204)


class StagingConManifiestoLento(FakeChunkStaging):
    """`load_manifest` se queda esperando a que otra petición se atienda, como un disco lento."""

    def __init__(self):
        super().__init__()
        self.lento = False
        self.esperando = threading.Event()
        self.otra_atendida = threading.Event()
        self.vio_la_otra = []

    def load_manifest(self, upload_id):
        if self.lento and not self.vio_la_otra:
            self.esperando.set()
            self.vio_la_otra.append(self.otra_atendida.wait(ESPERA_MAXIMA))
        return super().load_manifest(upload_id)


def test_manifiesto_lento_no_bloquea_otra_peticion():
    staging = StagingConManifiestoLento()
    app, subidas = app_con(staging, staging.otra_atendida.set)
    upload_id, _ = subidas.start(sha(DATOS), len(DATOS), 8)
    staging.lento = True

    async def escenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as cliente:
            subida = asyncio.create_task(cliente.put(
                f"/uploads/{upload_id}/chunks/0", content=DATOS, headers={"X-Chunk-SHA256": sha(DATOS)}))
            await asyncio.to_thread(staging.esperando.wait, ESPERA_MAXIMA)
            otra = await cliente.get("/otra")
            return otra.status_code, (await subida).status_code

    assert asyncio.run(escenario()) == (200, 204)
    assert staging.vio_la_otra == [True]
