from datetime import timedelta

import fakeredis
import pytest
from dobles import FakeClock, FakeRetryScheduler
from fakes import make_fake_processor
from test_worker_node import make_worker, seed_subtask

from src.adapters.redis_retry_scheduler import SCHEDULED_KEY, RedisRetryScheduler
from src.workers.config import Settings
from src.workers.recovery import recover_subtask


def preparar(tmp_path, fallo, jitter=lambda: 0.0, **env):
    worker, redis_client, storage, _, reporter = make_worker(
        tmp_path, processor=make_fake_processor(outcome=fallo), MAX_ATTEMPTS="3", **env,
    )
    worker.retry_scheduler = FakeRetryScheduler(FakeClock())
    worker.jitter = jitter
    seed_subtask(redis_client, storage, "s1")
    redis_client.hset("case:c1", "status", "queued")
    redis_client.lpop("queue:transcode_video")
    return worker, redis_client, reporter


@pytest.mark.parametrize("env", [
    {"RETRY_BASE_S": "abc"}, {"RETRY_BASE_S": "0"}, {"RETRY_BASE_S": "-1"},
    {"RETRY_BASE_S": "5", "RETRY_CAP_S": "1"},
])
def test_variables_de_reintento_invalidas_se_rechazan(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


@pytest.mark.xfail(
    strict=True,
    reason="QA F-11 parte 2: RETRY_BASE_S=nan pasa la validacion (comparaciones con NaN son falsas); "
           "es el riesgo 10 del SPEC ahora en la configuracion",
)
def test_nan_en_retry_base_se_rechaza():
    with pytest.raises(ValueError):
        Settings.from_env({"RETRY_BASE_S": "nan"})


@pytest.mark.xfail(
    strict=True,
    reason="QA F-11 parte 2: RETRY_BASE_S=inf y RETRY_CAP_S=inf pasan la validacion y programan esperas infinitas",
)
def test_inf_en_retry_base_se_rechaza():
    with pytest.raises(ValueError):
        Settings.from_env({"RETRY_BASE_S": "inf", "RETRY_CAP_S": "inf"})


def test_fallo_permanente_valueerror_no_se_reintenta(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, ValueError("ilegible"))
    assert worker.handle_subtask("s1")["status"] == "failed"
    assert worker.retry_scheduler.programadas == []


def test_attempts_agotados_en_fallo_transitorio_reporta_failed(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, TimeoutError("t"))
    redis_client.hset("subtask:s1", "attempts", 5)
    assert worker.handle_subtask("s1")["status"] == "failed"
    assert worker.retry_scheduler.programadas == []


def test_la_espera_no_ocupa_slot_ni_queda_inflight(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, TimeoutError("t"))
    assert worker.handle_subtask("s1") is None
    assert not redis_client.sismember("worker:w1:inflight", "s1")
    assert redis_client.hget("subtask:s1", "status") == "pending"
    assert redis_client.hget("case:c1", "retries") == "1"


def test_caso_cancelado_durante_la_ejecucion_no_pasa_a_retrying(tmp_path):
    def cancelar_durante_proceso(_):
        redis_client.hset("case:c1", "status", "cancelled")
        raise TimeoutError("t")

    worker, redis_client, reporter = preparar(tmp_path, cancelar_durante_proceso)
    worker.handle_subtask("s1")
    assert redis_client.hget("case:c1", "status") == "cancelled"


def test_motivo_del_fallo_con_ruta_se_copia_tal_cual_al_log_de_reintento(tmp_path, caplog):
    worker, redis_client, reporter = preparar(tmp_path, TimeoutError("fallo en /srv/secreto/clave.pem"))
    with caplog.at_level("WARNING"):
        worker.handle_subtask("s1")
    assert "/srv/secreto/clave.pem" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.xfail(
    strict=True,
    reason="QA F-11 parte 2: un jitter que devuelve 1.0 hace que next_delay lance ValueError dentro de "
           "handle_subtask; la sub-tarea no se reporta ni se programa y queda inflight",
)
def test_jitter_fuera_de_rango_no_deja_la_subtarea_huerfana(tmp_path):
    worker, redis_client, reporter = preparar(tmp_path, TimeoutError("t"), jitter=lambda: 1.0)
    try:
        worker.handle_subtask("s1")
    except ValueError:
        pass
    assert not redis_client.sismember("worker:w1:inflight", "s1")


@pytest.mark.xfail(
    strict=True,
    reason="QA F-11 riesgo 12: si el worker muere tras schedule y antes de srem, el reaper reencola de inmediato y "
           "luego promote_due lo encola otra vez: la sub-tarea se ejecuta dos veces",
)
def test_muerte_entre_schedule_y_cambio_de_estado_no_duplica_la_subtarea(tmp_path):
    worker, redis_client, storage, _, reporter = make_worker(tmp_path, MAX_ATTEMPTS="3")
    reloj = FakeClock()
    planificador = RedisRetryScheduler(redis_client, reloj)
    redis_client.hset("subtask:s1", mapping={
        "subtask_id": "s1", "case_id": "c1", "operation": "transcode_video", "status": "running",
        "worker_id": "w1", "attempts": 1,
    })
    redis_client.hset("case:c1", "status", "processing")
    redis_client.sadd("worker:w1:inflight", "s1")
    planificador.schedule("s1", 1)

    settings = Settings.from_env({"MAX_ATTEMPTS": "3"})
    assert recover_subtask(redis_client, settings, reporter, "s1", "worker_lost") == "requeued"
    reloj.advance(timedelta(seconds=5))
    planificador.promote_due(reloj.now())

    assert redis_client.llen("queue:transcode_video") == 1
    assert redis_client.zcard(SCHEDULED_KEY) == 0


class _Reporte:
    def __init__(self):
        self.payloads = []

    def report(self, payload):
        self.payloads.append(payload)


def test_recovery_con_huerfanas_sigue_reencolando_inmediato_y_falla_al_limite():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    settings = Settings.from_env({"MAX_ATTEMPTS": "2"})
    reporte = _Reporte()
    for sid, intentos in (("a", 1), ("b", 2)):
        redis_client.hset(f"subtask:{sid}", mapping={
            "case_id": "c", "operation": "x", "status": "running", "attempts": intentos,
        })

    assert recover_subtask(redis_client, settings, reporte, "a", "worker_lost") == "requeued"
    assert redis_client.lrange("queue:x", 0, -1) == ["a"]
    assert recover_subtask(redis_client, settings, reporte, "b", "worker_lost") == "failed"
    assert reporte.payloads[0]["error_type"] == "WorkerLostError"
