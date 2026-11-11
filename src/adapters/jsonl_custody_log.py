import fcntl
import json
import os
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path

from src.application.ports import Clock
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, seal, verify_chain

KEY_BYTES = 32
FILE_MODE = 0o600


class CustodyCorrupted(Exception):
    pass


class JsonlCustodyLog:
    def __init__(self, path: str | os.PathLike, key: bytes, clock: Clock) -> None:
        if not isinstance(key, bytes):
            raise TypeError("la llave de custodia debe ser bytes")
        if len(key) != KEY_BYTES:
            raise ValueError(f"la llave de custodia debe medir {KEY_BYTES} bytes")
        self._path = Path(path)
        self._anchor_path = self._path.with_name(self._path.name + ".head")
        self._key = key
        self._clock = clock

    def record(self, evidence_sha256: str, operation: str, result_sha256: str, actor: str) -> None:
        with self._locked_log() as fd:
            lines = self._read_verified(fd)
            previous = json.loads(lines[-1])["entry_hash"] if lines else GENESIS_HASH
            fields = {
                "ts": self._clock.now().astimezone(timezone.utc).isoformat(),
                "evidence_sha256": evidence_sha256,
                "operation": operation,
                "result_sha256": result_sha256,
                "actor": actor,
            }
            entry = seal(self._key, previous, len(lines), fields)
            _write_all(fd, entry.line().encode("utf-8") + b"\n")
            os.fsync(fd)
            self._write_anchor(make_anchor(self._key, entry.seq, entry.entry_hash))

    @contextmanager
    def _locked_log(self):
        fd = self._open_log()
        try:
            os.fchmod(fd, FILE_MODE)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield fd
        finally:
            os.close(fd)

    def _open_log(self) -> int:
        flags = os.O_RDWR | os.O_APPEND
        try:
            return os.open(self._path, flags, FILE_MODE)
        except FileNotFoundError:
            self._verify([])
            return os.open(self._path, flags | os.O_CREAT, FILE_MODE)

    def _read_verified(self, fd: int) -> list[str]:
        lines = _split_lines(os.pread(fd, os.fstat(fd).st_size, 0))
        self._verify(lines)
        return lines

    def _verify(self, lines: list[str]) -> None:
        violations = verify_chain(lines, self._key, self._read_anchor())
        if violations:
            first = violations[0]
            raise CustodyCorrupted(f"custodia alterada en la línea {first.position}: {first.kind}, {first.detail}")

    def _read_anchor(self) -> Anchor | None:
        try:
            raw = self._anchor_path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            return Anchor(**json.loads(raw.decode("utf-8")))
        except (ValueError, TypeError, RecursionError) as error:
            raise CustodyCorrupted("el ancla de custodia es ilegible") from error

    def _write_anchor(self, anchor: Anchor) -> None:
        temporary = self._anchor_path.with_name(self._anchor_path.name + ".tmp")
        content = json.dumps({"seq": anchor.seq, "entry_hash": anchor.entry_hash, "mac": anchor.mac})
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
        try:
            os.fchmod(fd, FILE_MODE)
            _write_all(fd, content.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.replace(temporary, self._anchor_path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
        self._sync_directory()

    def _sync_directory(self) -> None:
        fd = os.open(self._path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _split_lines(data: bytes) -> list[str]:
    if not data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CustodyCorrupted("el log de custodia no es UTF-8") from error
    if not text.endswith("\n"):
        raise CustodyCorrupted("el log de custodia termina en una línea incompleta")
    return text[:-1].split("\n")


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]
