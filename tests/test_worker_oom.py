import fakeredis

from dobles import FakeResourceReader
from fakes import FakeStorage, make_fake_processor

from src.domain.admission import FootprintTable
from src.domain.resources import ResourceUsage
from src.infrastructure.cgroup_resources import MemoryEvents
from src.workers.multimedia_processor import ProcessingError
from test_worker_node import make_worker, seed_subtask


class EventosOom:
    def __init__(self, valor=0):
        self.valor = valor

    def __call__(self):
        return MemoryEvents(oom_kill=self.valor)


def error_con_codigo(codigo):
    error = ProcessingError("FFmpeg terminó")
    error.exit_code = codigo
    return error


def preparar(tmp_path, codigo, sube_oom, **campos):
    eventos = EventosOom()

    def proceso(llamada):
        if sube_oom:
            eventos.valor += 1
        raise error_con_codigo(codigo)

    redis_client = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()
    worker, redis_client, storage, _, reporter = make_worker(
        tmp_path, redis_client=redis_client, storage=storage,
        processor=make_fake_processor(outcome=proceso), WORKER_QUEUES="transcode_video",
    )
    worker.events_reader = eventos
    seed_subtask(redis_client, storage, "s1")
    if campos:
        redis_client.hset("subtask:s1", mapping=campos)
    return worker, redis_client, reporter


def test_processing_error_sin_codigo_tiene_exit_code_none():
    assert ProcessingError("x").exit_code is None


def test_oom_reencola_con_mas_reserva_sin_gastar_intentos(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, -9, True, mem_reserve=1000)
    assert worker.handle_subtask("s1") is None
    datos = redis_client.hgetall("subtask:s1")
    assert datos["status"] == "pending"
    assert datos["requeue_reason"] == "oom"
    assert int(datos["mem_reserve"]) == 1500
    assert int(datos["oom_count"]) == 1
    assert int(datos["attempts"]) == 0
    assert redis_client.lrange("queue:transcode_video", 0, -1) == ["s1"]
    assert reporter.calls == []


def test_oom_agotado_falla_con_causa_oom(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, -9, True, oom_count=2, mem_reserve=2250)
    payload = worker.handle_subtask("s1")
    assert payload["status"] == "failed"
    assert payload["error_type"] == "oom"
    assert redis_client.lrange("queue:transcode_video", 0, -1) == []


def test_menos_9_sin_oom_kill_no_se_reencola_como_oom(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, -9, False)
    payload = worker.handle_subtask("s1")
    assert payload["status"] == "failed"
    assert payload["error_type"] != "oom"
    assert redis_client.lrange("queue:transcode_video", 0, -1) == []


def test_reserva_se_suma_a_la_admision_mientras_corre(tmp_path):
    observado = []
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()

    def proceso(llamada):
        observado.append(worker._fits_in_memory())

    worker, *_ = make_worker(
        tmp_path, redis_client=redis_client, storage=storage,
        processor=make_fake_processor(outcome=proceso), WORKER_QUEUES="transcode_video",
    )
    worker.resource_reader = FakeResourceReader(ResourceUsage("w1", memory_current=500, memory_max=1000))
    worker.footprints = FootprintTable({"transcode_video": 100})
    worker.admission_margin = 0
    seed_subtask(redis_client, storage, "s1")
    assert worker._fits_in_memory() is True
    redis_client.hset("subtask:s1", "mem_reserve", 450)
    worker.handle_subtask("s1")
    assert observado == [False]
    assert worker._fits_in_memory() is True
