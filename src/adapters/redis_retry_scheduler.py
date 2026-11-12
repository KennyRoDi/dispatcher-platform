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
        return [subtask_id for subtask_id in due if self._promote(subtask_id)]

    def _promote(self, subtask_id: str) -> bool:
        subtask_key = f"subtask:{subtask_id}"

        def txn(pipe):
            if pipe.zscore(SCHEDULED_KEY, subtask_id) is None:
                return False
            operation, priority = pipe.hmget(subtask_key, "operation", "priority")
            pipe.multi()
            pipe.zrem(SCHEDULED_KEY, subtask_id)
            if operation:
                pipe.lpush(f"queue:{operation}:high" if priority == "high" else f"queue:{operation}", subtask_id)
            else:
                logger.error("subtarea %s sin operation, no se puede reencolar tras la espera", subtask_id)
            return True

        return self._client.transaction(txn, SCHEDULED_KEY, subtask_key, value_from_callable=True)
