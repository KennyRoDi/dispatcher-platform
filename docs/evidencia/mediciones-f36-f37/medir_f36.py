"""Medición F-36: cancela un caso pesado (>= 200 MB) en curso con el supervisor real y evalúa con scenarios.cancel_heavy."""
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone

from scenarios import cancel_heavy as ch
from src.adapters.posix_process_runner import PosixProcessRunner
from src.application.process_supervisor import ProcessSupervisor
from src.workers import multimedia_processor as mp


class Reloj:
    def now(self):
        return datetime.now(timezone.utc)


def ejecutar(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


entrada = "/tmp/caso_pesado.avi"
subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                "-t", "8", "-c:v", "rawvideo", "-pix_fmt", "yuv420p", entrada], check=True)
megabytes = os.path.getsize(entrada) // ch.MIB
assert megabytes >= ch.MEGABYTES_MINIMOS, megabytes

sup = ProcessSupervisor(runner=PosixProcessRunner(), clock=Reloj(), sleep=time.sleep, grace_seconds=2.0)
resultado_hilo = {}


def correr():
    try:
        mp.process("transcode_video", entrada, "/tmp/out", params={"width": 1920, "preset": "veryslow"}, supervisor=sup)
        resultado_hilo["salida"] = "terminó sin cancelar"
    except Exception as exc:
        resultado_hilo["salida"] = type(exc).__name__


hilo = threading.Thread(target=correr)
hilo.start()
time.sleep(3.0)
antes = ch.tomar_instantanea(ejecutar, "antes")
assert antes["pids_subtareas"], "no había sub-tarea ffmpeg en curso"
t_cancel = time.monotonic()
for pid in antes["pids_subtareas"]:
    sup.cancel(pid)
muestras = []
for _ in range(50):
    muestras.append((round(time.monotonic() - t_cancel, 2), ch._pids_subtareas(ejecutar(ch.COMANDO_PS))))
    time.sleep(0.1)
hilo.join(timeout=30)
despues = ch.tomar_instantanea(ejecutar, "despues")
estado_caso = "cancelled" if not hilo.is_alive() and not despues["pids_subtareas"] else "running"
veredicto = ch.evaluar(antes, despues, estado_caso)
print(json.dumps({"megabytes": megabytes, "antes": antes, "despues": despues, "estado_caso": estado_caso,
                  "hilo_resultado": resultado_hilo.get("salida"),
                  "tiempo_liberacion_s": ch.tiempo_liberacion(muestras), "veredicto": veredicto}, indent=2))
