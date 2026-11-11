"""Escenario F-37: saturación de memoria con carga mayor que memory.max.

La corrida real exige nodos worker; este módulo planifica la carga, toma muestras
(memory.current, memory.max) y evalúa las cuatro afirmaciones de US-37.
"""

import argparse
import json
from dataclasses import asdict, dataclass
from math import ceil


COMANDO_MEMORY_CURRENT = ("cat", "/sys/fs/cgroup/memory.current")
COMANDO_MEMORY_MAX = ("cat", "/sys/fs/cgroup/memory.max")
TOLERANCIA_HEARTBEATS = 3
ESTADOS_TERMINALES = frozenset({"completed", "failed", "cancelled"})
MIB = 1024 * 1024


@dataclass(frozen=True)
class PlanCarga:
    cupo: int
    subtareas: int


def planificar_carga(memory_max, margen, huella, factor):
    if memory_max < 1 or margen < 0 or huella < 1 or factor <= 1:
        raise ValueError("memory_max y huella deben ser positivos, margen no negativo y factor mayor que 1")
    cupo = (memory_max - margen) // huella
    if cupo < 1:
        raise ValueError("la huella no cabe en la memoria disponible")
    subtareas = max(cupo + 1, ceil(factor * (memory_max - margen) / huella), memory_max // huella + 1)
    return PlanCarga(cupo=cupo, subtareas=subtareas)


def tomar_muestra(ejecutar, etiqueta, instante):
    texto_maximo = ejecutar(COMANDO_MEMORY_MAX).strip()
    return {
        "etiqueta": etiqueta,
        "instante": instante,
        "memory_current": int(ejecutar(COMANDO_MEMORY_CURRENT).strip()),
        "memory_max": None if texto_maximo == "max" else int(texto_maximo),
    }


def huecos_heartbeat(instantes, intervalo, tolerancia):
    ordenados = sorted(instantes)
    limite = tolerancia * intervalo
    return [(a, b) for a, b in zip(ordenados, ordenados[1:]) if b - a > limite]


def evaluar(plan, muestras, estados_finales, intervalo_heartbeat):
    if not muestras:
        return {"cumple": False, "problemas": ["no hay muestras"]}
    problemas = []
    heartbeats = {m["ultimo_heartbeat"] for m in muestras}
    for desde, hasta in huecos_heartbeat(heartbeats, intervalo_heartbeat, TOLERANCIA_HEARTBEATS):
        problemas.append(f"hueco de heartbeat entre {desde} y {hasta}")
    if any(m["memory_max"] is not None and m["memory_current"] > m["memory_max"] for m in muestras):
        problemas.append("memory.current superó memory.max")
    if any(m["oom_killed"] for m in muestras):
        problemas.append("hubo OOMKilled")
    if any(m["en_curso"] > plan.cupo for m in muestras):
        problemas.append(f"se admitieron más sub-tareas que el cupo ({plan.cupo})")
    for nombre, estado in sorted(estados_finales.items()):
        if estado not in ESTADOS_TERMINALES:
            problemas.append(f"la sub-tarea {nombre} no terminó: {estado}")
    if len(estados_finales) < plan.subtareas:
        problemas.append(f"faltan estados: {len(estados_finales)} de {plan.subtareas} sub-tareas")
    return {"cumple": not problemas, "problemas": problemas}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Planifica la carga del escenario de saturación (F-37).")
    parser.add_argument("--memory-max-mib", type=int, required=True)
    parser.add_argument("--margen-mib", type=int, required=True)
    parser.add_argument("--huella-mib", type=int, required=True)
    parser.add_argument("--factor", type=float, default=2)
    parser.add_argument("--salida")
    args = parser.parse_args(argv)
    plan = planificar_carga(args.memory_max_mib * MIB, args.margen_mib * MIB, args.huella_mib * MIB, args.factor)
    texto = json.dumps({"plan": asdict(plan)}, indent=2)
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as archivo:
            archivo.write(texto)
    else:
        print(texto)


if __name__ == "__main__":
    main()
