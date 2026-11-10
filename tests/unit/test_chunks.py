import hashlib
import io
import threading

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


class _StagingQueCambiaEntrePasadas(FakeChunkStaging):
    """Simula un PUT concurrente del chunk 0 que llega entre el cálculo del hash y el `put`."""

    def __init__(self):
        super().__init__()
        self.aperturas = 0
        self.al_reabrir = None

    def open_chunk(self, upload_id, index):
        self.aperturas += 1
        if index == 0 and self.aperturas > 1 and self.al_reabrir:
            self.al_reabrir()
            self.al_reabrir = None
        return super().open_chunk(upload_id, index)


def test_objeto_entregado_coincide_con_su_sha256_aunque_cambie_un_chunk_al_completar():
    datos = b"abcdefgh"
    staging = _StagingQueCambiaEntrePasadas()
    almacen = FakeObjectStore()
    caso = ChunkedUpload(staging, almacen, max_chunk_size=64)
    upload_id, _ = iniciar(caso, datos)
    for indice, parte in enumerate(partir(datos)):
        caso.receive(upload_id, indice, parte, sha(parte))
    staging.al_reabrir = lambda: caso.receive(upload_id, 0, b"ZZZZ", sha(b"ZZZZ"))
    try:
        caso.complete(upload_id)
    except IntegrityMismatch:
        pass
    for clave, contenido in almacen.objetos.items():
        assert sha(contenido) == clave


def test_indice_igual_a_la_cantidad_de_chunks_se_rechaza_aunque_venga_vacio():
    caso, _ = subida()
    upload_id, cantidad = iniciar(caso, b"abcdefgh")
    with pytest.raises(ChunkRejected):
        caso.receive(upload_id, cantidad, b"", sha(b""))
    assert caso.status(upload_id) == ([], [0, 1])


def test_indice_booleano_se_rechaza():
    manifiesto = UploadManifest(sha(b"abcd"), 4, 4)
    with pytest.raises(ChunkRejected):
        verify_chunk(manifiesto, False, b"abcd", sha(b"abcd"))


class _ArchivoVigilado(io.BytesIO):
    def __init__(self, datos, staging):
        super().__init__(datos)
        self._staging = staging
        staging.abiertos += 1
        staging.max_abiertos = max(staging.max_abiertos, staging.abiertos)

    def close(self):
        if not self.closed:
            self._staging.abiertos -= 1
        super().close()


class _StagingVigilado(FakeChunkStaging):
    def __init__(self):
        super().__init__()
        self.abiertos = 0
        self.max_abiertos = 0
        self.aperturas = 0
        self.archivos = []

    def open_chunk(self, upload_id, index):
        self.aperturas += 1
        # Se retiene la referencia: así el recolector de CPython no oculta un archivo sin cerrar.
        self.archivos.append(_ArchivoVigilado(self.chunks[upload_id][index], self))
        return self.archivos[-1]


class _AlmacenQueLeePorBloques(FakeObjectStore):
    def __init__(self, staging):
        super().__init__()
        self._staging = staging

    def put(self, sha256, content, size):
        assert not isinstance(content, (bytes, bytearray, io.BytesIO))
        aperturas_antes = self._staging.aperturas
        partes = [content.read(CHUNK)]
        assert self._staging.aperturas - aperturas_antes <= 1
        while bloque := content.read(CHUNK):
            partes.append(bloque)
        self.objetos[sha256] = b"".join(partes)


def test_completar_entrega_por_flujo_un_chunk_abierto_a_la_vez_y_los_cierra():
    datos = b"0123456789abcdef!"
    staging = _StagingVigilado()
    almacen = _AlmacenQueLeePorBloques(staging)
    caso = ChunkedUpload(staging, almacen, max_chunk_size=64)
    upload_id, _ = iniciar(caso, datos)
    for indice, parte in enumerate(partir(datos)):
        caso.receive(upload_id, indice, parte, sha(parte))
    caso.complete(upload_id)
    assert almacen.objetos[sha(datos)] == datos
    assert staging.max_abiertos == 1
    assert staging.abiertos == 0


class _AlmacenQueLeeSoloSize(FakeObjectStore):
    def put(self, sha256, content, size):
        self.objetos[sha256] = content.read(size)


