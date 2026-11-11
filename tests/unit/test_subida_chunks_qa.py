import asyncio
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeChunkStaging, FakeObjectStore

CHUNK = 4
MAXIMO = 64
MIB = 1 << 20


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def app_con(staging):
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(staging, FakeObjectStore(), max_chunk_size=MAXIMO)
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas
    return app, subidas


def put_por_asgi(app, ruta, piezas, cabeceras):
    """Llama a la app ASGI sin red y cuenta cuántos bytes del cuerpo llegó a pedir el servidor.

    TestClient lee el cuerpo completo antes de entregarlo, así que no sirve para medir si el
    servidor deja de leer a tiempo.
    """
    pedidos = 0
    estado = {}

    async def receive():
        nonlocal pedidos
        if pedidos >= piezas:
            return {"type": "http.disconnect"}
        pedidos += 1
        return {"type": "http.request", "body": b"x" * MIB, "more_body": pedidos < piezas}

    async def send(mensaje):
        if mensaje["type"] == "http.response.start":
            estado["codigo"] = mensaje["status"]

    alcance = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "PUT",
        "scheme": "http", "path": ruta, "raw_path": ruta.encode(), "root_path": "", "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in cabeceras.items()],
        "client": ("127.0.0.1", 1), "server": ("testserver", 80),
    }
    asyncio.run(app(alcance, receive, send))
    return estado.get("codigo"), pedidos * MIB


def test_put_deja_de_leer_un_cuerpo_mayor_que_el_chunk_esperado():
    # [B.5 M3]: el servidor nunca mantiene en memoria más de un chunk por petición.
    app, subidas = app_con(FakeChunkStaging())
    upload_id, _ = subidas.start(sha(b"abcdefghij"), 10, CHUNK)
    piezas = 64
    codigo, leidos = put_por_asgi(
        app, f"/uploads/{upload_id}/chunks/0", piezas,
        {"X-Chunk-SHA256": sha(b"abcd"), "Content-Length": str(piezas * MIB)},
    )
    assert codigo in (413, 422)
    assert leidos <= MIB, f"el servidor leyó {leidos >> 20} MiB para un chunk de {CHUNK} bytes"


def test_iniciar_rechaza_una_subida_con_cantidad_de_chunks_inmanejable():
    # Con size=2**60 y chunk_size=1, GET /uploads/{id} y complete materializan 2**60 índices
    # (set(range(chunk_count))) y agotan la memoria; la 409 con `missing` tampoco es representable.
    app, _ = app_con(FakeChunkStaging())
    respuesta = TestClient(app).post("/uploads", json={"sha256": "a" * 64, "size": 1 << 60, "chunk_size": 1})
    assert respuesta.status_code == 422


class StagingConCompleteConcurrente(DiskChunkStaging):
    """Simula que otro `complete` termina y descarta la subida mientras este lee los chunks."""

    def open_chunk(self, upload_id, index):
        if index == 1 and not getattr(self, "_descartada", False):
            self._descartada = True
            self.discard(upload_id)
        return super().open_chunk(upload_id, index)


def test_complete_concurrente_con_otro_complete_no_responde_500(tmp_path):
    app, subidas = app_con(StagingConCompleteConcurrente(tmp_path))
    datos = b"abcdefgh"
    upload_id, _ = subidas.start(sha(datos), len(datos), CHUNK)
    for indice in range(2):
        parte = datos[indice * CHUNK:(indice + 1) * CHUNK]
        subidas.receive(upload_id, indice, parte, sha(parte))
    respuesta = TestClient(app, raise_server_exceptions=False).post(f"/uploads/{upload_id}/complete")
    assert respuesta.status_code in (201, 404, 409), respuesta.text


def test_staging_en_disco_no_guarda_chunk_en_carpeta_sin_manifiesto(tmp_path):
    staging = DiskChunkStaging(tmp_path)
    (tmp_path / "u1").mkdir()
    with pytest.raises(KeyError):
        staging.put_chunk("u1", 0, b"abc")
    assert list((tmp_path / "u1").iterdir()) == []
