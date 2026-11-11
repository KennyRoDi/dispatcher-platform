"""Escenario F-36: cancelación en curso de un caso pesado (>= 200 MB).

La corrida real exige nodos worker; este módulo solo genera la carga sintética,
toma las instantáneas de la ficha (ps, ls /scratch, memory.current) y las evalúa.
"""

from pathlib import Path

MIB = 1024 * 1024
MEGABYTES_MINIMOS = 200
ESPERA_MAXIMA_SEGUNDOS = 30.0
COMANDO_PS = ("ps", "-eo", "pid,ppid,stat,rss,cmd")
COMANDO_SCRATCH = ("ls", "-la", "/scratch")
COMANDO_MEMORIA = ("cat", "/sys/fs/cgroup/memory.current")
EJECUTABLE_SUBTAREA = "ffmpeg"


def generar_archivo_pesado(ruta, megabytes=MEGABYTES_MINIMOS, exigir_minimo=False):
    if exigir_minimo and megabytes < MEGABYTES_MINIMOS:
        raise ValueError(f"el enunciado exige al menos {MEGABYTES_MINIMOS} MB, se pidieron {megabytes}")
    ruta = Path(ruta)
    bloque = bytes(range(256)) * (MIB // 256)
    with ruta.open("wb") as archivo:
        for _ in range(megabytes):
            archivo.write(bloque)
    return ruta


def _pids_subtareas(salida_ps):
    pids = []
    for linea in salida_ps.splitlines()[1:]:
        campos = linea.split(None, 4)
        if len(campos) == 5 and campos[4].split()[0].rsplit("/", 1)[-1] == EJECUTABLE_SUBTAREA:
            pids.append(int(campos[0]))
    return pids


def _entradas_scratch(salida_ls):
    nombres = []
    for linea in salida_ls.splitlines():
        if linea.startswith("total") or not linea.strip():
            continue
        nombre = linea.split()[-1]
        if nombre not in (".", ".."):
            nombres.append(nombre)
    return nombres


def tomar_instantanea(ejecutar, etiqueta):
    return {
        "etiqueta": etiqueta,
        "pids_subtareas": _pids_subtareas(ejecutar(COMANDO_PS)),
        "scratch": _entradas_scratch(ejecutar(COMANDO_SCRATCH)),
        "memory_current": int(ejecutar(COMANDO_MEMORIA).strip()),
    }


def evaluar(antes, despues, estado_caso):
    problemas = []
    if despues["pids_subtareas"]:
        problemas.append(f"quedan procesos de sub-tareas: {despues['pids_subtareas']}")
    if despues["scratch"]:
        problemas.append(f"quedan archivos temporales en scratch: {despues['scratch']}")
    if despues["memory_current"] >= antes["memory_current"]:
        problemas.append("la memoria del worker no disminuyó")
    if estado_caso != "cancelled":
        problemas.append(f"el caso debía quedar cancelled y quedó {estado_caso}")
    return {"cumple": not problemas, "problemas": problemas}


def tiempo_liberacion(muestras):
    """Instante desde el cual no vuelve a haber procesos; None si nunca se liberó."""
    liberado = None
    for instante, pids in muestras:
        if pids:
            liberado = None
        elif liberado is None:
            liberado = instante
    return liberado
