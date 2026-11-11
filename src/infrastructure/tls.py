import logging
import os
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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
        ca_file = Path(raw_path)
        if not ca_file.is_file():
            raise TlsConfigError("TLS_CA_FILE no apunta a un archivo existente")
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
    if coordinator_url is not None and not coordinator_url.lower().startswith("https://"):
        raise TlsConfigError("con TLS activo la URL del coordinador debe usar https://")
    if redis_url is not None and not redis_url.lower().startswith("rediss://"):
        raise TlsConfigError("con TLS activo la URL de Redis debe usar rediss://")
    if minio_secure is False:
        raise TlsConfigError("con TLS activo MinIO debe usar conexión segura")


def redis_kwargs(settings: TlsSettings) -> dict:
    if not settings.enabled:
        return {}
    return {
        "ssl": True,
        "ssl_ca_certs": str(settings.ca_file),
        "ssl_cert_reqs": "required",
        "ssl_check_hostname": True,
        "ssl_min_version": ssl.TLSVersion.TLSv1_3,
    }


def requests_session(settings: TlsSettings) -> requests.Session:
    session = requests.Session()
    if settings.enabled:
        session.verify = str(settings.ca_file)
    return session


def minio_http_client(settings: TlsSettings) -> urllib3.PoolManager | None:
    if not settings.enabled:
        return None
    return urllib3.PoolManager(ssl_context=client_context(settings))
