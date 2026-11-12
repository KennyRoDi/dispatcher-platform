"""Gráficos de la ráfaga F-33 desde latencia_por_caso.csv y recursos_por_nodo.csv de cada corrida.

Uso: python docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/graficar.py  (escribe los PNG junto al script)
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CARPETA = Path(__file__).parent
CORRIDAS = ["rep1", "rep2", "rep3", "opcional_40casos"]
COLORES_HOST = {"worker-sim-1": "#0072B2", "worker-sim-2": "#D55E00", "worker-sim-3": "#009E73"}
COLORES_PRIORIDAD = {"normal": "#0072B2", "high": "#E69F00"}
AVISO = "SIMULACIÓN LOCAL: no acredita B.2 ni Tailscale ni entidades separadas"


def leer(corrida, nombre):
    with (CARPETA / corrida / nombre).open(encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def figura(titulo):
    fig, ejes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    fig.suptitle(f"{titulo}\n{AVISO}", fontsize=11)
    return fig, ejes.flat


def graficar_latencia():
    fig, ejes = figura("F-33: latencia por caso (duración desde el envío hasta el estado final)")
    for eje, corrida in zip(ejes, CORRIDAS):
        filas = sorted(leer(corrida, "latencia_por_caso.csv"), key=lambda f: float(f["duracion_s"]))
        for posicion, fila in enumerate(filas):
            eje.bar(posicion, float(fila["duracion_s"]), color=COLORES_PRIORIDAD[fila["prioridad"]])
        eje.set(title=f"{corrida} ({len(filas)} casos)", xlabel="casos ordenados por latencia", ylabel="segundos")
    ejes[0].legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in COLORES_PRIORIDAD.values()],
                   labels=list(COLORES_PRIORIDAD), title="prioridad")
    fig.savefig(CARPETA / "latencia_por_caso.png", dpi=130)


def graficar_recursos():
    fig, ejes = figura("F-33: CPU del host por worker en el tiempo (psutil del heartbeat; el host es el mismo)")
    for eje, corrida in zip(ejes, CORRIDAS):
        filas = leer(corrida, "recursos_por_nodo.csv")
        for host, color in COLORES_HOST.items():
            propios = [f for f in filas if f["host"] == host]
            eje.plot([float(f["instante"]) for f in propios], [float(f["cpu_percent"]) for f in propios],
                     marker="o", color=color, label=host)
        eje.set(title=corrida, xlabel="segundos desde el inicio", ylabel="cpu_percent", ylim=(0, 105))
    ejes[0].legend()
    fig.savefig(CARPETA / "recursos_por_nodo.png", dpi=130)


if __name__ == "__main__":
    graficar_latencia()
    graficar_recursos()
