from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.domain.priority import Priority


class ContentKind(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class QueueFull(Exception):
    pass


@dataclass(frozen=True)
class Subtask:
    id: str
    case_id: str
    kind: ContentKind
    source_sha256: str
    priority: Priority
    enqueued_at: datetime
    attempts: int = 0
    node_class: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "kind": self.kind.value,
            "source_sha256": self.source_sha256,
            "priority": self.priority.name.lower(),
            "enqueued_at": self.enqueued_at.isoformat(),
            "attempts": self.attempts,
            "node_class": self.node_class,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Subtask":
        return cls(
            id=data["id"],
            case_id=data["case_id"],
            kind=ContentKind(data["kind"]),
            source_sha256=data["source_sha256"],
            priority=Priority.from_name(data["priority"]),
            enqueued_at=datetime.fromisoformat(data["enqueued_at"]),
            attempts=data["attempts"],
            node_class=data["node_class"],
        )
