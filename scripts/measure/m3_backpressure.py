from __future__ import annotations

import argparse
import csv
import statistics
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import redis
import requests

CASO = {"subtasks": [{"task_type": "auto", "file_path": "videos/a.mp4"}]}


def percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p / 100 * (len(ordenados) - 1)))]


def resumir(filas: list[dict]) -> dict:
    muestras = [f for f in filas if f["tipo"] == "muestra"]
    respuestas = [f for f in filas if f["tipo"] == "respuesta"]
    latencias = [f["latencia_ms"] for f in respuestas]
    return {
        "profundidad_max": max((f["profundidad"] for f in muestras), default=0),
        "codigos": dict(sorted(Counter(f["codigo"] for f in respuestas).items())),
        "latencia_p50_ms": percentil(latencias, 50),
        "latencia_p95_ms": percentil(latencias, 95),
        "latencia_media_ms": round(statistics.fmean(latencias), 2) if latencias else None,
    }


def medir(url: str, cliente_redis: redis.Redis, productores: int, duracion: float, intervalo: float) -> list[dict]:
    """Ráfaga de `POST /cases` sin workers mientras se muestrea la profundidad total de `queue:*` (QA-05)."""
    filas: list[dict] = []
    candado = threading.Lock()
    inicio = time.monotonic()
    fin = inicio + duracion

    def muestrear() -> None:
        while time.monotonic() < fin:
            profundidad = sum(cliente_redis.llen(cola) for cola in cliente_redis.scan_iter("queue:*"))
            with candado:
                filas.append({"tipo": "muestra", "t_s": round(time.monotonic() - inicio, 3), "profundidad": profundidad,
                              "codigo": "", "latencia_ms": ""})
            time.sleep(intervalo)

    def producir() -> None:
        sesion = requests.Session()
        while time.monotonic() < fin:
            t0 = time.monotonic()
            codigo = sesion.post(f"{url}/cases", json=CASO, timeout=30).status_code
            with candado:
                filas.append({"tipo": "respuesta", "t_s": round(t0 - inicio, 3), "profundidad": "",
                              "codigo": codigo, "latencia_ms": round((time.monotonic() - t0) * 1000, 2)})

    hilos = [threading.Thread(target=muestrear)] + [threading.Thread(target=producir) for _ in range(productores)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return sorted(filas, key=lambda f: f["t_s"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide backpressure con y sin límite de cola (F-24, QA-05).")
    parser.add_argument("--url", required=True)
    parser.add_argument("--redis", required=True, help="URL de Redis del coordinador, p. ej. redis://localhost:6379/0")
    parser.add_argument("--limite", required=True, type=int, help="QUEUE_MAX_DEPTH con que corre el coordinador")
    parser.add_argument("--productores", type=int, default=20)
    parser.add_argument("--duracion", type=float, default=60)
    parser.add_argument("--intervalo", type=float, default=0.25)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    cliente_redis = redis.Redis.from_url(args.redis, decode_responses=True)
    for cola in cliente_redis.scan_iter("queue:*"):
        cliente_redis.delete(cola)
    filas = medir(args.url.rstrip("/"), cliente_redis, args.productores, args.duracion, args.intervalo)
    with args.out.open("w", newline="", encoding="utf-8") as salida:
        escritor = csv.DictWriter(salida, fieldnames=["tipo", "t_s", "profundidad", "codigo", "latencia_ms"])
        escritor.writeheader()
        escritor.writerows(filas)
    print({"limite": args.limite, **resumir(filas)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
