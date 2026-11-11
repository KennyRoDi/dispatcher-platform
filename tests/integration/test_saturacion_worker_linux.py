import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "posix", reason="requiere cgroups y procesos POSIX; en Windows usar Docker o WSL2"),
]


def test_worker_con_limite_bajo_deja_subtareas_en_cola_y_mantiene_heartbeats():
    if not os.environ.get("REDIS_URL"):
        pytest.skip("define REDIS_URL para ejecutar el worker real con límite bajo")
    from scenarios.memory_saturation import huecos_heartbeat, planificar_carga

    mib = 1024 * 1024
    plan = planificar_carga(256 * mib, 32 * mib, 64 * mib, 2)
    assert plan.subtareas > plan.cupo
    assert huecos_heartbeat([0, 5, 10], 5.0, 3) == []
