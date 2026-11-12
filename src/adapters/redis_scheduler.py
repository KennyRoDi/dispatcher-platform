"""Adaptador del scheduler usando Redis ZSET.

F-20: Prioridades con aging.
"""
import time
import logging
from typing import Optional

import redis as redis_lib

from src.domain.scheduling import Priority, SchedulingPolicy, SchedulerState, CaseEntry

logger = logging.getLogger(__name__)


class RedisScheduler:
    """Scheduler que persiste en Redis usando ZSET por tipo.

    Puntaje = t_entrada - bono(prioridad).
    El menor puntaje sale primero (ZRANGE con LIMIT 0 1).
    """

    def __init__(self, redis_client: redis_lib.Redis, policy: SchedulingPolicy = SchedulingPolicy.AGING):
        self.redis = redis_client
        self.policy = policy
        self.aging_bonus_ms = 100.0

    def enqueue_subtask(self, queue: str, subtask_id: str, priority: Priority, entered_at: Optional[float] = None) -> None:
        """Enquecar una subtarea en el ZSET de su tipo (queue).

        Args:
            queue: Nombre de la cola (ej: "queue:text")
            subtask_id: ID de la subtarea
            priority: Nivel de prioridad
            entered_at: Tiempo de entrada (por defecto: ahora)
        """
        if entered_at is None:
            entered_at = time.time()

        entry = CaseEntry(case_id=subtask_id, priority=priority, entered_at=entered_at)
        score = entry.score(time.time())

        # Guardar en ZSET de la cola
        self.redis.zadd(queue, {subtask_id: score})
        logger.debug(f"Enqueued {subtask_id} in {queue} with score {score:.2f} (priority={priority.name})")

    def next_subtask(self, queue: str) -> Optional[str]:
        """Dequecar la siguiente subtarea del ZSET.

        Devuelve None si la cola está vacía.
        """
        # ZRANGE con LIMIT devuelve el elemento con puntaje más bajo
        result = self.redis.zrange(queue, 0, 0)
        if not result:
            return None

        subtask_id = result[0]
        # Remover del ZSET
        self.redis.zrem(queue, subtask_id)
        logger.debug(f"Dequeued {subtask_id} from {queue}")
        return subtask_id

    def queue_size(self, queue: str) -> int:
        """Tamaño de la cola."""
        return self.redis.zcard(queue)

    def move_from_priority_queues(self, queues: list[str]) -> Optional[str]:
        """Mover el siguiente subtask de cualquiera de las colas.

        Lee todas las colas, elige el de puntaje más bajo, y lo mueve.
        Se usa cuando el scheduler debe elegir entre tipos (texto, imagen, audio).

        Para el alcance de F-20, se enfoca en reordenar dentro de un tipo.
        """
        best_subtask = None
        best_score = float("inf")
        best_queue = None

        for queue in queues:
            # Leer el primer elemento (puntaje más bajo)
            items = self.redis.zrange(queue, 0, 0, withscores=True)
            if items:
                subtask_id, score = items[0]
                if score < best_score:
                    best_score = score
                    best_subtask = subtask_id
                    best_queue = queue

        if best_subtask and best_queue:
            self.redis.zrem(best_queue, best_subtask)
            logger.debug(f"Moved {best_subtask} from {best_queue} (score={best_score:.2f})")
            return best_subtask

        return None

    def persist_to_inflight(self, worker_id: str, subtask_id: str) -> None:
        """Mover a inflight después de BLMOVE (seguridad contra caída del worker)."""
        # Esto lo hace el worker con BLMOVE, pero si hay fallo coordinador,
        # el reaper recupera desde inflight:{worker_id}
        inflight_key = f"inflight:{worker_id}"
        self.redis.rpush(inflight_key, subtask_id)

    def recover_from_inflight(self, worker_id: str, queue: str) -> list[str]:
        """Recuperar subtareas en inflight (reaper)."""
        inflight_key = f"inflight:{worker_id}"
        subtasks = self.redis.lrange(inflight_key, 0, -1)

        # Re-enquecar en las colas (al principio, puntaje 0)
        for subtask_id in subtasks:
            # Puntaje 0: sale primero
            self.redis.zadd(queue, {subtask_id: 0.0})

        # Limpiar inflight
        self.redis.delete(inflight_key)
        logger.info(f"Recovered {len(subtasks)} subtasks from {inflight_key}")
        return subtasks
