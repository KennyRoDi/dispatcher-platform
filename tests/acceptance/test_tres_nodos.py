import json
import os
from pathlib import Path

import pytest
import requests

from tests.acceptance.tres_nodos import problemas_tres_nodos

pytestmark = pytest.mark.acceptance


def test_tres_nodos_activos_procesan_subtareas():
    coordinador = os.environ.get("COORDINATOR_URL")
    ruta_run_load = os.environ.get("RUN_LOAD_JSON")
    if not (coordinador and ruta_run_load):
        pytest.skip("define COORDINATOR_URL y RUN_LOAD_JSON")

    respuesta = requests.get(f"{coordinador.rstrip('/')}/workers", timeout=10)
    respuesta.raise_for_status()
    run_load = json.loads(Path(ruta_run_load).read_text(encoding="utf-8"))

    assert problemas_tres_nodos(respuesta.json(), run_load) == []
