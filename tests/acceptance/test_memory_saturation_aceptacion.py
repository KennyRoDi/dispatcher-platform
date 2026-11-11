import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


def test_saturacion_de_memoria_cumple_las_afirmaciones_de_us_37():
    ruta = os.environ.get("MEMORY_SATURATION_JSON")
    if not ruta:
        pytest.skip("define MEMORY_SATURATION_JSON con la salida de scenarios/memory_saturation.py (requiere nodos reales)")
    from scenarios.memory_saturation import PlanCarga, evaluar

    corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))
    plan = PlanCarga(**corrida["plan"])

    assert plan.subtareas > plan.cupo
    veredicto = evaluar(plan, corrida["muestras"], corrida["estados_finales"], corrida["intervalo_heartbeat"])
    assert veredicto["problemas"] == []
