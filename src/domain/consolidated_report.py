import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.domain.evidence_position import BoxLocator, Locator, MessageLocator, SegmentLocator, UnknownLocator
from src.domain.finding import Finding, Severity

# Mismo conjunto que TERMINAL_CASE_STATUSES de src/coordinator/apoyo.py; se repite para no depender del coordinador.
TERMINAL_CASE_STATUSES = frozenset({"completed", "partially_completed", "failed", "cancelled"})

SEVERIDAD_ALTA = "severidad_alta"
SUBTAREA_FALLIDA = "subtarea_fallida"
EVIDENCIA_SIN_FUENTE = "evidencia_sin_fuente"
OBJETO_INEXISTENTE = "objeto_inexistente"
ALMACEN_NO_VERIFICABLE = "almacen_no_verificable"
HALLAZGOS_ILEGIBLES = "hallazgos_ilegibles"
POSICION_DESCONOCIDA = "posicion_desconocida"
_ORDEN_DE_INCIDENCIAS = (
    SEVERIDAD_ALTA,
    SUBTAREA_FALLIDA,
    EVIDENCIA_SIN_FUENTE,
    OBJETO_INEXISTENTE,
    ALMACEN_NO_VERIFICABLE,
    HALLAZGOS_ILEGIBLES,
    POSICION_DESCONOCIDA,
)
_RANGO_DE_SEVERIDAD = {Severity.BAJA: 0, Severity.MEDIA: 1, Severity.ALTA: 2}


@dataclass(frozen=True)
class CaseSource:
    sha256: str
    file_path: str
    kind: str
    status: str
    error_type: str | None = None


@dataclass(frozen=True)
class CaseInfo:
    case_id: str
    status: str
    created_at: datetime | None
    finished_at: datetime | None
    sources: tuple[CaseSource, ...]

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL_CASE_STATUSES


@dataclass(frozen=True)
class Fragment:
    sha256: str
    source: CaseSource | None
    locator: Locator
    timestamp_utc: datetime | None = None
    span_s: tuple[float, float] | None = None
    excerpt: str = ""
    in_store: bool | None = True

    def __post_init__(self) -> None:
        if self.timestamp_utc is None:
            return
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("la marca del fragmento exige zona horaria")
        try:
            object.__setattr__(self, "timestamp_utc", self.timestamp_utc.astimezone(timezone.utc))
        except OverflowError as error:
            raise ValueError("la marca del fragmento no cabe en UTC") from error


@dataclass(frozen=True)
class ReportedFinding:
    finding: Finding
    fragments: tuple[Fragment, ...]


@dataclass(frozen=True)
class CategorySummary:
    category: str
    count: int
    max_severity: Severity


@dataclass(frozen=True)
class TimelineEvent:
    category: str
    severity: Severity
    fragment: Fragment


@dataclass(frozen=True)
class Timeline:
    dated: tuple[TimelineEvent, ...]
    undated: tuple[TimelineEvent, ...]


@dataclass(frozen=True)
class Incident:
    kind: str
    detail: str
    sha256: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ConsolidatedReport:
    case_id: str
    status: str
    finished: bool
    generated_at: datetime
    findings: tuple[ReportedFinding, ...]
    categories: tuple[CategorySummary, ...]
    timeline: Timeline
    incidents: tuple[Incident, ...]


def category_summary(findings: Sequence[Finding]) -> tuple[CategorySummary, ...]:
    conteo = Counter(finding.category for finding in findings)
    return tuple(
        CategorySummary(categoria, conteo[categoria], _severidad_maxima(findings, categoria))
        for categoria in sorted(conteo)
    )


def _severidad_maxima(findings: Sequence[Finding], categoria: str) -> Severity:
    return max((f.severity for f in findings if f.category == categoria), key=_RANGO_DE_SEVERIDAD.__getitem__)


def build_timeline(reported: Sequence[ReportedFinding]) -> Timeline:
    eventos = [
        TimelineEvent(item.finding.category, item.finding.severity, fragmento)
        for item in reported
        for fragmento in item.fragments
    ]
    con_hora = [evento for evento in eventos if evento.fragment.timestamp_utc is not None]
    sin_hora = [evento for evento in eventos if evento.fragment.timestamp_utc is None]
    return Timeline(
        tuple(sorted(con_hora, key=_clave_con_hora)),
        tuple(sorted(sin_hora, key=_clave_sin_hora)),
    )


