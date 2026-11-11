from datetime import datetime, timezone

from redis.exceptions import WatchError

from src.domain.case_state import CaseState

_OUTCOMES = {"completed", "failed"}
_TERMINAL = {CaseState.COMPLETED, CaseState.PARTIALLY_COMPLETED, CaseState.FAILED, CaseState.CANCELLED}


class RedisCaseState:
    def __init__(self, client) -> None:
        self._client = client

    def mark_reported(self, case_id: str, subtask_id: str, outcome: str) -> bool:
        if outcome not in _OUTCOMES:
            raise ValueError(f"resultado desconocido: {outcome}")
        # HSETNX es la puerta atómica y la fuente de los conteos: no hay ventana entre marcar y contar.
        first = self._client.hsetnx(f"case:{case_id}:outcomes", subtask_id, outcome)
        self._client.sadd(f"case:{case_id}:done", subtask_id)
        return bool(first)

    def counts(self, case_id: str) -> tuple[int, int]:
        outcomes = list(self._client.hvals(f"case:{case_id}:outcomes"))
        return outcomes.count("completed"), outcomes.count("failed")

    def state(self, case_id: str) -> CaseState | None:
        raw = self._client.hget(f"case:{case_id}", "status")
        try:
            return CaseState(raw)
        except ValueError:
            return None

    def set_state(self, case_id: str, nuevo: CaseState, at: datetime) -> bool:
        key = f"case:{case_id}"
        entry = f"{nuevo.value}|{at.astimezone(timezone.utc).isoformat()}"
        with self._client.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(key)
                    if self.state(case_id) in _TERMINAL:
                        return False
                    pipe.multi()
                    pipe.hset(key, "status", nuevo.value)
                    pipe.rpush(f"{key}:state_history", entry)
                    pipe.execute()
                    return True
                except WatchError:
                    continue

    def history(self, case_id: str) -> list[tuple[CaseState, datetime]]:
        entries = self._client.lrange(f"case:{case_id}:state_history", 0, -1)
        result = []
        for entry in entries:
            name, _, instant = entry.partition("|")
            result.append((CaseState(name), datetime.fromisoformat(instant)))
        return result
