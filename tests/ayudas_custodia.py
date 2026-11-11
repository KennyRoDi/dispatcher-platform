import hashlib
import io
import json
import os
from pathlib import Path

from src.adapters.jsonl_custody_log import JsonlCustodyLog
from tests.dobles import FakeClock, FakeCustodyLog, FakeObjectStore

CONTENIDO_A = b"evidencia sintetica A"
CONTENIDO_B = b"evidencia sintetica B"
RESULTADO_A = b"transcripcion sintetica de A"
RESULTADO_A2 = b"resumen sintetico de la transcripcion de A"


def sha(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


# (evidencia, operacion, resultado, actor): ingreso de A, dos transformaciones encadenadas e ingreso de B.
PASOS = [
    (CONTENIDO_A, "ingreso", CONTENIDO_A, "recepcion"),
    (CONTENIDO_A, "transcribir", RESULTADO_A, "worker-1"),
    (RESULTADO_A, "resumir", RESULTADO_A2, "worker-2"),
    (CONTENIDO_B, "ingreso", CONTENIDO_B, "recepcion"),
]


def registrar_pasos(log, pasos=PASOS) -> None:
    for evidencia, operacion, resultado, actor in pasos:
        log.record(sha(evidencia), operacion, sha(resultado), actor)


def cadena_sellada(llave: bytes, pasos=PASOS):
    log = FakeCustodyLog(key=llave, clock=FakeClock())
    registrar_pasos(log, pasos)
    return log.leer()


def almacen_con_objetos(*contenidos: bytes) -> FakeObjectStore:
    almacen = FakeObjectStore()
    for contenido in contenidos:
        almacen.put(sha(contenido), io.BytesIO(contenido), len(contenido))
    return almacen


def almacen_completo() -> FakeObjectStore:
    return almacen_con_objetos(CONTENIDO_A, CONTENIDO_B, RESULTADO_A, RESULTADO_A2)


def escribir_llave(ruta: Path, llave: bytes, modo: int = 0o600) -> Path:
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, modo)
    with os.fdopen(descriptor, "wb") as archivo:
        archivo.write(llave)
    os.chmod(ruta, modo)
    return ruta


def escribir_objetos(directorio: Path, *contenidos: bytes) -> Path:
    directorio.mkdir(exist_ok=True)
    for contenido in contenidos:
        (directorio / sha(contenido)).write_bytes(contenido)
    return directorio


def log_en_disco(ruta_log: Path, llave: bytes) -> Path:
    """Escribe el log y su ancla `<log>.head` con el adaptador real, reabriéndolo en cada paso."""
    for paso in PASOS:
        registrar_pasos(JsonlCustodyLog(ruta_log, llave, FakeClock()), [paso])
    return ruta_log.with_name(ruta_log.name + ".head")


def lineas_de(ruta: Path) -> list[str]:
    datos = ruta.read_bytes().decode("utf-8")
    return datos[:-1].split("\n") if datos else []


def escribir_lineas(ruta: Path, lineas: list[str]) -> None:
    ruta.write_bytes(("\n".join(lineas) + "\n" if lineas else "").encode("utf-8"))


def alterar_actor(linea: str, actor: str = "intruso") -> str:
    entrada = json.loads(linea)
    entrada["actor"] = actor
    return json.dumps(entrada, sort_keys=True, separators=(",", ":"))
