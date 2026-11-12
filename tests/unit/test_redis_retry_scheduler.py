from datetime import timedelta

import fakeredis
import pytest

from src.adapters.redis_retry_scheduler import RedisRetryScheduler
from src.application.ports import RetryScheduler
from tests.contratos import comprobar_retry_scheduler
from tests.dobles import FakeClock


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def reloj():
    return FakeClock()


def sembrar(redis_falso, sid, operation, priority=None):
    mapping = {"subtask_id": sid, "operation": operation, "status": "pending"}
    if priority:
        mapping["priority"] = priority
    redis_falso.hset(f"subtask:{sid}", mapping=mapping)


def test_retry_scheduler_cumple_el_contrato(redis_falso, reloj):
    planificador = RedisRetryScheduler(redis_falso, reloj)
    assert isinstance(planificador, RetryScheduler)
    comprobar_retry_scheduler(planificador, reloj)


def test_schedule_guarda_el_instante_de_disponibilidad_como_puntaje(redis_falso, reloj):
    RedisRetryScheduler(redis_falso, reloj).schedule("s1", 7.5)
    assert redis_falso.zscore("retry:scheduled", "s1") == pytest.approx(reloj.now().timestamp() + 7.5)


def test_promote_due_mueve_solo_lo_vencido_a_su_cola_original(redis_falso, reloj):
    planificador = RedisRetryScheduler(redis_falso, reloj)
    sembrar(redis_falso, "s1", "transcode_video")
    sembrar(redis_falso, "s2", "extract_audio", priority="high")
    sembrar(redis_falso, "s3", "transcode_video")
    planificador.schedule("s1", 5)
    planificador.schedule("s2", 5)
    planificador.schedule("s3", 60)

    reloj.advance(timedelta(seconds=5))
    assert sorted(planificador.promote_due(reloj.now())) == ["s1", "s2"]

    assert redis_falso.lrange("queue:transcode_video", 0, -1) == ["s1"]
    assert redis_falso.lrange("queue:extract_audio:high", 0, -1) == ["s2"]
    assert redis_falso.zrange("retry:scheduled", 0, -1) == ["s3"]


def test_promote_due_no_duplica_en_la_cola(redis_falso, reloj):
    planificador = RedisRetryScheduler(redis_falso, reloj)
    sembrar(redis_falso, "s1", "transcode_video")
    planificador.schedule("s1", 1)
    reloj.advance(timedelta(seconds=2))

    assert planificador.promote_due(reloj.now()) == ["s1"]
    assert planificador.promote_due(reloj.now()) == []
    assert redis_falso.lrange("queue:transcode_video", 0, -1) == ["s1"]
