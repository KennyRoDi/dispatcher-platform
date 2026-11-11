import json
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Iterable

from src.domain.finding import Finding, Severity

HIGH_INCIDENT = "incidencia_alta"
CASE_CLOSED = "caso_finalizado"

# Repite los estados terminales del coordinador para no depender de él; cancelled no alerta (SUP-35).
ALERTING_STATUSES = frozenset({"completed", "partially_completed", "failed"})


@dataclass(frozen=True)
class Alert:
    kind: str
    case_id: str
    detail: str


@dataclass(frozen=True)
class StoredAlert:
    alert_id: str
    kind: str
    case_id: str
    detail: str
    emitted_at: datetime


def high_incident_alerts(case_id: str, findings: Iterable[Finding]) -> list[Alert]:
    return [_incident(case_id, f) for f in findings if f.severity is Severity.ALTA]


def case_closed_alert(case_id: str, status: str) -> Alert:
    if not isinstance(status, str) or status not in ALERTING_STATUSES:
        raise ValueError(f"estado sin alerta de cierre: {status!r}")
    return Alert(CASE_CLOSED, case_id, json.dumps({"estado": status}))


def _incident(case_id: str, finding: Finding) -> Alert:
    # No copia Finding.detail: puede contener texto de mensajes.
    detail = {
        "categoria": finding.category,
        "confianza": finding.confidence,
        "sha256": finding.evidence.object_sha256,
        "posicion": finding.evidence.position,
    }
    return Alert(HIGH_INCIDENT, case_id, json.dumps(detail))
