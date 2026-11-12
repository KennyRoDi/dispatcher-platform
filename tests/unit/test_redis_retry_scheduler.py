import json
from datetime import datetime, timedelta, timezone

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


def test_promocion_del_reintento_encola_el_json_de_subtask_en_la_cola_tipada(redis_falso, reloj):
    from src.adapters.redis_type_queue import RedisTypeQueue
    from src.domain.priority import Priority
    from src.domain.subtask import ContentKind, Subtask

    planificador = RedisRetryScheduler(redis_falso, reloj)
    subtarea = Subtask(
        "c1:sha-1:image", "c1", ContentKind.IMAGE, "sha-1", Priority.ALTA,
        datetime(2026, 11, 12, tzinfo=timezone.utc),
    )
    payload = json.dumps(subtarea.to_dict())
    sembrar(redis_falso, subtarea.id, "image", priority="high")
    redis_falso.hset(f"subtask:{subtarea.id}", mapping={"task_type": "image", "payload": payload})
    sembrar(redis_falso, "s-ffmpeg", "transcode_video")
    planificador.schedule(subtarea.id, 3)
    planificador.schedule("s-ffmpeg", 3)

    reloj.advance(timedelta(seconds=3))
    assert sorted(planificador.promote_due(reloj.now())) == sorted([subtarea.id, "s-ffmpeg"])

    assert redis_falso.lrange("queue:image", 0, -1) == [payload]
    assert redis_falso.llen("queue:image:high") == 0
    assert redis_falso.lrange("queue:transcode_video", 0, -1) == ["s-ffmpeg"]
    assert RedisTypeQueue(redis_falso, capacity=10).take("queue:image", "w1", timeout=0) == subtarea
