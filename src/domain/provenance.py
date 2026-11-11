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

    def __post_init__(self) -> None:
        for field_name in ("admitted_origins", "public_licenses", "rejected_licenses"):
            _require_text_tuple(field_name, getattr(self, field_name))


PUBLIC_ORIGIN = "publico"


def _require_text_tuple(field_name: str, values: object) -> None:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} debe ser una tupla de texto, no {values!r}")
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} solo admite texto no vacio, no {value!r}")


def _normalized(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _origin_defect(record: SourceRecord, policy: ProvenancePolicy) -> str | None:
    if record.origin is not None and not isinstance(record.origin, str):
        return f"{record.path}: el origen debe ser texto ({record.origin!r})"
    admitted = {_normalized(origin) for origin in policy.admitted_origins}
    if _normalized(record.origin) in admitted:
        return None
    return f"{record.path}: origen no admitido ({record.origin!r})"


def _license_defect(record: SourceRecord, policy: ProvenancePolicy) -> str | None:
    if record.license is not None and not isinstance(record.license, str):
        return f"{record.path}: la licencia debe ser texto ({record.license!r})"
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
