import fcntl
import json
import os
import re
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path

from src.application.ports import Clock
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, seal, verify_tail

KEY_BYTES = 32
FILE_MODE = 0o600
TAIL_LINES = 2
READ_BLOCK = 64 * 1024
LOCK_ATTEMPTS = 3
SHA256_HEX = re.compile(r"[0-9a-f]{64}")


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
        _require_sha256("evidence_sha256", evidence_sha256)
        _require_sha256("result_sha256", result_sha256)
        if not isinstance(operation, str) or not operation:
            raise ValueError("operation debe ser un texto no vacío")
        with self._locked_log() as fd:
            size = os.fstat(fd).st_size
            tail = self._read_verified(fd)
            last = json.loads(tail[-1]) if tail else None
            self._catch_up_anchor(last)
            fields = {
                "ts": self._utc_now().isoformat(),
                "evidence_sha256": evidence_sha256,
                "operation": operation,
                "result_sha256": result_sha256,
                "actor": actor,
            }
            seq, previous = (last["seq"] + 1, last["entry_hash"]) if last else (0, GENESIS_HASH)
            entry = seal(self._key, previous, seq, fields)
            _append(fd, entry.line().encode("utf-8") + b"\n", size)
            self._write_anchor(make_anchor(self._key, entry.seq, entry.entry_hash))

    def _utc_now(self):
        moment = self._clock.now()
        # Un reloj sin zona se declara UTC: interpretarlo como hora local daría fechas distintas por equipo.
        return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)

    @contextmanager
    def _locked_log(self):
        for _ in range(LOCK_ATTEMPTS):
            fd = self._open_log()
            try:
                os.fchmod(fd, FILE_MODE)
                fcntl.flock(fd, fcntl.LOCK_EX)
                if self._is_current(fd):
                    yield fd
                    return
            finally:
                os.close(fd)
        raise CustodyCorrupted("el log de custodia fue reemplazado mientras se esperaba el candado")

    def _open_log(self) -> int:
        flags = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW
        try:
            return os.open(self._path, flags, FILE_MODE)
        except FileNotFoundError:
            return self._create_log(flags)

    def _create_log(self, flags: int) -> int:
        try:
            self._verify([])
        except CustodyCorrupted:
            # Otro escritor pudo crear el log entre el primer intento y esta comprobación.
            try:
                return os.open(self._path, flags, FILE_MODE)
            except FileNotFoundError:
                raise CustodyCorrupted("el log de custodia falta y hay un ancla con entradas") from None
        return os.open(self._path, flags | os.O_CREAT, FILE_MODE)

    def _is_current(self, fd: int) -> bool:
        try:
            current = os.stat(self._path, follow_symlinks=False)
        except FileNotFoundError:
            return False
        opened = os.fstat(fd)
        return (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)

    def _read_verified(self, fd: int) -> list[str]:
        tail = _tail_lines(fd, os.fstat(fd).st_size)
        self._verify(tail)
        return tail

    def _verify(self, tail: list[str]) -> None:
        violations = verify_tail(self._key, tail, self._read_anchor())
        if violations:
            first = violations[0]
            raise CustodyCorrupted(f"custodia alterada: {first.kind}, {first.detail}")

    def _read_anchor(self) -> Anchor | None:
        try:
            raw = self._anchor_path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            return Anchor(**json.loads(raw.decode("utf-8")))
        except (ValueError, TypeError, RecursionError) as error:
            raise CustodyCorrupted("el ancla de custodia es ilegible") from error

    def _catch_up_anchor(self, last: dict | None) -> None:
        # El ancla génesis se escribe antes del primer anexo: así «sin ancla» con entradas siempre es alteración.
        # Tras una caída entre el anexo y el ancla, esta queda una entrada atrás; se corrige antes de anexar
        # para que fallos de E/S repetidos no la dejen fuera de la tolerancia de una entrada.
        sealed_hash = last["entry_hash"] if last else GENESIS_HASH
        anchor = self._read_anchor()
        if anchor is None or anchor.entry_hash != sealed_hash:
            self._replace_anchor(make_anchor(self._key, last["seq"] if last else 0, sealed_hash))

    def _write_anchor(self, anchor: Anchor) -> None:
        self._replace_anchor(anchor)

    def _replace_anchor(self, anchor: Anchor) -> None:
        temporary = self._anchor_path.with_name(self._anchor_path.name + ".tmp")
        content = json.dumps({"seq": anchor.seq, "entry_hash": anchor.entry_hash, "mac": anchor.mac})
        temporary.unlink(missing_ok=True)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, FILE_MODE)
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


def _require_sha256(name: str, value: object) -> None:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise ValueError(f"{name} debe ser un SHA-256 en 64 hexadecimales minúsculas")


def _tail_lines(fd: int, size: int) -> list[str]:
    if size == 0:
        return []
    if os.pread(fd, 1, size - 1) != b"\n":
        raise CustodyCorrupted("el log de custodia termina en una línea incompleta")
    start, chunk = size, b""
    while start > 0 and chunk.count(b"\n") <= TAIL_LINES:
        step = min(READ_BLOCK, start)
        start -= step
        chunk = os.pread(fd, step, start) + chunk
    try:
        return [line.decode("utf-8") for line in chunk.split(b"\n")[:-1][-TAIL_LINES:]]
    except UnicodeDecodeError as error:
        raise CustodyCorrupted("el log de custodia no es UTF-8") from error


def _append(fd: int, data: bytes, previous_size: int) -> None:
    try:
        _write_all(fd, data)
        os.fsync(fd)
    except OSError:
        # Una cola sin salto de línea dejaría el log inservible para el siguiente anexo.
        os.ftruncate(fd, previous_size)
        raise


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]
