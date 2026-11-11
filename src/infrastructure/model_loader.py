from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from src.application.analyze_audio import Transcriber
from src.domain.model_loading import LoadingConfig
from src.domain.transcription import TranscriptSegment


class ProcessRuntime(Protocol):
    def start(self, target: Callable, args: tuple, *, method: str) -> object: ...
    def result(self, handle: object) -> list[TranscriptSegment]: ...
    def terminate(self, handle: object) -> None: ...
    def join(self, handle: object) -> None: ...


def _load_and_transcribe(factory: Callable[[], Transcriber], path: Path) -> list[TranscriptSegment]:
    return factory().transcribe(path)


def _transcribe(model: Transcriber, path: Path) -> list[TranscriptSegment]:
    return model.transcribe(path)


class ModelLoader:
    def __init__(
        self, config: LoadingConfig, factory: Callable[[], Transcriber], runtime: ProcessRuntime
    ) -> None:
        self.config = config
        self.factory = factory
        self.runtime = runtime

    def run(self, path: Path) -> list[list[TranscriptSegment]]:
        if self.config.strategy == "fork_compartido":
            target, args = _transcribe, (self.factory(), path)
        else:
            target, args = _load_and_transcribe, (self.factory, path)
        handles = []
        try:
            for _ in range(self.config.processes):
                handles.append(self.runtime.start(target, args, method="fork"))
            results = [self.runtime.result(handle) for handle in handles]
        except BaseException as error:
            try:
                self._cleanup(handles, terminate=True)
            except BaseException as cleanup_error:
                error.add_note(f"falló la limpieza de procesos: {cleanup_error!r}")
            raise
        self._cleanup(handles, terminate=False)
        return results

    def _cleanup(self, handles: list[object], *, terminate: bool) -> None:
        first_error = None
        for handle in handles:
            try:
                if terminate:
                    self.runtime.terminate(handle)
            except BaseException as error:
                if first_error is None:
                    first_error = error
            finally:
                try:
                    self.runtime.join(handle)
                except BaseException as error:
                    if first_error is None:
                        first_error = error
        if first_error is not None:
            raise first_error
