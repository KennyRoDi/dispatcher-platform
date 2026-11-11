"""Medición M1 de F-18: OOM real del cgroup en un contenedor con memory.max finito.

Usa las piezas reales de producción (read_memory_events, classify_exit, OomPolicy) con la misma
secuencia que WorkerNode.handle_subtask: línea base de oom_kill, hijo que excede el límite, delta,
clasificación y decisión. No es WorkerNode: no hay Redis ni cola. Controles: SIGKILL externo sin OOM.
"""
import json
import os
import signal
import subprocess
import sys
import time

from src.domain.oom_policy import GiveUp, OomPolicy, classify_exit
from src.infrastructure.cgroup_resources import CgroupResourceReader, read_memory_events

CGROUP = "/sys/fs/cgroup"
MIB = 1024 * 1024


def hijo_que_excede(mib):
    codigo = f"b=bytearray({mib}*1024*1024)\nfor i in range(0,len(b),4096): b[i]=1\nimport time;time.sleep(5)"
    return subprocess.run([sys.executable, "-c", codigo]).returncode


def hijo_matado_externamente():
    p = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    time.sleep(0.5)
    os.kill(p.pid, signal.SIGKILL)
    return p.wait()


def intento(nombre, funcion):
    base = read_memory_events(CGROUP).oom_kill
    codigo = funcion()
    delta = read_memory_events(CGROUP).oom_kill - base
    return {"intento": nombre, "exit_code": codigo, "oom_kill_delta": delta,
            "causa": classify_exit(codigo, delta).value}


def main():
    limite_mib = int(sys.argv[1]); exceso_mib = int(sys.argv[2]); reserva_mib = int(sys.argv[3])
    memoria = CgroupResourceReader(cgroup_path=CGROUP, worker_id="medicion-f18").read()
    politica = OomPolicy()
    out = {"uid": os.getuid(), "memory_max": memoria.memory_max, "oom_kill_inicial": read_memory_events(CGROUP).oom_kill,
           "memory_events_inicial": open(f"{CGROUP}/memory.events").read().split("\n"),
           "exceso_mib": exceso_mib, "reserva_inicial_mib": reserva_mib, "secuencia": []}
    reserva, oom_count = reserva_mib * MIB, 0
    while True:
        r = intento(f"exceso_{exceso_mib}MiB_oom_count_{oom_count}", lambda: hijo_que_excede(exceso_mib))
        decision = politica.decide(oom_count, reserva) if r["causa"] == "oom" else None
        r["decision"] = ("giveup:" + decision.cause) if isinstance(decision, GiveUp) else (
            f"requeue:reserva={decision.reserve}" if decision else None)
        r["supervisor_vivo"] = True
        out["secuencia"].append(r)
        if decision is None or isinstance(decision, GiveUp):
            break
        reserva, oom_count = decision.reserve, oom_count + 1
    out["control_sigkill_externo"] = intento("sigkill_externo_sin_oom", hijo_matado_externamente)
    out["oom_kill_final"] = read_memory_events(CGROUP).oom_kill
    out["memory_events_final"] = open(f"{CGROUP}/memory.events").read().split("\n")
    print(json.dumps(out, indent=1))


main()
