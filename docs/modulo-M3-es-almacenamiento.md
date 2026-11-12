# M3 · E/S y almacenamiento

## Qué se implementó

F-22 agrega `scripts/measure/m3_chunks.py` para medir throughput de subida por tamaño de chunk. F-23 conecta MinIO cifrado, evita transferir contenido ya almacenado y guarda chunks temporalmente en el volumen `STAGING_DIR` del Nodo A.

F-24 acota la profundidad de cada cola de Redis (`QUEUE_MAX_DEPTH`): `POST /cases` admite un caso con un script Lua atómico que compara `LLEN + entrantes` con el límite y, si no cabe, responde `503` con `Retry-After`; `mover_acotado` deja la misma regla lista para el scheduler (AD-12). `scripts/measure/m3_backpressure.py` mide la profundidad y las respuestas con y sin límite.

F-25 garantiza que la API siga respondiendo durante subidas grandes: `PUT /uploads/{id}/chunks/{index}` lee el cuerpo con `async for`, y la lectura del manifiesto y la escritura del chunk corren en el pool de hilos (AD-13). `scripts/measure/m3_no_bloqueo.py` mide la latencia de `GET /health` antes, durante y después de una subida lenta.

## Concepto de Sistemas Operativos

El coordinador escribe los chunks en disco para limitar RAM, reensambla por flujo y transmite el objeto a MinIO. El SHA-256 permite evitar almacenamiento y transferencia repetidos. Para F-22, el runner mide los bytes por tiempo de subida y reporta por separado la duración de `complete` (reensamblado y hash).

F-24 es el problema del búfer acotado entre productores y consumidores: cuando los productores son más rápidos que los consumidores, una cola sin límite crece hasta agotar la memoria del servidor de colas. Con el límite, el productor recibe rechazo (backpressure) en vez de bloquearse, y la memoria ocupada por las colas queda acotada.

F-25 es E/S no bloqueante: mientras un cliente lento envía bytes, el event loop de uvicorn no queda esperando en esa conexión ni en el disco, porque la E/S de red es asíncrona y la de disco se delega a hilos. Así, otras peticiones se atienden durante la subida.

## Método de medición

F-22 se mide desde un worker en el Nodo B hacia el coordinador del Nodo A, sobre la red real entre nodos:

```bash
python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a
```

El archivo sintético debe tener al menos 200 MiB. El runner calcula el SHA-256 antes de cronometrar, envía cada chunk con su hash, mide desde `POST /uploads` hasta la respuesta de `complete`, reporta aparte el tiempo de `complete`, escribe cada repetición en CSV y muestra media y desviación de MiB/s. Borra el objeto después de cada repetición para que la deduplicación no evite la transferencia.

La tasa de deduplicación F-23 se midió con `python scripts/measure/m3_dedup.py --dir <dataset> --reps 3 --out docs/evidencia/m3_dedup_2026-11-11.csv`, un coordinador y MinIO locales aislados y el bucket vacío al inicio. El entorno, los comandos exactos y las limitaciones están en `docs/evidencia/F-23_deduplicacion_2026-11-11.md`.

F-24 se midió con un coordinador (uvicorn) y Redis 7.0.15 locales, sin workers, para forzar la saturación, con 20 productores durante 60 s y tres repeticiones por condición:

```bash
redis-server --port 6391 --save "" --appendonly no
QUEUE_MAX_DEPTH=200 QUEUE_RETRY_AFTER=5 REDIS_HOST=127.0.0.1 REDIS_PORT=6391 TLS_ENABLED=false AUTH_ENABLED=false \
  python -m uvicorn src.coordinator.main:app --host 127.0.0.1 --port 8091
python -m scripts.measure.m3_backpressure --url http://127.0.0.1:8091 --redis redis://127.0.0.1:6391/0 \
  --limite 200 --productores 20 --duracion 60 --out m3_backpressure_con_1.csv
```

La condición sin límite repite lo mismo con `QUEUE_MAX_DEPTH=0` y `--limite 0`. Antes de cada repetición se vacía Redis y se reinicia el coordinador. Entorno: contenedor Linux x86_64 de 2 CPU y 7 GiB de RAM, Python 3.13 (sesión de Claude, sin red entre nodos). El script muestrea la profundidad total de `queue:*` cada 250 ms y registra código y latencia de cada `POST /cases`.

F-25 se midió con un coordinador (uvicorn) de `main` más el cambio de F-25, Redis 7.0.15 y un S3 simulado (moto) como almacén de objetos, con cifrado activo. El cliente envía 256 MiB en chunks de 4 MiB limitado a 8 MiB/s mientras otro hilo pide `GET /health` cada 100 ms. Tres repeticiones, con semillas distintas para que la deduplicación no evite la subida:

```bash
python -m scripts.measure.m3_no_bloqueo --url http://127.0.0.1:8092 --mib 256 --kbps 8192 --semilla 1 --out m3_no_bloqueo_1.csv
```

