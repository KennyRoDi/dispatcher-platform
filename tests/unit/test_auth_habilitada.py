import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import conexion


@pytest.fixture(autouse=True)
def redis_falso(monkeypatch):
    monkeypatch.setattr(conexion, "redis_client", fakeredis.FakeRedis(decode_responses=True))


@pytest.mark.parametrize("entorno", [{}, {"AUTH_ENABLED": ""}, {"AUTH_ENABLED": "1"}, {"AUTH_ENABLED": "true"}])
def test_la_autenticacion_esta_activa_por_defecto(entorno):
    assert main.auth_habilitada(entorno) is True


@pytest.mark.parametrize("valor", ["0", "false", "False", "FALSE", "no", "off", " false "])
def test_se_desactiva_solo_con_un_valor_explicito(valor):
    assert main.auth_habilitada({"AUTH_ENABLED": valor}) is False


@pytest.mark.parametrize("valor", ["talvez", "2", "disabled", "nunca"])
def test_un_valor_desconocido_deja_la_autenticacion_activa(valor):
    assert main.auth_habilitada({"AUTH_ENABLED": valor}) is True


def test_la_app_del_modulo_exige_token_por_defecto():
    assert TestClient(main.app).get("/stats").status_code == 401


def test_crear_app_activa_exige_token_en_cada_router():
    cliente = TestClient(main.crear_app({}))
    assert [cliente.get(r).status_code for r in ("/cases", "/workers", "/stats")] == [401] * 3
    assert cliente.post("/subtasks/report", json={}).status_code == 401


def test_crear_app_con_auth_desactivada_no_pide_token():
    cliente = TestClient(main.crear_app({"AUTH_ENABLED": "false"}))
    assert cliente.get("/stats").status_code == 200
    assert cliente.get("/cases").status_code == 200


def test_crear_app_lee_os_environ_si_no_recibe_entorno(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    assert TestClient(main.crear_app()).get("/stats").status_code == 200
    monkeypatch.delenv("AUTH_ENABLED")
    assert TestClient(main.crear_app()).get("/stats").status_code == 401


def test_cada_app_creada_tiene_sus_propias_dependencias():
    con_auth, sin_auth = main.crear_app({}), main.crear_app({"AUTH_ENABLED": "0"})
    assert con_auth is not sin_auth
    assert TestClient(con_auth).get("/stats").status_code == 401
    assert TestClient(sin_auth).get("/stats").status_code == 200
