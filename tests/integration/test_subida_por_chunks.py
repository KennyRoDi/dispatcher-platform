import hashlib
import os
import threading
import time

import pytest
import requests
import uvicorn
from fastapi import FastAPI

from scripts import subir_por_chunks
from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos

pytestmark = pytest.mark.integration

MIB = 1 << 20
TAMANO = 200 * MIB


class AlmacenQueHashea:
    """ObjectStore mínimo: confirma el objeto solo si la lectura de `content` termina sin excepción."""

    def __init__(self, raiz):
        self._raiz = raiz
        self.objetos = {}

    def exists(self, sha256):
        return sha256 in self.objetos

    def put(self, sha256, content, size):
        resumen = hashlib.sha256()
        temporal = self._raiz / f".{sha256}.tmp"
        with open(temporal, "wb") as destino:
            while bloque := content.read(MIB):
                resumen.update(bloque)
                destino.write(bloque)
        os.replace(temporal, self._raiz / sha256)
        self.objetos[sha256] = (resumen.hexdigest(), os.path.getsize(self._raiz / sha256))

    def open(self, sha256):
        return open(self._raiz / sha256, "rb")


@pytest.fixture
def coordinador(tmp_path):
    (tmp_path / "objetos").mkdir()
    almacen = AlmacenQueHashea(tmp_path / "objetos")
    subidas = ChunkedUpload(DiskChunkStaging(tmp_path / "staging"), almacen)
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        assert time.monotonic() < limite, "uvicorn no arrancó"
        time.sleep(0.05)
    puerto = servidor.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{puerto}", almacen, tmp_path / "staging"
    servidor.should_exit = True
    hilo.join(timeout=10)


@pytest.fixture(scope="module")
def archivo_grande(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("dataset") / "sintetico_200mib.bin"
    resumen = hashlib.sha256()
    with open(ruta, "wb") as destino:
        for i in range(TAMANO // MIB):
            bloque = hashlib.sha256(i.to_bytes(4, "big")).digest() * (MIB // 32)
            resumen.update(bloque)
            destino.write(bloque)
    return ruta, resumen.hexdigest()


def test_archivo_de_200_mib_se_reensambla_con_su_sha256(coordinador, archivo_grande):
    url, almacen, staging = coordinador
    ruta, esperado = archivo_grande
    resultado = subir_por_chunks.subir(ruta, url, chunk_size=4 * MIB)
    assert resultado == {"sha256": esperado, "size": TAMANO}
    assert almacen.objetos[esperado] == (esperado, TAMANO)
    assert list(staging.iterdir()) == []


def test_chunk_alterado_en_transito_recibe_422(coordinador):
    url, almacen, _ = coordinador
    datos = os.urandom(2 * MIB)
    inicio = requests.post(f"{url}/uploads", json={
        "sha256": hashlib.sha256(datos).hexdigest(), "size": len(datos), "chunk_size": MIB,
    }, timeout=10).json()
    chunk = bytearray(datos[:MIB])
    sha_original = hashlib.sha256(chunk).hexdigest()
    chunk[1234] ^= 0xFF
    respuesta = requests.put(
        f"{url}/uploads/{inicio['upload_id']}/chunks/0",
        data=bytes(chunk), headers={"X-Chunk-SHA256": sha_original}, timeout=10,
    )
    assert respuesta.status_code == 422
    estado = requests.get(f"{url}/uploads/{inicio['upload_id']}", timeout=10).json()
    assert estado == {"received": [], "missing": [0, 1]}
    assert almacen.objetos == {}
