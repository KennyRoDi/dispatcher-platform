import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.adapters.media_generator import NEUTRAL, POSITIVE
from src.domain.ground_truth import Comparison, GroundTruthItem, ObservedItem
from src.domain.provenance import SourceRecord

IMAGE_KIND = "imagen"
NOT_DEFINED = "n/d"
HEADERS = ("categoria", "aciertos", "errores", "precision", "exhaustividad")


def read_manifest_records(path: Path) -> list[SourceRecord]:
    return [_source_record(row) for row in _read_rows(path)]


def read_sample_records(path: Path) -> list[SourceRecord]:
    return read_manifest_records(path)


def read_sample_truth(path: Path) -> list[GroundTruthItem]:
    return [GroundTruthItem(row["path"], _text_set(row, "esperadas")) for row in _read_rows(path)]


def read_observed(path: Path) -> list[ObservedItem]:
    return [ObservedItem(row["path"], _text_set(row, "categorias")) for row in _read_rows(path)]


def sample_from_manifest(rows: Iterable[dict]) -> list[dict]:
    labeled = (row for row in rows if _is_labeled_image(row))
    return [
        {
            "path": row["path"],
            "kind": IMAGE_KIND,
            "origen": row["origen"],
            "licencia": row["licencia"],
            "esperadas": [row["categoria"]] if row["etiqueta"] == POSITIVE else [],
        }
        for row in labeled
    ]


def render_text(comparison: Comparison) -> str:
    table = [HEADERS, *_score_rows(comparison)]
    widths = [max(len(row[column]) for row in table) for column in range(len(HEADERS))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in table]
    return "\n".join([*lines, "", _summary(comparison)])


def render_markdown(comparison: Comparison) -> str:
    separator = ["---"] * len(HEADERS)
    rows = [tuple(_escape_cell(cell) for cell in row) for row in _score_rows(comparison)]
    table = [HEADERS, separator, *rows]
    lines = ["| " + " | ".join(row) + " |" for row in table]
    return "\n".join([*lines, "", _summary(comparison)])


def _escape_cell(cell: str) -> str:
    return " ".join(cell.replace("|", "\\|").split())


def _is_labeled_image(row: dict) -> bool:
    return (
        row.get("kind") == IMAGE_KIND
        and row.get("etiqueta") in (POSITIVE, NEUTRAL)
        and isinstance(row.get("categoria"), str)
    )


def _read_rows(path: Path) -> list[dict]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as error:
        raise ValueError(f"{path}: JSON ilegible: {error}") from error
    if not isinstance(raw, list):
        raise ValueError(f"{path}: se esperaba una lista de objetos")
    for row in raw:
        _check_row(row, path)
    return raw


def _check_row(row: Any, source: Path) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"{source}: cada elemento debe ser un objeto, no {row!r}")
    item_path = row.get("path")
    if not isinstance(item_path, str) or not _is_safe(item_path):
        raise ValueError(f"{source}: ruta invalida {item_path!r}")


def _is_safe(item_path: str) -> bool:
    location = Path(item_path)
    if "\x00" in item_path or location.is_absolute():
        return False
    return bool(item_path) and ".." not in location.parts


def _source_record(row: dict) -> SourceRecord:
    return SourceRecord(row["path"], _optional_text(row, "origen"), _optional_text(row, "licencia"))


def _optional_text(row: dict, field: str) -> str | None:
    value = row.get(field)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{row['path']}: {field} debe ser texto, no {value!r}")
    return value


def _text_set(row: dict, field: str) -> frozenset[str]:
    values = row.get(field)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{row['path']}: {field} debe ser una lista de texto, no {values!r}")
    return frozenset(values)


def _score_rows(comparison: Comparison) -> list[tuple[str, ...]]:
    return [
        (
            score.category,
            str(score.hits),
            str(score.errors),
            _percent(score.precision),
            _percent(score.recall),
        )
        for score in comparison.scores
    ]


def _percent(value: float | None) -> str:
    return NOT_DEFINED if value is None else f"{value:.1%}"


def _summary(comparison: Comparison) -> str:
    return (
        f"Muestra: {comparison.total} elementos. "
        f"Exactitud (coincidencia exacta): {_percent(comparison.accuracy)}"
    )
