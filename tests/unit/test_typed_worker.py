import json
from datetime import datetime, timezone

import fakeredis
import pytest

from src.adapters.redis_retry_scheduler import RedisRetryScheduler
from src.adapters.redis_type_queue import RedisTypeQueue
from src.application.analyze_subtask import directorio_de_trabajo
from src.domain.admission import FootprintTable
from src.domain.priority import Priority
from src.domain.resources import ResourceUsage
from src.domain.subtask import ContentKind, Subtask
from src.workers.config import Settings
from src.workers.typed_worker import TypedWorker
from tests.dobles import FakeClock, FakeResourceReader

SHA = "a" * 64
CASO = "caso1"
SUBTAREA = f"{CASO}:{SHA}:text"


class AnalizadorFalso:
    def __init__(self, error=None, resultado=True):
        self.error = error
        self.resultado = resultado
        self.llamadas = []
        self.al_llamar = None

    def execute(self, subtask, source_name):
        self.llamadas.append((subtask.id, source_name))
        if self.al_llamar is not None:
            self.al_llamar()
        if self.error is not None:
            raise self.error
        return self.resultado


class ReporteroFalso:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.reportes = []
        self.en_vuelo_al_reportar = []

    def report(self, payload):
        self.reportes.append(payload)
        self.en_vuelo_al_reportar.append(self.redis.llen("inflight:w1"))
        return True

    def flush_pending(self):
        return 0


def subtarea(sha=SHA):
    return Subtask(
        id=f"{CASO}:{sha}:text", case_id=CASO, kind=ContentKind.TEXT, source_sha256=sha,
        priority=Priority.MEDIA, enqueued_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )


def sembrar(redis_client, queue, sub=None, status="pending", case_status="queued", attempts=None):
    sub = sub or subtarea()
    redis_client.hset(f"case:{CASO}", mapping={"case_id": CASO, "status": case_status, "total_subtasks": 1, "pending_subtasks": 1})
    mapping = {
        "subtask_id": sub.id, "case_id": CASO, "operation": "text", "file_path": "chat.txt",
        "status": status, "payload": json.dumps(sub.to_dict()),
    }
    if attempts is not None:
        mapping["attempts"] = attempts
    redis_client.hset(f"subtask:{sub.id}", mapping=mapping)
    queue.enqueue("queue:text", sub)
    return sub


class Entorno:
    def __init__(self, tmp_path, analizador=None, uso=None, **env):
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.queue = RedisTypeQueue(self.redis, 0)
        self.analizador = analizador or AnalizadorFalso()
        self.reportero = ReporteroFalso(self.redis)
        settings = Settings.from_env({
            "WORKER_ID": "w1", "WORK_DIR": str(tmp_path), "WORKER_KIND": "text",
            "FOOTPRINT_TEXT_BYTES": "300", **env,
        })
        self.worker = TypedWorker(
            settings, self.analizador, self.queue, redis_client=self.redis, reporter=self.reportero,
            resource_reader=FakeResourceReader(uso) if uso is not None else None,
            footprints=FootprintTable({"text": 300}), admission_margin=100,
            retry_scheduler=RedisRetryScheduler(self.redis, FakeClock()), jitter=lambda: 0.0,
            clock=FakeClock(), heartbeat_enabled=False,
        )

    def tomar(self):
        return self.queue.take("queue:text", "w1", 0)


@pytest.fixture
def entorno(tmp_path):
    return Entorno(tmp_path)


def test_directorio_de_trabajo_no_contiene_dos_puntos(tmp_path):
    directorio = directorio_de_trabajo(tmp_path, SUBTAREA)

    assert ":" not in directorio.name
    assert directorio.parent == tmp_path
    assert directorio.resolve().is_relative_to(tmp_path.resolve())
    directorio.mkdir()


def test_reclamo_pasa_el_caso_a_processing_y_cuenta_el_intento(entorno):
    sub = sembrar(entorno.redis, entorno.queue)

    resultado, datos, intento = entorno.worker._claim_subtask(sub.id)

    assert (resultado, intento) == ("claimed", 1)
    assert entorno.redis.hget(f"subtask:{sub.id}", "status") == "assigned"
    assert entorno.redis.hget(f"subtask:{sub.id}", "attempts") == "1"
    assert entorno.redis.hget(f"subtask:{sub.id}", "worker_id") == "w1"
    assert entorno.redis.hget(f"case:{CASO}", "status") == "processing"
    inicio = entorno.redis.hget(f"case:{CASO}", "started_at")
    assert inicio
    assert not entorno.redis.exists("worker:w1:inflight")

    entorno.redis.hset(f"case:{CASO}", "status", "retrying")
    entorno.worker._claim_subtask(sub.id)

    assert entorno.redis.hget(f"subtask:{sub.id}", "attempts") == "2"
    assert entorno.redis.hget(f"case:{CASO}", "started_at") == inicio


def test_subtarea_inexistente_se_confirma_sin_procesar(entorno):
    entorno.queue.enqueue("queue:text", subtarea())

    assert entorno.worker.poll_once(timeout=0) is True

    assert entorno.analizador.llamadas == []
    assert entorno.reportero.reportes == []
    assert entorno.redis.llen("inflight:w1") == 0


@pytest.mark.parametrize("estado", ["completed", "failed", "cancelled"])
def test_subtarea_terminal_se_confirma_sin_procesar(entorno, estado):
    sembrar(entorno.redis, entorno.queue, status=estado)

    entorno.worker.poll_once(timeout=0)

    assert entorno.analizador.llamadas == []
    assert entorno.reportero.reportes == []
    assert entorno.redis.llen("inflight:w1") == 0
    assert entorno.redis.hget(f"subtask:{SUBTAREA}", "status") == estado


