"""Reintentos de sub-tareas (F-11): analizador que falla N veces y analizador que se recupera."""
from datetime import timedelta

import fakeredis
import pytest

from fakes import FakeStorage, make_fake_processor
from test_worker_node import StubReporter, make_worker, seed_subtask

from src.adapters.redis_retry_scheduler import RedisRetryScheduler
from tests.dobles import FakeClock

pytestmark = pytest.mark.integration

COLA = "queue:transcode_video"


class Escenario:
    def __init__(self, tmp_path, fallos_antes_de_acertar, max_attempts=3):
        self.reloj = FakeClock()
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.estados_del_caso = []
        self.esperas = []
        self.fallos_restantes = fallos_antes_de_acertar
        storage = FakeStorage()

        def analizador(llamada):
            self.estados_del_caso.append(self.redis.hget("case:c1", "status"))
            if self.fallos_restantes is None:
                raise TimeoutError("el analizador no respondió")
            if self.fallos_restantes > 0:
                self.fallos_restantes -= 1
                raise TimeoutError("el analizador no respondió")

        self.reporter = StubReporter()
        self.worker, *_ = make_worker(
            tmp_path, redis_client=self.redis, storage=storage, reporter=self.reporter,
            processor=make_fake_processor(outcome=analizador), WORKER_QUEUES="transcode_video",
            MAX_ATTEMPTS=str(max_attempts), RETRY_BASE_S="1", RETRY_CAP_S="30",
        )
        self.planificador = RedisRetryScheduler(self.redis, self.reloj)
        self.worker.retry_scheduler = self.planificador
        self.worker.jitter = lambda: 0.0
        seed_subtask(self.redis, storage, "s1")
        self.redis.hset("case:c1", "status", "queued")

    def ejecutar_hasta_cerrar(self):
        payload = self.worker.handle_subtask(self.redis.lpop(COLA))
        while payload is None:
            self.estados_del_caso.append(self.redis.hget("case:c1", "status"))
            self.esperas.append(self.redis.zscore("retry:scheduled", "s1") - self.reloj.now().timestamp())
            assert self.redis.lrange(COLA, 0, -1) == []
            self.reloj.advance(timedelta(seconds=self.esperas[-1]))
            assert self.planificador.promote_due(self.reloj.now()) == ["s1"]
            payload = self.worker.handle_subtask(self.redis.lpop(COLA))
        return payload


def test_analizador_que_falla_n_veces_agota_y_falla_el_caso(tmp_path):
    escenario = Escenario(tmp_path, fallos_antes_de_acertar=None, max_attempts=3)

    payload = escenario.ejecutar_hasta_cerrar()

    assert payload["status"] == "failed"
    assert payload["attempts"] == 3
    assert len(escenario.esperas) == 2
    assert escenario.esperas[0] < escenario.esperas[1]
    assert escenario.estados_del_caso == [
        "processing", "retrying", "processing", "retrying", "processing",
    ]
    assert [llamada[1]["status"] for llamada in escenario.reporter.calls] == ["failed"]
    assert escenario.redis.zcard("retry:scheduled") == 0


def test_analizador_que_falla_y_luego_acierta_cierra_completed(tmp_path):
    escenario = Escenario(tmp_path, fallos_antes_de_acertar=1, max_attempts=3)

    payload = escenario.ejecutar_hasta_cerrar()

    assert payload["status"] == "completed"
    assert payload["attempts"] == 2
    assert len(escenario.esperas) == 1
    assert escenario.estados_del_caso == ["processing", "retrying", "processing"]
    assert [llamada[1]["status"] for llamada in escenario.reporter.calls] == ["completed"]
