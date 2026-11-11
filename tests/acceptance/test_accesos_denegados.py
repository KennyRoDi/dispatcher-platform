import os

import pytest
import requests

pytestmark = pytest.mark.acceptance

ROLES = ("analista", "supervisor", "administrador")
RUTAS_MONITOREO = ("/workers", "/stats", "/hardware")


@pytest.fixture(scope="module")
def entorno():
    coordinador = os.environ.get("COORDINATOR_URL")
    tokens = {rol: os.environ.get(f"TOKEN_{rol.upper()}") for rol in ROLES}
    if not coordinador or not all(tokens.values()):
        pytest.skip("define COORDINATOR_URL, TOKEN_ANALISTA, TOKEN_SUPERVISOR y TOKEN_ADMINISTRADOR")
    return coordinador.rstrip("/"), tokens


def pedir(entorno, metodo, ruta, rol=None, **kwargs):
    url, tokens = entorno
    cabeceras = {"Authorization": f"Bearer {tokens[rol]}"} if rol else {}
    return requests.request(metodo, f"{url}{ruta}", headers=cabeceras, timeout=10, **kwargs)


@pytest.mark.parametrize("ruta", ("/cases", *RUTAS_MONITOREO))
def test_sin_token_es_401(entorno, ruta):
    respuesta = pedir(entorno, "GET", ruta)
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("ruta", RUTAS_MONITOREO)
def test_analista_no_ve_el_monitoreo(entorno, ruta):
    assert pedir(entorno, "GET", ruta, "analista").status_code == 403


@pytest.mark.parametrize("rol", ("supervisor", "administrador"))
@pytest.mark.parametrize("ruta", RUTAS_MONITOREO)
def test_supervisor_y_administrador_ven_el_monitoreo(entorno, rol, ruta):
    assert pedir(entorno, "GET", ruta, rol).status_code == 200


def test_supervisor_no_crea_casos(entorno):
    cuerpo = {"subtasks": [{"task_type": "auto", "file_path": "videos/a.mp4"}]}
    assert pedir(entorno, "POST", "/cases", "supervisor", json=cuerpo).status_code == 403


def test_analista_no_cancela_casos(entorno):
    assert pedir(entorno, "POST", "/cases/inexistente/cancel", "analista").status_code == 403


@pytest.mark.parametrize("rol", ROLES)
def test_ningun_rol_humano_reporta_subtareas(entorno, rol):
    assert pedir(entorno, "POST", "/subtasks/report", rol, json={}).status_code == 403
