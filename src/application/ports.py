from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from src.domain.alert_policy import StoredAlert
from src.domain.chat_message import ChatMessage
from src.domain.consolidated_report import CaseInfo
from src.domain.finding import Finding
from src.domain.resources import ResourceUsage
from src.domain.subtask import Subtask


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class Analyzer(Protocol):
    def analyze(self, path: Path) -> list[Finding]: ...


@runtime_checkable
class ConversationParser(Protocol):
    def parse(self, path: Path) -> Iterable[ChatMessage]: ...


@runtime_checkable
class ObjectStore(Protocol):
    def exists(self, sha256: str) -> bool: ...
    def put(self, sha256: str, content: BinaryIO, size: int) -> None: ...
    def open(self, sha256: str) -> BinaryIO: ...


@runtime_checkable
class WorkQueue(Protocol):
    def has_capacity(self, queue: str) -> bool: ...
    def enqueue(self, queue: str, subtask: Subtask) -> None: ...
    def take(self, queue: str, worker_id: str, timeout: float) -> Subtask | None: ...
    def in_flight(self, worker_id: str) -> list[Subtask]: ...
    def acknowledge(self, worker_id: str, subtask: Subtask) -> None: ...


@runtime_checkable
class FindingStore(Protocol):
    def add(self, case_id: str, findings: Sequence[Finding]) -> None: ...
    def list(self, case_id: str) -> list[Finding]: ...


@runtime_checkable
class CaseCatalog(Protocol):
    def case(self, case_id: str) -> CaseInfo | None: ...


@runtime_checkable
class CustodyLog(Protocol):
    def record(self, evidence_sha256: str, operation: str, result_sha256: str, actor: str) -> None: ...


@runtime_checkable
class RoutingPolicy(Protocol):
    def route(self, subtask: Subtask, live_classes: Sequence[str]) -> str: ...


@runtime_checkable
class ResourceReader(Protocol):
    def read(self) -> ResourceUsage: ...


@runtime_checkable
class AlertPublisher(Protocol):
    def publish(self, kind: str, case_id: str, detail: str) -> None: ...


@runtime_checkable
class AlertReader(Protocol):
    def recent(self, limit: int) -> list[StoredAlert]: ...


@runtime_checkable
class ProcessRunner(Protocol):
    def start(self, argv: Sequence[str]) -> int: ...

    def signal_group(self, pid: int, sig: int) -> None: ...

    def reap(self, pid: int, block: bool = False) -> bool: ...

    def poll(self, pid: int) -> int | None: ...
