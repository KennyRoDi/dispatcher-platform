import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.coordinator import rutas_archivos
from tests.dobles import FakeChunkStaging, FakeObjectStore

CHUNK = 4
MAXIMO = 64


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def partir(datos, tamano=CHUNK):
    return [datos[i:i + tamano] for i in range(0, len(datos), tamano)]


def cliente_con(staging):
    almacen = FakeObjectStore()
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    subidas = ChunkedUpload(staging, almacen, max_chunk_size=MAXIMO)
    app.dependency_overrides[rutas_archivos.obtener_subidas] = lambda: subidas
    return TestClient(app), almacen


@pytest.fixture
def api():
    return cliente_con(FakeChunkStaging())


def iniciar(cliente, datos, tamano=CHUNK, sha256=None):
    respuesta = cliente.post("/uploads", json={"sha256": sha256 or sha(datos), "size": len(datos), "chunk_size": tamano})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def enviar(cliente, upload_id, indice, dato, sha256=None):
    return cliente.put(
        f"/uploads/{upload_id}/chunks/{indice}",
        content=dato,
        headers={"X-Chunk-SHA256": sha256 or sha(dato)},
    )


def test_iniciar_devuelve_id_y_cantidad_de_chunks(api):
    cliente, _ = api
    cuerpo = iniciar(cliente, b"abcdefghij")
    assert cuerpo["chunk_count"] == 3
    assert isinstance(cuerpo["upload_id"], str) and cuerpo["upload_id"]


@pytest.mark.parametrize("cuerpo", [
    {"sha256": "no-es-hex", "size": 10, "chunk_size": 4},
    {"sha256": "a" * 64, "size": 0, "chunk_size": 4},
    {"sha256": "a" * 64, "size": 10, "chunk_size": 0},
    {"sha256": "a" * 64, "size": 10, "chunk_size": MAXIMO + 1},
    {"sha256": "a" * 64, "size": 10},
])
def test_iniciar_con_datos_invalidos_responde_422(api, cuerpo):
    cliente, _ = api
    assert cliente.post("/uploads", json=cuerpo).status_code == 422


def test_subida_completa_entrega_el_objeto_con_su_sha256(api):
    cliente, almacen = api
    datos = b"archivo grande de prueba"
    upload_id = iniciar(cliente, datos)["upload_id"]
    for indice, dato in enumerate(partir(datos)):
        assert enviar(cliente, upload_id, indice, dato).status_code == 204
    respuesta = cliente.post(f"/uploads/{upload_id}/complete")
    assert respuesta.status_code == 201
    assert respuesta.json() == {"sha256": sha(datos), "size": len(datos)}
    assert almacen.objetos[sha(datos)] == datos


def test_chunks_en_orden_inverso_se_reensamblan(api):
    cliente, almacen = api
    datos = b"0123456789abcdef!"
    upload_id = iniciar(cliente, datos)["upload_id"]
    for indice, dato in reversed(list(enumerate(partir(datos)))):
        assert enviar(cliente, upload_id, indice, dato).status_code == 204
    assert cliente.post(f"/uploads/{upload_id}/complete").status_code == 201
    assert almacen.objetos[sha(datos)] == datos


def test_chunk_alterado_responde_422_y_reenviarlo_correcto_se_acepta(api):
    cliente, _ = api
    datos = b"abcdefgh"
    upload_id = iniciar(cliente, datos)["upload_id"]
    alterado = enviar(cliente, upload_id, 0, b"abXd", sha256=sha(b"abcd"))
    assert alterado.status_code == 422
    assert cliente.get(f"/uploads/{upload_id}").json()["received"] == []
    assert enviar(cliente, upload_id, 0, b"abcd").status_code == 204


@pytest.mark.parametrize("indice, dato", [(5, b"abcd"), (-1, b"abcd"), (1, b"ef")])
def test_indice_o_tamano_invalido_responde_422(api, indice, dato):
    cliente, _ = api
    upload_id = iniciar(cliente, b"abcdefgh")["upload_id"]
    assert enviar(cliente, upload_id, indice, dato).status_code == 422


