import logging
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_alert_stream import RedisAlertStream
from src.application.alerting import SafeAlertPublisher
from src.coordinator import conexion, rutas_alertas
from tests.dobles import FakeClock

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
ESTAMPA = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def servidor(monkeypatch):
    servidor = fakeredis.FakeServer()
    monkeypatch.setattr(conexion, "redis_client", fakeredis.FakeRedis(server=servidor, decode_responses=True))
    return servidor


@pytest.fixture
def cliente(servidor):
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def flujo(servidor):
    return RedisAlertStream(conexion.redis_client, FakeClock(INICIO))


def agregar(campos_extra=None, **cambios):
    campos = {"kind": "k", "case_id": "c", "detail": "d", "emitted_at": ESTAMPA, **cambios}
    conexion.redis_client.xadd("alerts", {**campos, **(campos_extra or {})})


class ClienteRedis:
    def __init__(self, error):
        self.error = error

    def xrevrange(self, *args, **kwargs):
        raise self.error

    def xadd(self, *args, **kwargs):
        raise self.error


def test_entradas_sin_campos_o_con_vacios_no_rompen_la_ruta(cliente, flujo):
    flujo.publish("incidencia_alta", "c1", "{}")
    conexion.redis_client.xadd("alerts", {"kind": "k"})
    agregar(case_id="", kind="", detail="")
    respuesta = cliente.get("/alerts")
    assert respuesta.status_code == 200
    assert len(respuesta.json()["alertas"]) == 2


def test_detalle_enorme_y_unicode_viajan_intactos(cliente, flujo):
    detalle = "ñ😀\n\"\\" * 50_000
    flujo.publish("incidencia_alta", "caso-ñ", detalle)
    (alerta,) = cliente.get("/alerts").json()["alertas"]
    assert alerta["detail"] == detalle and alerta["case_id"] == "caso-ñ"


def test_ids_del_mismo_milisegundo_se_ordenan_mas_reciente_primero(cliente, servidor):
    for secuencia in range(3):
        conexion.redis_client.xadd(
            "alerts", {"kind": "k", "case_id": f"c{secuencia}", "detail": "d", "emitted_at": ESTAMPA}, id=f"99999999999999-{secuencia}"
        )
    alertas = cliente.get("/alerts").json()["alertas"]
    assert [a["case_id"] for a in alertas] == ["c2", "c1", "c0"]
    assert [a["alert_id"] for a in alertas] == ["99999999999999-2", "99999999999999-1", "99999999999999-0"]


def test_reloj_en_otra_zona_se_guarda_en_utc(flujo):
    zona = timezone(timedelta(hours=-6))
    RedisAlertStream(conexion.redis_client, FakeClock(datetime(2026, 11, 3, 8, 0, tzinfo=zona))).publish("k", "c", "d")
    (alerta,) = flujo.recent(1)
    assert alerta.emitted_at.utcoffset() == timedelta(0)
    assert alerta.emitted_at == datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("metodo", ["post", "put", "delete", "patch"])
def test_metodos_de_escritura_responden_405_y_no_escriben(cliente, servidor, metodo):
    assert getattr(cliente, metodo)("/alerts").status_code == 405
    assert conexion.redis_client.dbsize() == 0


def test_get_no_escribe_nada_en_redis(cliente, flujo):
    flujo.publish("incidencia_alta", "c1", "{}")
    antes = conexion.redis_client.xrange("alerts")
    for parametros in ({}, {"limit": 1}, {"limit": 0}, {"limit": "x"}):
        cliente.get("/alerts", params=parametros)
    assert conexion.redis_client.xrange("alerts") == antes
    assert conexion.redis_client.dbsize() == 1


def test_limite_repetido_no_rompe_y_valida_el_ultimo(cliente, flujo):
    for numero in range(3):
        flujo.publish("k", f"c{numero}", "d")
    assert len(cliente.get("/alerts?limit=1&limit=2").json()["alertas"]) == 2
    assert cliente.get("/alerts?limit=1&limit=500").status_code == 422


@pytest.mark.parametrize("limite", ["0", "-1", "abc", "1e2", "99999999999999999999", " ", "%00"])
def test_limites_hostiles_responden_422_sin_tocar_redis(servidor, limite):
    conexion.redis_client = ClienteRedis(AssertionError("no debe leer"))
    assert TestClient(main.app, raise_server_exceptions=False).get("/alerts", params={"limit": limite}).status_code == 422


def test_la_ruta_no_pisa_rutas_existentes():
    rutas = main.app.openapi()["paths"]
    assert list(rutas["/alerts"]) == ["get"]
    assert {"/health", "/cases", "/workers", "/stats"} <= set(rutas)


