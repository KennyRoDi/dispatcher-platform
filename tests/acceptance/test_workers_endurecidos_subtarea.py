import json
import os
from pathlib import Path

import pytest
import requests

from tests.acceptance.tres_nodos import _hosts_con_completadas

pytestmark = pytest.mark.acceptance


def test_subtarea_completa_con_workers_endurecidos():
    coordinador = os.environ.get("COORDINATOR_URL")
    ruta_run_load = os.environ.get("RUN_LOAD_JSON")
    if not (coordinador and ruta_run_load):
        pytest.skip("define COORDINATOR_URL y RUN_LOAD_JSON (corrida con imagen y video grande)")

    run_load = json.loads(Path(ruta_run_load).read_text(encoding="utf-8"))
    respuesta = requests.get(f"{coordinador.rstrip('/')}/workers", timeout=10)
    respuesta.raise_for_status()

    assert any(worker.get("alive") is True for worker in respuesta.json())
    assert not run_load.get("timed_out")
    assert _hosts_con_completadas(run_load), "ninguna sub-tarea completada con workers endurecidos"
