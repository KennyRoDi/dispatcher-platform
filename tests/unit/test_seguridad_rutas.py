import pytest

import src.coordinator.main as main
from src.coordinator.seguridad import ACCIONES_POR_RUTA, RUTAS_PUBLICAS
from src.domain.rbac import Action

ESPERADO = {
    ("POST", "/cases"): Action.CREAR_CASO,
    ("POST", "/cases/"): Action.CREAR_CASO,
    ("GET", "/cases"): Action.CONSULTAR_CASO,
    ("GET", "/cases/"): Action.CONSULTAR_CASO,
    ("GET", "/cases/{case_id}"): Action.CONSULTAR_CASO,
    ("GET", "/cases/{case_id}/report"): Action.CONSULTAR_CASO,
    ("GET", "/subtasks/{subtask_id}"): Action.CONSULTAR_CASO,
    ("POST", "/cases/{case_id}/cancel"): Action.CANCELAR_CASO,
    ("GET", "/workers"): Action.VER_MONITOREO,
    ("GET", "/stats"): Action.VER_MONITOREO,
    ("GET", "/hardware"): Action.VER_MONITOREO,
    ("POST", "/subtasks/report"): Action.REPORTAR_SUBTAREA,
}
DOCUMENTACION = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}


# FastAPI 0.141 no aplana los routers incluidos: viven en original_router.
def hojas(rutas):
    for ruta in rutas:
        if hasattr(ruta, "original_router"):
            yield from hojas(ruta.original_router.routes)
        else:
            yield ruta


def rutas_de_la_app():
    rutas = set()
    for ruta in hojas(main.app.routes):
        metodos = getattr(ruta, "methods", None) or {"*"}
        rutas.update((metodo, ruta.path) for metodo in metodos - {"HEAD", "OPTIONS"})
    return rutas


def test_el_mapa_ruta_accion_es_el_de_la_matriz_del_spec():
    assert dict(ACCIONES_POR_RUTA) == ESPERADO


def test_las_acciones_del_mapa_son_acciones_del_dominio():
    assert all(isinstance(accion, Action) for accion in ACCIONES_POR_RUTA.values())


def test_toda_ruta_esta_clasificada():
    sin_clasificar = rutas_de_la_app() - set(ACCIONES_POR_RUTA) - set(RUTAS_PUBLICAS)
    assert not sin_clasificar, sorted(sin_clasificar)


def test_el_mapa_no_tiene_rutas_inexistentes():
    assert set(ACCIONES_POR_RUTA) <= rutas_de_la_app()


def test_health_es_publica():
    assert ("GET", "/health") in RUTAS_PUBLICAS
    assert ("GET", "/health") not in ACCIONES_POR_RUTA


def test_solo_health_y_la_documentacion_pueden_ser_publicas():
    assert {ruta for _, ruta in RUTAS_PUBLICAS} <= {"/health"} | DOCUMENTACION
    assert {metodo for metodo, _ in RUTAS_PUBLICAS} == {"GET"}


def test_ninguna_ruta_esta_a_la_vez_protegida_y_publica():
    assert not set(ACCIONES_POR_RUTA) & set(RUTAS_PUBLICAS)


@pytest.mark.parametrize("ruta", sorted(DOCUMENTACION))
def test_las_rutas_de_documentacion_estan_deshabilitadas_o_clasificadas(ruta):
    existe = ("GET", ruta) in rutas_de_la_app()
    assert not existe or ("GET", ruta) in RUTAS_PUBLICAS