def _clave_con_hora(evento: TimelineEvent) -> tuple[Any, ...]:
    fragmento = evento.fragment
    return (fragmento.timestamp_utc, fragmento.sha256, _clave_de_posicion(fragmento.locator), *_desempate(evento))


def _clave_sin_hora(evento: TimelineEvent) -> tuple[Any, ...]:
    fragmento = evento.fragment
    ruta = fragmento.source.file_path if fragmento.source else ""
    inicio = fragmento.locator.start_s if isinstance(fragmento.locator, SegmentLocator) else 0.0
    # NaN no es comparable: sin esta separación sorted daría un orden que depende de la entrada.
    inicio_ordenable = (math.isnan(inicio), 0.0 if math.isnan(inicio) else inicio)
    return (ruta, inicio_ordenable, fragmento.sha256, _clave_de_posicion(fragmento.locator), *_desempate(evento))


def _desempate(evento: TimelineEvent) -> tuple[Any, ...]:
    return evento.category, _RANGO_DE_SEVERIDAD[evento.severity], repr(evento.fragment)


def _clave_de_posicion(locador: Locator) -> tuple[Any, ...]:
    if isinstance(locador, (MessageLocator, SegmentLocator)):
        return (locador.index,)
    if isinstance(locador, BoxLocator):
        return (locador.x1, locador.y1, locador.x2, locador.y2)
    return ()


def find_incidents(
    reported: Sequence[ReportedFinding], case: CaseInfo, unreadable_findings: int = 0
) -> tuple[Incident, ...]:
    incidencias = {incidencia for item in reported for incidencia in _del_hallazgo(item)}
    incidencias.update(_de_subtareas_fallidas(case))
    if unreadable_findings > 0:
        detalle = f"{unreadable_findings} hallazgos ilegibles omitidos del reporte"
        incidencias.add(Incident(HALLAZGOS_ILEGIBLES, detalle))
    return tuple(sorted(incidencias, key=_clave_de_incidencia))


def _del_hallazgo(item: ReportedFinding) -> list[Incident]:
    finding = item.finding
    sha, categoria = finding.evidence.object_sha256, finding.category
    incidencias = []
    if finding.severity is Severity.ALTA:
        detalle = f"hallazgo de severidad alta: {categoria} en {finding.evidence.position}"
        incidencias.append(Incident(SEVERIDAD_ALTA, detalle, sha, categoria))
    for fragmento in item.fragments:
        incidencias.extend(_del_fragmento(fragmento, categoria))
    return incidencias


def _del_fragmento(fragmento: Fragment, categoria: str) -> list[Incident]:
    sha = fragmento.sha256
    incidencias = []
    if fragmento.source is None:
        detalle = f"la evidencia {sha} no está en el caso"
        incidencias.append(Incident(EVIDENCIA_SIN_FUENTE, detalle, sha, categoria))
    elif fragmento.in_store is False:
        detalle = f"el objeto {sha} no existe en el almacén"
        incidencias.append(Incident(OBJETO_INEXISTENTE, detalle, sha, categoria))
    elif fragmento.in_store is None:
        detalle = f"no se pudo verificar el objeto {sha} en el almacén"
        incidencias.append(Incident(ALMACEN_NO_VERIFICABLE, detalle, sha, categoria))
    if isinstance(fragmento.locator, UnknownLocator):
        detalle = f"posición no reconocida: {fragmento.locator.raw!r}"
        incidencias.append(Incident(POSICION_DESCONOCIDA, detalle, sha, categoria))
    return incidencias


def _de_subtareas_fallidas(case: CaseInfo) -> list[Incident]:
    return [
        Incident(SUBTAREA_FALLIDA, _detalle_de_fallo(fuente), fuente.sha256)
        for fuente in case.sources
        if fuente.status == "failed"
    ]


def _detalle_de_fallo(fuente: CaseSource) -> str:
    return f"{fuente.file_path} falló: {fuente.error_type or 'sin tipo de error'}"


def _clave_de_incidencia(incidencia: Incident) -> tuple[Any, ...]:
    orden = _ORDEN_DE_INCIDENCIAS.index(incidencia.kind)
    return orden, incidencia.sha256 or "", incidencia.category or "", incidencia.detail
