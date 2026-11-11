"""Redis y MinIO reales con TLS, levantados con los mismos parámetros del docker-compose.yml.

Se omiten sin Docker, sin openssl o sin RUN_DOCKER_TLS=1 (descargan imágenes y publican puertos locales).
"""
import os
import re
import shutil
import socket
import ssl
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import redis
import urllib3
import yaml
from minio import Minio

from src.infrastructure.tls import TlsSettings, minio_http_client, redis_kwargs

pytestmark = pytest.mark.integration

RAIZ = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
CLAVE_REDIS = "clave-de-prueba"
ACCESO_MINIO, SECRETO_MINIO = "acceso-de-prueba", "secreto-de-prueba-largo"


def _docker_disponible() -> bool:
    if shutil.which("docker") is None or shutil.which("openssl") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False, timeout=30).returncode == 0


if os.environ.get("RUN_DOCKER_TLS") != "1" or not _docker_disponible():
    pytest.skip("requiere Docker, openssl y RUN_DOCKER_TLS=1", allow_module_level=True)


def _resolver(texto: str, valores: dict[str, str]) -> str:
    def sustituir(coincidencia: re.Match) -> str:
        nombre, operador, resto = coincidencia[1], coincidencia[2], coincidencia[3]
        if nombre in valores:
            return valores[nombre]
        return resto if operador == ":-" else ""

    return re.sub(r"\$\{(\w+)(?:(:-|:\?)([^}]*))?\}", sustituir, str(texto))


def _servicio(nombre: str) -> dict:
    return yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))["services"][nombre]


