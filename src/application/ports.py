from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from src.domain.finding import Finding


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class Analyzer(Protocol):
    def analyze(self, path: Path) -> list[Finding]: ...


@runtime_checkable
class ObjectStore(Protocol):
    def exists(self, sha256: str) -> bool: ...
    def put(self, sha256: str, content: BinaryIO, size: int) -> None: ...
    def open(self, sha256: str) -> BinaryIO: ...


@runtime_checkable
class WorkQueue(Protocol):
    def enqueue(self, queue: str, subtask: dict) -> None: ...
    def take(self, queue: str, worker_id: str, timeout: float) -> dict | None: ...
    def acknowledge(self, worker_id: str, subtask: dict) -> None: ...


@runtime_checkable
class AlertPublisher(Protocol):
    def publish(self, kind: str, case_id: str, detail: str) -> None: ...
