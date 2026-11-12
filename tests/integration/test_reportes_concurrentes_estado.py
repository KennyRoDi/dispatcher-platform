import os
import threading
import uuid
from datetime import datetime, timezone

import pytest
import redis

from src.adapters.redis_case_state import RedisCaseState
from src.application.report_subtask import ReportSubtask
from src.domain.case_state import CaseState
from tests.dobles import FakeClock

pytestmark = pytest.mark.integration

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
SUBTAREAS = 12
HILOS_POR_REPORTE = 4


@pytest.fixture
def cliente():
    conexion = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    try:
        conexion.ping()
    except redis.exceptions.RedisError:
        pytest.skip("define REDIS_HOST/REDIS_PORT de un Redis real (Compose)")
    return conexion


@pytest.fixture
def caso_id(cliente):
    identificador = f"f10-{uuid.uuid4().hex[:8]}"
    yield identificador
    claves = cliente.keys(f"*{identificador}*")
    if claves:
        cliente.delete(*claves)


def test_reportes_concurrentes_cierran_una_vez(cliente, caso_id):
    cliente.hset(f"case:{caso_id}", mapping={"status": "queued"})
    almacen = RedisCaseState(cliente)
    caso_de_uso = ReportSubtask(almacen, FakeClock(INICIO))
    cierres, errores = [], []
    barrera = threading.Barrier(SUBTAREAS * HILOS_POR_REPORTE)

    def reportar(n):
        barrera.wait()
        try:
            resultado = caso_de_uso.execute(caso_id, f"s{n}", "failed" if n == 0 else "completed", SUBTAREAS)
            if resultado is not None:
                cierres.append(resultado)
        except Exception as error:  # noqa: BLE001
            errores.append(repr(error))

    hilos = [
        threading.Thread(target=reportar, args=(n,))
        for n in range(SUBTAREAS)
        for _ in range(HILOS_POR_REPORTE)
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
    assert cierres == [CaseState.PARTIALLY_COMPLETED]
    assert almacen.counts(caso_id) == (SUBTAREAS - 1, 1)
    assert almacen.state(caso_id) is CaseState.PARTIALLY_COMPLETED
    estados = [estado for estado, _ in almacen.history(caso_id)]
    assert estados.count(CaseState.PARTIALLY_COMPLETED) == 1
