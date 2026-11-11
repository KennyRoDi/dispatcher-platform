from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecord:
    path: str
    origin: str | None
    license: str | None


@dataclass(frozen=True)
class ProvenancePolicy:
    admitted_origins: tuple[str, ...] = ("sintetico", "propio", "publico")
    public_licenses: tuple[str, ...] = (
        "CC0-1.0",
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "MIT",
        "Apache-2.0",
    )
    rejected_licenses: tuple[str, ...] = (
        "desconocida",
        "ninguna",
        "sin licencia",
        "n/a",
        "-",
    )


PUBLIC_ORIGIN = "publico"


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _origin_defect(record: SourceRecord, policy: ProvenancePolicy) -> str | None:
    admitted = {_normalized(origin) for origin in policy.admitted_origins}
    if _normalized(record.origin) in admitted:
        return None
    return f"{record.path}: origen no admitido ({record.origin!r})"


def _license_defect(record: SourceRecord, policy: ProvenancePolicy) -> str | None:
    license_name = _normalized(record.license)
    if not license_name:
        return f"{record.path}: falta la licencia"
    if license_name in {_normalized(name) for name in policy.rejected_licenses}:
        return f"{record.path}: licencia de relleno ({record.license.strip()!r})"
    public = {_normalized(name) for name in policy.public_licenses}
    if _normalized(record.origin) == PUBLIC_ORIGIN and license_name not in public:
        return f"{record.path}: licencia no admitida en fuente publica ({record.license.strip()!r})"
    return None


def validate_provenance(
    records: list[SourceRecord], policy: ProvenancePolicy = ProvenancePolicy()
) -> list[str]:
    checks = (_origin_defect, _license_defect)
    defects = (check(record, policy) for record in records for check in checks)
    return [defect for defect in defects if defect]
