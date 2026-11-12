# F-41 · Recálculos documentales

Ejecutado el 2026-11-12 con Python 3.14 local, usando archivos históricos del repositorio. No es una medición nueva del SO ni reproducción en otra máquina. M5 conserva agregados históricos, no tiempos individuales: se comprueba la transcripción de su tabla, no se reconstruye el p95 original. M4 aporta casos categóricos, no una cifra agregada que recalcular.

Comando exacto PowerShell desde la raíz (el ejecutable usado es el instalado localmente):

```powershell
@'
import csv, json, statistics
from collections import defaultdict
from pathlib import Path
runs=json.loads(Path("docs/evidencia/F-19/comparacion/run-20261111T050340678173Z.json").read_text())["runs"]
groups=defaultdict(list)
for run in runs:
    snap=next(s for s in run["snapshots"] if s["stage"]=="inferred")
    groups[(run["strategy"],run["workers"])].append(snap["pss_bytes"])
for key,values in sorted(groups.items()):
    print("M1",key,"n=",len(values),"PSS media B=",statistics.mean(values))
groups=defaultdict(list)
for row in csv.DictReader(Path("docs/evidencia/F-21_comparacion_politicas_2026-11-11.csv").open()):
    groups[(row["politica"],row["nivel"])].append(row)
for key,rows in sorted(groups.items()):
    print("M2",key,[(field,round(statistics.mean(float(r[field]) for r in rows),4)) for field in ("espera_ms","turnaround_ms","throughput_cps")])
row=next(csv.DictReader(Path("docs/evidencia/m3_dedup_2026-11-11.csv").open()))
logical,stored,saved=(int(row[k]) for k in ("logical_bytes","stored_bytes","bytes_saved"))
assert logical-stored==saved
print("M3 ahorro B=",saved,"tasa %=",saved/logical*100)
rows=json.loads(Path("docs/evidencia/F-31_m5_bench_2026-11-11.json").read_text())
for r in rows:
    print("M5",r["config"],*[round(r[k],3) for k in ("latencia_media_s","latencia_p95_s","throughput_x_realtime")],round(r["memoria_pico_mb"]),"MiB",r["repeticiones"])
from scripts.conformidad import revisar_ficha
for path in sorted(Path("docs").glob("modulo-M*.md")):
    print("ESTRUCTURA",path.name,revisar_ficha(path.read_text(encoding="utf-8")))
'@ | & C:\Users\Usuario\AppData\Local\Python\pythoncore-3.14-64\python.exe -
```

Salida real:

```text
M1 ('por_proceso', 1) n= 5 PSS media B= 264806195.2
M1 ('por_proceso', 2) n= 5 PSS media B= 420311449.6
M1 ('workers_compartidos', 1) n= 5 PSS media B= 261983232
M1 ('workers_compartidos', 2) n= 5 PSS media B= 281929728
M2 ('aging', 'alta') [('espera_ms', 443.5823), ('turnaround_ms', 453.7397), ('throughput_cps', 64.0121)]
M2 ('aging', 'baja') [('espera_ms', 234.9867), ('turnaround_ms', 244.2467), ('throughput_cps', 3.2006)]
M2 ('fifo', 'alta') [('espera_ms', 452.8023), ('turnaround_ms', 462.9193), ('throughput_cps', 64.0121)]
M2 ('fifo', 'baja') [('espera_ms', 50.5887), ('turnaround_ms', 60.656), ('throughput_cps', 3.2006)]
M3 ahorro B= 1392219185 tasa %= 66.9368965988105
M5 cpu-float32-h1 2.31 2.505 4.922 488 MiB 5
M5 cpu-float32-h2 1.611 1.653 7.057 470 MiB 5
M5 cpu-float32-h4 1.321 1.367 8.612 519 MiB 5
M5 cpu-int8-h1 1.954 2.233 5.821 317 MiB 5
M5 cpu-int8-h2 1.049 1.187 10.841 343 MiB 5
M5 cpu-int8-h4 0.828 0.947 13.727 345 MiB 5
ESTRUCTURA modulo-M1-memoria.md []
ESTRUCTURA modulo-M2-planificacion.md []
ESTRUCTURA modulo-M3-es-almacenamiento.md []
ESTRUCTURA modulo-M4-seguridad.md []
ESTRUCTURA modulo-M5-computo.md []
```

Las medias M1 coinciden con la ficha al redondear a bytes; M2 coincide al redondear a una decimal (throughput dos); deduplicación M3 coincide a seis decimales. El campo M5 `memoria_pico_mb` está en MiB por la división RSS/1024² del runner. Estos cálculos no completan los productos experimentales pendientes ni la reproducción US-41.
