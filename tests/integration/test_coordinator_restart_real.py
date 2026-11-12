"""Prueba de integracion: una instancia nueva del coordinador ve el mismo estado (F-35).

Simula el reinicio con dos clientes fakeredis DISTINTOS conectados al mismo
FakeServer (misma "base de datos"), igual que dos procesos reales se
reconectarian al mismo Redis. No reimplementa crear_app ni las rutas.
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.coordinator import conexion
import src.coordinator.main as main


def _crear_cliente(server, monkeypatch):
    """Simula "un coordinador nuevo": conexion propia contra el mismo FakeServer."""
    r = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", r)
    return TestClient(main.app), r


@pytest.mark.integration
class TestCoordinatorRestartReal:
    def test_coordinator_restart_real_conserva_subtareas(self, monkeypatch, sin_autorizacion):
        server = fakeredis.FakeServer()
        client1, _r1 = _crear_cliente(server, monkeypatch)

        creado = client1.post("/cases", json={
            "subtasks": [
                {"task_type": "auto", "file_path": "videos/a.mp4"},
                {"task_type": "auto", "file_path": "videos/b.mp4"},
            ],
        }).json()
        case_id = creado["case_id"]
        antes = client1.get(f"/cases/{case_id}").json()
        ids_antes = {s["subtask_id"]: s["status"] for s in antes["subtasks"]}
        assert len(ids_antes) == 2

        # "Reinicio": conexion nueva (otro cliente fakeredis) contra el mismo FakeServer.
        client2, _r2 = _crear_cliente(server, monkeypatch)
        despues = client2.get(f"/cases/{case_id}").json()
        ids_despues = {s["subtask_id"]: s["status"] for s in despues["subtasks"]}

        assert ids_despues == ids_antes
        assert despues["case"]["status"] == antes["case"]["status"]

        # La instancia nueva sigue operando con normalidad: puede reportar.
        sid = next(iter(ids_despues))
        reporte = client2.post("/subtasks/report", json={
            "subtask_id": sid, "case_id": case_id, "status": "completed",
            "worker_id": "w1", "host": "h1", "outputs": [f"out/{sid}.mp4"],
        })
        assert reporte.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
