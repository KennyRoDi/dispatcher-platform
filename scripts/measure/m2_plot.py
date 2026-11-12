from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NIVELES_ORDEN = ("baja", "media", "alta", "critica")
METRICAS = (("espera_ms", "Espera (ms)"), ("turnaround_ms", "Turnaround (ms)"), ("throughput_cps", "Throughput (casos/s)"))


def leer_filas(rutas: list[Path]):
    filas = []
    for ruta in rutas:
        with ruta.open(newline="", encoding="utf-8") as archivo:
            filas.extend(csv.DictReader(archivo))
    return filas


def agregar(filas):
    """Promedia por (politica, nivel) si hay varias repeticiones (columna seed opcional)."""
    acumulado = defaultdict(lambda: defaultdict(list))
    for fila in filas:
        clave = (fila["politica"], fila["nivel"])
        for metrica, _ in METRICAS:
            acumulado[clave][metrica].append(float(fila[metrica]))
    return {
        clave: {metrica: sum(valores) / len(valores) for metrica, valores in metricas.items()}
        for clave, metricas in acumulado.items()
    }


def graficar(agregados, salida: Path) -> None:
    politicas = sorted({politica for politica, _ in agregados})
    niveles = sorted({nivel for _, nivel in agregados}, key=lambda n: NIVELES_ORDEN.index(n) if n in NIVELES_ORDEN else 99)

    fig, ejes = plt.subplots(1, len(METRICAS), figsize=(5 * len(METRICAS), 4))
    ancho = 0.8 / len(politicas)
    for eje, (metrica, titulo) in zip(ejes, METRICAS):
        for i, politica in enumerate(politicas):
            valores = [agregados.get((politica, nivel), {}).get(metrica, 0.0) for nivel in niveles]
            posiciones = [x + i * ancho for x in range(len(niveles))]
            eje.bar(posiciones, valores, width=ancho, label=politica)
        eje.set_xticks([x + ancho * (len(politicas) - 1) / 2 for x in range(len(niveles))])
        eje.set_xticklabels(niveles)
        eje.set_title(titulo)
        eje.set_xlabel("nivel de prioridad")
        eje.legend()

    fig.tight_layout()
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera gráficos comparativos de espera/turnaround/throughput por política (F-21)."
    )
    parser.add_argument("csv", nargs="+", type=Path, help="CSV producidos por m2_sched.py")
    parser.add_argument("--out", type=Path, default=Path("m2_comparacion.png"))
    args = parser.parse_args(argv)
    if not all(ruta.is_file() for ruta in args.csv):
        parser.error("todos los CSV deben existir")

    filas = leer_filas(args.csv)
    if not filas:
        parser.error("los CSV no contienen filas")
    agregados = agregar(filas)
    graficar(agregados, args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
