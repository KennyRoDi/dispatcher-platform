import hashlib
import io
import uuid

from src.application.ports import ChunkStaging, ObjectStore
from src.domain.chunks import (
    IntegrityMismatch,
    MissingChunks,
    UploadManifest,
    UploadNotFound,
    missing_chunks,
    verify_chunk,
)

MAX_CHUNK_SIZE = 64 * 1024 * 1024
# Acota la lista de faltantes y el conjunto de índices que se materializan en status y complete.
MAX_CHUNKS = 100_000
BLOQUE_LECTURA = 1 << 20


class ChunkedUpload:
    def __init__(self, staging: ChunkStaging, object_store: ObjectStore, max_chunk_size: int = MAX_CHUNK_SIZE) -> None:
        self._staging = staging
        self._object_store = object_store
        self._max_chunk_size = max_chunk_size

    def start(self, sha256: str, size: int, chunk_size: int) -> tuple[str, int]:
        manifest = UploadManifest(sha256, size, chunk_size)
        if manifest.chunk_size > self._max_chunk_size:
            raise ValueError(f"chunk_size {chunk_size} excede el máximo {self._max_chunk_size}")
        if manifest.chunk_count > MAX_CHUNKS:
            raise ValueError(f"{manifest.chunk_count} chunks exceden el máximo {MAX_CHUNKS}; usa un chunk_size mayor")
        upload_id = uuid.uuid4().hex
        self._staging.save_manifest(upload_id, manifest.to_dict())
        return upload_id, manifest.chunk_count

    def expected_size(self, upload_id: str, index: int) -> int:
        return self._manifest(upload_id).expected_size(index)

    def receive(self, upload_id: str, index: int, data: bytes, sha256: str) -> None:
        verify_chunk(self._manifest(upload_id), index, data, sha256)
        try:
            self._staging.put_chunk(upload_id, index, data)
        except KeyError:
            raise UploadNotFound(upload_id) from None

    def status(self, upload_id: str) -> tuple[list[int], list[int]]:
        manifest = self._manifest(upload_id)
        recibidos = self._staging.received(upload_id)
        return sorted(recibidos), missing_chunks(manifest, recibidos)

    def complete(self, upload_id: str) -> tuple[str, int]:
        manifest = self._manifest(upload_id)
        faltantes = missing_chunks(manifest, self._staging.received(upload_id))
        if faltantes:
            # Otro complete pudo descartar la subida entre leer el manifiesto y listar los chunks.
            self._manifest(upload_id)
            raise MissingChunks(faltantes)
        try:
            with self._flujo(upload_id, manifest) as flujo:
                self._object_store.put(manifest.sha256, flujo, manifest.size)
        except KeyError:
            raise UploadNotFound(upload_id) from None
        self._staging.discard(upload_id)
        return manifest.sha256, manifest.size

    def _manifest(self, upload_id: str) -> UploadManifest:
        try:
            datos = self._staging.load_manifest(upload_id)
        except (KeyError, ValueError):
            raise UploadNotFound(upload_id) from None
        return UploadManifest.from_dict(datos)

    def _flujo(self, upload_id: str, manifest: UploadManifest) -> io.BufferedReader:
        return io.BufferedReader(_ChunksVerificados(self._staging, upload_id, manifest), BLOQUE_LECTURA)


class _ChunksVerificados(io.RawIOBase):
    """Une los chunks por índice abriendo uno a la vez, para no cargar el archivo en memoria.

    El staging se lee una sola vez y el SHA-256 se calcula sobre los mismos bytes que recibe
    `ObjectStore`: un chunk reemplazado por un `receive` concurrente no puede colarse entre el
    cálculo del hash y la entrega. La verificación ocurre antes de soltar el último byte, así
    que ante una discrepancia `put` termina con `IntegrityMismatch` sin haber leído el objeto
    completo.
    """

    def __init__(self, staging: ChunkStaging, upload_id: str, manifest: UploadManifest) -> None:
        self._pendientes = (staging.open_chunk(upload_id, i) for i in range(manifest.chunk_count))
        self._actual = None
        self._upload_id = upload_id
        self._manifest = manifest
        self._resumen = hashlib.sha256()
        self._entregados = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        leidos = self._leer_en(buffer)
        self._resumen.update(memoryview(buffer)[:leidos])
        self._entregados += leidos
        if leidos == 0 or self._entregados >= self._manifest.size:
            self._verificar()
        return leidos

    def _verificar(self) -> None:
        if self._entregados != self._manifest.size or self._resumen.hexdigest() != self._manifest.sha256:
            raise IntegrityMismatch(f"el sha256 de la subida {self._upload_id} no coincide con el declarado")

    def _leer_en(self, buffer) -> int:
        while True:
            if self._actual is None:
                self._actual = next(self._pendientes, None)
                if self._actual is None:
                    return 0
            leidos = self._actual.readinto(buffer)
            if leidos:
                return leidos
            self._cerrar_actual()

    def close(self) -> None:
        self._cerrar_actual()
        super().close()

    def _cerrar_actual(self) -> None:
        if self._actual is not None:
            self._actual.close()
            self._actual = None
