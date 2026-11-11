import json
from collections.abc import Sequence

from src.domain.finding import EvidenceRef, Finding, Severity


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
        return [_decode(raw) for raw in self._client.lrange(_key(case_id), 0, -1)]


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


def _decode(raw: str) -> Finding:
    data = json.loads(raw)
    return Finding(
        data["category"],
        Severity(data["severity"]),
        data["confidence"],
        EvidenceRef(data["sha256"], data["position"]),
        data["detail"],
    )
