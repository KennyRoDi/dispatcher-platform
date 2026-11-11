from src.application.ports import CaseCatalog, Clock, FindingStore, ObjectStore
from src.domain.consolidated_report import (
    CaseInfo,
    CaseSource,
    ConsolidatedReport,
    Fragment,
    ReportedFinding,
    build_timeline,
    category_summary,
    find_incidents,
)
from src.domain.evidence_position import MessageLocator, SegmentLocator, parse_position
from src.domain.finding import Finding


class CaseNotFound(Exception):
    pass


def build_report(
    case_id: str, findings: FindingStore, catalog: CaseCatalog, store: ObjectStore, clock: Clock
) -> ConsolidatedReport:
    case = catalog.case(case_id)
    if case is None:
        raise CaseNotFound(case_id)
    stored = findings.list(case_id)
    reported = tuple(ReportedFinding(f, _fragments(f, case, store)) for f in stored)
    return ConsolidatedReport(
        case_id=case.case_id,
        status=case.status,
        finished=case.finished,
        generated_at=clock.now(),
        findings=reported,
        categories=category_summary(stored),
        timeline=build_timeline(reported),
        incidents=find_incidents(reported, case),
    )


def _fragments(finding: Finding, case: CaseInfo, store: ObjectStore) -> tuple[Fragment, ...]:
    sha = finding.evidence.object_sha256
    source = _source(case, sha)
    in_store = store.exists(sha)
    return tuple(_fragment(finding, locator, source, in_store) for locator in parse_position(finding))


def _fragment(finding, locator, source: CaseSource | None, in_store: bool) -> Fragment:
    timestamp = locator.timestamp_utc if isinstance(locator, MessageLocator) else None
    is_segment = isinstance(locator, SegmentLocator)
    return Fragment(
        sha256=finding.evidence.object_sha256,
        source=source,
        locator=locator,
        timestamp_utc=timestamp,
        span_s=(locator.start_s, locator.end_s) if is_segment else None,
        excerpt=finding.detail if is_segment else "",
        in_store=in_store,
    )


def _source(case: CaseInfo, sha: str) -> CaseSource | None:
    # El almacén es direccionado por contenido: file_path igual al sha256 identifica la fuente si falta source_sha256.
    by_hash = next((s for s in case.sources if s.sha256 == sha), None)
    return by_hash or next((s for s in case.sources if s.file_path == sha), None)