def test_caso_cancelado_en_cola_marca_la_subtarea_cancelada_y_confirma(entorno):
    sembrar(entorno.redis, entorno.queue, case_status="cancelled")

    entorno.worker.poll_once(timeout=0)

    assert entorno.redis.hget(f"subtask:{SUBTAREA}", "status") == "cancelled"
    assert entorno.analizador.llamadas == []
    assert entorno.reportero.reportes == []
    assert entorno.redis.llen("inflight:w1") == 0


def test_exito_reporta_completed_y_confirma_el_inflight(entorno):
    sembrar(entorno.redis, entorno.queue)

    entorno.worker.poll_once(timeout=0)

    assert entorno.analizador.llamadas == [(SUBTAREA, "chat.txt")]
    (reporte,) = entorno.reportero.reportes
    assert reporte["status"] == "completed"
    assert reporte["outputs"] == []
    assert reporte["attempts"] == 1
    assert reporte["subtask_id"] == SUBTAREA and reporte["case_id"] == CASO and reporte["worker_id"] == "w1"
    assert entorno.reportero.en_vuelo_al_reportar == [1]
    assert entorno.redis.llen("inflight:w1") == 0
    assert entorno.worker.stats.snapshot() == {"active": 0, "completed": 1, "failed": 0}


def test_fallo_permanente_reporta_failed_con_su_tipo_de_error(tmp_path):
    entorno = Entorno(tmp_path, AnalizadorFalso(error=ValueError("entrada ilegible")))
    sembrar(entorno.redis, entorno.queue)

    entorno.worker.poll_once(timeout=0)

    (reporte,) = entorno.reportero.reportes
    assert reporte["status"] == "failed"
    assert reporte["error_type"] == "ValueError"
    assert reporte["error"] == "entrada ilegible"
    assert entorno.redis.zcard("retry:scheduled") == 0
    assert entorno.redis.llen("inflight:w1") == 0


def test_fallo_transitorio_programa_reintento_y_confirma(tmp_path):
    entorno = Entorno(tmp_path, AnalizadorFalso(error=TimeoutError("lento")))
    sembrar(entorno.redis, entorno.queue)

    entorno.worker.poll_once(timeout=0)

    assert entorno.redis.zscore("retry:scheduled", SUBTAREA) is not None
    assert entorno.redis.hget(f"subtask:{SUBTAREA}", "status") == "pending"
    assert entorno.redis.hget(f"subtask:{SUBTAREA}", "worker_id") == ""
    assert entorno.redis.hget(f"case:{CASO}", "status") == "retrying"
    assert entorno.reportero.reportes == []
    assert entorno.redis.llen("inflight:w1") == 0


def test_fallo_transitorio_sin_intentos_restantes_reporta_failed(tmp_path):
    entorno = Entorno(tmp_path, AnalizadorFalso(error=TimeoutError("lento")), MAX_ATTEMPTS="1")
    sembrar(entorno.redis, entorno.queue)

    entorno.worker.poll_once(timeout=0)

    (reporte,) = entorno.reportero.reportes
    assert reporte["status"] == "failed" and reporte["error_type"] == "TimeoutError"
    assert entorno.redis.zcard("retry:scheduled") == 0


def test_intentos_agotados_al_reclamar_reportan_worker_lost_sin_procesar(entorno):
    sembrar(entorno.redis, entorno.queue, status="assigned", attempts=3)

    entorno.worker.poll_once(timeout=0)

    assert entorno.analizador.llamadas == []
    (reporte,) = entorno.reportero.reportes
    assert reporte["status"] == "failed" and reporte["error_type"] == "WorkerLostError"
    assert reporte["attempts"] == 3
    assert entorno.redis.llen("inflight:w1") == 0


def test_admision_de_memoria_deja_la_subtarea_en_cola(tmp_path):
    entorno = Entorno(tmp_path, uso=ResourceUsage("w1", memory_current=800, memory_max=1000))
    sembrar(entorno.redis, entorno.queue)
    llamadas = []
    original = entorno.queue.take
    entorno.queue.take = lambda *args, **kwargs: llamadas.append(args) or original(*args, **kwargs)

    assert entorno.worker.poll_once(timeout=0) is False

    assert llamadas == []
    assert entorno.redis.llen("queue:text") == 1


def test_admision_de_memoria_consume_si_cabe(tmp_path):
    entorno = Entorno(tmp_path, uso=ResourceUsage("w1", memory_current=100, memory_max=1000))
    sembrar(entorno.redis, entorno.queue)

    assert entorno.worker.poll_once(timeout=0) is True

    assert len(entorno.reportero.reportes) == 1


def test_al_iniciar_reencola_su_propio_inflight(entorno):
    sembrar(entorno.redis, entorno.queue)
    assert entorno.tomar() is not None
    assert entorno.redis.llen("inflight:w1") == 1

    conteos = entorno.worker.recover_own_inflight()

    assert conteos["requeued"] == 1
    assert entorno.redis.llen("inflight:w1") == 0
    assert entorno.queue.take("queue:text", "w1", 0) == subtarea()


def test_stop_event_termina_la_subtarea_en_curso_y_no_toma_otra(entorno):
    sembrar(entorno.redis, entorno.queue)
    otra = subtarea("b" * 64)
    sembrar(entorno.redis, entorno.queue, sub=otra)
    entorno.analizador.al_llamar = entorno.worker.stop_event.set

    entorno.worker._consumer_loop()

    assert [r["subtask_id"] for r in entorno.reportero.reportes] == [SUBTAREA]
    assert entorno.redis.lrange("queue:text", 0, -1) == [json.dumps(otra.to_dict())]
    assert entorno.worker.poll_once(timeout=0) is False
