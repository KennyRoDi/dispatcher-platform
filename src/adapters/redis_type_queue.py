"""Adaptador Redis confiable del puerto WorkQueue (F-06).

Usa BLMOVE para que tomar una sub-tarea y marcarla en vuelo sean la misma
operacion atomica de Redis: no hay ventana en la que una sub-tarea no este
en ninguna parte (ni en la cola, ni en inflight), a diferencia del camino
heredado (BLPOP + SADD por separado).
"""
import json

from src.domain.decomposition import queue_for
from src.domain.subtask import QueueFull, Subtask


class RedisTypeQueue:
    def __init__(self, redis_client, capacity: int):
        self.redis = redis_client
        self.capacity = capacity

    def has_capacity(self, queue: str) -> bool:
        return self.redis.llen(queue) < self.capacity

    def enqueue(self, queue: str, subtask: Subtask) -> None:
        if not self.has_capacity(queue):
            raise QueueFull(queue)
        self.redis.rpush(queue, self._serializar(subtask))

    def take(self, queue: str, worker_id: str, timeout: float) -> Subtask | None:
        destino = self._inflight_key(worker_id)
        if timeout <= 0:
            raw = self.redis.lmove(queue, destino, "LEFT", "RIGHT")
        else:
            raw = self.redis.blmove(queue, destino, timeout=timeout, src="LEFT", dest="RIGHT")
        return Subtask.from_dict(json.loads(raw)) if raw is not None else None

    def in_flight(self, worker_id: str) -> list[Subtask]:
        raw_items = self.redis.lrange(self._inflight_key(worker_id), 0, -1)
        return [Subtask.from_dict(json.loads(raw)) for raw in raw_items]

    def acknowledge(self, worker_id: str, subtask: Subtask) -> None:
        self.redis.lrem(self._inflight_key(worker_id), 1, self._serializar(subtask))

    def reencolar_huerfanas(self, worker_id: str, limite: int | None = None) -> int:
        """Mueve, una por una y atomicamente, cada sub-tarea de inflight de vuelta a su cola.

        Si se interrumpe a medias (p. ej. el proceso que reencola muere), lo
        no movido sigue intacto en inflight: una llamada posterior retoma
        donde quedo, sin perder ni duplicar nada.
        """
        origen = self._inflight_key(worker_id)
        movidas = 0
        while limite is None or movidas < limite:
            raw = self.redis.lindex(origen, 0)
            if raw is None:
                break
            subtask = Subtask.from_dict(json.loads(raw))
            destino = queue_for(subtask.kind)
            self.redis.lmove(origen, destino, "LEFT", "RIGHT")
            movidas += 1
        return movidas

    @staticmethod
    def _inflight_key(worker_id: str) -> str:
        return f"inflight:{worker_id}"

    @staticmethod
    def _serializar(subtask: Subtask) -> str:
        return json.dumps(subtask.to_dict())
