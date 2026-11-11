from enum import Enum
from types import MappingProxyType


class Role(Enum):
    ANALISTA = "analista"
    SUPERVISOR = "supervisor"
    ADMINISTRADOR = "administrador"
    SERVICIO = "servicio"


class Action(Enum):
    CREAR_CASO = "crear_caso"
    CONSULTAR_CASO = "consultar_caso"
    CANCELAR_CASO = "cancelar_caso"
    VER_MONITOREO = "ver_monitoreo"
    REPORTAR_SUBTAREA = "reportar_subtarea"


PERMISOS = MappingProxyType(
    {
        Role.ANALISTA: frozenset({Action.CREAR_CASO, Action.CONSULTAR_CASO}),
        Role.SUPERVISOR: frozenset(
            {Action.CONSULTAR_CASO, Action.CANCELAR_CASO, Action.VER_MONITOREO}
        ),
        Role.ADMINISTRADOR: frozenset(
            {
                Action.CREAR_CASO,
                Action.CONSULTAR_CASO,
                Action.CANCELAR_CASO,
                Action.VER_MONITOREO,
            }
        ),
        Role.SERVICIO: frozenset({Action.REPORTAR_SUBTAREA}),
    }
)


def can(role: object, action: object) -> bool:
    if not isinstance(role, Role) or not isinstance(action, Action):
        return False
    return action in PERMISOS[role]
