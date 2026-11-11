"""Medición F-37: saturación de memoria en un contenedor aislado con memory.max finito.

Usa la admisión real de producción (src.domain.admission, CgroupResourceReader, read_memory_events)
y el plan/evaluación de scenarios.memory_saturation. Las sub-tareas son procesos hijos que reservan y
tocan `huella` MiB reales. No es WorkerNode: no hay Redis ni cola; el heartbeat es un hilo del arnés.
Uso: python medir_f37.py [--sin-admision] --huella-mib 64 --margen-mib 32 --factor 2
"""
import argparse
import json
import subprocess
import sys
import threading
import time

from scenarios import memory_saturation as ms
from src.domain.admission import admits
from src.infrastructure.cgroup_resources import CgroupResourceReader, read_memory_events

CGROUP = "/sys/fs/cgroup"
INTERVALO_HEARTBEAT = 1.0
RETENCION_SEGUNDOS = 4.0


def ejecutar(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def lanzar(huella_bytes):
    codigo = (
        f"import time;b=bytearray({huella_bytes});"
        f"[b.__setitem__(slice(i,i+4096),b'x'*4096) for i in range(0,len(b),4096)];time.sleep({RETENCION_SEGUNDOS})"
    )
    return subprocess.Popen([sys.executable, "-c", codigo])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--huella-mib", type=int, required=True)
    parser.add_argument("--margen-mib", type=int, required=True)
    parser.add_argument("--factor", type=float, default=2)
    parser.add_argument("--sin-admision", action="store_true")
    args = parser.parse_args()

    lector = CgroupResourceReader(cgroup_path=CGROUP, worker_id="medicion-f37")
    memory_max = lector.read().memory_max
    huella, margen = args.huella_mib * ms.MIB, args.margen_mib * ms.MIB
    plan = ms.planificar_carga(memory_max, margen, huella, args.factor)
    oom_inicial = read_memory_events(CGROUP).oom_kill
    ultimo_hb = {"t": time.monotonic()}
    detener = threading.Event()

    def latido():
        while not detener.wait(INTERVALO_HEARTBEAT):
            ultimo_hb["t"] = time.monotonic()

    threading.Thread(target=latido, daemon=True).start()

    inicio = time.monotonic()
    pendientes = list(range(plan.subtareas))
    activas = {}
    estados = {}
    muestras = []
    while pendientes or activas:
        for nombre, proc in list(activas.items()):
            codigo = proc.poll()
            if codigo is not None:
                estados[nombre] = "completed" if codigo == 0 else "failed"
                del activas[nombre]
        while pendientes:
            reserva = len(activas) * huella
            if not args.sin_admision:
                uso = lector.read()
                if not admits(current=uso.memory_current, max=uso.memory_max, footprint=huella + reserva, margin=margen):
                    break
            nombre = f"sub-{pendientes.pop(0)}"
            activas[nombre] = lanzar(huella)
        muestra = ms.tomar_muestra(ejecutar, "ciclo", round(time.monotonic() - inicio, 2))
        muestra.update(
            en_curso=len(activas),
            en_cola=len(pendientes),
            oom_killed=read_memory_events(CGROUP).oom_kill > oom_inicial,
            ultimo_heartbeat=round(ultimo_hb["t"] - inicio, 2),
        )
        muestras.append(muestra)
        time.sleep(0.2)
    detener.set()
    veredicto = ms.evaluar(plan, muestras, estados, INTERVALO_HEARTBEAT)
    print(json.dumps({
        "plan": {"cupo": plan.cupo, "subtareas": plan.subtareas},
        "memory_max": memory_max,
        "huella_bytes": huella,
        "margen_bytes": margen,
        "sin_admision": args.sin_admision,
        "intervalo_heartbeat": INTERVALO_HEARTBEAT,
        "pico_memory_current": max(m["memory_current"] for m in muestras),
        "pico_en_curso": max(m["en_curso"] for m in muestras),
        "oom_kill_total": read_memory_events(CGROUP).oom_kill - oom_inicial,
        "estados_finales": estados,
        "muestras": muestras,
        "veredicto": veredicto,
    }, indent=2))


main()
