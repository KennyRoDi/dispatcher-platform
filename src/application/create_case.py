"""Caso de uso: crear un caso a partir de fuentes (F-01).

Integra la clasificacion/decomposicion y el encolado confiable de F-05/F-06
con el esquema de persistencia heredado, para que GET /cases/{id} y /report
(sin modificar) sigan funcionando con casos multifuente. Ver AD-47.
"""
import json

from src.application.dispatch_case import DispatchCase
from src.application.ports import Clock, WorkQueue
from src.domain.decomposition import CaseSource, classify_source
from src.domain.priority import Priority


class FuenteNoSubida(Exception):
    def __init__(self, sha256: str) -> None:
        super().__init__(f"la fuente {sha256} no tiene un objeto subido")
        self.sha256 = sha256


class CreateMultiSourceCase:
    def __init__(self, redis_client, queue: WorkQueue, clock: Clock, subidas) -> None:
        self._redis = redis_client
        self._dispatch = DispatchCase(queue, clock)
        self._clock = clock
        self._subidas = subidas

    def execute(self, case_id: str, sources: list, priority: Priority, metadata: dict | None = None) -> dict:
        faltante = next((s for s in sources if not self._subidas.already_stored(s.sha256)), None)
        if faltante is not None:
            raise FuenteNoSubida(faltante.sha256)

        nombre_por_sha256 = {s.sha256: s.name for s in sources}
        case_sources = [CaseSource(s.sha256, s.name, classify_source(s.name)) for s in sources]

        routed = self._dispatch.execute(case_id, case_sources, priority)

        created_at = self._clock.now().isoformat()
        subtask_ids = [subtask.id for _queue, subtask in routed]
        self._persistir(case_id, routed, priority, created_at, metadata or {}, nombre_por_sha256)

        return {
            "case_id": case_id,
            "status": "queued",
            "priority": priority.name.lower(),
            "total_subtasks": len(subtask_ids),
            "subtask_ids": subtask_ids,
            "created_at": created_at,
        }

    def _persistir(self, case_id, routed, priority, created_at, metadata, nombre_por_sha256) -> None:
        total = len(routed)
        self._redis.hset(f"case:{case_id}", mapping={
            "case_id": case_id,
            "status": "queued",
            "total_subtasks": total,
            "pending_subtasks": total,
            "created_at": created_at,
            "priority": priority.name.lower(),
            "metadata": json.dumps(metadata),
            "retries": "0",
        })
        self._redis.sadd("cases:registry", case_id)
        for _queue, subtask in routed:
            self._redis.hset(f"subtask:{subtask.id}", mapping={
                "subtask_id": subtask.id,
                "case_id": case_id,
                "operation": subtask.kind.value,
                "task_type": subtask.kind.value,
                "file_path": nombre_por_sha256.get(subtask.source_sha256, ""),
                "status": "pending",
                "source_sha256": subtask.source_sha256,
                "params": "{}",
                "metadata": "{}",
                "priority": priority.name.lower(),
            })
            self._redis.rpush(f"case:{case_id}:subtasks", subtask.id)
