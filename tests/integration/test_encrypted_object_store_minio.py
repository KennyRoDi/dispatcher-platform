import io
import os
import shutil
import socket
import subprocess
import time
import uuid

import minio
import pytest

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.file_key_provider import FileKeyProvider
from src.application.ports import DecryptionError

pytestmark = pytest.mark.integration

MARCADOR = b"MARCADOR-SINTETICO-F28-ca5e0b1a"
IMAGEN_MINIO = os.environ.get("MINIO_IMAGE", "cgr.dev/chainguard/minio:latest")


class MinioParaPrueba:
    """Adaptador mínimo solo de prueba: el de producción es F-23 (Melany), no este."""

    def __init__(self, client: minio.Minio, bucket: str):
        self.client, self.bucket = client, bucket

    def exists(self, sha256):
        try:
            self.client.stat_object(self.bucket, sha256)
            return True
        except minio.S3Error:
            return False

    def put(self, sha256, content, size):
        self.client.put_object(self.bucket, sha256, content, length=size)

    def open(self, sha256):
        respuesta = self.client.get_object(self.bucket, sha256)
        try:
            return io.BytesIO(respuesta.read())
        finally:
            respuesta.close()
            respuesta.release_conn()


def _puerto_libre() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _arrancar_minio_efimero():
    """MinIO en Docker sin TLS, con credenciales aleatorias y puerto libre; devuelve (nombre, endpoint, acceso, secreto)."""
    if shutil.which("docker") is None:
        pytest.skip("sin Docker ni MINIO_ENDPOINT")
    nombre = f"f28-minio-{uuid.uuid4().hex[:8]}"
    puerto, acceso, secreto = _puerto_libre(), uuid.uuid4().hex, uuid.uuid4().hex
    comando = [
        "docker", "run", "-d", "--rm", "--name", nombre, "-p", f"127.0.0.1:{puerto}:9000",
        "-e", f"MINIO_ROOT_USER={acceso}", "-e", f"MINIO_ROOT_PASSWORD={secreto}",
        IMAGEN_MINIO, "server", "/data",
    ]
    arranque = subprocess.run(comando, capture_output=True, text=True)
    if arranque.returncode != 0:
        pytest.skip(f"docker run falló: {arranque.stderr.strip()[:200]}")
    return nombre, f"127.0.0.1:{puerto}", acceso, secreto


@pytest.fixture(scope="module")
def cliente():
    nombre = None
    endpoint = os.environ.get("MINIO_ENDPOINT")
    acceso, secreto = os.environ.get("MINIO_ACCESS_KEY"), os.environ.get("MINIO_SECRET_KEY")
    if not (endpoint and acceso and secreto):
        nombre, endpoint, acceso, secreto = _arrancar_minio_efimero()
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
def almacen_real(cliente, tmp_path):
    bucket = f"f28-prueba-{uuid.uuid4().hex[:12]}"
    cliente.make_bucket(bucket)
    crudo = MinioParaPrueba(cliente, bucket)
    archivo_kek = tmp_path / "kek.bin"
    archivo_kek.write_bytes(os.urandom(32))
    archivo_kek.chmod(0o600)
    cifrador = EnvelopeCipher(FileKeyProvider(archivo_kek))
    yield EncryptedObjectStore(crudo, cifrador), crudo
    for objeto in cliente.list_objects(bucket):
        cliente.remove_object(bucket, objeto.object_name)
    cliente.remove_bucket(bucket)


def _guardar(almacen, contenido):
    import hashlib

    sha = hashlib.sha256(contenido).hexdigest()
    almacen.put(sha, io.BytesIO(contenido), len(contenido))
    return sha


def test_objeto_real_en_minio_no_contiene_marcador(almacen_real):
    almacen, crudo = almacen_real
    contenido = b"inicio " + MARCADOR + os.urandom(1024) + MARCADOR
    sha = _guardar(almacen, contenido)
    directo = crudo.open(sha).read()
    print(f"objeto crudo en MinIO: {len(directo)} bytes, marcador presente: {MARCADOR in directo}")
    assert MARCADOR not in directo
    assert almacen.open(sha).read() == contenido


def test_byte_alterado_en_minio_falla(almacen_real):
    almacen, crudo = almacen_real
    sha = _guardar(almacen, MARCADOR + os.urandom(512))
    alterado = bytearray(crudo.open(sha).read())
    alterado[-1] ^= 0x01
    print(f"objeto crudo: {len(alterado)} bytes; se invierte 1 bit del último byte")
    crudo.put(sha, io.BytesIO(bytes(alterado)), len(alterado))
    with pytest.raises(DecryptionError):
        almacen.open(sha).read()