def test_redis_caido_en_publish_se_propaga_pero_el_publicador_del_coordinador_lo_absorbe(servidor, caplog):
    servidor.connected = False
    flujo = RedisAlertStream(conexion.redis_client, FakeClock(INICIO))
    with pytest.raises(redis.ConnectionError):
        flujo.publish("k", "c", "d")
    with caplog.at_level(logging.ERROR):
        rutas_alertas.obtener_publicador_alertas().publish("k", "c", "d")
    assert isinstance(rutas_alertas.obtener_publicador_alertas(), SafeAlertPublisher)


def test_error_de_respuesta_de_redis_en_publish_lo_absorbe_el_publicador_seguro(monkeypatch, caplog):
    monkeypatch.setattr(conexion, "redis_client", ClienteRedis(redis.ResponseError("OOM command not allowed")))
    with caplog.at_level(logging.ERROR):
        rutas_alertas.obtener_publicador_alertas().publish("k", "c", "d")
    assert caplog.records


@pytest.mark.xfail(
    strict=True,
    reason="Media: con Redis caido el 503 incluye host, puerto y el texto del error de redis-py en el cuerpo "
    "(conexion.redis_unavailable); fuga de topologia a cualquier cliente de /alerts",
)
def test_503_no_filtra_host_puerto_ni_detalle_del_error(monkeypatch, servidor, cliente):
    monkeypatch.setattr(conexion, "REDIS_HOST", "10.9.8.7")
    servidor.connected = False
    respuesta = cliente.get("/alerts")
    assert respuesta.status_code == 503
    assert "10.9.8.7" not in respuesta.text and "6379" not in respuesta.text
    assert "emulating" not in respuesta.text


@pytest.mark.xfail(
    strict=True,
    reason="Media: una sola entrada con bytes no UTF-8 en el Stream hace fallar toda la lectura (UnicodeDecodeError "
    "en redis-py con decode_responses=True, fuera del try de _decode): /alerts responde 500 mientras la entrada siga "
    "entre las ultimas 'limit'",
)
def test_una_entrada_con_bytes_no_utf8_se_omite_sin_tirar_la_ruta(cliente, flujo, servidor):
    flujo.publish("incidencia_alta", "c1", "{}")
    sin_decodificar = fakeredis.FakeRedis(server=servidor, decode_responses=False)
    sin_decodificar.xadd("alerts", {"kind": b"\xff\xfe", "case_id": "c2", "detail": "d", "emitted_at": ESTAMPA})
    respuesta = cliente.get("/alerts")
    assert respuesta.status_code == 200
    assert [a["case_id"] for a in respuesta.json()["alertas"]] == ["c1"]


@pytest.mark.xfail(
    strict=True,
    reason="Media/baja: un redis.ResponseError (p. ej. WRONGTYPE si la clave 'alerts' no es un Stream) no se atrapa "
    "en la ruta y responde 500 generico; el SPEC pide 503 limpio solo para Redis que no responde, pero un error de "
    "servidor tambien debe ser limpio y registrado",
)
def test_error_de_respuesta_de_redis_en_lectura_no_es_500(monkeypatch, cliente):
    monkeypatch.setattr(conexion, "redis_client", ClienteRedis(redis.ResponseError("WRONGTYPE")))
    assert cliente.get("/alerts").status_code == 503


@pytest.mark.xfail(
    strict=True,
    reason="Baja: una entrada ajena con emitted_at sin zona ('2026-01-01T00:00:00' o solo fecha) se devuelve tal cual, "
    "sin offset; el SPEC promete ISO-8601 UTC y el contrato exige utcoffset 0",
)
def test_emitted_at_sin_zona_no_sale_sin_offset(cliente, servidor):
    agregar(emitted_at="2026-01-01T00:00:00")
    for alerta in cliente.get("/alerts").json()["alertas"]:
        assert datetime.fromisoformat(alerta["emitted_at"]).utcoffset() == timedelta(0)


@pytest.mark.xfail(
    strict=True,
    reason="Baja: recent(0) lanza redis.DataError (XREVRANGE COUNT 0 invalido) mientras FakeAlertReader devuelve []; "
    "el adaptador no cumple igual que el doble para limites no positivos y filtra un tipo de redis-py al llamador",
)
def test_recent_con_limite_cero_devuelve_lista_vacia(flujo):
    flujo.publish("k", "c", "d")
    assert flujo.recent(0) == []


@pytest.mark.xfail(
    strict=True,
    reason="Baja: maxlen=0 o negativo se acepta y XADD ... MAXLEN ~ 0 descarta cada alerta al instante (publish "
    "'exitoso' que no guarda nada, sin error ni log); el constructor deberia rechazarlo con ValueError",
)
def test_maxlen_no_positivo_se_rechaza():
    with pytest.raises(ValueError):
        RedisAlertStream(fakeredis.FakeRedis(decode_responses=True), FakeClock(INICIO), maxlen=0)
