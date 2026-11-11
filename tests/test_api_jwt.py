import asyncio
import secrets
from datetime import datetime, timezone

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.jwt_tokens import issue_token
from src.coordinator import conexion
from src.domain.rbac import Role
from src.workers.config import Settings
from src.workers.reporter import Reporter

ANALISTA, SUPERVISOR, ADMINISTRADOR, SERVICIO = (
    Role.ANALISTA,
    Role.SUPERVISOR,
    Role.ADMINISTRADOR,
    Role.SERVICIO,
)
PERMITIDOS = {
    "crear_caso": {ANALISTA, ADMINISTRADOR},
    "consultar_lista": {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    "consultar_caso": {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    "consultar_reporte": {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    "consultar_subtarea": {ANALISTA, SUPERVISOR, ADMINISTRADOR},
    "cancelar_caso": {SUPERVISOR, ADMINISTRADOR},
    "workers": {SUPERVISOR, ADMINISTRADOR},
    "stats": {SUPERVISOR, ADMINISTRADOR},
    "hardware": {SUPERVISOR, ADMINISTRADOR},
    "reportar_subtarea": {SERVICIO},
}
ESTADO_OK = {"crear_caso": 201}
CUERPO_CASO = {"subtasks": [{"task_type": "auto", "file_path": "videos/a.mp4"}]}


class Ahora:
    def now(self):
        return datetime.now(timezone.utc)


@pytest.fixture
def secreto(monkeypatch):
    valor = secrets.token_hex(32)
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
    monkeypatch.setenv("JWT_SECRET", valor)
    return valor


@pytest.fixture
def fake(monkeypatch):
    redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", redis)
    return redis


@pytest.fixture
def cliente(fake, secreto):
    return TestClient(main.app)


def token(secreto, rol):
    return issue_token(secreto, role=rol, subject=f"u-{rol.value}", clock=Ahora())


def cabeceras(secreto, rol):
    return {"Authorization": f"Bearer {token(secreto, rol)}"}


def crear_caso(cliente, secreto):
    respuesta = cliente.post("/cases", json=CUERPO_CASO, headers=cabeceras(secreto, ADMINISTRADOR))
    assert respuesta.status_code == 201
    return respuesta.json()


def peticion(accion, cliente, secreto, rol):
    caso = crear_caso(cliente, secreto)
    case_id, subtask_id = caso["case_id"], caso["subtask_ids"][0]
    informe = {"subtask_id": subtask_id, "case_id": case_id, "status": "completed", "outputs": ["o"]}
    solicitudes = {
        "crear_caso": ("POST", "/cases", {"json": CUERPO_CASO}),
        "consultar_lista": ("GET", "/cases", {}),
        "consultar_caso": ("GET", f"/cases/{case_id}", {}),
        "consultar_reporte": ("GET", f"/cases/{case_id}/report", {}),
        "consultar_subtarea": ("GET", f"/subtasks/{subtask_id}", {}),
        "cancelar_caso": ("POST", f"/cases/{case_id}/cancel", {}),
        "workers": ("GET", "/workers", {}),
        "stats": ("GET", "/stats", {}),
        "hardware": ("GET", "/hardware", {}),
        "reportar_subtarea": ("POST", "/subtasks/report", {"json": informe}),
    }
    metodo, ruta, extra = solicitudes[accion]
    return cliente.request(metodo, ruta, headers=cabeceras(secreto, rol), **extra)


@pytest.mark.parametrize("rol", list(Role))
@pytest.mark.parametrize("accion", list(PERMITIDOS))
def test_api_con_jwt_real_por_rol(cliente, secreto, accion, rol):
    respuesta = peticion(accion, cliente, secreto, rol)
    if rol in PERMITIDOS[accion]:
        assert respuesta.status_code == ESTADO_OK.get(accion, 200), respuesta.text
    else:
        assert respuesta.status_code == 403


@pytest.mark.parametrize("ruta", ["/cases", "/cases/", "/workers", "/stats", "/hardware"])
def test_get_sin_token_es_401_con_la_api_real(cliente, ruta):
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("ruta", ["/cases", "/cases/", "/subtasks/report"])
def test_post_sin_token_es_401_con_la_api_real(cliente, ruta):
    assert cliente.post(ruta, json=CUERPO_CASO).status_code == 401


def test_token_firmado_con_otro_secreto_es_401(cliente):
    ajeno = secrets.token_hex(32)
    respuesta = cliente.get("/cases", headers=cabeceras(ajeno, ADMINISTRADOR))
    assert respuesta.status_code == 401


def test_barra_final_en_cases_se_autoriza_como_cases(cliente, secreto):
    cuerpo = CUERPO_CASO
    assert cliente.post("/cases/", json=cuerpo, headers=cabeceras(secreto, SUPERVISOR)).status_code == 403
    assert cliente.get("/cases/", headers=cabeceras(secreto, ANALISTA)).status_code == 200


def test_health_es_publica(cliente):
    assert cliente.get("/health").status_code == 200


def test_sin_secreto_configurado_todo_es_401_salvo_health(fake, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    cliente = TestClient(main.app)
    asumido = issue_token(secrets.token_hex(32), role=ADMINISTRADOR, subject="x", clock=Ahora())
    assert cliente.get("/cases", headers={"Authorization": f"Bearer {asumido}"}).status_code == 401
    assert cliente.get("/health").status_code == 200


class SesionAsgi:
    def __init__(self, cliente):
        self.cliente = cliente

    def post(self, url, **kwargs):
        return self.cliente.post(url, **kwargs)


def reportero(fake, cliente_http):
    ajustes = Settings.from_env({"COORDINATOR_URL": "http://testserver"})
    return Reporter(ajustes, fake, session=SesionAsgi(cliente_http), delays=(0,), sleep=lambda s: None)


def test_worker_reporta_con_token_servicio(fake, secreto):
    anonimo = TestClient(main.app)
    caso = crear_caso(anonimo, secreto)
    informe = {
        "subtask_id": caso["subtask_ids"][0],
        "case_id": caso["case_id"],
        "status": "completed",
        "worker_id": "w1",
        "outputs": ["o"],
    }
    worker = TestClient(main.app, headers=cabeceras(secreto, SERVICIO))
    assert reportero(fake, worker).report(informe) is True
    assert fake.hget(f"case:{caso['case_id']}", "status") == "completed"


def test_worker_sin_token_no_entrega_y_no_reintenta(fake, secreto):
    anonimo = TestClient(main.app, headers=cabeceras(secreto, ADMINISTRADOR))
    caso = crear_caso(anonimo, secreto)
    informe = {"subtask_id": caso["subtask_ids"][0], "case_id": caso["case_id"], "status": "completed"}
    sin_token = TestClient(main.app)
    assert reportero(fake, sin_token).report(informe) is False
    assert fake.hget(f"case:{caso['case_id']}", "status") != "completed"


@pytest.mark.parametrize("cabecera", [None, "Bearer basura"])
@pytest.mark.parametrize("ruta", ["/cases", "/subtasks/report"])
def test_json_roto_sin_credenciales_validas_es_401_y_no_422(cliente, ruta, cabecera):
    encabezados = {"content-type": "application/json"}
    if cabecera:
        encabezados["Authorization"] = cabecera
    respuesta = cliente.post(ruta, content=b"{", headers=encabezados)
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_json_roto_con_token_valido_llega_a_la_validacion_y_da_422(cliente, secreto):
    encabezados = {**cabeceras(secreto, ADMINISTRADOR), "content-type": "application/json"}
    assert cliente.post("/cases", content=b"{", headers=encabezados).status_code == 422


def test_cuerpo_no_se_lee_antes_de_autenticar():
    cuerpo_leido = []
    respuestas = []

    async def receive():
        cuerpo_leido.append(True)
        return {"type": "http.request", "body": b"x" * 1024, "more_body": False}

    async def send(mensaje):
        respuestas.append(mensaje)

    alcance = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": "/cases",
        "raw_path": b"/cases",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    asyncio.run(main.crear_app({})(alcance, receive, send))
    assert respuestas[0]["status"] == 401
    assert not cuerpo_leido
