"""Prueba de aceptacion: cliente de carga sube 4 fuentes y crea un caso heterogeneo (F-01).

Ejercita el flujo real: POST /uploads -> PUT chunks -> complete -> POST /cases -> GET /cases/{id}.
"""
import hashlib

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.application.chunked_upload import ChunkedUpload
from src.coordinator import conexion, rutas_archivos
import src.coordinator.main as main
from tests.dobles import FakeChunkStaging, FakeObjectStore


@pytest.fixture
def fake(monkeypatch):
    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", r)
    return r


@pytest.fixture
def client(fake, sin_autorizacion):
    # Configuracion real (no dependency_overrides): ejercita el mismo camino
    # que produccion para /uploads y para POST /cases con "sources".
    rutas_archivos.configurar(ChunkedUpload(FakeChunkStaging(), FakeObjectStore(), max_chunk_size=1 << 20))
    yield TestClient(main.app)
    rutas_archivos.configurar(None)


def _subir(client, contenido, nombre):
    sha256 = hashlib.sha256(contenido).hexdigest()
    inicio = client.post("/uploads", json={"sha256": sha256, "size": len(contenido), "chunk_size": len(contenido)})
    assert inicio.status_code == 201
    upload_id = inicio.json()["upload_id"]
    chunk_sha = hashlib.sha256(contenido).hexdigest()
    puesto = client.put(
        f"/uploads/{upload_id}/chunks/0",
        content=contenido,
        headers={"X-Chunk-Sha256": chunk_sha},
    )
    assert puesto.status_code == 204
    completado = client.post(f"/uploads/{upload_id}/complete")
    assert completado.status_code == 201
    assert completado.json()["sha256"] == sha256
    return sha256, nombre


@pytest.mark.acceptance
class TestCasoHeterogeneoClienteDeCarga:
    def test_caso_heterogeneo_cliente_de_carga(self, client):
        fuentes = [
            _subir(client, b"hola mundo, nota de analista", "conversacion.txt"),
            _subir(client, b"\xff\xd8\xff\xe0contenido-jpg-de-prueba", "evidencia.jpg"),
            _subir(client, b"contenido-mp3-de-prueba", "nota_de_voz.mp3"),
            _subir(client, b"contenido-mp4-de-prueba", "clip_relevante.mp4"),
        ]

        respuesta = client.post("/cases", json={
            "sources": [{"sha256": sha, "name": nombre} for sha, nombre in fuentes],
            "priority": "high",
        })
        assert respuesta.status_code == 201
        datos = respuesta.json()
        assert datos["status"] == "queued"
        assert datos["total_subtasks"] == 5  # 4 fuentes, el video expande a audio+imagen

        obtenido = client.get(f"/cases/{datos['case_id']}").json()
        assert obtenido["case"]["status"] == "queued"
        sha256s_en_caso = {s["source_sha256"] for s in obtenido["subtasks"]}
        assert sha256s_en_caso == {sha for sha, _ in fuentes}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
