import json
import logging
from collections.abc import Sequence

from src.domain.finding import EvidenceRef, Finding, Severity

logger = logging.getLogger(__name__)


class RedisFindingStore:
    def __init__(self, client) -> None:
        self._client = client

    def add(self, case_id: str, findings: Sequence[Finding]) -> None:
        if not findings:
            return
        pipe = self._client.pipeline()
        pipe.rpush(_key(case_id), *(_encode(f) for f in findings))
        pipe.execute()

    def list(self, case_id: str) -> list[Finding]:
        decoded = [_decode(raw) for raw in self._client.lrange(_key(case_id), 0, -1)]
        valid = [finding for finding in decoded if finding is not None]
        if len(valid) < len(decoded):
            logger.warning("Caso %s: %d hallazgos ilegibles omitidos", case_id, len(decoded) - len(valid))
        return valid


def _key(case_id: str) -> str:
    return f"case:{case_id}:findings"


def _encode(finding: Finding) -> str:
    return json.dumps(
        {
            "category": finding.category,
            "severity": finding.severity.value,
            "confidence": finding.confidence,
            "sha256": finding.evidence.object_sha256,
            "position": finding.evidence.position,
            "detail": finding.detail,
        },
        ensure_ascii=False,
    )


def _decode(raw: str) -> Finding | None:
    try:
        data = json.loads(raw)
        texts = (data["category"], data["sha256"], data["position"], data["detail"])
        confidence = data["confidence"]
        if not all(isinstance(text, str) for text in texts) or isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return None
        return Finding(
            data["category"], Severity(data["severity"]), confidence, EvidenceRef(data["sha256"], data["position"]), data["detail"]
        )
    except (ValueError, TypeError, KeyError):
        return None
