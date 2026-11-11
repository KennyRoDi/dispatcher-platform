import logging
import os
from functools import lru_cache
from datetime import datetime, timezone
from types import MappingProxyType

from fastapi import Depends, HTTPException, Request

from src.adapters.jwt_tokens import ClosedVerifier, verificador_desde_entorno
from src.application.ports import InvalidToken, TokenVerifier
from src.domain.rbac import Action, can

log = logging.getLogger(__name__)

ACCIONES_POR_RUTA = MappingProxyType(
    {
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
)

RUTAS_PUBLICAS = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
    }
)


class _UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@lru_cache(maxsize=4)
def _verificador_para(archivo: str | None, secreto: str | None) -> TokenVerifier:
    entorno = {"JWT_SECRET_FILE": archivo or "", "JWT_SECRET": secreto or ""}
    try:
        return verificador_desde_entorno(entorno, _UtcClock())
    except ValueError as error:
        log.error("autenticacion cerrada por configuracion de secreto invalida: %s", error)
        return ClosedVerifier()


def obtener_verificador() -> TokenVerifier:
    return _verificador_para(os.environ.get("JWT_SECRET_FILE"), os.environ.get("JWT_SECRET"))


def _unauthorized() -> HTTPException:
    return HTTPException(
        401, "credenciales ausentes o invalidas", headers={"WWW-Authenticate": "Bearer"}
    )


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        raise _unauthorized()
    return token


def autorizar(request: Request, verificador: TokenVerifier = Depends(obtener_verificador)) -> None:
    clave = (request.method, request.scope["route"].path)
    if clave in RUTAS_PUBLICAS:
        return
    try:
        identidad = verificador.verify(_bearer_token(request))
    except InvalidToken:
        raise _unauthorized() from None
    accion = ACCIONES_POR_RUTA.get(clave)
    if accion is None or not can(identidad.role, accion):
        raise HTTPException(403, "rol sin permiso para esta ruta")
