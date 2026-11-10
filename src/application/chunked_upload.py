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
        upload_id = uuid.uuid4().hex
        self._staging.save_manifest(upload_id, manifest.to_dict())
        return upload_id, manifest.chunk_count

    def receive(self, upload_id: str, index: int, data: bytes, sha256: str) -> None:
        verify_chunk(self._manifest(upload_id), index, data, sha256)
        self._staging.put_chunk(upload_id, index, data)

    def status(self, upload_id: str) -> tuple[list[int], list[int]]:
        manifest = self._manifest(upload_id)
        recibidos = self._staging.received(upload_id)
        return sorted(recibidos), missing_chunks(manifest, recibidos)

    def complete(self, upload_id: str) -> tuple[str, int]:
        manifest = self._manifest(upload_id)
        faltantes = missing_chunks(manifest, self._staging.received(upload_id))
        if faltantes:
            raise MissingChunks(faltantes)
        if self._sha256_reensamblado(upload_id, manifest) != manifest.sha256:
            raise IntegrityMismatch(f"el sha256 de la subida {upload_id} no coincide con el declarado")
        with self._flujo(upload_id, manifest) as flujo:
            self._object_store.put(manifest.sha256, flujo, manifest.size)
        self._staging.discard(upload_id)
        return manifest.sha256, manifest.size

    def _manifest(self, upload_id: str) -> UploadManifest:
        try:
            return UploadManifest.from_dict(self._staging.load_manifest(upload_id))
        except KeyError:
            raise UploadNotFound(upload_id) from None

    def _sha256_reensamblado(self, upload_id: str, manifest: UploadManifest) -> str:
        resumen = hashlib.sha256()
        with self._flujo(upload_id, manifest) as flujo:
            while bloque := flujo.read(BLOQUE_LECTURA):
                resumen.update(bloque)
        return resumen.hexdigest()

    def _flujo(self, upload_id: str, manifest: UploadManifest) -> io.BufferedReader:
        return io.BufferedReader(_ChunksEnOrden(self._staging, upload_id, manifest.chunk_count), BLOQUE_LECTURA)


class _ChunksEnOrden(io.RawIOBase):
    """Une los chunks por índice abriendo uno a la vez, para no cargar el archivo en memoria."""

    def __init__(self, staging: ChunkStaging, upload_id: str, chunk_count: int) -> None:
        self._pendientes = (staging.open_chunk(upload_id, i) for i in range(chunk_count))
        self._actual = None

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
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
