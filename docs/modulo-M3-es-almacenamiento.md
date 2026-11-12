# M3 · E/S y almacenamiento

## Qué se implementó

F-22 agrega `scripts/measure/m3_chunks.py` para medir throughput de subida por tamaño de chunk. F-23 conecta MinIO cifrado, evita transferir contenido ya almacenado y guarda chunks temporalmente en el volumen `STAGING_DIR` del Nodo A.

## Concepto de Sistemas Operativos

El coordinador escribe los chunks en disco para limitar RAM, reensambla por flujo y transmite el objeto a MinIO. El SHA-256 permite evitar almacenamiento y transferencia repetidos. Para F-22, el runner mide los bytes por tiempo de subida y reporta por separado la duración de `complete` (reensamblado y hash).

## Método de medición

F-22 se mide desde un worker en el Nodo B hacia el coordinador del Nodo A, sobre la red real entre nodos:

```bash
python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a
```

El archivo sintético debe tener al menos 200 MiB. El runner calcula el SHA-256 antes de cronometrar, envía cada chunk con su hash, mide desde `POST /uploads` hasta la respuesta de `complete`, reporta aparte el tiempo de `complete`, escribe cada repetición en CSV y muestra media y desviación de MiB/s. Borra el objeto después de cada repetición para que la deduplicación no evite la transferencia.

La tasa de deduplicación F-23 se midió con `python scripts/measure/m3_dedup.py --dir <dataset> --reps 3 --out docs/evidencia/m3_dedup_2026-11-11.csv`, un coordinador y MinIO locales aislados y el bucket vacío al inicio. El entorno, los comandos exactos y las limitaciones están en `docs/evidencia/F-23_deduplicacion_2026-11-11.md`.

## Resultados

**F-22, throughput entre nodos: pendiente.** No está disponible `dataset/media/case_h1.mp4` ni un coordinador en Nodo A con un worker remoto en Nodo B. La simulación local no acredita tráfico entre nodos y no se usa como sustituto.

**F-23, deduplicación:** dataset sintético de 480 archivos, 693,299,339 bytes por pasada y tres pasadas. Se midieron 2,079,898,017 bytes lógicos, 687,678,832 bytes almacenados y 1,392,219,185 bytes ahorrados: **66.936897%**. El CSV crudo está en `docs/evidencia/m3_dedup_2026-11-11.csv`. Esta medición local aislada no representa throughput entre nodos.

## Interpretación

La medición de throughput requiere un medio sintético de al menos 200 MiB y un worker remoto en otro nodo. La tasa de deduplicación sí cuenta con datos medidos; queda pendiente únicamente el throughput distribuido de F-22 para cerrar AD-10.