def test_chunk_sin_cabecera_de_hash_responde_422(api):
    cliente, _ = api
    upload_id = iniciar(cliente, b"abcdefgh")["upload_id"]
    assert cliente.put(f"/uploads/{upload_id}/chunks/0", content=b"abcd").status_code == 422


def test_reenvio_del_mismo_chunk_es_idempotente(api):
    cliente, _ = api
    upload_id = iniciar(cliente, b"abcdefgh")["upload_id"]
    assert enviar(cliente, upload_id, 0, b"abcd").status_code == 204
    assert enviar(cliente, upload_id, 0, b"abcd").status_code == 204
    assert cliente.get(f"/uploads/{upload_id}").json() == {"received": [0], "missing": [1]}


def test_estado_lista_recibidos_y_faltantes(api):
    cliente, _ = api
    upload_id = iniciar(cliente, b"abcdefghij")["upload_id"]
    enviar(cliente, upload_id, 2, b"ij")
    respuesta = cliente.get(f"/uploads/{upload_id}")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"received": [2], "missing": [0, 1]}


def test_completar_con_faltantes_responde_409_con_indices(api):
    cliente, almacen = api
    upload_id = iniciar(cliente, b"abcdefghij")["upload_id"]
    enviar(cliente, upload_id, 1, b"efgh")
    respuesta = cliente.post(f"/uploads/{upload_id}/complete")
    assert respuesta.status_code == 409
    assert respuesta.json()["missing"] == [0, 2]
    assert almacen.objetos == {}


def test_sha256_total_distinto_responde_422_y_no_guarda(api):
    cliente, almacen = api
    datos = b"abcdefgh"
    upload_id = iniciar(cliente, datos, sha256=sha(b"otro contenido"))["upload_id"]
    for indice, dato in enumerate(partir(datos)):
        enviar(cliente, upload_id, indice, dato)
    assert cliente.post(f"/uploads/{upload_id}/complete").status_code == 422
    assert almacen.objetos == {}


def test_subida_completada_ya_no_existe(api):
    cliente, _ = api
    datos = b"abcd"
    upload_id = iniciar(cliente, datos)["upload_id"]
    enviar(cliente, upload_id, 0, datos)
    cliente.post(f"/uploads/{upload_id}/complete")
    assert cliente.get(f"/uploads/{upload_id}").status_code == 404


@pytest.mark.parametrize("peticion", [
    lambda c: c.get("/uploads/no-existe"),
    lambda c: c.post("/uploads/no-existe/complete"),
    lambda c: enviar(c, "no-existe", 0, b"abcd"),
])
def test_subida_inexistente_responde_404(api, peticion):
    cliente, _ = api
    assert peticion(cliente).status_code == 404


@pytest.mark.parametrize("upload_id", ["%2E%2E", "%2E", "a%5Cb"])
def test_id_invalido_en_disco_responde_404_sin_salir_del_staging(tmp_path, upload_id):
    raiz = tmp_path / "staging"
    cliente, _ = cliente_con(DiskChunkStaging(raiz))
    assert cliente.get(f"/uploads/{upload_id}").status_code == 404
    assert enviar(cliente, upload_id, 0, b"abcd").status_code == 404
    assert sorted(p.name for p in tmp_path.iterdir()) == ["staging"]


def test_sin_almacen_configurado_responde_503():
    app = FastAPI()
    app.include_router(rutas_archivos.router)
    respuesta = TestClient(app).post("/uploads", json={"sha256": "a" * 64, "size": 4, "chunk_size": 4})
    assert respuesta.status_code == 503


def test_el_coordinador_publica_las_rutas_de_subida():
    from src.coordinator.main import app

    rutas = {(metodo.upper(), ruta) for ruta, metodos in app.openapi()["paths"].items() for metodo in metodos}
    assert {
        ("POST", "/uploads"),
        ("PUT", "/uploads/{upload_id}/chunks/{index}"),
        ("GET", "/uploads/{upload_id}"),
        ("POST", "/uploads/{upload_id}/complete"),
    } <= rutas
