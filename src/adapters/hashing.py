import hashlib
from pathlib import Path

BLOQUE_LECTURA = 1 << 20


def sha256_de_archivo(path: Path) -> str:
    resumen = hashlib.sha256()
    with open(path, "rb") as archivo:
        while bloque := archivo.read(BLOQUE_LECTURA):
            resumen.update(bloque)
    return resumen.hexdigest()
