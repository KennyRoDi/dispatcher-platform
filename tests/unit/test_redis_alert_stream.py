import logging
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
import redis

from src.adapters.redis_alert_stream import RedisAlertStream
from src.application.alerting import SafeAlertPublisher
from src.application.ports import AlertPublisher, AlertReader
from src.domain.alert_policy import StoredAlert
from tests.contratos import comprobar_alert_publisher, comprobar_alert_reader
from tests.dobles import FakeAlertPublisher, FakeAlertReader, FakeClock

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
DETALLE = '{"categoria": "amenaza", "confianza": 0.9, "sha256": "aaaa", "posicion": "mensajes 3"}'


@pytest.fixture
def servidor():
    return fakeredis.FakeServer()


@pytest.fixture
def redis_falso(servidor):
    return fakeredis.FakeRedis(server=servidor, decode_responses=True)


@pytest.fixture
def reloj():
    return FakeClock(INICIO)


def test_doble_cumple_el_contrato():
    reloj = FakeClock(INICIO)
    publicador = FakeAlertPublisher(reloj)
    comprobar_alert_publisher(FakeAlertPublisher())
    comprobar_alert_reader(publicador, FakeAlertReader(publicador), reloj)


def test_stream_cumple_el_puerto_de_publicacion_y_el_de_lectura(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj)
    assert isinstance(flujo, AlertPublisher)
    assert isinstance(flujo, AlertReader)
    assert isinstance(FakeAlertReader(FakeAlertPublisher()), AlertReader)


def test_stream_cumple_el_contrato_de_publicador(redis_falso, reloj):
    comprobar_alert_publisher(RedisAlertStream(redis_falso, reloj))


def test_stream_cumple_el_contrato_de_lector(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj)
    comprobar_alert_reader(flujo, flujo, reloj)


def test_publicar_hace_un_xadd_con_los_cuatro_campos_en_la_clave_por_defecto(redis_falso, reloj):
    RedisAlertStream(redis_falso, reloj).publish("incidencia_alta", "c1", DETALLE)
    (_, campos), = redis_falso.xrange("alerts")
    assert campos == {"kind": "incidencia_alta", "case_id": "c1", "detail": DETALLE, "emitted_at": INICIO.isoformat()}


def test_la_marca_sale_del_reloj_en_utc(redis_falso):
    costa_rica = timezone(timedelta(hours=-6))
    reloj = FakeClock(datetime(2026, 11, 3, 2, 0, tzinfo=costa_rica))
    RedisAlertStream(redis_falso, reloj).publish("caso_finalizado", "c1", "{}")
    (_, campos), = redis_falso.xrange("alerts")
    assert datetime.fromisoformat(campos["emitted_at"]) == INICIO
    assert campos["emitted_at"].endswith("+00:00")


def test_clave_configurable(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj, key="otras")
    flujo.publish("caso_finalizado", "c1", "{}")
    assert redis_falso.xlen("otras") == 1 and redis_falso.exists("alerts") == 0
    assert [a.case_id for a in flujo.recent(5)] == ["c1"]


def test_recent_devuelve_alertas_almacenadas_con_id_del_stream(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj)
    flujo.publish("incidencia_alta", "c1", DETALLE)
    (alerta,) = flujo.recent(10)
    (id_stream, _), = redis_falso.xrange("alerts")
    assert alerta == StoredAlert(id_stream, "incidencia_alta", "c1", DETALLE, INICIO)


def test_recent_respeta_el_limite_y_el_orden_mas_reciente_primero(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj)
    for numero in range(5):
        flujo.publish("incidencia_alta", f"c{numero}", "{}")
        reloj.advance(timedelta(seconds=1))
    assert [a.case_id for a in flujo.recent(3)] == ["c4", "c3", "c2"]
    assert [a.case_id for a in flujo.recent(50)] == ["c4", "c3", "c2", "c1", "c0"]


def test_recent_de_un_stream_vacio_es_lista_vacia(redis_falso, reloj):
    assert RedisAlertStream(redis_falso, reloj).recent(10) == []


def test_recent_conserva_unicode_y_detalle_vacio(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj)
    flujo.publish("incidencia_alta", "caso-ñandú", '{"categoria": "canción"}')
    flujo.publish("caso_finalizado", "c2", "")
    vacia, unicode = flujo.recent(10)
    assert vacia.detail == "" and unicode.case_id == "caso-ñandú" and "canción" in unicode.detail


def test_el_stream_se_acota_por_maxlen(redis_falso, reloj):
    flujo = RedisAlertStream(redis_falso, reloj, maxlen=100)
    for numero in range(1000):
        flujo.publish("incidencia_alta", f"c{numero}", "{}")
    # MAXLEN ~ recorta por bloques: acota con holgura, no exacto.
    assert redis_falso.xlen("alerts") <= 200
    assert flujo.recent(1)[0].case_id == "c999"


def test_las_entradas_corruptas_se_omiten_sin_trazas_y_se_registran(redis_falso, reloj, caplog):
    flujo = RedisAlertStream(redis_falso, reloj)
    flujo.publish("incidencia_alta", "c1", "{}")
    redis_falso.xadd("alerts", {"kind": "incidencia_alta", "case_id": "c2", "detail": "{}"})
    redis_falso.xadd("alerts", {"kind": "incidencia_alta", "case_id": "c3", "detail": "{}", "emitted_at": "no-es-fecha"})
    redis_falso.xadd("alerts", {"emitted_at": INICIO.isoformat(), "case_id": "c4", "detail": "{}"})
    redis_falso.xadd("alerts", {"basura": "1"})
    flujo.publish("caso_finalizado", "c5", "{}")
    with caplog.at_level(logging.WARNING):
        alertas = flujo.recent(10)
    assert [a.case_id for a in alertas] == ["c5", "c1"]
    assert "omitid" in caplog.text


def test_publicar_con_redis_caido_propaga_el_error_del_canal(servidor, redis_falso, reloj):
    servidor.connected = False
    with pytest.raises(redis.exceptions.ConnectionError):
        RedisAlertStream(redis_falso, reloj).publish("incidencia_alta", "c1", "{}")


def test_leer_con_redis_caido_propaga_el_error_del_canal(servidor, redis_falso, reloj):
    servidor.connected = False
    with pytest.raises(redis.exceptions.ConnectionError):
        RedisAlertStream(redis_falso, reloj).recent(10)


def test_publicador_seguro_absorbe_un_redis_caido_y_lo_registra(servidor, redis_falso, reloj, caplog):
    servidor.connected = False
    seguro = SafeAlertPublisher(RedisAlertStream(redis_falso, reloj), logging.getLogger("test.alertas"))
    with caplog.at_level(logging.ERROR, logger="test.alertas"):
        seguro.publish("incidencia_alta", "c1", "{}")
    assert "c1" in caplog.text or "incidencia_alta" in caplog.text
