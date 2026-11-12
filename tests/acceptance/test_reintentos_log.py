"""Evidencia de F-11: tiempos entre intentos de una sub-tarea que falla (reloj real, esperas de décimas)."""
import time
from datetime import datetime, timezone
from pathlib import Path

import fakeredis
import pytest

from fakes import FakeStorage, make_fake_processor
from test_worker_node import StubReporter, make_worker, seed_subtask

from src.adapters.redis_retry_scheduler import RedisRetryScheduler
from src.infrastructure.clock import SystemClock

pytestmark = pytest.mark.acceptance

INTENTOS = 4
BASE_S = 0.1
TOPE_S = 1.0
EVIDENCIA = Path(__file__).resolve().parents[2] / "docs" / "evidencia"


def test_reintentos_registran_tiempos_entre_intentos(tmp_path):
    redis_falso = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()
    inicios = []

    def analizador_que_falla(llamada):
        inicios.append(time.monotonic())
        raise TimeoutError("fallo transitorio sintético")

    reporter = StubReporter()
    worker, *_ = make_worker(
        tmp_path, redis_client=redis_falso, storage=storage, reporter=reporter,
        processor=make_fake_processor(outcome=analizador_que_falla), WORKER_QUEUES="transcode_video",
        MAX_ATTEMPTS=str(INTENTOS), RETRY_BASE_S=str(BASE_S), RETRY_CAP_S=str(TOPE_S),
    )
    reloj = SystemClock()
    planificador = RedisRetryScheduler(redis_falso, reloj)
    worker.retry_scheduler = planificador
    worker.jitter = lambda: 0.0
    seed_subtask(redis_falso, storage, "s1")
    redis_falso.hset("case:c1", "status", "queued")

    esperas_programadas = []
    payload = worker.handle_subtask(redis_falso.lpop("queue:transcode_video"))
    while payload is None:
        esperas_programadas.append(redis_falso.zscore("retry:scheduled", "s1") - reloj.now().timestamp())
        while not planificador.promote_due(reloj.now()):
            time.sleep(0.01)
        payload = worker.handle_subtask(redis_falso.lpop("queue:transcode_video"))

    tiempos = [b - a for a, b in zip(inicios, inicios[1:])]
    assert payload["status"] == "failed"
    assert len(inicios) == INTENTOS
    assert len(tiempos) == INTENTOS - 1
    assert all(tiempo >= espera - 0.02 for tiempo, espera in zip(tiempos, esperas_programadas))
    assert tiempos == sorted(tiempos) and len({round(t, 2) for t in tiempos}) == len(tiempos)

    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filas = "\n".join(
        f"| {i} → {i + 1} | {espera:.3f} | {tiempo:.3f} |"
        for i, (espera, tiempo) in enumerate(zip(esperas_programadas, tiempos), start=1)
    )
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / f"F-11_reintentos_{fecha}.md").write_text(
        f"# F-11: tiempos entre intentos ({fecha})\n\n"
        f"Generado por `tests/acceptance/test_reintentos_log.py` con reloj real, fakeredis y un analizador "
        f"sintético que siempre lanza `TimeoutError`. Configuración, no medición de SO: "
        f"`MAX_ATTEMPTS={INTENTOS}`, `RETRY_BASE_S={BASE_S}`, `RETRY_CAP_S={TOPE_S}`, jitter fijo en 0.\n\n"
        f"| Entre intentos | Espera programada (s) | Tiempo observado (s) |\n|---|---|---|\n{filas}\n\n"
        f"Resultado final: `{payload['status']}` tras {payload['attempts']} intentos.\n",
        encoding="utf-8",
    )
