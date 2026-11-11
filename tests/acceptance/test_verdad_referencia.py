import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, build_manifest
from scripts.dataset_verdad import main
from src.adapters.dataset_truth_files import read_observed, read_sample_truth, render_text, sample_from_manifest
from src.domain.dataset_plan import IMAGE_CATEGORIES, DatasetParams, plan_dataset
from src.domain.ground_truth import compare

pytestmark = pytest.mark.acceptance

RAIZ = Path(__file__).resolve().parents[2]
REAL_MANIFEST = Path(os.environ["DATASET_OUT"]).expanduser() / MANIFEST_NAME if "DATASET_OUT" in os.environ else RAIZ / "dataset" / "sintetico" / MANIFEST_NAME
REDUCED = DatasetParams(
    cases=8,
    light_heterogeneous=2,
    heavy_heterogeneous=2,
    messages=200,
    images=60,
    audios=24,
    heavy_bytes=1024,
)
VIDEO_SUFFIX = ".mpg"


class DobleDeEjecutor:
    """Doble de prueba: escribe bytes deterministas en lugar de invocar ffmpeg."""

    def __call__(self, args: list[str]) -> None:
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix == VIDEO_SUFFIX:
            output.write_bytes(b"\0" * 2048)
            return
        output.write_bytes(hashlib.sha256(" ".join(args[:-1]).encode()).digest())


def _doble_de_salidas(sample: list[dict]) -> list[dict]:
    """Salidas de prueba, no de un analizador: aciertan salvo la primera imagen de cada categoría."""
    outputs, flipped = [], set()
    for row in sample:
        categories = list(row["esperadas"])
        category = categories[0] if categories else None
        if category and category not in flipped:
            flipped.add(category)
            categories = []
        outputs.append({"path": row["path"], "categorias": categories})
    return outputs


def test_comparacion_sobre_la_muestra_etiquetada(tmp_path, capsys):
    rows = build_manifest(plan_dataset(1, REDUCED), tmp_path / "dataset", DobleDeEjecutor())
    sample = sample_from_manifest(rows)
    outputs = _doble_de_salidas(sample)
    muestra = tmp_path / "muestra_etiquetada.json"
    salidas = tmp_path / "salidas_de_prueba.json"
    muestra.write_text(json.dumps(sample), encoding="utf-8")
    salidas.write_text(json.dumps(outputs), encoding="utf-8")

    code = main(["comparar", "--muestra", str(muestra), "--salidas", str(salidas)])

    out = capsys.readouterr().out
    comparison = compare(read_sample_truth(muestra), read_observed(salidas))
    assert code == 0
    assert len(sample) == sum(row["kind"] == "imagen" for row in rows) == REDUCED.images
    assert render_text(comparison) in out
    assert {score.category for score in comparison.scores} == set(IMAGE_CATEGORIES)
    assert all(score.errors >= 1 for score in comparison.scores)
    assert all(score.hits + score.errors == len(sample) for score in comparison.scores)


def test_procedencia_sobre_el_manifiesto_real(capsys):
    if not REAL_MANIFEST.is_file():
        pytest.skip(f"no hay manifiesto generado en {REAL_MANIFEST}")

    code = main(["procedencia", "--manifiesto", str(REAL_MANIFEST)])

    assert code == 0, capsys.readouterr().out
