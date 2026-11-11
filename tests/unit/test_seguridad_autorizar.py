import secrets
from datetime import timedelta

import jwt
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from src.adapters.jwt_tokens import JwtTokenVerifier, issue_token
from src.application.ports import Identity
from src.coordinator.seguridad import autorizar, obtener_verificador
from src.domain.rbac import Role
from tests.dobles import FakeClock, FakeTokenVerifier

ANALISTA, SUPERVISOR, ADMINISTRADOR, SERVICIO = Role.ANALISTA, Role.SUPERVISOR, Role.ADMINISTRADOR, Role.SERVICIO

ROLES_PERMITIDOS = {
    ("POST", "/cases"): {ANALISTA, ADMINISTRADOR},
    ("POST", "/cases/"): {ANALISTA, ADMINISTRADOR},
    ("GET", "/cases"): {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    ("GET", "/cases/"): {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    ("GET", "/cases/{case_id}"): {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    ("GET", "/cases/{case_id}/report"): {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    ("GET", "/subtasks/{subtask_id}"): {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    ("POST", "/cases/{case_id}/cancel"): {SUPERVISOR, ADMINISTRADOR},
    ("GET", "/workers"): {SUPERVISOR, ADMINISTRADOR},
    ("GET", "/stats"): {SUPERVISOR, ADMINISTRADOR},
    ("GET", "/hardware"): {SUPERVISOR, ADMINISTRADOR},
    ("POST", "/subtasks/report"): {SERVICIO},
}
PARES = [(metodo, ruta, rol) for (metodo, ruta) in ROLES_PERMITIDOS for rol in Role]
IDENTIDADES = {f"tok-{rol.value}": Identity(rol.value, rol) for rol in Role}


def concreta(ruta):
    return ruta.format(case_id="c1", subtask_id="s1")


def crear_app(rutas):
    app = FastAPI()
    router = APIRouter(dependencies=[Depends(autorizar)])
    for metodo, ruta in rutas:
        router.add_api_route(ruta, lambda: {"ok": True}, methods=[metodo])
    app.include_router(router)
    return app


@pytest.fixture
def app():
    app = crear_app([*ROLES_PERMITIDOS, ("GET", "/health")])
    app.dependency_overrides[obtener_verificador] = lambda: FakeTokenVerifier(IDENTIDADES)
    return app


@pytest.fixture
def cliente(app):
    return TestClient(app)


def con_token(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("metodo, ruta", list(ROLES_PERMITIDOS))
def test_sin_token_es_401_con_www_authenticate(cliente, metodo, ruta):
    respuesta = cliente.request(metodo, concreta(ruta))
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "cabecera",
    ["Bearer", "Bearer ", "Bearer a b", "Basic dXNlcjpwYXNz", "tok-analista", "Bearer tok-desconocido"],
)
def test_cabecera_mal_formada_o_token_desconocido_es_401(cliente, cabecera):
    respuesta = cliente.post("/cases", headers={"Authorization": cabecera})
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("metodo, ruta, rol", PARES)
def test_cada_rol_solo_pasa_donde_la_matriz_lo_permite(cliente, metodo, ruta, rol):
    respuesta = cliente.request(metodo, concreta(ruta), headers=con_token(f"tok-{rol.value}"))
    esperado = 200 if rol in ROLES_PERMITIDOS[(metodo, ruta)] else 403
    assert respuesta.status_code == esperado


def test_con_permiso_la_respuesta_es_la_del_manejador(cliente):
    respuesta = cliente.post("/cases", headers=con_token("tok-analista"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}


def test_rol_insuficiente_no_lleva_www_authenticate(cliente):
    respuesta = cliente.post("/cases/c1/cancel", headers=con_token("tok-analista"))
    assert respuesta.status_code == 403
    assert "WWW-Authenticate" not in respuesta.headers


@pytest.mark.parametrize("metodo, ruta", [("GET", "/cases"), ("POST", "/cases")])
def test_health_no_pide_token_y_las_demas_rutas_si(cliente, metodo, ruta):
    assert cliente.get("/health").status_code == 200
    assert cliente.request(metodo, ruta).status_code == 401


def test_health_no_verifica_el_token_aunque_venga_mal(cliente):
    assert cliente.get("/health", headers=con_token("basura")).status_code == 200


def test_rol_desconocido_en_la_identidad_es_403_y_no_500(app):
    app.dependency_overrides[obtener_verificador] = lambda: FakeTokenVerifier({"t": Identity("x", "superusuario")})
    respuesta = TestClient(app).get("/cases", headers=con_token("t"))
    assert respuesta.status_code == 403


def test_ruta_sin_clasificar_se_deniega_aunque_el_rol_sea_administrador(app):
    app.add_api_route("/nueva", lambda: {"ok": True}, methods=["GET"], dependencies=[Depends(autorizar)])
    respuesta = TestClient(app).get("/nueva", headers=con_token("tok-administrador"))
    assert respuesta.status_code == 403


def test_con_jwt_real_el_rol_desconocido_es_403(app):
    secreto, reloj = secrets.token_hex(32), FakeClock()
    ahora = int(reloj.now().timestamp())
    token = jwt.encode({"sub": "x", "role": "root", "iat": ahora, "exp": ahora + 600}, secreto, algorithm="HS256")
    app.dependency_overrides[obtener_verificador] = lambda: JwtTokenVerifier(secreto, reloj)
    assert TestClient(app).get("/cases", headers=con_token(token)).status_code == 403


def test_con_jwt_real_expirado_es_401(app):
    secreto, reloj = secrets.token_hex(32), FakeClock()
    token = issue_token(secreto, role=ADMINISTRADOR, subject="demo", clock=reloj, minutes=1)
    reloj.advance(timedelta(minutes=2))
    app.dependency_overrides[obtener_verificador] = lambda: JwtTokenVerifier(secreto, reloj)
    respuesta = TestClient(app).get("/cases", headers=con_token(token))
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_sin_secreto_configurado_todo_es_401_y_health_sigue_publica(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
    cliente = TestClient(crear_app([*ROLES_PERMITIDOS, ("GET", "/health")]))
    token = issue_token(secrets.token_hex(32), role=ADMINISTRADOR, subject="demo", clock=FakeClock())
    for metodo, ruta in ROLES_PERMITIDOS:
        respuesta = cliente.request(metodo, concreta(ruta), headers=con_token(token))
        assert respuesta.status_code == 401, (metodo, ruta)
    assert cliente.get("/health").status_code == 200

