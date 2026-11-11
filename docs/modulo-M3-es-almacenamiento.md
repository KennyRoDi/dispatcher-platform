# M3 · E/S y almacenamiento

## Qué se implementó

F-22 agrega `scripts/measure/m3_chunks.py` para medir throughput de subida por tamaño de chunk, y F-23 prepara el coordinador con MinIO cifrado, deduplicación antes de transferir y staging en volumen local del Nodo A.

## Concepto de Sistemas Operativos

El coordinador guarda temporalmente los chunks en disco para limitar RAM, reensambla por flujo y transfiere el objeto por red hacia MinIO. La medición calcula bytes sobre tiempo y cronometra aparte el complete (reensamblado y hash).

## Método de medición

Comando reproducible desde el Nodo B (worker) hacia el coordinador del Nodo A, conectado por la red real de nodos:

```bash
python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a
```

El archivo debe ser sintético y tener al menos 200 MiB. El runner calcula el SHA-256 antes de cronometrar, envía cada chunk con su hash, mide desde `POST /uploads` hasta la respuesta de `complete`, reporta aparte la duración de `complete`, escribe cada repetición en CSV y muestra media y desviación de MiB/s. El objeto se borra después de cada repetición para que la deduplicación no evite la transferencia de red.

La tasa de deduplicación F-23 se midió por separado con `python scripts/measure/m3_dedup.py --dir <dataset> --reps 3 --out docs/evidencia/m3_dedup_2026-11-11.csv`, coordinador y MinIO locales aislados y bucket vacío al inicio. El entorno, comandos y limitaciones están en `docs/evidencia/F-23_deduplicacion_2026-11-11.md`.

## Resultados

F-22, throughput entre nodos: pendiente. Este entorno no tiene `dataset/media/case_h1.mp4`, ni un coordinador desplegado en Nodo A y un worker remoto en Nodo B. Docker local no demuestra tráfico entre nodos y no se usa como sustituto.

F-23, deduplicación: 480 archivos sintéticos, 693,299,339 bytes por pasada, 3 pasadas. Se midieron 2,079,898,017 bytes lógicos, 687,678,832 bytes almacenados y 1,392,219,185 bytes ahorrados: **66.936897%**. La medición local aislada no representa throughput entre nodos.

## Interpretación

La medición de throughput requiere un medio sintético de al menos 200 MiB y un worker remoto en un nodo distinto. La tasa de deduplicación ya tiene datos medidos; permanece pendiente únicamente el throughput distribuido de F-22 para cerrar AD-10.
