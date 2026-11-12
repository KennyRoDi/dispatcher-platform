from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChatMessage:
    timestamp_utc: datetime
    sender: str
    text: str
    source_ref: str

    def __post_init__(self) -> None:
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("el mensaje exige una hora con zona horaria")
