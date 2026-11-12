# F-23 · Medición de deduplicación M3

Fecha: 2026-11-11.

## Entorno

- Dataset sintético local generado con FFmpeg: 480 archivos, semilla 42, 693,299,339 bytes por pasada; 469 hashes de contenido únicos.
- Cliente: Windows 11 (10.0.26300), Python 3.14.0.
- MinIO y coordinador en Docker Compose aislado (`melany-m3`), Docker Engine 29.7.2; coordinador Python 3.13.
- Bucket `objetos` vacío al iniciar; tres pasadas del dataset.
- TLS y autenticación desactivados solo en el stack aislado de esta medición. El almacén cifrado estuvo activo con KEK efímera generada para desarrollo; la llave no se guardó ni registró.

## Comandos

```powershell
py -3.14 -m scripts.build_dataset --out <dir-temporal> --files 480 --seed 42 --jobs 4
$env:MINIO_ENDPOINT = 'localhost:9000'
$env:MINIO_ACCESS_KEY = 'minioadmin'
$env:MINIO_SECRET_KEY = 'minioadmin'
$env:MINIO_SECURE = 'false'
$env:TLS_ENABLED = 'false'
$env:OBJECTS_BUCKET = 'objetos'
$env:COORDINATOR_URL = 'http://localhost:8000'
py -3.14 -m scripts.measure.m3_dedup --dir <dir-temporal>\media --reps 3 --out docs/evidencia/m3_dedup_2026-11-11.csv
```

## Resultado observado

| Archivos | Pasadas | Bytes lógicos | Objetos únicos | Bytes almacenados | Bytes ahorrados | Deduplicación |
|---:|---:|---:|---:|---:|---:|---:|
| 480 | 3 | 2,079,898,017 | 469 | 687,678,832 | 1,392,219,185 | 66.936897% |

Los bytes almacenados incluyen 43,069 bytes de cabeceras de cifrado sobre 687,635,763 bytes de contenido único. El resultado usa la fórmula `1 − bytes almacenados / bytes lógicos`. El CSV crudo con los totales observados está en `docs/evidencia/m3_dedup_2026-11-11.csv`.

La medición es de deduplicación con MinIO real en un contenedor local; no mide throughput entre nodos. F-22 sigue requiriendo worker y coordinador en nodos reales separados.
