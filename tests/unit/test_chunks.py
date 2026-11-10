import hashlib
import io

import pytest

from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application import ports
from src.application.chunked_upload import ChunkedUpload
from src.domain.chunks import (
    ChunkRejected,
    IntegrityMismatch,
    MissingChunks,
    UploadManifest,
    UploadNotFound,
    missing_chunks,
    verify_chunk,
)
from tests.contratos import comprobar_chunk_staging
from tests.dobles import FakeChunkStaging, FakeObjectStore

CHUNK = 4


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def partir(datos, tamano=CHUNK):
    return [datos[i:i + tamano] for i in range(0, len(datos), tamano)]


def subida(maximo=64):
    almacen = FakeObjectStore()
    caso = ChunkedUpload(FakeChunkStaging(), almacen, max_chunk_size=maximo)
    return caso, almacen


def iniciar(caso, datos, tamano=CHUNK):
    upload_id, cantidad = caso.start(sha(datos), len(datos), tamano)
    return upload_id, cantidad


# Dominio


def test_manifiesto_deriva_cantidad_y_tamano_del_ultimo_chunk():
    manifiesto = UploadManifest(sha(b"x" * 10), 10, 4)
    assert manifiesto.chunk_count == 3
    assert [manifiesto.expected_size(i) for i in range(3)] == [4, 4, 2]


@pytest.mark.parametrize("sha256, size, chunk_size", [
    ("no-es-hex", 10, 4),
    (sha(b"a"), 0, 4),
    (sha(b"a"), 10, 0),
])
def test_manifiesto_invalido_se_rechaza(sha256, size, chunk_size):
    with pytest.raises(ValueError):
        UploadManifest(sha256, size, chunk_size)


def test_manifiesto_se_reconstruye_desde_su_diccionario():
    manifiesto = UploadManifest(sha(b"abc"), 3, 2)
    assert UploadManifest.from_dict(manifiesto.to_dict()) == manifiesto


def test_verificar_chunk_acepta_hash_en_mayusculas():
    manifiesto = UploadManifest(sha(b"abcd"), 4, 4)
    verify_chunk(manifiesto, 0, b"abcd", sha(b"abcd").upper())


def test_faltantes_se_listan_en_orden():
    manifiesto = UploadManifest(sha(b"x" * 10), 10, 2)
    assert missing_chunks(manifiesto, {4, 0, 2}) == [1, 3]


# Caso de uso


def test_reensamblado_coincide_con_sha256():
    datos = bytes(range(256)) * 3
    caso, almacen = subida()
    upload_id, cantidad = iniciar(caso, datos)
    for indice, parte in enumerate(partir(datos)):
        caso.receive(upload_id, indice, parte, sha(parte))
    assert caso.complete(upload_id) == (sha(datos), len(datos))
    assert cantidad == len(partir(datos))
    assert almacen.open(sha(datos)).read() == datos


def test_chunk_alterado_se_rechaza():
    datos = b"abcdefgh"
    caso, _ = subida()
    upload_id, _ = iniciar(caso, datos)
    with pytest.raises(ChunkRejected):
        caso.receive(upload_id, 0, b"abcX", sha(b"abcd"))
    assert caso.status(upload_id) == ([], [0, 1])


def test_chunk_alterado_reenviado_correcto_se_acepta():
    datos = b"abcdefgh"
    caso, _ = subida()
    upload_id, _ = iniciar(caso, datos)
    with pytest.raises(ChunkRejected):
        caso.receive(upload_id, 0, b"abcX", sha(b"abcd"))
    caso.receive(upload_id, 0, b"abcd", sha(b"abcd"))
    assert caso.status(upload_id) == ([0], [1])


def test_chunk_fuera_de_orden_se_ordena():
    datos = b"0123456789abcdef!"
    caso, almacen = subida()
    upload_id, _ = iniciar(caso, datos)
    partes = list(enumerate(partir(datos)))
    for indice, parte in reversed(partes):
        caso.receive(upload_id, indice, parte, sha(parte))
    caso.complete(upload_id)
    assert almacen.open(sha(datos)).read() == datos