@pytest.fixture(scope="module")
def certificados(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("certs") / "salida"
    entorno = {"PATH": os.environ["PATH"], "HOME": str(destino.parent), "CERTS_DIR": str(destino), "NODE_IP": HOST, "NODE_NAME": "localhost"}
    resultado = subprocess.run(["bash", str(RAIZ / "deploy/tls/generar_certs.sh")], env=entorno, capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, resultado.stderr
    # Las imágenes corren con otro UID: solo en la prueba se abre la lectura de las llaves (SPEC, pregunta 5).
    for archivo in destino.rglob("*"):
        archivo.chmod(0o755 if archivo.is_dir() else 0o644)
    return destino


@pytest.fixture(scope="module")
def ajustes(certificados) -> TlsSettings:
    return TlsSettings(enabled=True, ca_file=certificados / "ca.pem")


def _levantar(nombre: str, certificados: Path, puerto_interno: int, extra_env: dict[str, str]):
    servicio = _servicio(nombre)
    valores = {"CERTS_DIR": str(certificados), "REDIS_PASSWORD": CLAVE_REDIS, "MINIO_ACCESS_KEY": ACCESO_MINIO,
               "MINIO_SECRET_KEY": SECRETO_MINIO, "NODE_IP": HOST, **extra_env}
    comando = [_resolver(argumento, valores) for argumento in servicio["command"]] if isinstance(servicio["command"], list) \
        else _resolver(servicio["command"], valores).split()
    montajes = []
    for volumen in servicio.get("volumes") or []:
        origen = _resolver(volumen.split(":")[0], valores)
        if origen.startswith(str(certificados)):
            montajes += ["-v", f"{origen}:{volumen.split(':')[1]}:ro"]
    entorno = []
    for clave, valor in (servicio.get("environment") or {}).items():
        entorno += ["-e", f"{clave}={_resolver(valor, valores)}"]
    contenedor = f"tls-{nombre}-{uuid.uuid4().hex[:8]}"
    imagen = _resolver(servicio["image"], valores)
    arranque = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", contenedor, "-p", f"{HOST}::{puerto_interno}", *montajes, *entorno, imagen, *comando],
        capture_output=True, text=True, check=False, timeout=600,
    )
    assert arranque.returncode == 0, arranque.stderr
    puerto = subprocess.run(["docker", "port", contenedor, str(puerto_interno)], capture_output=True, text=True, check=True).stdout
    return contenedor, int(puerto.strip().splitlines()[0].rsplit(":", 1)[1])


def _esperar(puerto: int, contenedor: str, segundos: int = 60) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        try:
            socket.create_connection((HOST, puerto), timeout=1).close()
            return
        except OSError:
            time.sleep(0.5)
    registro = subprocess.run(["docker", "logs", contenedor], capture_output=True, text=True, check=False)
    pytest.fail(f"{contenedor} no escucha en {puerto}: {registro.stdout[-800:]}{registro.stderr[-800:]}")


@pytest.fixture(scope="module")
def redis_tls(certificados):
    contenedor, puerto = _levantar("redis", certificados, 6380, {})
    _esperar(puerto, contenedor)
    yield contenedor, puerto
    subprocess.run(["docker", "rm", "-f", contenedor], capture_output=True, check=False)


@pytest.fixture(scope="module")
def minio_tls(certificados):
    contenedor, puerto = _levantar("minio", certificados, 9000, {})
    _esperar(puerto, contenedor)
    yield contenedor, puerto
    subprocess.run(["docker", "rm", "-f", contenedor], capture_output=True, check=False)


def test_redis_tls_real_acepta_al_cliente_con_la_ca(redis_tls, ajustes):
    _, puerto = redis_tls
    cliente = redis.Redis(host=HOST, port=puerto, password=CLAVE_REDIS, **redis_kwargs(ajustes))
    assert cliente.ping() is True


def test_redis_tls_real_rechaza_al_cliente_sin_la_ca(redis_tls):
    _, puerto = redis_tls
    cliente = redis.Redis(host=HOST, port=puerto, password=CLAVE_REDIS, ssl=True, ssl_cert_reqs="required")
    with pytest.raises((redis.exceptions.ConnectionError, ssl.SSLError)):
        cliente.ping()


def test_redis_tls_real_rechaza_la_conexion_en_claro(redis_tls):
    _, puerto = redis_tls
    cliente = redis.Redis(host=HOST, port=puerto, password=CLAVE_REDIS, socket_timeout=3)
    with pytest.raises(redis.exceptions.RedisError):
        cliente.ping()


def test_redis_real_tiene_cerrado_el_puerto_en_claro(redis_tls):
    contenedor, _ = redis_tls
    intento = subprocess.run(["docker", "exec", contenedor, "redis-cli", "-p", "6379", "ping"], capture_output=True, text=True, check=False)
    assert "PONG" not in intento.stdout
    assert intento.returncode != 0


def test_redis_real_no_negocia_tls12(redis_tls, ajustes):
    _, puerto = redis_tls
    contexto = ssl.create_default_context(cafile=str(ajustes.ca_file))
    contexto.maximum_version = ssl.TLSVersion.TLSv1_2
    with pytest.raises(ssl.SSLError), socket.create_connection((HOST, puerto), timeout=5) as crudo:
        contexto.wrap_socket(crudo, server_hostname=HOST)


def _minio(puerto: int, secure: bool = True, http_client=None) -> Minio:
    return Minio(f"{HOST}:{puerto}", access_key=ACCESO_MINIO, secret_key=SECRETO_MINIO, secure=secure, http_client=http_client)


def test_minio_tls_real_con_la_ca_lista_y_crea_buckets(minio_tls, ajustes):
    _, puerto = minio_tls
    cliente = _minio(puerto, http_client=minio_http_client(ajustes))
    nombre = f"tls-{uuid.uuid4().hex[:8]}"
    cliente.make_bucket(nombre)
    assert nombre in [bucket.name for bucket in cliente.list_buckets()]


def test_minio_tls_real_rechaza_al_cliente_sin_la_ca(minio_tls):
    _, puerto = minio_tls
    cliente = _minio(puerto, http_client=urllib3.PoolManager(retries=False, timeout=5))
    with pytest.raises(urllib3.exceptions.HTTPError):
        cliente.list_buckets()


def test_minio_tls_real_no_atiende_http_en_claro(minio_tls):
    _, puerto = minio_tls
    cliente = _minio(puerto, secure=False, http_client=urllib3.PoolManager(retries=False, timeout=5))
    with pytest.raises(Exception):
        cliente.list_buckets()
