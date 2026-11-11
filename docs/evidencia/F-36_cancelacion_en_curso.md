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

## Medición B.6 en nodos reales: Medición pendiente (depende de F-38)

La medición de cancelación en curso sobre tres nodos worker reales queda pendiente hasta que F-38 (despliegue en tres nodos) esté disponible. Hasta entonces no hay datos medidos en esta ficha: no hay valores de memoria, tiempos de liberación ni resultados de la corrida real.
