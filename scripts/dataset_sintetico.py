import argparse
import dataclasses
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath

from src.adapters.chat_export_generator import export_plan_chats
from src.adapters.document_generator import generate_documents
from src.adapters.hashing import sha256_de_archivo
from src.adapters.heavy_case_generator import generate_heavy_cases
from src.adapters.media_generator import LICENSE_NAME, ORIGIN, POSITIVE, Runner, generate_media, run_ffmpeg
from src.domain.dataset_plan import (
    IMAGE_CATEGORIES,
    MIN_AUDIOS,
    MIN_CASES,
    MIN_HEAVY,
    MIN_HEAVY_BYTES,
    MIN_HETEROGENEOUS,
    MIN_IMAGES,
    MIN_MESSAGES,
    DatasetParams,
    DatasetPlan,
    Level,
    plan_dataset,
)

MANIFEST_NAME = "manifest.json"
MANIFEST_FIELDS = (
    "case",
    "kind",
    "path",
    "bytes",
    "sha256",
    "origen",
    "licencia",
    "semilla",
    "etiqueta",
    "heterogeneo",
    "categoria",
    "positivo",
    "duracion_s",
)
REQUIRED_KINDS = {
    Level.LIGHT.value: ("texto", "imagen", "audio", "documento"),
    Level.HEAVY.value: ("texto", "imagen", "audio", "video"),
}
CHATS_DIR = "chats"
DEFAULT_OUT = "~/scratch/dataset"
MIN_LIGHT = 5
MIN_DISTINCT_DURATIONS = 2
WHATSAPP_HEADER = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}, \d{2}:\d{2} - ", re.MULTILINE)


def build_manifest(plan: DatasetPlan, out_dir: Path, runner: Runner = run_ffmpeg) -> list[dict]:
    levels = {case.name: case.heterogeneo for case in plan.cases}

    def row(case: str, kind: str, path: Path, etiqueta=None, categoria=None, duracion_s=None) -> dict:
        return {
            "case": case,
            "kind": kind,
            "path": path.relative_to(out_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_de_archivo(path),
            "origen": ORIGIN,
            "licencia": LICENSE_NAME,
            "semilla": plan.seed,
            "etiqueta": etiqueta,
            "heterogeneo": levels[case],
            "categoria": categoria,
            "positivo": etiqueta == POSITIVE if kind == "imagen" else None,
            "duracion_s": duracion_s,
        }

    rows = [row(case, "texto", path) for case, path in export_plan_chats(plan, out_dir / CHATS_DIR).items()]
    rows += [row(f.case, f.kind, f.path, f.etiqueta, f.categoria, f.duration_s) for f in generate_media(plan, out_dir, runner)]
    rows += [row(f.case, f.kind, f.path) for f in generate_heavy_cases(plan, out_dir, runner)]
    rows += [row(f.case, f.kind, f.path) for f in generate_documents(plan, out_dir)]
    return sorted(rows, key=lambda r: (r["case"], r["path"]))


def validate_manifest(manifest_path: Path) -> list[str]:
    root = manifest_path.parent
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{manifest_path.name}: manifiesto ilegible: {error}"]
    if not isinstance(raw, list):
        return [f"{manifest_path.name}: se esperaba una lista de filas"]
    rows, problems = _usable_rows(raw)
    problems += [p for row in rows for p in _check_row(row, root)]
    minimums, message_problems = _check_minimums(rows, root)
    return problems + minimums + message_problems + _check_kinds(rows) + _check_declared_labels(rows)


def _usable_rows(raw: list) -> tuple[list[dict], list[str]]:
    rows, problems, seen = [], [], set()
    for index, row in enumerate(raw):
        defect = _row_defect(row)
        if defect:
            problems.append(f"fila {index}: {defect}")
        elif Path(row["path"]).as_posix() in seen:
            problems.append(f"{row['path']}: fila duplicada")
        else:
            seen.add(Path(row["path"]).as_posix())
            rows.append(row)
    return rows, problems


def _row_defect(row) -> str | None:
    if not isinstance(row, dict):
        return "no es un objeto"
    missing = [name for name in MANIFEST_FIELDS if name not in row]
    if missing:
        return f"faltan campos {missing}"
    if not isinstance(row["path"], str) or "\x00" in row["path"] or any(
        ruta.root or ruta.drive or ".." in ruta.parts
        for ruta in (PurePosixPath(row["path"]), PureWindowsPath(row["path"]))
    ):
        return f"ruta invalida {row['path']!r}"
    if not all(value is None or isinstance(value, (str, int, float)) for value in row.values()):
        return "hay valores que no son escalares"
    if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int):
        return f"{row['path']}: bytes debe ser un entero, no {row['bytes']!r}"
    if not isinstance(row["case"], str):
        return f"{row['path']}: case debe ser una cadena, no {row['case']!r}"
    return None


