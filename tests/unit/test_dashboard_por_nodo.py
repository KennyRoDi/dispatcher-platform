import threading

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from dashboard.nodos import resumen_por_nodo
from src.coordinator import conexion
from src.domain.resources import ResourceUsage
from src.workers.config import Settings
from src.workers.heartbeat import Heartbeat, WorkerStats
from tests.dobles import FakeResourceReader

GIB = 1 << 30


def heartbeat(resource_reader=None):
    redis = fakeredis.FakeRedis(decode_responses=True)
    settings = Settings.from_env({"WORKER_ID": "w1", "NODE_NAME": "nodo-a", "NODE_IP": "10.0.0.1"})
    latido = Heartbeat(settings, redis, WorkerStats(), threading.Event(), ffmpeg_info=("x", "none"),
                       gpu_info={}, resource_reader=resource_reader)
    latido.beat()
    return redis.hgetall("worker:w1")


def test_heartbeat_incluye_memoria_de_cgroup():
    datos = heartbeat(FakeResourceReader(ResourceUsage("w1", memory_current=GIB, memory_max=4 * GIB)))
    assert (datos["cgroup_memory_current"], datos["cgroup_memory_max"]) == (str(GIB), str(4 * GIB))


def test_sin_lector_no_publica_memoria_de_cgroup():
    datos = heartbeat()
    assert "cgroup_memory_current" not in datos and datos["worker_id"] == "w1"


class LectorQueFalla:
    def read(self):
        raise OSError("memory.current no existe")


def test_lector_que_falla_no_rompe_el_heartbeat():
    datos = heartbeat(LectorQueFalla())
    assert "cgroup_memory_current" not in datos and datos["host"] == "nodo-a"


def test_get_workers_devuelve_la_memoria_de_cgroup(monkeypatch, sin_autorizacion):
    redis = fakeredis.FakeRedis(decode_responses=True)
    redis.sadd("workers:registry", "w1")
    redis.hset("worker:w1", mapping={"worker_id": "w1", "host": "nodo-a", "cgroup_memory_current": GIB,
                                     "cgroup_memory_max": 4 * GIB})
    monkeypatch.setattr(conexion, "redis_client", redis)
    trabajador, = TestClient(main.app).get("/workers").json()
    assert (trabajador["cgroup_memory_current"], trabajador["cgroup_memory_max"]) == (str(GIB), str(4 * GIB))


def trabajador(wid, host, alive=True, **campos):
    return {"worker_id": wid, "host": host, "alive": alive, **campos}


def test_agrupa_por_nodo_y_resume_recursos():
    nodos = resumen_por_nodo([
        trabajador("w1", "nodo-a", cpu_percent="40", mem_percent="50", cgroup_memory_current=str(GIB),
                   cgroup_memory_max=str(2 * GIB), active_subtasks="2", gpu="none"),
        trabajador("w2", "nodo-a", cpu_percent="60", mem_percent="70", cgroup_memory_current=str(GIB),
                   cgroup_memory_max=str(2 * GIB), active_subtasks="1", gpu="RTX 3060", gpu_percent="35"),
        trabajador("w3", "nodo-b", cpu_percent="10", mem_percent="20", active_subtasks="0"),
    ])
    a, b = nodos
    assert a["nodo"] == "nodo-a" and b["nodo"] == "nodo-b"
    assert (a["workers_vivos"], a["workers"], a["activas"]) == (2, 2, 3)
    assert (a["cpu_percent"], a["mem_percent"]) == (50.0, 60.0)
    assert (a["cgroup_memory_current"], a["cgroup_memory_max"], a["cgroup_percent"]) == (2 * GIB, 4 * GIB, 50.0)
    assert (a["gpu"], a["gpu_percent"]) == ("RTX 3060", 35.0)
    assert (b["cgroup_memory_max"], b["cgroup_percent"], b["gpu"]) == (None, None, None)


def test_los_workers_caidos_cuentan_pero_no_promedian():
    nodo, = resumen_por_nodo([
        trabajador("w1", "nodo-a", cpu_percent="80", mem_percent="40"),
        trabajador("w2", "nodo-a", alive=False, cpu_percent="0", mem_percent="0"),
    ])
    assert (nodo["workers_vivos"], nodo["workers"], nodo["cpu_percent"], nodo["mem_percent"]) == (1, 2, 80.0, 40.0)


@pytest.mark.parametrize("workers", [[], None])
def test_sin_workers_no_hay_nodos(workers):
    assert resumen_por_nodo(workers) == []


def test_valores_faltantes_o_invalidos_no_rompen():
    nodo, = resumen_por_nodo([trabajador("w1", None, cpu_percent="x", cgroup_memory_max="", active_subtasks=None)])
    assert nodo["nodo"] == "desconocido"
    assert (nodo["cpu_percent"], nodo["cgroup_memory_max"], nodo["activas"]) == (None, None, 0)
