import os
import stat
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

import jwt  # PyJWT (MIT), https://github.com/jpadilla/pyjwt

from src.application.ports import Clock, Identity, InvalidToken, TokenVerifier
from src.domain.rbac import Role

ALGORITHM = "HS256"
MIN_SECRET_BYTES = 32
DEFAULT_MINUTES = 60
REQUIRED_CLAIMS = ("sub", "role", "iat", "exp")


def _checked_secret(secret: str | bytes | None) -> str | bytes:
    if not secret or len(secret.encode() if isinstance(secret, str) else secret) < MIN_SECRET_BYTES:
        raise ValueError(f"el secreto JWT debe tener al menos {MIN_SECRET_BYTES} bytes")
    return secret


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class JwtTokenVerifier:
    def __init__(self, secret: str | bytes | None, clock: Clock) -> None:
        self._secret = _checked_secret(secret)
        self._clock = clock

    def verify(self, token: str) -> Identity:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"require": list(REQUIRED_CLAIMS), "verify_exp": False, "verify_iat": False},
            )
        except jwt.PyJWTError:
            raise InvalidToken("token invalido") from None
        subject, role = claims["sub"], claims["role"]
        if not (isinstance(subject, str) and isinstance(role, str)):
            raise InvalidToken("reclamos con tipo invalido")
        self._check_validity_window(claims["iat"], claims["exp"])
        try:
            return Identity(subject, Role(role))
        except ValueError:
            return Identity(subject, role)

    def _check_validity_window(self, issued_at: object, expires_at: object) -> None:
        if not (_is_number(issued_at) and _is_number(expires_at)):
            raise InvalidToken("iat y exp deben ser numericos")
        now = self._clock.now().timestamp()
        if issued_at > now or expires_at <= now:
            raise InvalidToken("token fuera de su ventana de validez")


class ClosedVerifier:
    def verify(self, token: str) -> Identity:
        raise InvalidToken("autenticacion sin secreto configurado")


def issue_token(
    secret: str | bytes,
    *,
    role: Role,
    subject: str,
    clock: Clock,
    minutes: int = DEFAULT_MINUTES,
) -> str:
    issued_at = clock.now()
    claims = {
        "sub": subject,
        "role": role.value,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(claims, _checked_secret(secret), algorithm=ALGORITHM)


def _secret_from_file(path: str) -> str:
    try:
        with Path(path).open() as handle:
            mode = os.fstat(handle.fileno()).st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise ValueError("JWT_SECRET_FILE no debe tener permisos para grupo ni otros")
            return handle.read().rstrip("\r\n")
    except OSError:
        raise ValueError("JWT_SECRET_FILE no se pudo leer") from None


def verificador_desde_entorno(env: Mapping[str, str], clock: Clock) -> TokenVerifier:
    if env.get("JWT_SECRET_FILE"):
        return JwtTokenVerifier(_secret_from_file(env["JWT_SECRET_FILE"]), clock)
    if env.get("JWT_SECRET"):
        return JwtTokenVerifier(env["JWT_SECRET"], clock)
    return ClosedVerifier()
