import logging
from datetime import datetime

from src.application.ports import Clock

logger = logging.getLogger(__name__)

SCHEDULED_KEY = "retry:scheduled"


class RedisRetryScheduler:
    def __init__(self, client, clock: Clock):
        self._client = client
        self._clock = clock

    def schedule(self, subtask_id: str, delay_s: float) -> None:
        self._client.zadd(SCHEDULED_KEY, {subtask_id: self._clock.now().timestamp() + delay_s})

    def promote_due(self, now: datetime) -> list[str]:
        due = self._client.zrangebyscore(SCHEDULED_KEY, "-inf", now.timestamp())
        promoted = []
        for subtask_id in due:
            try:
                if self._promote(subtask_id):
                    promoted.append(subtask_id)
            except Exception:
                # Se deja en el ZSET: una clave corrupta no debe bloquear a las demás y se reintenta luego.
                logger.exception("no se pudo promover la subtarea %s tras la espera", subtask_id)
        return promoted

    def _promote(self, subtask_id: str) -> bool:
        subtask_key = f"subtask:{subtask_id}"

        def txn(pipe):
            if pipe.zscore(SCHEDULED_KEY, subtask_id) is None:
                return False
            operation, priority, status, case_id = pipe.hmget(
                subtask_key, "operation", "priority", "status", "case_id"
            )
            case_status = pipe.hget(f"case:{case_id}", "status") if case_id else None
            pipe.multi()
            pipe.zrem(SCHEDULED_KEY, subtask_id)
            # Si el reaper ya la reencoló o el caso terminó, encolarla otra vez la duplicaría o la resucitaría.
            if status not in (None, "pending") or case_status == "cancelled":
                return False
            if operation:
                pipe.lpush(f"queue:{operation}:high" if priority == "high" else f"queue:{operation}", subtask_id)
            else:
                logger.error("subtarea %s sin operation, no se puede reencolar tras la espera", subtask_id)
            return True

        return self._client.transaction(txn, SCHEDULED_KEY, subtask_key, value_from_callable=True)
