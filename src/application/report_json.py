from src.domain.consolidated_report import ConsolidatedReport, Fragment, ReportedFinding, TimelineEvent
from src.domain.evidence_position import BoxLocator, MessageLocator, SegmentLocator, UnknownLocator


def report_to_dict(report: ConsolidatedReport) -> dict:
    return {
        "case_id": report.case_id,
        "status": report.status,
        "finalizado": report.finished,
        "generado_en": report.generated_at.isoformat(),
        "hallazgos": [_finding(item) for item in report.findings],
        "categorias": [
            {"categoria": c.category, "cantidad": c.count, "severidad_maxima": c.max_severity.value}
            for c in report.categories
        ],
        "linea_temporal": [_event(e) for e in report.timeline.dated],
        "sin_marca_absoluta": [_event(e) for e in report.timeline.undated],
        "incidencias": [
            {"tipo": i.kind, "detalle": i.detail, "sha256": i.sha256, "categoria": i.category}
            for i in report.incidents
        ],
    }


def _finding(item: ReportedFinding) -> dict:
    finding = item.finding
    return {
        "categoria": finding.category,
        "severidad": finding.severity.value,
        "confianza": finding.confidence,
        "detalle": finding.detail,
        "evidencia": [_fragment(f) for f in item.fragments],
    }


def _event(event: TimelineEvent) -> dict:
    return {"categoria": event.category, "severidad": event.severity.value, **_fragment(event.fragment)}


def _fragment(fragment: Fragment) -> dict:
    source = fragment.source
    return {
        "fuente": {"sha256": source.sha256, "file_path": source.file_path, "tipo": source.kind}
        if source
        else {"sha256": fragment.sha256, "file_path": None, "tipo": None},
        "localizador": _locator(fragment.locator),
        "timestamp_utc": fragment.timestamp_utc.isoformat() if fragment.timestamp_utc else None,
        "tramo_s": list(fragment.span_s) if fragment.span_s else None,
        "extracto": fragment.excerpt,
    }


def _locator(locator) -> dict:
    if isinstance(locator, MessageLocator):
        return {"tipo": "mensaje", "indice": locator.index, "source_ref": locator.source_ref}
    if isinstance(locator, SegmentLocator):
        return {"tipo": "segmento", "indice": locator.index, "inicio_s": locator.start_s, "fin_s": locator.end_s}
    if isinstance(locator, BoxLocator):
        return {"tipo": "caja", "x1": locator.x1, "y1": locator.y1, "x2": locator.x2, "y2": locator.y2}
    assert isinstance(locator, UnknownLocator)
    return {"tipo": "desconocido", "raw": locator.raw}