def test_hash_total_distinto_se_detecta_aunque_el_almacen_no_lea_hasta_el_final():
    almacen = _AlmacenQueLeeSoloSize()
    caso = ChunkedUpload(FakeChunkStaging(), almacen, max_chunk_size=64)
    upload_id, _ = iniciar(caso, b"abcdefgh")
    for indice, parte in enumerate(partir(b"zzzzzzzz")):
        caso.receive(upload_id, indice, parte, sha(parte))
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert almacen.objetos == {}


def _subida_recibida(staging, almacen, datos):
    caso = ChunkedUpload(staging, almacen, max_chunk_size=64)
    upload_id, _ = iniciar(caso, datos)
    for indice, parte in enumerate(partir(datos)):
        caso.receive(upload_id, indice, parte, sha(parte))
    return caso, upload_id


def test_chunk_final_mas_largo_en_staging_no_llega_al_almacen_que_lee_solo_size():
    staging = FakeChunkStaging()
    almacen = _AlmacenQueLeeSoloSize()
    caso, upload_id = _subida_recibida(staging, almacen, b"abcdefghij")
    staging.chunks[upload_id][2] = b"XYZW"
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert almacen.objetos == {}


def test_chunk_final_mas_corto_en_staging_no_llega_al_almacen():
    staging = FakeChunkStaging()
    almacen = _AlmacenQueLeeSoloSize()
    caso, upload_id = _subida_recibida(staging, almacen, b"abcdefghij")
    staging.chunks[upload_id][2] = b"i"
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert almacen.objetos == {}


@pytest.mark.parametrize("bloque", [1, CHUNK - 1, 100])
def test_integridad_fallida_a_mitad_de_lectura_cierra_el_chunk_abierto(bloque):
    staging = _StagingVigilado()
    almacen = _AlmacenQueLeePorBloques(staging)
    caso, upload_id = _subida_recibida(staging, almacen, b"0123456789abcdef!")
    staging.chunks[upload_id][1] = b"XXXX"
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert staging.max_abiertos == 1
    assert staging.abiertos == 0
    assert almacen.objetos == {}


def test_reintento_correcto_tras_integridad_fallida_en_disco(tmp_path):
    datos = b"abcdefghij"
    almacen = FakeObjectStore()
    caso, upload_id = _subida_recibida(DiskChunkStaging(tmp_path), almacen, datos)
    caso.receive(upload_id, 1, b"ZZZZ", sha(b"ZZZZ"))
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert caso.status(upload_id) == ([0, 1, 2], [])
    caso.receive(upload_id, 1, b"efgh", sha(b"efgh"))
    assert caso.complete(upload_id) == (sha(datos), len(datos))
    assert almacen.objetos == {sha(datos): datos}
    assert list(tmp_path.iterdir()) == []


class _AlmacenQueReemplazaEnOtroHilo(FakeObjectStore):
    def __init__(self):
        super().__init__()
        self.reemplazar = None

    def put(self, sha256, content, size):
        partes = [content.read(1)]
        hilo = threading.Thread(target=self.reemplazar)
        hilo.start()
        hilo.join()
        while bloque := content.read(1):
            partes.append(bloque)
        self.objetos[sha256] = b"".join(partes)


@pytest.mark.parametrize("indice", [1, 2])
def test_chunk_reemplazado_por_otro_hilo_durante_la_lectura_en_disco(tmp_path, indice):
    datos = b"abcdefghij"
    almacen = _AlmacenQueReemplazaEnOtroHilo()
    caso, upload_id = _subida_recibida(DiskChunkStaging(tmp_path), almacen, datos)
    nuevo = b"ZZZZ"[: len(partir(datos)[indice])]
    almacen.reemplazar = lambda: caso.receive(upload_id, indice, nuevo, sha(nuevo))
    with pytest.raises(IntegrityMismatch):
        caso.complete(upload_id)
    assert almacen.objetos == {}


@pytest.mark.parametrize("datos, tamano", [(b"abcdefgh", 4), (b"abcd", 4), (b"a", 4), (b"abcdefgh", 1)])
def test_bordes_de_tamano_se_reensamblan(datos, tamano):
    caso, almacen = subida()
    upload_id, _ = iniciar(caso, datos, tamano)
    for indice, parte in enumerate(partir(datos, tamano)):
        caso.receive(upload_id, indice, parte, sha(parte))
    caso.complete(upload_id)
    assert almacen.objetos == {sha(datos): datos}
