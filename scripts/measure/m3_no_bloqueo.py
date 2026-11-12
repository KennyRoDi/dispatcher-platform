from __future__ import annotations

import argparse
import csv
import hashlib
import random
import statistics
import sys
import threading
import time
from pathlib import Path

import requests

PIEZA = 64 * 1024


def bloque(semilla: int, indice: int, tamano: int) -> bytes:
    return random.Random(semilla * 1_000_003 + indice).randbytes(tamano)


def percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p / 100 * (len(ordenados) - 1)))]


def resumir(filas: list[dict]) -> dict:
    resumen = {}
    for fase in ("antes", "durante", "despues"):
        latencias = [f["latencia_ms"] for f in filas if f["fase"] == fase and f["codigo"] == 200]
        resumen[fase] = {
            "n": len(latencias),
            "errores": sum(1 for f in filas if f["fase"] == fase and f["codigo"] != 200),
            "p50_ms": percentil(latencias, 50),
            "p95_ms": percentil(latencias, 95),
            "max_ms": max(latencias, default=None),
            "media_ms": round(statistics.fmean(latencias), 2) if latencias else None,
        }
    return resumen


def _cuerpo_lento(datos: bytes, bytes_por_segundo: float):
    for inicio in range(0, len(datos), PIEZA):
        yield datos[inicio:inicio + PIEZA]
        time.sleep(PIEZA / bytes_por_segundo)


def subir_lento(url: str, mib: int, chunk: int, kbps: int, semilla: int) -> float:
    """Sube `mib` MiB sintéticos limitando el envío a `kbps` KiB/s; devuelve la duración en segundos."""
    tamano = mib << 20
    cantidad = -(-tamano // chunk)
    resumen = hashlib.sha256()
    for i in range(cantidad):
        resumen.update(bloque(semilla, i, min(chunk, tamano - i * chunk)))
    inicio = time.monotonic()
    respuesta = requests.post(f"{url}/uploads", json={"sha256": resumen.hexdigest(), "size": tamano,
                                                      "chunk_size": chunk}, timeout=60)
    respuesta.raise_for_status()
    if respuesta.json().get("stored"):
        raise RuntimeError("el contenido ya estaba almacenado: usa otra --semilla")
    upload_id = respuesta.json()["upload_id"]
    for i in range(cantidad):
        datos = bloque(semilla, i, min(chunk, tamano - i * chunk))
        requests.put(f"{url}/uploads/{upload_id}/chunks/{i}", data=_cuerpo_lento(datos, kbps * 1024),
                     headers={"X-Chunk-SHA256": hashlib.sha256(datos).hexdigest()}, timeout=600).raise_for_status()
    requests.post(f"{url}/uploads/{upload_id}/complete", timeout=600).raise_for_status()
    return time.monotonic() - inicio


def medir(url: str, mib: int, chunk: int, kbps: int, semilla: int, intervalo: float, margen: float) -> list[dict]:
    """Muestrea `GET /health` antes, durante y después de una subida lenta (RF-34)."""
    filas: list[dict] = []
    fase = ["antes"]
    fin = threading.Event()
    origen = time.monotonic()

    def muestrear() -> None:
        sesion = requests.Session()
        while not fin.is_set():
            t0 = time.monotonic()
            try:
                codigo = sesion.get(f"{url}/health", timeout=10).status_code
            except requests.RequestException:
                codigo = 0
            filas.append({"t_s": round(t0 - origen, 3), "fase": fase[0], "codigo": codigo,
                          "latencia_ms": round((time.monotonic() - t0) * 1000, 2)})
            time.sleep(intervalo)

    muestreador = threading.Thread(target=muestrear)
    muestreador.start()
    try:
        time.sleep(margen)
        fase[0] = "durante"
        subir_lento(url, mib, chunk, kbps, semilla)
        fase[0] = "despues"
        time.sleep(margen)
    finally:
        fin.set()
        muestreador.join()
    return filas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide la latencia de la API durante una subida grande (F-25, RF-34).")
    parser.add_argument("--url", required=True)
    parser.add_argument("--mib", type=int, default=256)
    parser.add_argument("--chunk", type=int, default=4 << 20, help="bytes por chunk")
    parser.add_argument("--kbps", type=int, default=8192, help="KiB/s de envío del cliente lento")
    parser.add_argument("--semilla", type=int, default=1)
    parser.add_argument("--intervalo", type=float, default=0.1)
    parser.add_argument("--margen", type=float, default=2.0, help="segundos de muestreo antes y después")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    filas = medir(args.url.rstrip("/"), args.mib, args.chunk, args.kbps, args.semilla, args.intervalo, args.margen)
    with args.out.open("w", newline="", encoding="utf-8") as salida:
        escritor = csv.DictWriter(salida, fieldnames=["t_s", "fase", "codigo", "latencia_ms"])
        escritor.writeheader()
        escritor.writerows(filas)
    print(resumir(filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
