import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


def test_cancelacion_en_curso_libera_recursos_con_archivo_de_200_mb():
    ruta = os.environ.get("CANCEL_HEAVY_JSON")
    if not ruta:
        pytest.skip("define CANCEL_HEAVY_JSON con la salida de scenarios/cancel_heavy.py (requiere nodos reales)")
    from scenarios.cancel_heavy import evaluar

    corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))

    assert corrida["megabytes"] >= 200
    veredicto = evaluar(corrida["antes"], corrida["despues"], estado_caso=corrida["estado_caso"])
    assert veredicto["problemas"] == []
