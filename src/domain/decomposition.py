from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import PurePath

from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask


class SourceKind(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True)
class CaseSource:
    sha256: str
    name: str
    kind: SourceKind


_EXTENSIONS_BY_KIND = {
    SourceKind.TEXT: (".txt", ".csv", ".json"),
    SourceKind.IMAGE: (".jpg", ".jpeg", ".png"),
    SourceKind.AUDIO: (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma"),
    SourceKind.VIDEO: (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"),
}
_KIND_BY_EXTENSION = {ext: kind for kind, exts in _EXTENSIONS_BY_KIND.items() for ext in exts}

QUEUE_BY_KIND = {
    ContentKind.TEXT: "queue:text",
    ContentKind.IMAGE: "queue:image",
    ContentKind.AUDIO: "queue:audio",
}

# Un video no es un ContentKind: se expande y la imagen va antes que el audio.
_CONTENT_KINDS_BY_SOURCE = {
    SourceKind.TEXT: (ContentKind.TEXT,),
    SourceKind.IMAGE: (ContentKind.IMAGE,),
    SourceKind.AUDIO: (ContentKind.AUDIO,),
    SourceKind.VIDEO: (ContentKind.IMAGE, ContentKind.AUDIO),
}


def classify_source(name: str) -> SourceKind:
    extension = PurePath(name).suffix.lower()
    if extension not in _KIND_BY_EXTENSION:
        raise ValueError(f"extension no soportada: {name}")
    return _KIND_BY_EXTENSION[extension]


def queue_for(kind: ContentKind) -> str:
    return QUEUE_BY_KIND[kind]


def decompose(
    case_id: str, sources: list[CaseSource], priority: Priority, enqueued_at: datetime
) -> list[Subtask]:
    subtasks: dict[str, Subtask] = {}
    for source in sources:
        for kind in _CONTENT_KINDS_BY_SOURCE[source.kind]:
            subtask_id = f"{case_id}:{source.sha256}:{kind.value}"
            subtasks.setdefault(
                subtask_id,
                Subtask(subtask_id, case_id, kind, source.sha256, priority, enqueued_at),
            )
    return list(subtasks.values())
