import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from src.application.ports import ObjectStore
from src.domain.custody_chain import Anchor, Violation, verify_chain

INGRESO = "ingreso"
CHAIN_BREAKS = frozenset(("entrada", "enlace", "sello"))
READ_BLOCK = 1 << 20


class KeyProvider(Protocol):
    def kek(self) -> bytes: ...


@dataclass
class VerificationReport:
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def verify_custody(
    lines: Sequence[str], anchor: Anchor | None, key_provider: KeyProvider, store: ObjectStore | None
) -> VerificationReport:
    key = key_provider.kek()
    violations = verify_chain(lines, key, anchor)
    # Tras un eslabón roto los siguientes no son confiables: linaje y evidencia solo miran los anteriores.
    broken = next((v.position for v in violations if v.kind in CHAIN_BREAKS), len(lines) + 1)
    entries = [json.loads(line) for line in lines[: broken - 1]]
    violations += _lineage(entries)
    if store is not None:
        violations += _evidence(entries, store)
    return VerificationReport(violations)


def _lineage(entries: list[dict]) -> list[Violation]:
    known: set[str] = set()
    found = []
    for position, entry in enumerate(entries, start=1):
        if entry["operation"] == INGRESO:
            known.add(entry["evidence_sha256"])
        elif entry["evidence_sha256"] not in known:
            found.append(Violation(position, "linaje", f"parte de {entry['evidence_sha256']}, que no fue ingresada ni producida antes"))
        known.add(entry["result_sha256"])
    return found


def _evidence(entries: list[dict], store: ObjectStore) -> list[Violation]:
    found = []
    for position, entry in enumerate(entries, start=1):
        expected = entry["result_sha256"]
        if not store.exists(expected):
            # Un resultado intermedio puede no haberse guardado; solo el ingreso debe existir.
            if entry["operation"] == INGRESO:
                found.append(Violation(position, "evidencia", f"falta el objeto {expected}"))
        elif (actual := _sha256_of(store, expected)) != expected:
            found.append(Violation(position, "evidencia", f"se esperaba {expected} y el objeto tiene {actual}"))
    return found


def _sha256_of(store: ObjectStore, sha256: str) -> str:
    digest = hashlib.sha256()
    with store.open(sha256) as stream:
        while block := stream.read(READ_BLOCK):
            digest.update(block)
    return digest.hexdigest()
