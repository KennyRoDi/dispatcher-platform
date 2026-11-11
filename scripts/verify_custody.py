import argparse
import json
import os
import sys
from pathlib import Path

from src.adapters.file_key_provider import FileKeyProvider
from src.application.ports import KeyUnavailable
from src.application.verify_custody import verify_custody
from src.domain.custody_chain import Anchor

KEY_ENV = "CUSTODY_KEY_FILE"
EXIT_OK, EXIT_TAMPERED, EXIT_CLOSED = 0, 1, 2
UNREADABLE_ANCHOR = Anchor(seq=-1, entry_hash="", mac="")


class DirectoryStore:
    """Objetos en `DIR/<sha256>`; solo lectura."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def exists(self, sha256: str) -> bool:
        return (self._directory / sha256).is_file() and Path(sha256).name == sha256

    def open(self, sha256: str):
        return open(self._directory / sha256, "rb")

    def put(self, sha256, content, size):
        raise NotImplementedError("el verificador no escribe objetos")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        anchor = _read_anchor(args.anchor)
        lines = _read_lines(args.log)
        key_provider = FileKeyProvider(os.environ.get(KEY_ENV) or _unset())
        store = DirectoryStore(args.store) if args.store else None
        report = verify_custody(lines, anchor, key_provider, store)
    except _InvalidUtf8 as error:
        print(f"posicion {error.position}: utf8_invalido: la linea no es UTF-8 valido")
        return EXIT_TAMPERED
    except (KeyUnavailable, OSError) as error:
        print(f"no se pudo verificar: {error}", file=sys.stderr)
        return EXIT_CLOSED
    if report.ok:
        print("ok: la cadena de custodia no tiene alteraciones")
        return EXIT_OK
    for violation in report.violations:
        print(f"posicion {violation.position}: {violation.kind}: {violation.detail}")
    return EXIT_TAMPERED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verifica la cadena de custodia (llave en CUSTODY_KEY_FILE).")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--store", type=Path, help="directorio con los objetos en <sha256>")
    return parser


def _unset() -> str:
    raise KeyUnavailable(f"falta la variable {KEY_ENV}")


class _InvalidUtf8(Exception):
    def __init__(self, position: int) -> None:
        super().__init__(position)
        self.position = position


def _read_lines(path: Path) -> list[str]:
    # No se usa splitlines: parte en separadores Unicode que no delimitan entradas.
    raw_lines = path.read_bytes().split(b"\n")
    lines = []
    for position, raw in enumerate(raw_lines):
        try:
            lines.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            raise _InvalidUtf8(position) from None
    return lines[:-1] if lines[-1] == "" else lines


def _read_anchor(path: Path) -> Anchor | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        return Anchor(**json.loads(raw.decode("utf-8")))
    except (ValueError, TypeError, RecursionError):
        return UNREADABLE_ANCHOR


if __name__ == "__main__":
    sys.exit(main())
