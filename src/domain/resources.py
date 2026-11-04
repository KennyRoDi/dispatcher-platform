from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceUsage:
    worker_id: str
    memory_current: int
    memory_max: int

    @property
    def memory_available(self) -> int:
        return max(self.memory_max - self.memory_current, 0)
