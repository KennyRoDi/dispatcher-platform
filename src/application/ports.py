from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from src.domain.alert_policy import StoredAlert
from src.domain.case_state import CaseState
from src.domain.chat_message import ChatMessage
from src.domain.consolidated_report import CaseInfo
from src.domain.finding import Finding
from src.domain.rbac import Role
from src.domain.resources import ResourceUsage
from src.domain.scheduling import Priority
from src.domain.subtask import Subtask


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class CaseStateStore(Protocol):
    def mark_reported(self, case_id: str, subtask_id: str, outcome: str) -> bool: ...

    def counts(self, case_id: str) -> tuple[int, int]: ...

    def state(self, case_id: str) -> CaseState | None: ...

    def set_state(self, case_id: str, nuevo: CaseState, at: datetime) -> bool | None: ...

    def history(self, case_id: str) -> list[tuple[CaseState, datetime]]: ...


@runtime_checkable
class RetryScheduler(Protocol):
    def schedule(self, subtask_id: str, delay_s: float) -> None: ...

    def promote_due(self, now: datetime) -> list[str]: ...


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
class ChunkStaging(Protocol):
    def save_manifest(self, upload_id: str, manifest: dict) -> None: ...
    def load_manifest(self, upload_id: str) -> dict: ...
    def put_chunk(self, upload_id: str, index: int, data: bytes) -> None: ...
    def received(self, upload_id: str) -> set[int]: ...
    def open_chunk(self, upload_id: str, index: int) -> BinaryIO: ...
    def discard(self, upload_id: str) -> None: ...


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
class OmissionAwareFindingStore(FindingStore, Protocol):
    def list_with_omitted(self, case_id: str) -> tuple[list[Finding], int]: ...


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


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    subject: str
    role: Role | str


@runtime_checkable
class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...


@runtime_checkable
class SchedulingPolicy(Protocol):
    """Política de planificación de casos: FIFO o Aging."""

    def next(self) -> str | None:
        """Dequecar el siguiente caso según la política."""
        ...

    def enqueue(self, case_id: str, priority: Priority, entered_at: float) -> None:
        """Enquecar un caso con prioridad."""
        ...


class KeyUnavailable(Exception):
    pass


class DecryptionError(Exception):
    pass
