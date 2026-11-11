import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import redis

from src.adapters.redis_alert_stream import RedisAlertStream
from tests.contratos import comprobar_alert_publisher, comprobar_alert_reader
from tests.dobles import FakeClock

pytestmark = pytest.mark.integration

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


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
def clave(cliente):
    nombre = f"alerts-f14-{uuid.uuid4().hex[:8]}"
    yield nombre
    cliente.delete(nombre)


def test_stream_publica_y_lector_ve_alertas_recientes_primero(cliente, clave):
    reloj = FakeClock(INICIO)
    flujo = RedisAlertStream(cliente, reloj, key=clave)
    for numero in range(3):
        flujo.publish("incidencia_alta", f"c{numero}", "{}")
        reloj.advance(timedelta(seconds=1))
    alertas = flujo.recent(10)
    assert [a.case_id for a in alertas] == ["c2", "c1", "c0"]
    assert [a.emitted_at for a in alertas] == [INICIO + timedelta(seconds=n) for n in (2, 1, 0)]


def test_stream_cumple_el_contrato_con_redis_real(cliente, clave):
    reloj = FakeClock(INICIO)
    flujo = RedisAlertStream(cliente, reloj, key=clave)
    comprobar_alert_reader(flujo, flujo, reloj)
    comprobar_alert_publisher(flujo)


def test_stream_se_acota_por_maxlen(cliente, clave):
    flujo = RedisAlertStream(cliente, FakeClock(INICIO), key=clave, maxlen=100)
    for numero in range(1000):
        flujo.publish("incidencia_alta", f"c{numero}", "{}")
    # MAXLEN ~ recorta por nodos del Stream (100 entradas por defecto): acota con holgura.
    assert cliente.xlen(clave) <= 200
    assert flujo.recent(1)[0].case_id == "c999"


def test_publicar_sin_consumidor_no_espera(cliente, clave):
    flujo = RedisAlertStream(cliente, FakeClock(INICIO), key=clave)
    inicio = time.monotonic()
    flujo.publish("incidencia_alta", "c1", "{}")
    assert time.monotonic() - inicio < 2
    assert cliente.xinfo_groups(clave) == []
    assert cliente.xlen(clave) == 1
