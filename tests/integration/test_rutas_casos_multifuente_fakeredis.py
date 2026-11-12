"""Prueba de integracion: POST /cases con fuentes, via fakeredis (F-01).

Verifica que el camino nuevo deja el caso consultable por GET /cases/{id}
y /report SIN modificar esos endpoints.
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.coordinator import conexion, rutas_casos
import src.coordinator.main as main


class _SubidasFalsas:
    def __init__(self, almacenadas):
        self._almacenadas = set(almacenadas)

    def already_stored(self, sha256):
        return sha256 in self._almacenadas


@pytest.fixture
def fake(monkeypatch):
    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", r)
    return r


@pytest.fixture
def client(fake, sin_autorizacion):
    subidas = _SubidasFalsas({"sha-texto", "sha-imagen", "sha-audio", "sha-video"})
    main.app.dependency_overrides[rutas_casos._obtener_subidas_opcional] = lambda: subidas
    yield TestClient(main.app)
    main.app.dependency_overrides.pop(rutas_casos._obtener_subidas_opcional, None)


@pytest.mark.integration
class TestCasoMultifuenteAPI:
    def test_caso_multifuente_con_fakeredis_queda_consultable(self, client):
        cuerpo = {
            "sources": [
                {"sha256": "sha-texto", "name": "nota.txt"},
                {"sha256": "sha-imagen", "name": "foto.jpg"},
                {"sha256": "sha-audio", "name": "voz.mp3"},
                {"sha256": "sha-video", "name": "clip.mp4"},
            ],
            "priority": "normal",
        }
        respuesta = client.post("/cases", json=cuerpo)
        assert respuesta.status_code == 201
        datos = respuesta.json()
        case_id = datos["case_id"]
        assert datos["status"] == "queued"
        assert datos["total_subtasks"] == 5

        # GET /cases/{id} y /report son codigo existente, sin modificar.
        obtenido = client.get(f"/cases/{case_id}")
        assert obtenido.status_code == 200
        cuerpo_obtenido = obtenido.json()
        assert cuerpo_obtenido["case"]["status"] == "queued"
        assert len(cuerpo_obtenido["subtasks"]) == 5

        reporte = client.get(f"/cases/{case_id}/report")
        assert reporte.status_code == 200
        assert reporte.json()["totals"]["total"] == 5

    def test_fuente_sin_subir_responde_422_en_la_api(self, client):
        cuerpo = {
            "sources": [
                {"sha256": "sha-texto", "name": "nota.txt"},
                {"sha256": "sha-no-subida", "name": "otra.jpg"},
            ],
        }
        respuesta = client.post("/cases", json=cuerpo)
        assert respuesta.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
