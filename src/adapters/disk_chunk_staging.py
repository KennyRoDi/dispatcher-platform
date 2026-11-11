import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

MANIFIESTO = "manifest.json"
_CHUNK = re.compile(r"chunk_(\d+)")


class DiskChunkStaging:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def save_manifest(self, upload_id: str, manifest: dict) -> None:
        self._escribir(self._carpeta(upload_id) / MANIFIESTO, json.dumps(manifest).encode("utf-8"))

    def load_manifest(self, upload_id: str) -> dict:
        try:
            return json.loads((self._carpeta(upload_id) / MANIFIESTO).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(upload_id) from None

    def put_chunk(self, upload_id: str, index: int, data: bytes) -> None:
        if not (self._carpeta(upload_id) / MANIFIESTO).is_file():
            raise KeyError(upload_id)
        try:
            self._escribir(self._chunk(upload_id, index), data, crear_carpeta=False)
        except FileNotFoundError:
            raise KeyError(upload_id) from None

    def received(self, upload_id: str) -> set[int]:
        carpeta = self._carpeta(upload_id)
        if not carpeta.is_dir():
            return set()
        return {int(m.group(1)) for p in carpeta.iterdir() if (m := _CHUNK.fullmatch(p.name))}

    def open_chunk(self, upload_id: str, index: int) -> BinaryIO:
        try:
            return open(self._chunk(upload_id, index), "rb")
        except FileNotFoundError:
            raise KeyError((upload_id, index)) from None

    def discard(self, upload_id: str) -> None:
        shutil.rmtree(self._carpeta(upload_id), ignore_errors=True)

    def _carpeta(self, upload_id: str) -> Path:
        # El id llega desde la URL: un separador o «..» permitiría escribir fuera del staging.
        if not upload_id or upload_id in {".", ".."} or Path(upload_id).name != upload_id or "/" in upload_id or "\\" in upload_id:
            raise ValueError(f"upload_id inválido: {upload_id!r}")
        return self._root / upload_id

    def _chunk(self, upload_id: str, index: int) -> Path:
        return self._carpeta(upload_id) / f"chunk_{index:06d}"

    @staticmethod
    def _escribir(destino: Path, datos: bytes, crear_carpeta: bool = True) -> None:
        # Temporal con nombre único y renombrado atómico: dos reenvíos simultáneos del mismo
        # chunk no se pisan y un corte nunca deja un chunk a medias con nombre válido.
        if crear_carpeta:
            destino.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=destino.parent, prefix=".tmp-")
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                archivo.write(datos)
            os.replace(temporal, destino)
        except BaseException:
            Path(temporal).unlink(missing_ok=True)
            raise
