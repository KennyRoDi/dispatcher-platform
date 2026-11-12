"""QA F-15: Worker.start() debe pasar su resource_reader al Heartbeat (el mutante sin el argumento sobrevivía)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_worker_node import make_worker  # noqa: E402
from dobles import FakeResourceReader  # noqa: E402

from src.domain.resources import ResourceUsage  # noqa: E402


def test_worker_start_publica_memoria_de_cgroup(tmp_path):
    worker, redis_client, *_ = make_worker(tmp_path)
    worker.resource_reader = FakeResourceReader(ResourceUsage("w1", memory_current=300, memory_max=1000))
    worker.heartbeat_enabled = True
    worker.start()
    try:
        time.sleep(0.1)
        assert worker.heartbeat.resource_reader is worker.resource_reader
        datos = redis_client.hgetall(worker.heartbeat.key)
        assert datos.get("cgroup_memory_current") == "300"
        assert datos.get("cgroup_memory_max") == "1000"
    finally:
        worker.stop(timeout=2)
