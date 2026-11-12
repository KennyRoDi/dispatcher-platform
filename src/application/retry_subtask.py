from src.application.ports import CaseStateStore, Clock, RetryScheduler
from src.domain.case_state import CaseState, transition
from src.domain.retry import GiveUp, Jitter, Retry, RetryPolicy, decide_retry


class RetrySubtask:
    def __init__(
        self,
        store: CaseStateStore,
        scheduler: RetryScheduler,
        clock: Clock,
        policy: RetryPolicy,
        jitter: Jitter,
    ):
        self._store = store
        self._scheduler = scheduler
        self._clock = clock
        self._policy = policy
        self._jitter = jitter

    def execute(self, case_id: str, subtask_id: str, attempts: int) -> Retry | GiveUp | None:
        current = self._store.state(case_id)
        if current is CaseState.CANCELLED:
            return None
        decision = decide_retry(attempts, self._policy, self._jitter)
        if isinstance(decision, Retry):
            if current is not CaseState.RETRYING:
                self._store.set_state(case_id, transition(current, CaseState.RETRYING), self._clock.now())
            self._scheduler.schedule(subtask_id, decision.delay)
        return decision
