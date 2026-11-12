import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


def test_worker_crash_aceptacion():
    ruta = os.environ.get("WORKER_CRASH_JSON")
    if not ruta:
        pytest.skip("define WORKER_CRASH_JSON con la salida de scenarios/worker_crash.py (corrida real)")
    from scenarios.worker_crash import evaluar

    corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))

    veredicto = evaluar(
        creadas=corrida["creadas"],
        terminadas=corrida["terminadas"],
        perdidas=corrida["perdidas"],
        duplicadas=corrida["duplicadas"],
        estado_caso=corrida["estado_caso"],
    )
    assert veredicto["problemas"] == []
    assert corrida["tiempo_deteccion_s"] is not None
    assert corrida["tiempo_reasignacion_s"] is not None
