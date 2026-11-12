import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


def test_la_rafaga_cumple_las_afirmaciones_de_us_33():
    ruta = os.environ.get("BURST_JSON")
    if not ruta:
        pytest.skip("define BURST_JSON con el carga_<fecha>.json de la ráfaga (requiere tres nodos worker)")
    from scenarios.burst import evaluar

    corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))

    assert corrida["metrics"]["cases"] >= 20
    veredicto = evaluar(corrida)
    assert veredicto["problemas"] == []