def _check_row(row: dict, root: Path) -> list[str]:
    path, problems = row["path"], []
    if row["origen"] != ORIGIN:
        problems.append(f"{path}: origen {row['origen']!r} distinto de {ORIGIN!r}")
    if row["licencia"] != LICENSE_NAME:
        problems.append(f"{path}: licencia {row['licencia']!r} distinta de {LICENSE_NAME!r}")
    file = root / path
    try:
        if not file.resolve().is_relative_to(root.resolve()):
            return problems + [f"{path}: apunta fuera del directorio del manifiesto"]
    except UnicodeError:
        return problems + [f"{path}: ruta con caracteres no codificables"]
    try:
        if not file.is_file():
            return problems + [f"{path}: no existe"]
        size = file.stat().st_size
        if size != row["bytes"]:
            return problems + [f"{path}: tiene {size} bytes y el manifiesto declara {row['bytes']}"]
        if sha256_de_archivo(file) != row["sha256"]:
            problems.append(f"{path}: sha256 distinto del declarado")
    except OSError as error:
        problems.append(f"{path}: no se pudo leer ({error.strerror})")
    return problems


def _check_minimums(rows: list[dict], root: Path) -> tuple[list[str], list[str]]:
    cases = {r["case"] for r in rows}
    by_level = {level.value: {r["case"] for r in rows if r["heterogeneo"] == level.value} for level in Level}
    heavy_files = {r["case"] for r in rows if r["bytes"] >= MIN_HEAVY_BYTES and r["heterogeneo"] == Level.HEAVY.value}
    heterogeneous = by_level[Level.LIGHT.value] | by_level[Level.HEAVY.value]
    durations = {r["duracion_s"] for r in rows if r["kind"] == "audio"}
    messages, message_problems = _count_messages(rows, root)
    checks = [
        (len(cases), MIN_CASES, "casos"),
        (len(heterogeneous), MIN_HETEROGENEOUS, "casos heterogeneos"),
        (len(by_level[Level.LIGHT.value]), MIN_LIGHT, "casos heterogeneos livianos"),
        (len(by_level[Level.HEAVY.value]), MIN_HEAVY, "casos heterogeneos pesados"),
        (len(heavy_files), MIN_HEAVY, "casos pesados de al menos 200 MiB"),
        (messages, MIN_MESSAGES, "mensajes"),
        (sum(r["kind"] == "imagen" for r in rows), MIN_IMAGES, "imagenes"),
        (sum(r["kind"] == "audio" for r in rows), MIN_AUDIOS, "audios"),
        (len(durations), MIN_DISTINCT_DURATIONS, "duraciones de audio distintas"),
    ]
    return [f"{label}: {found} de al menos {minimum}" for found, minimum, label in checks if found < minimum], message_problems


