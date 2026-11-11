import os
from pathlib import Path

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest

pytestmark = pytest.mark.acceptance

OUT = Path(os.environ.get("DATASET_OUT", "~/scratch/dataset")).expanduser()


def test_validador_sobre_dataset_completo(capsys):
    if not (OUT / MANIFEST_NAME).is_file():
        pytest.skip(f"no hay dataset generado en {OUT}")

    assert validate_manifest(OUT / MANIFEST_NAME) == []
    assert main(["--validar", "--out", str(OUT)]) == 0
    print(capsys.readouterr().out)
