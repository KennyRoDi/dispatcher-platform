import logging
import os
from functools import lru_cache
from types import MappingProxyType

from fastapi import Depends, HTTPException, Request
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.adapters.jwt_tokens import ClosedVerifier, UtcClock, verificador_desde_entorno
from src.application.ports import InvalidToken, TokenVerifier
from src.domain.rbac import Action, can

log = logging.getLogger(__name__)

ACCIONES_POR_RUTA = MappingProxyType(
    {
        ("POST", "/cases"): Action.CREAR_CASO,
        ("POST", "/uploads"): Action.CREAR_CASO,
        ("PUT", "/uploads/{upload_id}/chunks/{index}"): Action.CREAR_CASO,
        ("GET", "/uploads/{upload_id}"): Action.CONSULTAR_CASO,
        ("POST", "/uploads/{upload_id}/complete"): Action.CREAR_CASO,
        ("POST", "/cases/"): Action.CREAR_CASO,
        ("GET", "/cases"): Action.CONSULTAR_CASO,
        ("GET", "/cases/"): Action.CONSULTAR_CASO,
        ("GET", "/cases/{case_id}"): Action.CONSULTAR_CASO,
        ("GET", "/cases/{case_id}/report"): Action.CONSULTAR_CASO,
        ("GET", "/cases/{case_id}/consolidated-report"): Action.CONSULTAR_CASO,
        ("GET", "/subtasks/{subtask_id}"): Action.CONSULTAR_CASO,
        ("POST", "/cases/{case_id}/cancel"): Action.CANCELAR_CASO,
        ("GET", "/workers"): Action.VER_MONITOREO,
        ("GET", "/stats"): Action.VER_MONITOREO,
        ("GET", "/hardware"): Action.VER_MONITOREO,
        ("GET", "/alerts"): Action.VER_MONITOREO,
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


@lru_cache(maxsize=4)
def _verificador_para(archivo: str | None, secreto: str | None) -> TokenVerifier:
    entorno = {"JWT_SECRET_FILE": archivo or "", "JWT_SECRET": secreto or ""}
    try:
        return verificador_desde_entorno(entorno, UtcClock())
    except ValueError as error:
        log.error("autenticacion cerrada por configuracion de secreto invalida: %s", error)
        return ClosedVerifier()


def obtener_verificador() -> TokenVerifier:
    return _verificador_para(os.environ.get("JWT_SECRET_FILE"), os.environ.get("JWT_SECRET"))


def _unauthorized() -> HTTPException:
    return HTTPException(
        401, "credenciales ausentes o invalidas", headers={"WWW-Authenticate": "Bearer"}
    )


def _bearer_token(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        raise _unauthorized()
    return token


def autorizar(request: Request, verificador: TokenVerifier = Depends(obtener_verificador)) -> None:
    clave = (request.method, request.scope["route"].path)
    if clave in RUTAS_PUBLICAS:
        return
    try:
        identidad = verificador.verify(_bearer_token(request.headers.get("Authorization", "")))
    except InvalidToken:
        raise _unauthorized() from None
    accion = ACCIONES_POR_RUTA.get(clave)
    if accion is None or not can(identidad.role, accion):
        raise HTTPException(403, "rol sin permiso para esta ruta")


class AutenticacionPrevia:
    """Rechaza con 401 antes de que FastAPI lea o valide el cuerpo."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not self._autorizada(scope):
            error = _unauthorized()
            respuesta = JSONResponse({"detail": error.detail}, 401, headers=error.headers)
            return await respuesta(scope, receive, send)
        await self.app(scope, receive, send)

    @staticmethod
    def _autorizada(scope: Scope) -> bool:
        if (scope["method"], scope["path"]) in RUTAS_PUBLICAS:
            return True
        reemplazos = scope["app"].dependency_overrides
        if autorizar in reemplazos:
            return True
        obtener = reemplazos.get(obtener_verificador, obtener_verificador)
        try:
            token = _bearer_token(Headers(scope=scope).get("Authorization", ""))
            obtener().verify(token)
        except (HTTPException, InvalidToken):
            return False
        return True
