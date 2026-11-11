from types import MappingProxyType

import pytest

from src.domain import rbac
from src.domain.rbac import Action, Role, can

PERMITIDAS = {
    Role.ANALISTA: {Action.CREAR_CASO, Action.CONSULTAR_CASO},
    Role.SUPERVISOR: {
        Action.CONSULTAR_CASO,
        Action.CANCELAR_CASO,
        Action.VER_MONITOREO,
    },
    Role.ADMINISTRADOR: {
        Action.CREAR_CASO,
        Action.CONSULTAR_CASO,
        Action.CANCELAR_CASO,
        Action.VER_MONITOREO,
    },
    Role.SERVICIO: {Action.REPORTAR_SUBTAREA},
}

TODOS_LOS_PARES = [(rol, accion) for rol in Role for accion in Action]


def test_la_prueba_cubre_todos_los_roles_y_acciones():
    assert set(PERMITIDAS) == set(Role)
    assert {a.value for a in Action} == {
        "crear_caso",
        "consultar_caso",
        "cancelar_caso",
        "ver_monitoreo",
        "reportar_subtarea",
    }
    assert {r.value for r in Role} == {
        "analista",
        "supervisor",
        "administrador",
        "servicio",
    }


@pytest.mark.parametrize(("rol", "accion"), TODOS_LOS_PARES)
def test_matriz_de_permisos(rol, accion):
    assert can(rol, accion) is (accion in PERMITIDAS[rol])


@pytest.mark.parametrize("accion", list(Action))
def test_servicio_solo_puede_reportar_subtarea(accion):
    assert can(Role.SERVICIO, accion) is (accion is Action.REPORTAR_SUBTAREA)


@pytest.mark.parametrize("rol", [r for r in Role if r is not Role.SERVICIO])
def test_los_roles_humanos_no_pueden_reportar_subtarea(rol):
    assert can(rol, Action.REPORTAR_SUBTAREA) is False


@pytest.mark.parametrize("accion", list(Action))
@pytest.mark.parametrize("rol_desconocido", ["root", "ANALISTA", "", "analista "])
def test_rol_desconocido_no_tiene_permisos(rol_desconocido, accion):
    assert can(rol_desconocido, accion) is False


@pytest.mark.parametrize("rol", list(Role))
@pytest.mark.parametrize("accion_desconocida", ["borrar_todo", "", "CREAR_CASO"])
def test_accion_desconocida_se_deniega(rol, accion_desconocida):
    assert can(rol, accion_desconocida) is False


@pytest.mark.parametrize("valor", [None, 0, 1, 1.5, b"analista", [], {}, object()])
def test_tipos_incorrectos_se_deniegan_sin_excepcion(valor):
    assert can(valor, Action.CONSULTAR_CASO) is False
    assert can(Role.ADMINISTRADOR, valor) is False
    assert can(valor, valor) is False


def test_el_valor_de_un_rol_no_equivale_al_rol():
    assert can(Role.ADMINISTRADOR.value, Action.CREAR_CASO.value) is False


def test_la_matriz_es_inmutable():
    matriz = rbac.PERMISOS
    assert isinstance(matriz, MappingProxyType)
    with pytest.raises(TypeError):
        matriz[Role.SERVICIO] = frozenset(Action)
    with pytest.raises(TypeError):
        del matriz[Role.ANALISTA]


@pytest.mark.parametrize("rol", list(Role))
def test_los_permisos_de_cada_rol_son_inmutables(rol):
    permisos = rbac.PERMISOS[rol]
    assert isinstance(permisos, frozenset)
    assert not hasattr(permisos, "add")


def test_mutar_la_matriz_no_cambia_can():
    antes = {(r, a): can(r, a) for r, a in TODOS_LOS_PARES}
    with pytest.raises(TypeError):
        rbac.PERMISOS[Role.ANALISTA] = frozenset(Action)
    assert {(r, a): can(r, a) for r, a in TODOS_LOS_PARES} == antes


def test_la_matriz_tiene_una_entrada_por_rol():
    assert set(rbac.PERMISOS) == set(Role)
