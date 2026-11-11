# M3 · E/S y almacenamiento

## F-22 · Throughput por tamaño de chunk

Comando reproducible desde el Nodo B (worker) hacia el coordinador del Nodo A, conectado por la red real de nodos:

```bash
python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a
```

El archivo debe ser sintético y tener al menos 200 MiB. El runner calcula el SHA-256 antes de cronometrar, envía cada chunk con su hash, mide desde `POST /uploads` hasta la respuesta de `complete`, reporta aparte la duración de `complete`, escribe cada repetición en CSV y muestra media y desviación de MiB/s. El objeto se borra después de cada repetición para que la deduplicación no evite la transferencia de red.

**Resultados pendientes:** no se generaron cifras porque este entorno no tiene `dataset/media/case_h1.mp4`, ni coordinador activo, ni tres nodos reales. Docker mostró solo servicios Supabase. La simulación local documentada en F-38 no demuestra tráfico entre nodos y no se usa como sustituto. AD-10 permanece provisional hasta ejecutar la medición real.

## F-23 · Deduplicación

La composición cifra siempre los objetos con `EncryptedObjectStore`; sin KEK válida falla cerrada como requiere F-28. El coordinador persiste chunks en el volumen configurado por `STAGING_DIR`. Si la clave SHA-256 ya existe, `POST /uploads` devuelve `200 stored` y el cliente no transfiere chunks.

El runner de deduplicación es `scripts/measure/m3_dedup.py` y genera CSV desde un bucket vacío. La medición queda pendiente hasta disponer de dataset multimedia y coordinador con MinIO. No se publican cifras estimadas.
