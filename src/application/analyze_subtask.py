"""Caso de uso: analizar una sub-tarea tipada de la cola (F-43, AD-51)."""
import hashlib
import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path, PureWindowsPath
from typing import Protocol

from src.application.ports import Analyzer, ObjectStore, SubtaskFindingStore
from src.domain.finding import Finding
from src.domain.subtask import ContentKind, Subtask

VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm"})
_EXTENSION_VALIDA = re.compile(r"\.[A-Za-z0-9]{1,10}")
_FUERA_DE_NOMBRE = re.compile(r"[^A-Za-z0-9._-]")
_BLOQUE = 1024 * 1024


class ShaDistinto(ValueError):
    pass


class VideoNoSoportado(ValueError):
    pass


class VideoAnalyzer(Protocol):
    def analyze(self, path: Path) -> list[Finding]: ...


def directorio_de_trabajo(work_dir: Path, subtask_id: str) -> Path:
    nombre = _FUERA_DE_NOMBRE.sub("_", subtask_id).lstrip(".") or "subtarea"
    return Path(work_dir) / nombre


def extension_de_la_fuente(nombre: str) -> str:
    extension = PureWindowsPath(nombre).suffix.lower()
    return extension if _EXTENSION_VALIDA.fullmatch(extension) else ""


class AnalyzeSubtask:
    def __init__(
        self,
        store: ObjectStore,
        analyzers: Mapping[ContentKind, Analyzer],
        findings: SubtaskFindingStore,
        work_dir: Path,
        is_cancelled: Callable[[str], bool],
        video_analyzer: VideoAnalyzer | None = None,
        video_for: Callable[[Subtask], VideoAnalyzer] | None = None,
    ) -> None:
        self._store = store
        self._analyzers = analyzers
        self._findings = findings
        self._work_dir = Path(work_dir)
        self._is_cancelled = is_cancelled
        self._video_analyzer = video_analyzer
        self._video_for = video_for

    def execute(self, subtask: Subtask, source_name: str) -> bool:
        """True si escribió los hallazgos; False si el caso se canceló y se descartaron."""
        analyzer = self._analyzers.get(subtask.kind)
        if analyzer is None:
            raise ValueError(f"no hay analizador para el tipo {subtask.kind.value!r}")
        extension = extension_de_la_fuente(source_name)
        directory = directorio_de_trabajo(self._work_dir, subtask.id)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"fuente{extension}"
            self._descargar(subtask.source_sha256, path)
            found = self._analizar(subtask, analyzer, path, extension)
            if self._is_cancelled(subtask.case_id):
                return False
            self._findings.add_once(subtask.case_id, subtask.id, found)
            return True
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def _descargar(self, sha256: str, destino: Path) -> None:
        digest = hashlib.sha256()
        with self._store.open(sha256) as origen, destino.open("wb") as salida:
            while bloque := origen.read(_BLOQUE):
                digest.update(bloque)
                salida.write(bloque)
        if digest.hexdigest() != sha256:
            raise ShaDistinto(f"el objeto descargado no coincide con el SHA-256 {sha256}")

    def _analizar(self, subtask: Subtask, analyzer: Analyzer, path: Path, extension: str) -> list[Finding]:
        if subtask.kind is ContentKind.IMAGE and extension in VIDEO_EXTENSIONS:
            video = self._video_for(subtask) if self._video_for is not None else self._video_analyzer
            if video is None:
                raise VideoNoSoportado(f"este worker no analiza video ({extension})")
            return list(video.analyze(path))
        return list(analyzer.analyze(path))
