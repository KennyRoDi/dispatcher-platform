import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from src.adapters.chat_export_generator import export_plan_chats
from src.adapters.document_generator import generate_documents
from src.adapters.hashing import sha256_de_archivo
from src.adapters.heavy_case_generator import generate_heavy_cases
from src.adapters.media_generator import LICENSE_NAME, ORIGIN, POSITIVE, Runner, generate_media, run_ffmpeg
from src.domain.dataset_plan import (
    IMAGE_CATEGORIES,
    MIN_HEAVY,
    MIN_HEAVY_BYTES,
    MIN_HETEROGENEOUS,
    DatasetParams,
    DatasetPlan,
    Level,
    plan_dataset,
)

MANIFEST_NAME = "manifest.json"
CHATS_DIR = "chats"
DEFAULT_OUT = "~/scratch/dataset"
MIN_CASES = 40
MIN_LIGHT = 5
MIN_MESSAGES = 20_000
MIN_IMAGES = 300
MIN_AUDIOS = 150
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
    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = [p for row in rows for p in _check_row(row, root)]
    return problems + _check_minimums(rows, root) + _check_declared_labels(rows)


def _check_row(row: dict, root: Path) -> list[str]:
    path, problems = row["path"], []
    if row["origen"] != ORIGIN:
        problems.append(f"{path}: origen {row['origen']!r} distinto de {ORIGIN!r}")
    if row["licencia"] != LICENSE_NAME:
        problems.append(f"{path}: licencia {row['licencia']!r} distinta de {LICENSE_NAME!r}")
    file = root / path
    if not file.is_file():
        return problems + [f"{path}: no existe"]
    if file.stat().st_size != row["bytes"]:
        return problems + [f"{path}: tiene {file.stat().st_size} bytes y el manifiesto declara {row['bytes']}"]
    if sha256_de_archivo(file) != row["sha256"]:
        problems.append(f"{path}: sha256 distinto del declarado")
    return problems


def _check_minimums(rows: list[dict], root: Path) -> list[str]:
    cases = {r["case"] for r in rows}
    by_level = {level.value: {r["case"] for r in rows if r["heterogeneo"] == level.value} for level in Level}
    heavy_files = {r["case"] for r in rows if r["bytes"] >= MIN_HEAVY_BYTES}
    heterogeneous = by_level[Level.LIGHT.value] | by_level[Level.HEAVY.value]
    durations = {r["duracion_s"] for r in rows if r["kind"] == "audio"}
    checks = [
        (len(cases), MIN_CASES, "casos"),
        (len(heterogeneous), MIN_HETEROGENEOUS, "casos heterogeneos"),
        (len(by_level[Level.LIGHT.value]), MIN_LIGHT, "casos heterogeneos livianos"),
        (len(by_level[Level.HEAVY.value]), MIN_HEAVY, "casos heterogeneos pesados"),
        (len(heavy_files), MIN_HEAVY, "casos pesados de al menos 200 MiB"),
        (sum(_count_messages(root / r["path"]) for r in rows if r["kind"] == "texto"), MIN_MESSAGES, "mensajes"),
        (sum(r["kind"] == "imagen" for r in rows), MIN_IMAGES, "imagenes"),
        (sum(r["kind"] == "audio" for r in rows), MIN_AUDIOS, "audios"),
        (len(durations), MIN_DISTINCT_DURATIONS, "duraciones de audio distintas"),
    ]
    return [f"{label}: {found} de al menos {minimum}" for found, minimum, label in checks if found < minimum]


def _count_messages(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return len(json.loads(text)["messages"])
    return len(WHATSAPP_HEADER.findall(text))


def _check_declared_labels(rows: list[dict]) -> list[str]:
    images = [r for r in rows if r["kind"] == "imagen"]
    return [
        f"categoria {category}: sin proporcion positiva declarada"
        for category in IMAGE_CATEGORIES
        if {r["positivo"] for r in images if r["categoria"] == category} != {True, False}
    ]


def main(argv: list[str] | None = None, runner: Callable[[list[str]], None] = run_ffmpeg) -> int:
    args = _parser().parse_args(argv)
    out = Path(args.out).expanduser()
    if args.validar:
        return _validate(out)
    params = DatasetParams(**json.loads(Path(args.params).read_text(encoding="utf-8"))) if args.params else DatasetParams()
    rows = build_manifest(plan_dataset(args.seed, params), out, runner)
    (out / MANIFEST_NAME).write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} archivos en {out}")
    return 0


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
