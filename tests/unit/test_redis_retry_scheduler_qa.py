import threading
from datetime import timedelta

import fakeredis
import pytest

from src.adapters.redis_retry_scheduler import SCHEDULED_KEY, RedisRetryScheduler
from tests.dobles import FakeClock


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def reloj():
    return FakeClock()


def vencer(planificador, reloj, segundos=2):
    reloj.advance(timedelta(seconds=segundos))
    return planificador.promote_due(reloj.now())


def test_sin_operation_se_descarta_del_zset_y_no_llega_a_ninguna_cola(redis_falso, reloj, caplog):
    redis_falso.hset("subtask:s1", mapping={"status": "pending"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 1)

    with caplog.at_level("ERROR"):
        vencer(planificador, reloj)

    assert redis_falso.zcard(SCHEDULED_KEY) == 0
    assert redis_falso.keys("queue:*") == []
    assert any("sin operation" in r.getMessage() for r in caplog.records)


def test_subtarea_inexistente_se_descarta_sin_excepcion(redis_falso, reloj):
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("fantasma", 1)
    vencer(planificador, reloj)
    assert redis_falso.zcard(SCHEDULED_KEY) == 0


def test_priority_desconocida_va_a_la_cola_normal(redis_falso, reloj):
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video", "priority": "urgentisima"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 1)
    vencer(planificador, reloj)
    assert redis_falso.lrange("queue:transcode_video", 0, -1) == ["s1"]


def test_programar_dos_veces_el_mismo_id_deja_una_sola_entrada_y_una_sola_promocion(redis_falso, reloj):
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 1)
    planificador.schedule("s1", 5)
    assert redis_falso.zcard(SCHEDULED_KEY) == 1
    assert vencer(planificador, reloj, 2) == []
    assert vencer(planificador, reloj, 10) == ["s1"]
    assert redis_falso.llen("queue:transcode_video") == 1


def test_varios_reapers_concurrentes_encolan_una_sola_vez(redis_falso, reloj):
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video"})
    RedisRetryScheduler(redis_falso, reloj).schedule("s1", 1)
    reloj.advance(timedelta(seconds=2))
    resultados = []

    def reaper():
        resultados.append(RedisRetryScheduler(redis_falso, reloj).promote_due(reloj.now()))

    hilos = [threading.Thread(target=reaper) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert redis_falso.llen("queue:transcode_video") == 1
    assert sorted(i for r in resultados for i in r) == ["s1"]


def test_promocion_ganada_por_otro_reaper_entre_lectura_y_transaccion_no_duplica(redis_falso, reloj):
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 1)
    reloj.advance(timedelta(seconds=2))

    original = redis_falso.zrangebyscore

    def zrangebyscore_y_otro_reaper_gana(*args, **kwargs):
        vencidas = original(*args, **kwargs)
        RedisRetryScheduler(redis_falso, reloj)._promote("s1")
        return vencidas

    redis_falso.zrangebyscore = zrangebyscore_y_otro_reaper_gana
    assert planificador.promote_due(reloj.now()) == []
    assert redis_falso.llen("queue:transcode_video") == 1


def test_puntaje_exacto_en_el_limite_se_promueve(redis_falso, reloj):
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 3)
    reloj.advance(timedelta(seconds=3))
    assert planificador.promote_due(reloj.now()) == ["s1"]


def test_subtarea_de_caso_cancelado_no_se_reencola(redis_falso, reloj):
    redis_falso.hset("case:c1", "status", "cancelled")
    redis_falso.hset("subtask:s1", mapping={"operation": "transcode_video", "case_id": "c1", "status": "pending"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("s1", 1)
    vencer(planificador, reloj)
    assert redis_falso.llen("queue:transcode_video") == 0


def test_una_entrada_corrupta_no_bloquea_a_las_demas(redis_falso, reloj):
    redis_falso.set("subtask:malo", "no-es-un-hash")
    redis_falso.hset("subtask:bueno", mapping={"operation": "transcode_video"})
    planificador = RedisRetryScheduler(redis_falso, reloj)
    planificador.schedule("malo", 1)
    planificador.schedule("bueno", 2)
    reloj.advance(timedelta(seconds=5))
    try:
        planificador.promote_due(reloj.now())
    except Exception:
        pass
    assert redis_falso.lrange("queue:transcode_video", 0, -1) == ["bueno"]
