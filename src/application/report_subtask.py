from src.application.ports import CaseStateStore, Clock
from src.domain.case_state import CaseState, final_state

_OUTCOMES = {"completed", "failed"}
_REOPEN = {CaseState.QUEUED, CaseState.RETRYING}
_OPEN = _REOPEN | {CaseState.PROCESSING, None}


class ReportSubtask:
    def __init__(self, store: CaseStateStore, clock: Clock):
        self._store = store
        self._clock = clock

    def execute(self, case_id: str, subtask_id: str, outcome: str, expected: int) -> CaseState | None:
        if outcome not in _OUTCOMES:
            raise ValueError(f"resultado desconocido: {outcome}")
        if not self._store.mark_reported(case_id, subtask_id, outcome):
            return None
        completed, failed = self._store.counts(case_id)
        actual = self._store.state(case_id)
        if completed + failed < expected or actual not in _OPEN:
            return None
        if actual in _REOPEN:
            self._store.set_state(case_id, CaseState.PROCESSING, self._clock.now())
        final = final_state(completed, failed, actual)
        self._store.set_state(case_id, final, self._clock.now())
        return final
