import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


def test_coordinator_restart_aceptacion():
    ruta = os.environ.get("COORDINATOR_RESTART_JSON")
    if not ruta:
        pytest.skip("define COORDINATOR_RESTART_JSON con la salida de scenarios/coordinator_restart.py (corrida real)")
    from scenarios.coordinator_restart import evaluar

    corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))

    veredicto = evaluar(
        creadas=corrida["creadas"],
        contadas_antes=corrida["contadas_antes"],
        contadas_despues=corrida["contadas_despues"],
    )
    assert veredicto["problemas"] == []
    assert corrida["tiempo_arranque_s"] is not None
