from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


@dataclass(frozen=True)
class EvidenceRef:
    object_sha256: str
    position: str


@dataclass(frozen=True)
class Finding:
    category: str
    severity: Severity
    confidence: float
    evidence: EvidenceRef
    detail: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confianza fuera de rango: {self.confidence}")