def _count_messages(rows: list[dict], root: Path) -> tuple[int, list[str]]:
    total, problems = 0, []
    for row in (r for r in rows if r["kind"] == "texto" and (root / r["path"]).is_file()):
        try:
            total += _messages_in(root / row["path"])
        except (ValueError, KeyError, TypeError) as error:
            problems.append(f"{row['path']}: no se pudieron contar los mensajes ({type(error).__name__}: {error})")
    return total, problems


def _messages_in(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return len(json.loads(text)["messages"])
    return len(WHATSAPP_HEADER.findall(text))


def _check_kinds(rows: list[dict]) -> list[str]:
    problems = []
    for level, required in REQUIRED_KINDS.items():
        for case in sorted({r["case"] for r in rows if r["heterogeneo"] == level}):
            present = {r["kind"] for r in rows if r["case"] == case}
            missing = [kind for kind in required if kind not in present]
            if missing:
                problems.append(f"{case}: caso heterogeneo {level} sin los tipos {', '.join(missing)}")
    return problems


def _check_declared_labels(rows: list[dict]) -> list[str]:
    images = [r for r in rows if r["kind"] == "imagen"]
    return [
        f"categoria {category}: sin proporcion positiva declarada"
        for category in IMAGE_CATEGORIES
        if {r["positivo"] for r in images if r["categoria"] == category} != {True, False}
    ]


def main(argv: list[str] | None = None, runner: Callable[[list[str]], None] = run_ffmpeg) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    out = Path(args.out).expanduser()
    if args.validar:
        return _validate(out)
    try:
        params = _load_params(args.params)
    except ValueError as error:
        parser.error(f"--params: {error}")
    if (out.exists() or out.is_symlink()) and not out.is_dir():
        parser.error(f"--out: {out} no es un directorio")
    rows = _generate(plan_dataset(args.seed, params), out, runner)
    print(f"{len(rows)} archivos en {out}")
    return 0


def _generate(plan: DatasetPlan, out: Path, runner: Runner) -> list[dict]:
    created_dirs = [directory for directory in (out, *out.parents) if not directory.exists()]
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.rglob("*"))
    try:
        links = sorted(str(path) for path in before if path.is_symlink())
        if links:
            raise RuntimeError(f"--out contiene enlaces simbolicos que no se siguen: {links}")
        (out / MANIFEST_NAME).unlink(missing_ok=True)
        before.discard(out / MANIFEST_NAME)
        rows = build_manifest(plan, out, runner)
        (out / MANIFEST_NAME).write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except BaseException:
        _remove_created(out, before, created_dirs)
        raise
    return rows


def _remove_created(out: Path, before: set[Path], created_dirs: list[Path]) -> None:
    for path in sorted(set(out.rglob("*")) - before, reverse=True):
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
        else:
            path.unlink()
    for directory in created_dirs:
        directory.rmdir()


def _load_params(path: str | None) -> DatasetParams:
    if path is None:
        return DatasetParams()
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"no se pudo leer {path}: {error.strerror}") from error
    names = {field.name for field in dataclasses.fields(DatasetParams)}
    if not isinstance(raw, dict) or not set(raw) <= names:
        raise ValueError(f"se esperaba un objeto con las claves {sorted(names)}")
    for name, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} debe ser un entero no negativo, no {value!r}")
    return DatasetParams(**raw)


def _validate(out: Path) -> int:
    manifest = out / MANIFEST_NAME
    if not manifest.is_file():
        print(f"no existe {manifest}")
        return 1
    problems = validate_manifest(manifest)
    print("\n".join(problems) if problems else f"{manifest}: cumple los minimos de B.3")
    return 1 if problems else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera y valida el dataset sintetico de F-03.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", required=True, help=f"directorio de salida, fuera del repo (p. ej. {DEFAULT_OUT})")
    parser.add_argument("--params", help="JSON con campos de DatasetParams")
    parser.add_argument("--validar", action="store_true", help="valida <out>/manifest.json y no genera")
    return parser


if __name__ == "__main__":
    sys.exit(main())
