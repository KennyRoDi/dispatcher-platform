import json
import logging

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import conexion, rutas_alertas
from tests.ayudas_cierre import crear_caso, reportar
from tests.dobles import FakeAlertPublisher


pytestmark = pytest.mark.usefixtures("sin_autorizacion")


class PublicadorRoto:
    def __init__(self):
        self.llamadas = 0

    def publish(self, kind, case_id, detail):
        self.llamadas += 1
        raise RuntimeError("redis de alertas caido")


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


def estado(fake, case_id):
    return fake.hget(f"case:{case_id}", "status")


@pytest.mark.parametrize(
    "estados, final",
    [(("completed",), "completed"), (("failed",), "failed"), (("completed", "failed"), "partially_completed")],
)
def test_cierre_publica_una_alerta_con_el_estado_final(client, fake, publicador, estados, final):
    case_id, subtareas = crear_caso(client, len(estados))
    for subtarea, resultado in zip(subtareas, estados):
        reportar(client, case_id, subtarea, resultado)
    assert estado(fake, case_id) == final
    assert publicador.alertas == [("caso_finalizado", case_id, json.dumps({"estado": final}))]


def test_una_alerta_por_caso_y_no_por_subtarea(client, publicador):
    case_id, subtareas = crear_caso(client, 3)
    for subtarea in subtareas[:-1]:
        reportar(client, case_id, subtarea)
        assert publicador.alertas == []
    reportar(client, case_id, subtareas[-1])
    assert [a[0] for a in publicador.alertas] == ["caso_finalizado"]


def test_cada_caso_publica_su_propia_alerta(client, publicador):
    primero, (s1,) = crear_caso(client)
    segundo, (s2,) = crear_caso(client)
    reportar(client, primero, s1)
    reportar(client, segundo, s2, "failed")
    assert [(a[1], json.loads(a[2])["estado"]) for a in publicador.alertas] == [(primero, "completed"), (segundo, "failed")]


def test_reporte_repetido_no_duplica_la_alerta(client, publicador):
    case_id, (subtarea,) = crear_caso(client)
    reportar(client, case_id, subtarea)
    repetido = reportar(client, case_id, subtarea)
    assert repetido.json()["message"] == "Reporte ignorado por idempotencia"
    assert len(publicador.alertas) == 1


def test_reporte_con_estado_invalido_no_alerta(client, publicador):
    case_id, (subtarea,) = crear_caso(client)
    assert reportar(client, case_id, subtarea, "weird").status_code == 422
    assert publicador.alertas == []


def test_reporte_de_subtarea_inexistente_no_alerta(client, publicador):
    case_id, _ = crear_caso(client)
    assert reportar(client, case_id, "no-existe").status_code == 404
    assert publicador.alertas == []


def test_cancelado_no_alerta_ni_al_cancelar_ni_al_reportar_despues(client, fake, publicador):
    case_id, (s1, s2) = crear_caso(client, 2)
    reportar(client, case_id, s1)
    assert client.post(f"/cases/{case_id}/cancel").status_code == 200
    respuesta = reportar(client, case_id, s2)
    assert respuesta.json()["case_status"] == "cancelled"
    assert estado(fake, case_id) == "cancelled"
    assert publicador.alertas == []


def test_el_caso_ya_es_terminal_cuando_se_publica_la_alerta(client, fake, publicador):
    case_id, (subtarea,) = crear_caso(client)
    vistos = []
    publicar = publicador.publish

    def espia(kind, case, detail):
        vistos.append((estado(fake, case), fake.hget(f"case:{case}", "finished_at")))
        publicar(kind, case, detail)

    publicador.publish = espia
    reportar(client, case_id, subtarea)
    assert len(vistos) == 1
    assert vistos[0][0] == "completed" and vistos[0][1]


def test_la_alerta_no_se_publica_mientras_quedan_subtareas(client, fake, publicador):
    case_id, (s1, s2) = crear_caso(client, 2)
    assert reportar(client, case_id, s1).json()["case_status"] == "processing"
    assert publicador.alertas == []
    assert reportar(client, case_id, s2).json()["case_status"] == "completed"
    assert len(publicador.alertas) == 1


def respuesta_de_cierre(client, publicador_inyectado):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: publicador_inyectado
    case_id, (s1, s2) = crear_caso(client, 2)
    reportar(client, case_id, s1)
    return case_id, reportar(client, case_id, s2, "failed", error="boom", error_type="FFmpegError")


def test_publicador_roto_no_cambia_la_respuesta_ni_el_estado(client, fake, caplog):
    case_sano, sana = respuesta_de_cierre(client, FakeAlertPublisher())
    roto = PublicadorRoto()
    with caplog.at_level(logging.ERROR):
        case_roto, caida = respuesta_de_cierre(client, roto)
    assert roto.llamadas == 1
    assert caida.status_code == sana.status_code == 200
    normalizar = lambda r, c: {k: (v.replace(c, "CASO") if isinstance(v, str) else v) for k, v in r.json().items()}
    assert {k: v for k, v in normalizar(caida, case_roto).items() if k != "subtask_id"} == {
        k: v for k, v in normalizar(sana, case_sano).items() if k != "subtask_id"
    }
    assert estado(fake, case_roto) == estado(fake, case_sano) == "partially_completed"
    assert fake.hget(f"case:{case_roto}", "pending_subtasks") == "0"
    assert fake.hget(f"case:{case_roto}", "finished_at")
    assert any("alerta" in registro.getMessage().lower() for registro in caplog.records)


def test_publicador_roto_no_impide_reportes_posteriores(client, fake):
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = PublicadorRoto
    primero, (s1,) = crear_caso(client)
    segundo, (s2,) = crear_caso(client)
    assert reportar(client, primero, s1).status_code == 200
    assert reportar(client, segundo, s2).status_code == 200
    assert estado(fake, primero) == estado(fake, segundo) == "completed"


def test_respuesta_de_cierre_conserva_sus_claves(client):
    case_id, (subtarea,) = crear_caso(client)
    respuesta = reportar(client, case_id, subtarea)
    assert respuesta.json() == {
        "message": "Reporte procesado correctamente",
        "subtask_id": subtarea,
        "case_id": case_id,
        "subtask_status": "completed",
        "case_status": "completed",
        "pending_subtasks": 0,
    }


def test_por_defecto_la_alerta_llega_al_stream_que_lee_alerts(fake):
    cliente = TestClient(main.app)
    case_id, (subtarea,) = crear_caso(cliente)
    reportar(cliente, case_id, subtarea)
    (alerta,) = cliente.get("/alerts").json()["alertas"]
    assert (alerta["kind"], alerta["case_id"], json.loads(alerta["detail"])) == ("caso_finalizado", case_id, {"estado": "completed"})
