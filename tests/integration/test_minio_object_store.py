import hashlib
import io
import os
import shutil
import socket
import subprocess
import threading
import time
import uuid

import minio
import pytest

from src.adapters.minio_object_store import MinioObjectStore
from tests.contratos import comprobar_object_store

pytestmark = pytest.mark.integration

IMAGEN_MINIO = os.environ.get("MINIO_IMAGE", "cgr.dev/chainguard/minio:latest")
MIB = 1 << 20


def _puerto_libre():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def cliente():
    """MinIO de `MINIO_ENDPOINT` o, si no hay, uno efímero en Docker sin TLS y con credenciales aleatorias."""
    endpoint = os.environ.get("MINIO_ENDPOINT")
    acceso, secreto = os.environ.get("MINIO_ACCESS_KEY"), os.environ.get("MINIO_SECRET_KEY")
    nombre = None
    if not (endpoint and acceso and secreto):
        if shutil.which("docker") is None:
            pytest.skip("sin Docker ni MINIO_ENDPOINT")
        nombre = f"f23-minio-{uuid.uuid4().hex[:8]}"
        puerto, acceso, secreto = _puerto_libre(), uuid.uuid4().hex, uuid.uuid4().hex
        arranque = subprocess.run([
            "docker", "run", "-d", "--rm", "--name", nombre, "-p", f"127.0.0.1:{puerto}:9000",
            "-e", f"MINIO_ROOT_USER={acceso}", "-e", f"MINIO_ROOT_PASSWORD={secreto}",
            IMAGEN_MINIO, "server", "/data",
        ], capture_output=True, text=True)
        if arranque.returncode != 0:
            pytest.skip(f"docker run falló: {arranque.stderr.strip()[:200]}")
        endpoint = f"127.0.0.1:{puerto}"
    try:
        conexion = minio.Minio(endpoint, access_key=acceso, secret_key=secreto, secure=False)
        for _ in range(30):
            try:
                conexion.list_buckets()
                break
            except Exception:
                time.sleep(1)
        else:
            pytest.skip(f"MinIO no responde en {endpoint}")
        yield conexion
    finally:
        if nombre:
            subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


@pytest.fixture
def bucket(cliente):
    nombre = f"f23-prueba-{uuid.uuid4().hex[:12]}"
    cliente.make_bucket(nombre)
    yield nombre
    for objeto in cliente.list_objects(nombre):
        cliente.remove_object(nombre, objeto.object_name)
    cliente.remove_bucket(nombre)


def _objetos(cliente, bucket):
    return [objeto.object_name for objeto in cliente.list_objects(bucket)]


class _FallaAlFinal(io.RawIOBase):
    """Entrega `tamano - 1` bytes y falla en el último, como el flujo verificado de F-22 ante un hash ajeno."""

    def __init__(self, tamano):
        self._restantes = tamano - 1

    def readable(self):
        return True

    def readinto(self, buffer):
        if self._restantes == 0:
            raise RuntimeError("sha256 ajeno")
        leidos = min(len(buffer), self._restantes)
        buffer[:leidos] = b"a" * leidos
        self._restantes -= leidos
        return leidos


def test_cumple_el_contrato_con_minio_real(cliente, bucket):
    comprobar_object_store(MinioObjectStore(cliente, bucket))


def test_subidas_concurrentes_del_mismo_contenido_dejan_un_objeto(cliente, bucket):
    almacen = MinioObjectStore(cliente, bucket)
    datos = os.urandom(2 * MIB)
    clave = hashlib.sha256(datos).hexdigest()
    barrera = threading.Barrier(8)
    errores = []

    def subir():
        barrera.wait()
        try:
            almacen.put(clave, io.BytesIO(datos), len(datos))
        except Exception as error:  # noqa: BLE001 — cualquier fallo invalida la prueba
            errores.append(repr(error))

    hilos = [threading.Thread(target=subir) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert errores == []
    assert _objetos(cliente, bucket) == [clave]
    with almacen.open(clave) as flujo:
        assert hashlib.sha256(flujo.read()).hexdigest() == clave


@pytest.mark.parametrize("tamano", [1 * MIB, 12 * MIB])
def test_put_que_falla_a_mitad_no_deja_objeto(cliente, bucket, tamano):
    almacen = MinioObjectStore(cliente, bucket)
    clave = "f" * 64
    with pytest.raises(RuntimeError):
        almacen.put(clave, io.BufferedReader(_FallaAlFinal(tamano)), tamano)
    assert not almacen.exists(clave)
    assert _objetos(cliente, bucket) == []
