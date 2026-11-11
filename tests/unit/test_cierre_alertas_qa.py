import json
import logging
from concurrent.futures import ThreadPoolExecutor

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import conexion, rutas_alertas, rutas_subtareas
from src.coordinator.modelos import SubtaskReport
from tests.ayudas_cierre import crear_caso, reportar
from tests.dobles import FakeAlertPublisher


@pytest.fixture
def fake(monkeypatch):
    servidor = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", servidor)
    return servidor


@pytest.fixture
def publicador():
    return FakeAlertPublisher()


@pytest.fixture
def client(fake, publicador):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: publicador
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def publicar_con(excepcion):
    class Publicador:
        def publish(self, kind, case_id, detail):
            raise excepcion

    return Publicador()


def informe(case_id, subtask_id):
    return SubtaskReport(subtask_id=subtask_id, case_id=case_id, status="completed", worker_id="w1")


def test_reportes_simultaneos_publican_una_sola_alerta_por_caso(client, publicador):
    casos = [crear_caso(client, 4) for _ in range(15)]
    trabajos = [(c, s) for c, subs in casos for s in subs]
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda t: reportar(client, *t), trabajos))
    alertados = [a[1] for a in publicador.alertas]
    assert sorted(alertados) == sorted(c for c, _ in casos)


def test_keyboard_interrupt_del_publicador_no_se_traga(fake):
    case_id, (subtarea,) = crear_caso(TestClient(main.app))
    with pytest.raises(KeyboardInterrupt):
        rutas_subtareas.report_subtask(informe(case_id, subtarea), publicar_con(KeyboardInterrupt()))
    assert fake.hget(f"case:{case_id}", "status") == "completed"


def test_system_exit_del_publicador_no_se_traga(fake):
    case_id, (subtarea,) = crear_caso(TestClient(main.app))
    with pytest.raises(SystemExit):
        rutas_subtareas.report_subtask(informe(case_id, subtarea), publicar_con(SystemExit(1)))


def test_redis_caido_al_publicar_conserva_respuesta_y_estado(fake, monkeypatch):
    cliente = TestClient(main.app)
    case_id, (subtarea,) = crear_caso(cliente)

    def xadd_caido(*args, **kwargs):
        raise redis.exceptions.ConnectionError("Connection refused 10.0.0.5:6379 clave-secreta")

    monkeypatch.setattr(fake, "xadd", xadd_caido)
    respuesta = reportar(cliente, case_id, subtarea)
    assert respuesta.status_code == 200
    assert respuesta.json()["case_status"] == "completed"
    assert "10.0.0.5" not in respuesta.text and "secreta" not in respuesta.text
    assert fake.hget(f"case:{case_id}", "status") == "completed"
    assert fake.hget(f"case:{case_id}", "finished_at")


def test_error_de_redis_con_publicador_sin_safe_conserva_respuesta(client, fake):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: publicar_con(
        redis.exceptions.ResponseError("OOM command not allowed")
    )
    case_id, (subtarea,) = crear_caso(client)
    respuesta = reportar(client, case_id, subtarea)
    assert respuesta.status_code == 200 and respuesta.json()["case_status"] == "completed"


def test_el_log_de_la_excepcion_no_viaja_en_la_respuesta(client, caplog):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: publicar_con(
        RuntimeError("token=abc123 host=10.1.1.1")
    )
    case_id, (subtarea,) = crear_caso(client)
    with caplog.at_level(logging.ERROR):
        respuesta = reportar(client, case_id, subtarea)
    assert "abc123" not in respuesta.text
    assert any(r.exc_info for r in caplog.records)


def test_caso_sin_reportes_ni_subtareas_pendientes_no_alerta(client, publicador):
    case_id, _ = crear_caso(client, 2)
    assert publicador.alertas == []
    assert client.get(f"/cases/{case_id}").status_code == 200


def test_caso_sin_subtareas_no_se_crea_ni_alerta(client, publicador):
    assert client.post("/cases", json={"subtasks": []}).status_code >= 400
    assert publicador.alertas == []


def test_reporte_de_caso_ya_terminal_no_realerta(client, publicador, fake):
    case_id, (subtarea,) = crear_caso(client)
    reportar(client, case_id, subtarea)
    reportar(client, case_id, subtarea)
    reportar(client, case_id, subtarea, "failed")
    assert len(publicador.alertas) == 1
    assert fake.hget(f"case:{case_id}", "status") == "completed"


def test_cancelado_con_subtareas_en_vuelo_no_alerta_aunque_pending_llegue_a_cero(client, publicador, fake):
    case_id, (s1, s2) = crear_caso(client, 2)
    client.post(f"/cases/{case_id}/cancel")
    reportar(client, case_id, s1)
    reportar(client, case_id, s2)
    assert fake.hget(f"case:{case_id}", "status") == "cancelled"
    assert publicador.alertas == []


def test_log_del_fallo_de_alerta_no_inyecta_lineas_con_case_id_hostil(client, fake, caplog):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: publicar_con(RuntimeError("x"))
    _, (subtarea,) = crear_caso(client)
    hostil = "falso\nERROR forged: caso Z finalizado"
    with caplog.at_level(logging.ERROR):
        reportar(client, hostil, subtarea)
    mensajes = [r.getMessage() for r in caplog.records if "no publicada" in r.getMessage()]
    assert mensajes and all("\n" not in m for m in mensajes)


@pytest.mark.xfail(
    strict=True,
    reason="el reporte no valida que case_id sea el caso de la sub-tarea (previo a F-14): cierra y alerta un caso ajeno sin que termine; previo a F-14, código de Nahúm; pendiente fuera de F-14",
)
def test_reporte_con_case_id_ajeno_no_cierra_ni_alerta_otro_caso(client, publicador, fake):
    caso_a, (a1, _a2) = crear_caso(client, 2)
    caso_b, _ = crear_caso(client, 1)
    reportar(client, caso_b, a1)
    assert fake.hget(f"case:{caso_b}", "status") == "queued"
    assert publicador.alertas == []


@pytest.mark.xfail(
    strict=True,
    reason="case_id inexistente crea un caso fantasma y publica caso_finalizado (el reporte no valida el caso); previo a F-14, código de Nahúm; pendiente fuera de F-14",
)
def test_reporte_con_case_id_inexistente_no_publica_alerta(client, publicador, fake):
    _, (subtarea,) = crear_caso(client)
    reportar(client, "caso-que-no-existe", subtarea)
    assert publicador.alertas == []
    assert not fake.exists("case:caso-que-no-existe")


@pytest.mark.xfail(
    strict=True,
    reason="cancelar entre el HGET de estado y el HSET terminal es sobrescrito: el caso cancelado pasa a completed y alerta (carrera previa a F-14); previo a F-14, código de Nahúm; pendiente fuera de F-14",
)
def test_cancelacion_durante_el_cierre_no_se_sobrescribe(client, publicador, fake, monkeypatch):
    case_id, (subtarea,) = crear_caso(client)
    original = rutas_subtareas.final_case_status

    def cancelando(case):
        client.post(f"/cases/{case}/cancel")
        return original(case)

    monkeypatch.setattr(rutas_subtareas, "final_case_status", cancelando)
    reportar(client, case_id, subtarea)
    assert fake.hget(f"case:{case_id}", "status") == "cancelled"
    assert publicador.alertas == []
