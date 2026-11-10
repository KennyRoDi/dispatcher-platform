import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from src.domain.dataset_plan import MIB

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requiere ffmpeg"),
]

PARAMS = {
    "cases": 4,
    "light_heterogeneous": 1,
    "heavy_heterogeneous": 1,
    "messages": 40,
    "images": 12,
    "audios": 6,
    "heavy_bytes": MIB,
}


def test_generacion_reducida_escribe_manifiesto(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps(PARAMS), encoding="utf-8")
    out = tmp_path / "dataset"

    assert main(["--seed", "5", "--out", str(out), "--params", str(params)]) == 0

    rows = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert {r["kind"] for r in rows} == {"texto", "imagen", "audio", "video"}
    assert sum(r["kind"] == "imagen" for r in rows) == PARAMS["images"]
    assert sum(r["kind"] == "audio" for r in rows) == PARAMS["audios"]
    for row in rows:
        path = out / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert all(r["bytes"] >= MIB for r in rows if r["kind"] == "video")
    problemas = validate_manifest(out / MANIFEST_NAME)
    assert problemas and not any(p for p in problemas if "sha256" in p or "no existe" in p or "bytes" in p)
