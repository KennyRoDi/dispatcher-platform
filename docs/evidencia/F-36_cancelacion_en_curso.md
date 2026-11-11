# F-36 · Evidencia de cancelación en curso de un caso pesado

## Qué cubre el escenario

`scenarios/cancel_heavy.py` prepara la evaluación de cancelar un caso pesado (>= 200 MB) mientras corre una sub-tarea (FFmpeg) en un worker:

1. Genera un archivo sintético de al menos 200 MB (`generar_archivo_pesado`).
2. Toma una instantánea antes y otra después de la cancelación (`tomar_instantanea`):
   - `ps -eo pid,ppid,stat,rss,cmd`, filtrando procesos `ffmpeg`.
   - `ls -la /scratch`, para comprobar que no quedan temporales.
   - `cat /sys/fs/cgroup/memory.current`, para medir la memoria del worker.
3. Evalúa el resultado (`evaluar`): no deben quedar procesos de sub-tarea ni entradas en scratch, la memoria debe bajar y el caso debe quedar `cancelled`.
4. Calcula el tiempo de liberación (`tiempo_liberacion`): instante desde el cual ya no hay procesos de sub-tarea en las muestras.

El módulo no lanza la corrida real: solo genera la carga, toma las instantáneas y evalúa. La corrida la hace un worker en nodos reales.

## Cómo correrlo

- **Unitarias** (en cualquier sistema, sin red ni nodos):
  ```
  py -m pytest tests/unit/test_cancel_heavy.py -q
  ```
  Resultado: 14 pruebas.

- **Integración Linux** (requiere procesos POSIX): en un contenedor Docker con el repositorio montado en `/app`, con `procps` y, para la prueba de FFmpeg, `ffmpeg` en el PATH. Archivo: `tests/integration/test_cancelacion_en_curso_linux.py`.

- **Aceptación** (requiere la salida JSON de una corrida real): exportar la salida de `scenarios/cancel_heavy.py` a un archivo y apuntar la variable al archivo:
  ```
  CANCEL_HEAVY_JSON=<ruta_al_json> py -m pytest tests/acceptance/test_cancel_heavy_aceptacion.py -q
  ```
  El JSON debe tener las claves `megabytes`, `antes`, `despues` y `estado_caso`.

## Límites

- Las pruebas de integración usan procesos POSIX. En Windows se omiten: 3 pruebas `skipped`.
- La prueba de aceptación se omite sin `CANCEL_HEAVY_JSON`: 1 prueba `skipped`.
- Total en Windows: 14 pasan (unitarias) y 4 se omiten (integración y aceptación).
- Las pruebas unitarias usan datos simulados; no prueban el comportamiento real del sistema operativo.

## Medición real en un contenedor Docker (2026-11-11)

**Entorno:** un único host Docker Desktop (Linux, WSL2 kernel 6.18.33.2, 16 CPUs, 15,6 GB), cgroup v2, contenedor con `--memory=2g`, Python 3.13.18, FFmpeg 7.1.5, usuario no root (10001), commit base `63f6b62`. **No son tres nodos**: la medición en tres nodos worker sigue como **Medición pendiente** (requiere los nodos de F-38).

**Qué se hizo:** `docs/evidencia/mediciones-f36-f37/medir_f36.py` genera un caso de 316 MB (video sin comprimir, ≥ 200 MB), lanza `multimedia_processor.process("transcode_video", ...)` con `ProcessSupervisor` y `PosixProcessRunner` reales, toma la instantánea `antes` a los 3 s (FFmpeg en curso), cancela con `supervisor.cancel`, muestrea `ps` cada 0,1 s y toma `despues`. Evalúa con `scenarios.cancel_heavy.evaluar`.

```
docker build -f docs/evidencia/mediciones-f36-f37/Dockerfile.medicion -t medicion-f36-f37 .
docker run --rm --memory=2g --memory-swap=2g -v "<repo>:/app:ro" -w /app -e PYTHONPATH=/app medicion-f36-f37 python docs/evidencia/mediciones-f36-f37/medir_f36.py
```

Salida cruda: [`mediciones-f36-f37/F-36_corrida_2026-11-11.json`](mediciones-f36-f37/F-36_corrida_2026-11-11.json). Una repetición.

| Dato | Antes de cancelar | Después |
|---|---|---|
| Procesos `ffmpeg` | 1 (PID 76) | 0 |
| Entradas en `/scratch` | 1 (`ffmpeg-<id>`) | 0 |
| `memory.current` | 1 051 451 392 B | 354 623 488 B |
| Tiempo hasta no haber procesos | | 0,1 s (primer muestreo) |

Veredicto de `evaluar`: `cumple = true`, sin problemas. La prueba de aceptación `test_cancel_heavy_aceptacion.py` con este JSON: 1 pasa.

**Límites:** `estado_caso = cancelled` lo decide el arnés (el hilo terminó y no quedan procesos); no hay coordinador ni cola, así que no se comprobó el estado del caso en el sistema completo. `process` terminó con `CorruptInputError` por la cancelación. `memory.current` incluye caché de página del archivo de entrada, que explica que no baje a cero. Una sola repetición y un host: no hay variabilidad medida.
