from collections.abc import Callable
from dataclasses import dataclass

Jitter = Callable[[], float]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base: float
    cap: float

    def __post_init__(self):
        if self.max_attempts < 1 or self.base <= 0 or self.cap < self.base:
            raise ValueError("política de reintento inválida")


@dataclass(frozen=True)
class Retry:
    delay: float


@dataclass(frozen=True)
class GiveUp:
    pass


def next_delay(attempt: int, base: float, cap: float, jitter: Jitter) -> float:
    if attempt < 1 or base <= 0 or cap < base:
        raise ValueError("parámetros de backoff inválidos")
    fraction = jitter()
    if not 0 <= fraction < 1:
        raise ValueError("el jitter debe estar en [0, 1)")
    # Backoff exponencial con jitter parcial: AWS Architecture Blog, "Exponential Backoff And Jitter".
    return min(cap, base * 2 ** (attempt - 1)) * (0.5 + 0.5 * fraction)


def decide_retry(attempts: int, policy: RetryPolicy, jitter: Jitter) -> Retry | GiveUp:
    if attempts >= policy.max_attempts:
        return GiveUp()
    return Retry(delay=next_delay(attempts + 1, policy.base, policy.cap, jitter))
