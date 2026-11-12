"""Worker tipado (text, image, audio): un proceso por tipo con concurrencia 1 (F-43, AD-51).

Reutiliza Worker para el ciclo de vida, el heartbeat, la admisión de memoria y el reclamo
WATCH/MULTI, pero consume RedisTypeQueue en lugar de las colas heredadas de FFmpeg.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import redis

from src.adapters.redis_alert_stream import RedisAlertStream
from src.adapters.redis_case_state import RedisCaseState
from src.adapters.redis_finding_store import RedisFindingStore
from src.adapters.redis_type_queue import RedisTypeQueue
from src.application.alerting import AlertingFindingStore
from src.application.analyze_subtask import AnalyzeSubtask
from src.application.retry_subtask import RetrySubtask
from src.domain.admission import FootprintTable
from src.domain.decomposition import queue_for
from src.domain.retry import GiveUp, Retry, RetryPolicy
from src.domain.subtask import ContentKind, Subtask
from src.infrastructure.analizadores import crear_analizador
from src.infrastructure.cgroup_resources import CgroupResourceReader
from src.infrastructure.clock import SystemClock
from src.infrastructure.object_store import crear_almacen_lectura
from src.workers.config import Settings, load_admission_config, make_redis
from src.workers.fallos import es_transitorio
from src.workers.worker_node import Worker

logger = logging.getLogger(__name__)


class _SinAlmacen:
    def ensure_buckets(self) -> None:
        return None


def caso_cancelado(redis_client: redis.Redis):
    def cancelado(case_id: str) -> bool:
        return bool(redis_client.exists(f"cancel:{case_id}")) or redis_client.hget(f"case:{case_id}", "status") == "cancelled"

    return cancelado


class TypedWorker(Worker):
    _registra_en_set_heredado = False

    def __init__(
        self,
        settings: Settings,
        analyze: AnalyzeSubtask,
        queue: RedisTypeQueue,
        redis_client: redis.Redis | None = None,
        reporter=None,
        resource_reader=None,
        footprints: FootprintTable | None = None,
        admission_margin: int | None = None,
        retry_scheduler=None,
        jitter=None,
        clock=None,
        heartbeat_enabled: bool = True,
        supervisor=None,
    ):
        if settings.worker_kind is None:
            raise ValueError("TypedWorker exige WORKER_KIND")
        self.kind = ContentKind(settings.worker_kind)
        self.queue_name = queue_for(self.kind)
        super().__init__(
            replace(settings, worker_queues=(settings.worker_kind,)),
            redis_client=redis_client,
            storage=_SinAlmacen(),
            processor=SimpleNamespace(),
            reporter=reporter,
            heartbeat_enabled=heartbeat_enabled,
            ffmpeg_info=("unavailable", "none"),
            supervisor=supervisor,
            resource_reader=resource_reader,
            footprints=footprints,
            admission_margin=admission_margin,
            retry_scheduler=retry_scheduler,
            jitter=jitter,
        )
        self.analyze = analyze
        self.queue = queue
        policy = RetryPolicy(settings.max_attempts, settings.retry_base_s, settings.retry_cap_s)
        self.retry = RetrySubtask(
            RedisCaseState(self.redis), self.retry_scheduler, clock if clock is not None else SystemClock(), policy, self.jitter
        )

    def recover_own_inflight(self) -> dict:
        counts = {"requeued": 0, "failed": 0, "cleaned": 0}
        try:
            counts["requeued"] = self.queue.reencolar_huerfanas(self.settings.worker_id)
        except Exception:
            logger.exception("no se pudo reencolar el inflight de %s al iniciar", self.settings.worker_id)
        if counts["requeued"]:
            logger.warning("worker %s reencoló %d sub-tareas propias al iniciar", self.settings.worker_id, counts["requeued"])
        return counts

    def poll_once(self, timeout: int = 1) -> bool:
        if self.stop_event.is_set():
            return False
        if self.resource_reader is not None and not self._fits_in_memory():
            self.stop_event.wait(timeout)
            return False
        subtask = self.queue.take(self.queue_name, self.settings.worker_id, timeout)
        if subtask is None:
            return False
        self.procesar(subtask)
        return True

    def procesar(self, subtask: Subtask) -> dict | None:
        outcome, data, attempts = self._claim_subtask(subtask.id)
        if outcome != "claimed":
            logger.info("subtarea %s se confirma sin procesar (%s)", subtask.id, outcome)
            self._confirmar(subtask)
            return None
        if attempts > self.settings.max_attempts:
            return self._reportar(
                subtask, data, "failed", attempts - 1, data["assigned_at"], time.monotonic(),
                error=f"Sub-tarea abandonada tras {attempts - 1} intentos (worker_lost)", error_type="WorkerLostError",
            )

        self.stats.task_started()
        started_monotonic = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        self.redis.hset(f"subtask:{subtask.id}", mapping={"status": "running", "started_at": started_at, "progress": 0})
        try:
            escribio = self.analyze.execute(subtask, data.get("file_path", ""))
        except Exception as fallo:
            return self._fallar(subtask, data, attempts, fallo, started_at, started_monotonic)
        if not escribio:
            self.redis.hset(f"subtask:{subtask.id}", "status", "cancelled")
            self._cerrar(subtask, ok=False)
            return None
        return self._reportar(subtask, data, "completed", attempts, started_at, started_monotonic)

    def _fallar(self, subtask, data, attempts, fallo, started_at, started_monotonic) -> dict | None:
        if es_transitorio(fallo) and self._programar_reintento_tipado(subtask, attempts, fallo):
            return None
        logger.warning("subtarea %s falló: %s: %s", subtask.id, type(fallo).__name__, fallo)
        return self._reportar(
            subtask, data, "failed", attempts, started_at, started_monotonic,
            error=str(fallo), error_type=type(fallo).__name__,
        )

    def _programar_reintento_tipado(self, subtask: Subtask, attempts: int, fallo: Exception) -> bool:
        try:
            decision = self.retry.execute(subtask.case_id, subtask.id, attempts)
        except ValueError:
            logger.exception("no se pudo programar el reintento de %s, se reporta como fallida", subtask.id)
            return False
        if isinstance(decision, GiveUp):
            return False
        estado = "pending" if isinstance(decision, Retry) else "cancelled"
        self.redis.hset(f"subtask:{subtask.id}", mapping={"status": estado, "worker_id": "", "progress": 0})
        if isinstance(decision, Retry):
            logger.warning(
                "reintento %s: intento %d, espera %.2f s, motivo %s: %s",
                subtask.id, attempts, decision.delay, type(fallo).__name__, fallo,
            )
        self._cerrar(subtask, ok=False)
        return True

    def _reportar(
        self, subtask, data, status, attempts, started_at, started_monotonic, error=None, error_type=None
    ) -> dict | None:
        payload = {
            "subtask_id": subtask.id,
            "case_id": subtask.case_id,
            "worker_id": self.settings.worker_id,
            "host": self.host,
            "status": status,
            "result_path": "",
            "outputs": [],
            "error": error,
            "error_type": error_type,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "processing_s": round(time.monotonic() - started_monotonic, 3),
            "media_duration_s": None,
            "output_bytes": 0,
            "encoder": None,
            "attempts": attempts,
        }
        try:
            self.reporter.report(payload)
            self._cerrar(subtask, ok=status == "completed")
        except Exception:
            logger.exception("error al finalizar subtarea %s", subtask.id)
        return payload

    def _cerrar(self, subtask: Subtask, ok: bool) -> None:
        self._confirmar(subtask)
        self.stats.task_finished(ok)

    def _confirmar(self, subtask: Subtask) -> None:
        self.queue.acknowledge(self.settings.worker_id, subtask)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    if settings.worker_kind is None:
        raise SystemExit("WORKER_KIND es obligatoria: text, image o audio")
    footprints, margin = load_admission_config(os.environ, (settings.worker_kind,))
    redis_client = make_redis(settings)
    findings = AlertingFindingStore(
        RedisFindingStore(redis_client), RedisAlertStream(redis_client, SystemClock())
    )
    kind = ContentKind(settings.worker_kind)
    analyze = AnalyzeSubtask(
        crear_almacen_lectura(os.environ),
        {kind: crear_analizador(settings.worker_kind, os.environ)},
        findings,
        settings.work_dir,
        caso_cancelado(redis_client),
    )
    TypedWorker(
        settings,
        analyze,
        RedisTypeQueue(redis_client, 0),
        redis_client=redis_client,
        resource_reader=CgroupResourceReader(
            cgroup_path=os.environ.get("CGROUP_PATH", "/sys/fs/cgroup"), worker_id=settings.worker_id
        ),
        footprints=footprints,
        admission_margin=margin,
    ).run_forever()


if __name__ == "__main__":
    main()
