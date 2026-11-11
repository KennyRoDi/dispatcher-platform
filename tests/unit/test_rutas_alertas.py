import logging
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_alert_stream import RedisAlertStream
from src.application.alerting import SafeAlertPublisher
from src.application.ports import AlertPublisher
from src.coordinator import conexion, rutas_alertas
from tests.dobles import FakeAlertPublisher, FakeAlertReader, FakeClock

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
CLAVES = ["alert_id", "kind", "case_id", "detail", "emitted_at"]
DETALLE = '{"categoria": "amenaza", "confianza": 0.9, "sha256": "aaaa", "posicion": "mensajes 3"}'


@pytest.fixture
def reloj():
    return FakeClock(INICIO)


@pytest.fixture
def publicador(reloj):
    return FakeAlertPublisher(reloj)


@pytest.fixture
def cliente(publicador):
    main.app.dependency_overrides[rutas_alertas.obtener_lector_alertas] = lambda: FakeAlertReader(publicador)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def publicar(publicador, reloj, cantidad, kind="incidencia_alta"):
    for numero in range(cantidad):
        publicador.publish(kind, f"c{numero}", DETALLE)
        reloj.advance(timedelta(seconds=1))


def test_ruta_registrada_en_la_aplicacion():
    assert "get" in main.app.openapi()["paths"]["/alerts"]


def test_sin_alertas_responde_200_con_lista_vacia(cliente):
    respuesta = cliente.get("/alerts")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"alertas": []}


def test_devuelve_las_claves_acordadas_con_marca_iso_utc(cliente, publicador, reloj):
    publicar(publicador, reloj, 1)
    (alerta,) = cliente.get("/alerts").json()["alertas"]
    assert list(alerta) == CLAVES
    assert alerta["kind"] == "incidencia_alta" and alerta["case_id"] == "c0" and alerta["detail"] == DETALLE
    assert alerta["emitted_at"] == INICIO.isoformat()


def test_orden_mas_reciente_primero(cliente, publicador, reloj):
    publicar(publicador, reloj, 3)
    publicador.publish("caso_finalizado", "c0", '{"estado": "completed"}')
    alertas = cliente.get("/alerts").json()["alertas"]
    assert [a["kind"] for a in alertas] == ["caso_finalizado", "incidencia_alta", "incidencia_alta", "incidencia_alta"]
    assert [a["case_id"] for a in alertas][1:] == ["c2", "c1", "c0"]


def test_limite_por_defecto_es_50(cliente, publicador, reloj):
    publicar(publicador, reloj, 60)
    assert len(cliente.get("/alerts").json()["alertas"]) == 50


def test_limite_explicito_devuelve_las_mas_recientes(cliente, publicador, reloj):
    publicar(publicador, reloj, 10)
    alertas = cliente.get("/alerts", params={"limit": 3}).json()["alertas"]
    assert [a["case_id"] for a in alertas] == ["c9", "c8", "c7"]


@pytest.mark.parametrize("limite", [1, 200])
def test_limites_extremos_validos(cliente, publicador, reloj, limite):
    publicar(publicador, reloj, 5)
    assert cliente.get("/alerts", params={"limit": limite}).status_code == 200


@pytest.mark.parametrize("limite", ["0", "-1", "201", "abc", "1.5", ""])
def test_limite_fuera_de_rango_o_invalido_responde_422(cliente, limite):
    assert cliente.get("/alerts", params={"limit": limite}).status_code == 422


def test_el_lector_recibe_el_limite_pedido():
    pedidos = []

    class Espia:
        def recent(self, limit):
            pedidos.append(limit)
            return []

    main.app.dependency_overrides[rutas_alertas.obtener_lector_alertas] = lambda: Espia()
    try:
        TestClient(main.app).get("/alerts", params={"limit": 7})
        TestClient(main.app).get("/alerts")
    finally:
        main.app.dependency_overrides.clear()
    assert pedidos == [7, 50]


@pytest.fixture
def servidor(monkeypatch):
    servidor = fakeredis.FakeServer()
    monkeypatch.setattr(conexion, "redis_client", fakeredis.FakeRedis(server=servidor, decode_responses=True))
    return servidor


def test_por_defecto_lee_el_stream_de_alertas_del_redis_del_coordinador(servidor):
    RedisAlertStream(conexion.redis_client, FakeClock(INICIO)).publish("caso_finalizado", "c1", '{"estado": "failed"}')
    respuesta = TestClient(main.app).get("/alerts")
    assert respuesta.status_code == 200
    (alerta,) = respuesta.json()["alertas"]
    assert (alerta["kind"], alerta["case_id"], alerta["detail"]) == ("caso_finalizado", "c1", '{"estado": "failed"}')


def test_redis_caido_responde_503_limpio_solo_para_esta_ruta(servidor, caplog):
    servidor.connected = False
    cliente = TestClient(main.app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        respuesta = cliente.get("/alerts")
    assert respuesta.status_code == 503
    assert "Redis" in respuesta.json()["detail"]
    assert "Traceback" not in respuesta.text
    assert cliente.get("/openapi.json").status_code == 200


def test_entradas_corruptas_del_stream_se_omiten_en_la_respuesta(servidor):
    flujo = RedisAlertStream(conexion.redis_client, FakeClock(INICIO))
    flujo.publish("incidencia_alta", "c1", "{}")
    conexion.redis_client.xadd("alerts", {"basura": "1"})
    conexion.redis_client.xadd("alerts", {"kind": "x", "case_id": "c2", "detail": "{}", "emitted_at": "nunca"})
    respuesta = TestClient(main.app).get("/alerts")
    assert respuesta.status_code == 200
    assert [a["case_id"] for a in respuesta.json()["alertas"]] == ["c1"]


def test_publicador_del_coordinador_es_seguro_y_escribe_en_el_stream_del_coordinador(servidor):
    publicador = rutas_alertas.obtener_publicador_alertas()
    assert isinstance(publicador, SafeAlertPublisher) and isinstance(publicador, AlertPublisher)
    publicador.publish("caso_finalizado", "c1", '{"estado": "completed"}')
    (_, campos), = conexion.redis_client.xrange("alerts")
    assert (campos["kind"], campos["case_id"]) == ("caso_finalizado", "c1")
    assert datetime.fromisoformat(campos["emitted_at"]).utcoffset() == timedelta(0)


def test_publicador_del_coordinador_no_propaga_con_redis_caido(servidor, caplog):
    servidor.connected = False
    with caplog.at_level(logging.ERROR):
        rutas_alertas.obtener_publicador_alertas().publish("caso_finalizado", "c1", "{}")
    assert caplog.records


def test_lector_y_publicador_comparten_el_flujo_del_coordinador(servidor):
    flujo = rutas_alertas.crear_flujo_alertas()
    assert isinstance(flujo, RedisAlertStream)
    flujo.publish("caso_finalizado", "c1", "{}")
    assert [a.case_id for a in rutas_alertas.obtener_lector_alertas().recent(10)] == ["c1"]
