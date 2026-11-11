import logging
import os
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit

import requests
import urllib3

logger = logging.getLogger(__name__)

DISABLING_VALUES = frozenset({"0", "false", "no", "off"})


class TlsConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TlsSettings:
    enabled: bool
    ca_file: Path | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "TlsSettings":
        env = os.environ if env is None else env
        if env.get("TLS_ENABLED", "").strip().lower() in DISABLING_VALUES:
            logger.warning("TLS_ENABLED desactivado: el tráfico entre nodos viaja en claro")
            return cls(enabled=False, ca_file=None)
        raw_path = env.get("TLS_CA_FILE", "").strip()
        if not raw_path:
            raise TlsConfigError("TLS activo: falta TLS_CA_FILE con la ruta de ca.pem")
        ca_file = Path(os.path.abspath(raw_path))
        if not ca_file.is_file():
            raise TlsConfigError("TLS_CA_FILE no apunta a un archivo existente")
        try:
            ca_file.open("rb").close()
        except OSError:
            raise TlsConfigError("TLS_CA_FILE no se puede leer") from None
        return cls(enabled=True, ca_file=ca_file)


def client_context(settings: TlsSettings) -> ssl.SSLContext:
    if not settings.enabled or settings.ca_file is None:
        raise TlsConfigError("no hay contexto TLS de cliente con TLS desactivado")
    try:
        context = ssl.create_default_context(cafile=str(settings.ca_file))
    except (ssl.SSLError, OSError):
        raise TlsConfigError("TLS_CA_FILE no contiene un certificado PEM válido") from None
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    return context


def exigir_cifrado(
    settings: TlsSettings,
    *,
    coordinator_url: str | None = None,
    redis_url: str | None = None,
    minio_secure: bool | None = None,
) -> None:
    if not settings.enabled:
        return
    if coordinator_url is not None:
        _require_secure_url(coordinator_url, "https://", "la URL del coordinador")
    if redis_url is not None:
        _require_secure_url(redis_url, "rediss://", "la URL de Redis")
        if any(key.lower().startswith("ssl") for key, _ in _query_pairs(redis_url)):
            raise TlsConfigError("con TLS activo la URL de Redis no puede fijar opciones ssl_ en la query")
    if minio_secure is not None and minio_secure is not True:
        raise TlsConfigError("con TLS activo MinIO debe usar conexión segura")


def _query_pairs(url: str) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def _require_secure_url(url: str, prefix: str, name: str) -> None:
    if not url.lower().startswith(prefix):
        raise TlsConfigError(f"con TLS activo {name} debe usar {prefix}")
    try:
        host = urlsplit(url).hostname
    except ValueError:
        host = None
    if not host:
        raise TlsConfigError(f"{name} no es una URL válida")


def _require_ca(settings: TlsSettings) -> Path:
    client_context(settings)
    return settings.ca_file


def redis_kwargs(settings: TlsSettings) -> dict:
    if not settings.enabled:
        return {}
    return {
        "ssl": True,
        "ssl_ca_certs": str(_require_ca(settings)),
        "ssl_cert_reqs": "required",
        "ssl_check_hostname": True,
        "ssl_min_version": ssl.TLSVersion.TLSv1_3,
    }


class _HttpsOnlySession(requests.Session):
    def get_redirect_target(self, resp):
        target = super().get_redirect_target(resp)
        if target and urlsplit(urljoin(resp.url, target)).scheme != "https":
            raise requests.exceptions.InvalidSchema("redirección de https a un esquema en claro rechazada")
        return target


def requests_session(settings: TlsSettings) -> requests.Session:
    session = _HttpsOnlySession() if settings.enabled else requests.Session()
    if settings.enabled:
        session.trust_env = False
        session.verify = str(_require_ca(settings))
    return session


def minio_http_client(settings: TlsSettings) -> urllib3.PoolManager | None:
    if not settings.enabled:
        return None
    return urllib3.PoolManager(ssl_context=client_context(settings))
