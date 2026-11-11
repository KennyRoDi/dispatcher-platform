from dataclasses import replace
from datetime import timezone

from src.application.analyze_audio import CATEGORIA_TRANSCRIPCION
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


MAX_EXCERPT_CHARS = 10_000
TRUNCATION_MARK = "…[truncado]"


class CaseNotFound(Exception):
    pass


def build_report(
    case_id: str, findings: FindingStore, catalog: CaseCatalog, store: ObjectStore, clock: Clock
) -> ConsolidatedReport:
    case = catalog.case(case_id)
    if case is None:
        raise CaseNotFound(case_id)
    stored = findings.list(case_id)
    exists = _CachedExists(store)
    reported = tuple(ReportedFinding(f, _fragments(f, case, exists)) for f in stored)
    return ConsolidatedReport(
        case_id=case.case_id,
        status=case.status,
        finished=case.finished,
        generated_at=clock.now().astimezone(timezone.utc),
        findings=reported,
        categories=category_summary(stored),
        timeline=build_timeline(reported),
        incidents=find_incidents(reported, case),
    )


class _CachedExists:
    def __init__(self, store: ObjectStore) -> None:
        self._store = store
        self._known: dict[str, bool] = {}

    def __call__(self, sha: str) -> bool:
        if sha not in self._known:
            try:
                self._known[sha] = self._store.exists(sha)
            except Exception:
                # Almacén caído: el objeto queda como no verificable y el reporte sigue.
                self._known[sha] = False
        return self._known[sha]


def _fragments(finding: Finding, case: CaseInfo, exists: _CachedExists) -> tuple[Fragment, ...]:
    locators = parse_position(finding)
    if not locators:
        return ()
    sha = finding.evidence.object_sha256
    source, in_store = _source(case, sha), exists(sha)
    return tuple(_fragment(finding, locator, source, in_store) for locator in locators)


def _fragment(finding, locator, source: CaseSource | None, in_store: bool) -> Fragment:
    timestamp = locator.timestamp_utc if isinstance(locator, MessageLocator) else None
    is_segment = isinstance(locator, SegmentLocator)
    # Solo la transcripción trae el texto del segmento en detail; en otras categorías es metadato de posiciones.
    has_text = is_segment and finding.category == CATEGORIA_TRANSCRIPCION
    return Fragment(
        sha256=finding.evidence.object_sha256,
        source=source,
        locator=locator,
        timestamp_utc=timestamp,
        span_s=(locator.start_s, locator.end_s) if is_segment else None,
        excerpt=_limited(finding.detail) if has_text else "",
        in_store=in_store,
    )


def _limited(text: str) -> str:
    if len(text) <= MAX_EXCERPT_CHARS:
        return text
    return text[: MAX_EXCERPT_CHARS - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def _source(case: CaseInfo, sha: str) -> CaseSource | None:
    if not sha:
        return None
    # El almacén es direccionado por contenido: file_path igual al sha256 identifica la fuente si falta source_sha256.
    by_hash = next((s for s in case.sources if s.sha256 == sha), None)
    if by_hash:
        return by_hash
    by_path = next((s for s in case.sources if s.file_path == sha), None)
    return replace(by_path, sha256=sha) if by_path else None
