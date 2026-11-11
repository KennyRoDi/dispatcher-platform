from dataclasses import dataclass
from enum import Enum

SIGKILL_CODES = (-9, 137)


class ExitCause(Enum):
    OK = "ok"
    OOM = "oom"
    KILLED = "killed"
    FAILED = "failed"


def classify_exit(code: int, oom_delta: int) -> ExitCause:
    if code == 0:
        return ExitCause.OK
    if code in SIGKILL_CODES:
        return ExitCause.OOM if oom_delta > 0 else ExitCause.KILLED
    return ExitCause.FAILED


@dataclass(frozen=True)
class Requeue:
    reserve: int


@dataclass(frozen=True)
class GiveUp:
    cause: str = "oom"


class OomPolicy:
    def __init__(self, max_requeues: int = 2, step_factor: float = 1.5) -> None:
        if max_requeues < 0:
            raise ValueError("max_requeues no puede ser negativo")
        if step_factor <= 1:
            raise ValueError("step_factor debe ser mayor que 1")
        self._max_requeues = max_requeues
        self._step_factor = step_factor

    def decide(self, oom_count: int, reserve: int) -> Requeue | GiveUp:
        if oom_count >= self._max_requeues:
            return GiveUp()
        return Requeue(reserve=int(reserve * self._step_factor))
