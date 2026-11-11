from enum import Enum


class CaseState(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class InvalidTransition(ValueError):
    pass


_ALLOWED = {
    CaseState.QUEUED: {CaseState.PROCESSING, CaseState.CANCELLED},
    CaseState.PROCESSING: {
        CaseState.COMPLETED,
        CaseState.PARTIALLY_COMPLETED,
        CaseState.FAILED,
        CaseState.RETRYING,
        CaseState.CANCELLED,
    },
    CaseState.RETRYING: {CaseState.PROCESSING, CaseState.FAILED, CaseState.CANCELLED},
}


def transition(current: CaseState, target: CaseState) -> CaseState:
    if target not in _ALLOWED.get(current, set()):
        raise InvalidTransition(f"{current.value} -> {target.value}")
    return target


def final_state(completed: int, failed: int, actual: CaseState | None = None) -> CaseState:
    if actual is CaseState.CANCELLED:
        return actual
    if failed == 0:
        return CaseState.COMPLETED
    if completed == 0:
        return CaseState.FAILED
    return CaseState.PARTIALLY_COMPLETED


class Barrier:
    def __init__(self, expected: int):
        self._expected = expected
        self._outcomes: dict[str, str] = {}

    def report(self, subtask_id: str, outcome: str) -> bool:
        if subtask_id in self._outcomes:
            return False
        self._outcomes[subtask_id] = outcome
        return True

    def is_closed(self) -> bool:
        return len(self._outcomes) >= self._expected
