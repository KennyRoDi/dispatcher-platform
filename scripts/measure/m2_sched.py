from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.domain.scheduling import Priority, SchedulingPolicy, SchedulerState  # noqa: E402

ARRIVAL_MS = 5.0
SERVICE_MS = 10.0


def _reloj_virtual():
    estado = {"t": 0.0}

    def ahora():
        return estado["t"]

    def avanzar(delta):
        estado["t"] += max(0.0, delta)
        return estado["t"]

    return ahora, avanzar


def simular(policy: SchedulingPolicy, high_rate: int, low: int, seed: int):
    """Simula una ráfaga de casos altos con casos bajos ya en cola, en un reloj virtual.

    El servidor despacha a la mitad de la tasa de llegada durante la ráfaga
    (backlog creciente), y drena el resto al terminar. Devuelve una lista de
    eventos (case_id, prioridad_nominal, entered_at, departure_t, servicio_ms).
    """
    rng = random.Random(seed)
    ahora, avanzar = _reloj_virtual()
    scheduler = SchedulerState(policy=policy)
    pendientes: dict[str, tuple[Priority, float]] = {}
    eventos = []

    def despachar(servicio_ms):
        avanzar(servicio_ms)
        case_id = scheduler.next()
        if case_id is None:
            return
        prioridad, entrada = pendientes.pop(case_id)
        eventos.append((case_id, prioridad, entrada, ahora(), servicio_ms))

    with patch("time.time", side_effect=ahora):
        for i in range(low):
            case_id = f"bajo-{i}"
            scheduler.enqueue(case_id=case_id, priority=Priority.BAJA, entered_at=ahora())
            pendientes[case_id] = (Priority.BAJA, ahora())

        for i in range(high_rate):
            avanzar(max(0.1, rng.gauss(ARRIVAL_MS, 1.0)))
            case_id = f"alto-{i}"
            scheduler.enqueue(case_id=case_id, priority=Priority.ALTA, entered_at=ahora())
            pendientes[case_id] = (Priority.ALTA, ahora())
            if i % 2 == 1:
                despachar(max(0.1, rng.gauss(SERVICE_MS, 2.0)))

        while len(scheduler):
            despachar(max(0.1, rng.gauss(SERVICE_MS, 2.0)))

    return eventos, ahora()


def resumir(eventos, makespan_ms, policy: SchedulingPolicy):
    por_nivel: dict[Priority, list[tuple[float, float]]] = {}
    for _case_id, prioridad, entrada, salida, servicio_ms in eventos:
        espera_ms = (salida - entrada) - servicio_ms
        turnaround_ms = salida - entrada
        por_nivel.setdefault(prioridad, []).append((espera_ms, turnaround_ms))

    filas = []
    for prioridad, valores in sorted(por_nivel.items(), key=lambda kv: kv[0].value):
        esperas = [v[0] for v in valores]
        turnarounds = [v[1] for v in valores]
        throughput_cps = len(valores) / (makespan_ms / 1000) if makespan_ms else 0.0
        filas.append({
            "politica": policy.value,
            "nivel": prioridad.name.lower(),
            "espera_ms": round(sum(esperas) / len(esperas), 3),
            "turnaround_ms": round(sum(turnarounds) / len(turnarounds), 3),
            "throughput_cps": round(throughput_cps, 4),
        })
    return filas


def medir(policy: SchedulingPolicy, high_rate: int, low: int, seed: int, salida: Path) -> None:
    eventos, makespan_ms = simular(policy, high_rate, low, seed)
    filas = resumir(eventos, makespan_ms, policy)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=("politica", "nivel", "espera_ms", "turnaround_ms", "throughput_cps"))
        writer.writeheader()
        writer.writerows(filas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simula carga sintética para comparar políticas de scheduling (F-21)."
    )
    parser.add_argument("--high-rate", type=int, required=True, help="casos de prioridad alta en la ráfaga")
    parser.add_argument("--low", type=int, required=True, help="casos de prioridad baja ya en cola al iniciar")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.high_rate < 1 or args.low < 1:
        parser.error("--high-rate y --low deben ser al menos 1")

    valor_politica = os.environ.get("SCHED_POLICY", "fifo")
    try:
        policy = SchedulingPolicy.desde_configuracion(valor_politica)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    medir(policy, args.high_rate, args.low, args.seed, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