Entorno: el mismo contenedor Linux de 2 CPU y 7 GiB de F-24. El almacén simulado solo recibe el objeto al final (`complete`); la latencia medida corresponde a la API, no al almacén.

## Resultados

**F-22, throughput entre nodos: pendiente.** No está disponible `dataset/media/case_h1.mp4` ni un coordinador en Nodo A con un worker remoto en Nodo B. La simulación local no acredita tráfico entre nodos y no se usa como sustituto.

**F-23, deduplicación:** dataset sintético de 480 archivos, 693,299,339 bytes por pasada y tres pasadas. Se midieron 2,079,898,017 bytes lógicos, 687,678,832 bytes almacenados y 1,392,219,185 bytes ahorrados: **66.936897%**. El CSV crudo está en `docs/evidencia/m3_dedup_2026-11-11.csv`. Esta medición local aislada no representa throughput entre nodos.

**F-24, backpressure** (resumen por segundo en `docs/evidencia/m3_backpressure_2026-11-11.csv`; gráfico en `docs/evidencia/m3_backpressure_2026-11-11.png`):

| Condición | Rep. | Profundidad máxima muestreada | Respuestas 201 | Respuestas 503 | Latencia p50 / p95 (ms) |
|---|---|---|---|---|---|
| Límite 200 | 1 | 200 | 200 | 60,568 | 17.90 / 37.33 |
| Límite 200 | 2 | 200 | 200 | 61,162 | 17.56 / 37.42 |
| Límite 200 | 3 | 200 | 200 | 61,254 | 17.53 / 37.20 |
| Sin límite | 1 | 52,784 | 54,491 | 0 | 20.22 / 39.79 |
| Sin límite | 2 | 55,199 | 55,199 | 0 | 19.98 / 39.01 |
| Sin límite | 3 | 54,662 | 56,499 | 0 | 19.57 / 38.13 |

Todos los `503` llevaron `Retry-After`. En la condición sin límite el muestreador quedó sin turno en algunos segundos por la carga de los 20 productores en el mismo proceso; esos segundos quedan vacíos en el CSV y la profundidad final real es la de las respuestas 201.

**F-25, recepción no bloqueante** (crudo en `docs/evidencia/m3_no_bloqueo_2026-11-11.csv`; gráfico en `docs/evidencia/m3_no_bloqueo_2026-11-11.png`). Cada subida duró unos 37.5 s:

| Rep. | Fase | Peticiones | Errores | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---|---|---|---|---|---|
| 1 | Antes | 20 | 0 | 2.69 | 4.90 | 25.72 |
| 1 | Durante | 367 | 0 | 2.48 | 3.22 | 19.50 |
| 1 | Después | 20 | 0 | 2.82 | 5.98 | 7.57 |
| 2 | Antes | 20 | 0 | 2.85 | 3.54 | 4.33 |
| 2 | Durante | 365 | 0 | 2.40 | 4.10 | 21.60 |
| 2 | Después | 20 | 0 | 2.57 | 4.35 | 6.24 |
| 3 | Antes | 20 | 0 | 2.81 | 4.44 | 7.88 |
| 3 | Durante | 363 | 0 | 2.43 | 3.43 | 17.84 |
| 3 | Después | 20 | 0 | 2.47 | 2.94 | 6.29 |

## Interpretación

La medición de throughput requiere un medio sintético de al menos 200 MiB y un worker remoto en otro nodo. La tasa de deduplicación sí cuenta con datos medidos; queda pendiente únicamente el throughput distribuido de F-22 para cerrar AD-10.

**F-24:** con el límite, la profundidad se mantuvo exactamente en 200 durante los 60 s de las tres repeticiones y el excedente se rechazó con `503`; sin límite, la cola creció de forma sostenida a unas 900 subtareas por segundo y superó las 52,000 sin señal para los productores. La latencia de `POST /cases` fue similar en ambas condiciones (p95 de unos 37 a 40 ms), así que el rechazo no encarece la admisión. La medición es local y sin workers: muestra el mecanismo, no la capacidad del sistema distribuido.

**F-25:** durante las tres subidas de 256 MiB la API respondió las 1,095 peticiones sin errores, con una mediana de unos 2.4 ms, igual que antes y después de subir. Los máximos aislados de 18 a 22 ms coinciden con el cierre de cada chunk (hash y escritura en el pool de hilos) y siguen dos órdenes de magnitud por debajo de la duración de la subida. Es una medición local de un solo coordinador: demuestra que la recepción no bloquea, no mide la red entre nodos.

Referencia bibliográfica: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed., capítulo 7, problema del búfer acotado (productor y consumidor); edición del curso por confirmar según SUP-16. Referencia específica: documentación de Redis, `EVAL` (atomicidad de scripts Lua).

Referencia bibliográfica: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed., capítulo 12, «I/O Systems», E/S bloqueante y no bloqueante; edición del curso por confirmar según SUP-16.
