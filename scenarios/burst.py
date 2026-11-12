"""Escenario F-33: ráfaga de al menos 20 casos concurrentes sobre tres nodos worker.

Envuelve `scripts.run_load`, evalúa su JSON de forma pura y exporta los CSV de
latencia por caso y de recursos por nodo. La corrida real exige nodos worker.
"""

import argparse
import csv
import json
import sys
from argparse import Namespace
from pathlib import Path

from scripts import run_load
from scripts.submit_case import FINISHED_STATUSES
from src.workers.config import Settings

MINIMO_CASOS = 20
MINIMO_NODOS = 3
COLUMNAS_LATENCIA = {"caso": "name", "tipo": "kind", "prioridad": "priority", "estado": "status",
                     "subtareas": "subtasks", "duracion_s": "duration_s"}
COLUMNAS_RECURSOS = ("instante", "host", "cpu_percent", "mem_percent", "subtareas_activas")


class Filas(list):
    def __init__(self, filas, columnas):
        super().__init__(filas)
        self.columnas = list(columnas)


def ejecutar_rafaga(args, ejecutor):
    if not isinstance(args.limit, int) or args.limit < MINIMO_CASOS:
        raise ValueError(f"la ráfaga exige al menos {MINIMO_CASOS} casos (--limit)")
    if args.concurrency < args.limit:
        raise ValueError("la concurrencia debe ser al menos igual al número de casos")
    return ejecutor(args)


def _hosts(resultado):
    hosts = set(resultado["metrics"].get("subtasks_per_host", {}))
    for muestra in resultado["series"]:
        hosts.update(w["host"] for w in muestra["workers"].values())
    return hosts


def evaluar(resultado, minimo_casos=MINIMO_CASOS, minimo_nodos=MINIMO_NODOS):
    metricas = resultado["metrics"]
    problemas = []
    if metricas["cases"] < minimo_casos:
        problemas.append(f"se enviaron {metricas['cases']} casos, se exigen al menos {minimo_casos}")
    if resultado["timed_out"]:
        problemas.append("la corrida terminó por timed_out")
    for caso in metricas["per_case"]:
        if caso["status"] not in FINISHED_STATUSES:
            problemas.append(f"{caso['name']} sin estado final: {caso['status']}")
    if len(_hosts(resultado)) < minimo_nodos:
        problemas.append(f"se vieron {len(_hosts(resultado))} nodos, se exigen al menos {minimo_nodos}")
    if metricas.get("throughput_subtasks_per_min") is None:
        problemas.append("falta el throughput")
    if all(caso["duration_s"] is None for caso in metricas["per_case"]):
        problemas.append("ningún caso tiene latencia")
    if not metricas.get("peak_cpu_by_host") or not metricas.get("peak_active_by_host"):
        problemas.append("faltan recursos por nodo")
    return {"cumple": not problemas, "problemas": problemas}


def filas_latencia(resultado):
    return Filas([{columna: caso[origen] for columna, origen in COLUMNAS_LATENCIA.items()}
                  for caso in resultado["metrics"]["per_case"]], COLUMNAS_LATENCIA)


def filas_recursos(resultado):
    return Filas([{"instante": muestra["t"], "host": worker["host"], "cpu_percent": worker["cpu_percent"],
                   "mem_percent": worker["mem_percent"], "subtareas_activas": worker["active_subtasks"]}
                  for muestra in resultado["series"] for worker in muestra["workers"].values()],
                 COLUMNAS_RECURSOS)


def escribir_csv(filas, ruta):
    with Path(ruta).open("w", encoding="utf-8", newline="") as archivo:
        columnas = getattr(filas, "columnas", None) or (list(filas[0]) if filas else None)
        if columnas:
            escritor = csv.DictWriter(archivo, fieldnames=columnas)
            escritor.writeheader()
            escritor.writerows(filas)


def _ejecutar_run_load(args):
    _, ruta_md = run_load.run_load(args, Settings.from_env())
    return json.loads(ruta_md.with_suffix(".json").read_text(encoding="utf-8"))


def _argumentos(argv):
    parser = argparse.ArgumentParser(description="Ráfaga de carga concurrente (F-33).")
    parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    parser.add_argument("--limit", type=int, default=MINIMO_CASOS)
    parser.add_argument("--concurrency", type=int, default=MINIMO_CASOS)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--out", type=Path, default=Path("docs/evidencia"))
    args = parser.parse_args(argv)
    return Namespace(**vars(args), upload=False, kinds="homogeneous,heterogeneous", poll=5.0,
                     high_fraction=0.1, seed=42)


def main(argv=None):
    args = _argumentos(argv)
    try:
        args.out.mkdir(parents=True, exist_ok=True)
        resultado = ejecutar_rafaga(args, _ejecutar_run_load)
    except (ValueError, OSError) as error:
        raise SystemExit(f"error: {error}") from error
    escribir_csv(filas_latencia(resultado), args.out / "latencia_por_caso.csv")
    escribir_csv(filas_recursos(resultado), args.out / "recursos_por_nodo.csv")
    veredicto = evaluar(resultado)
    print(json.dumps(veredicto, indent=2, ensure_ascii=False))
    return 0 if veredicto["cumple"] else 1


if __name__ == "__main__":
    sys.exit(main())