def test_completar_con_faltantes_lista_indices():
    datos = b"x" * 16
    caso, almacen = subida()
    upload_id, _ = iniciar(caso, datos)
    caso.receive(upload_id, 1, b"xxxx", sha(b"xxxx"))
    with pytest.raises(MissingChunks) as error:
        caso.complete(upload_id)
    assert error.value.missing == [0, 2, 3]
    assert almacen.objetos == {}


def test_hash_total_distinto_no_guarda_objeto():
    declarado = b"abcdefgh"
    caso, almacen = subida()
    upload_id, _ = iniciar(caso, declarado)
    for indice, parte in enumerate(partir(b"zzzzzzzz")):
        caso.receive(upload_id, indice, parte, sha(parte))
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert almacen.objetos == {}


@pytest.mark.parametrize("indice, parte", [(5, b"abcd"), (-1, b"abcd"), (1, b"ef"), (0, b"abc")])
def test_tamano_de_chunk_invalido_se_rechaza(indice, parte):
    caso, _ = subida()
    upload_id, _ = iniciar(caso, b"abcdefgh")
    with pytest.raises(ChunkRejected):
        caso.receive(upload_id, indice, parte, sha(parte))


def test_chunk_size_sobre_el_maximo_se_rechaza():
    caso, _ = subida(maximo=8)
    with pytest.raises(ValueError):
        caso.start(sha(b"x" * 32), 32, 16)


def test_reenvio_del_mismo_chunk_es_idempotente():
    datos = b"abcdefgh"
    caso, almacen = subida()
    upload_id, _ = iniciar(caso, datos)
    for _ in range(2):
        caso.receive(upload_id, 0, b"abcd", sha(b"abcd"))
    caso.receive(upload_id, 1, b"efgh", sha(b"efgh"))
    assert caso.status(upload_id) == ([0, 1], [])
    caso.complete(upload_id)
    assert almacen.open(sha(datos)).read() == datos


def test_subida_inexistente_se_informa():
    caso, _ = subida()
    with pytest.raises(UploadNotFound):
        caso.status("no-existe")


def test_completar_libera_el_staging():
    datos = b"abcd"
    staging = FakeChunkStaging()
    caso = ChunkedUpload(staging, FakeObjectStore())
    upload_id, _ = caso.start(sha(datos), 4, 4)
    caso.receive(upload_id, 0, datos, sha(datos))
    caso.complete(upload_id)
    with pytest.raises(UploadNotFound):
        caso.status(upload_id)


# Contrato ChunkStaging


def test_staging_doble_cumple_el_puerto():
    assert isinstance(FakeChunkStaging(), ports.ChunkStaging)


def test_staging_doble_cumple_el_contrato():
    comprobar_chunk_staging(FakeChunkStaging())


def test_staging_en_disco_cumple_el_contrato(tmp_path):
    comprobar_chunk_staging(DiskChunkStaging(tmp_path))


def test_staging_en_disco_rechaza_identificador_con_ruta(tmp_path):
    with pytest.raises(ValueError):
        DiskChunkStaging(tmp_path).save_manifest("../fuera", {})


def test_staging_en_disco_no_deja_temporales(tmp_path):
    staging = DiskChunkStaging(tmp_path)
    staging.save_manifest("u1", {"a": 1})
    staging.put_chunk("u1", 0, b"datos")
    assert sorted(p.name for p in (tmp_path / "u1").iterdir()) == ["chunk_000000", "manifest.json"]


def test_reensamblado_en_disco_de_extremo_a_extremo(tmp_path):
    datos = io.BytesIO(bytes(range(256)) * 40).getvalue()
    almacen = FakeObjectStore()
    caso = ChunkedUpload(DiskChunkStaging(tmp_path), almacen, max_chunk_size=4096)
    upload_id, _ = caso.start(sha(datos), len(datos), 1000)
    for indice, parte in enumerate(partir(datos, 1000)):
        caso.receive(upload_id, indice, parte, sha(parte))
    caso.complete(upload_id)
    assert almacen.open(sha(datos)).read() == datos
    assert list(tmp_path.iterdir()) == []
