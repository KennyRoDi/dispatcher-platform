import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts import subir_por_chunks
from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeChunkStaging, FakeObjectStore

URL = "http://testserver"


class SesionSobreTestClient:
    """Expone la interfaz de `requests` que usa el cliente sobre un TestClient, sin red."""

    def __init__(self, cliente, perder_una_vez=()):
        self._cliente = cliente
        self._perder = set(perder_una_vez)
        self.chunks_enviados = []

    def post(self, url, json=None, timeout=None):
        return self._cliente.post(url, json=json)

    def get(self, url, timeout=None):
        return self._cliente.get(url)

    def put(self, url, data=None, headers=None, timeout=None):
        indice = int(url.rsplit("/", 1)[1])
        self.chunks_enviados.append(indice)
        if indice in self._perder:
            self._perder.discard(indice)
            return self._cliente.get(url.rsplit("/chunks/", 1)[0])
        return self._cliente.put(url, content=bytes(data), headers=headers)


@pytest.fixture
def servidor():
    almacen = FakeObjectStore()
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(FakeChunkStaging(), almacen, max_chunk_size=1 << 20)
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas
    return TestClient(app), almacen


def archivo(tmp_path, datos):
    ruta = tmp_path / "caso.bin"
    ruta.write_bytes(datos)
    return ruta


@pytest.mark.parametrize("texto, esperado", [
    ("256K", 256 * 1024), ("1M", 1 << 20), ("4m", 4 << 20), ("16M", 16 << 20), ("1000", 1000),
])
def test_tamano_de_chunk_acepta_sufijos_binarios(texto, esperado):
    assert subir_por_chunks.parse_tamano(texto) == esperado


@pytest.mark.parametrize("texto", ["", "0", "-1M", "4G", "cuatro"])
def test_tamano_de_chunk_invalido_se_rechaza(texto):
    with pytest.raises(ValueError):
        subir_por_chunks.parse_tamano(texto)


def test_sha256_del_archivo_se_calcula_por_partes(tmp_path):
    datos = bytes(range(256)) * 100
    assert subir_por_chunks.sha256_archivo(archivo(tmp_path, datos), bloque=7) == hashlib.sha256(datos).hexdigest()


def test_subir_entrega_el_archivo_completo_con_su_sha256(tmp_path, servidor):
    cliente, almacen = servidor
    datos = bytes(range(256)) * 41
    resultado = subir_por_chunks.subir(archivo(tmp_path, datos), URL, chunk_size=1000, session=SesionSobreTestClient(cliente))
    esperado = hashlib.sha256(datos).hexdigest()
    assert resultado == {"sha256": esperado, "size": len(datos)}
    assert almacen.objetos[esperado] == datos


def test_subir_envia_un_chunk_por_indice(tmp_path, servidor):
    cliente, _ = servidor
    sesion = SesionSobreTestClient(cliente)
    subir_por_chunks.subir(archivo(tmp_path, b"x" * 2500), URL, chunk_size=1000, session=sesion)
    assert sorted(sesion.chunks_enviados) == [0, 1, 2]


def test_subir_reenvia_los_chunks_que_faltan(tmp_path, servidor):
    cliente, almacen = servidor
    datos = b"y" * 3500
    sesion = SesionSobreTestClient(cliente, perder_una_vez={1, 3})
    resultado = subir_por_chunks.subir(archivo(tmp_path, datos), URL, chunk_size=1000, session=sesion)
    assert resultado["sha256"] in almacen.objetos
    assert sorted(sesion.chunks_enviados) == [0, 1, 1, 2, 3, 3]


def test_subir_falla_si_el_servidor_rechaza_un_chunk(tmp_path, servidor, monkeypatch):
    cliente, almacen = servidor
    monkeypatch.setattr(subir_por_chunks, "sha256_bytes", lambda datos: "0" * 64)
    with pytest.raises(subir_por_chunks.SubidaFallida):
        subir_por_chunks.subir(archivo(tmp_path, b"z" * 1500), URL, chunk_size=1000, session=SesionSobreTestClient(cliente))
    assert almacen.objetos == {}
