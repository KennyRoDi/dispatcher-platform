**Resumen:** Dataset sintético de F-03: procedencia, límites, casos por condición, cómo generarlo y validarlo, y qué se distribuye fuera del repo.

# Dataset sintético

## Procedencia

- Generado por el equipo (Grupo 3) con `scripts/dataset_sintetico.py`; origen `sintetico` y licencia MIT en las 490 filas del manifiesto. Ningún dato es real ni de terceros [B.3].
- Chats: plantillas de vocabulario neutro y frases de amenaza ficticias, redactadas con IA; la persona aprobó las frases de amenaza ficticias y los mensajes sintéticos. Imágenes, audios y videos los produce `ffmpeg`, de FFmpeg developers (ffmpeg.org, LGPL/GPL según la compilación); no se redistribuye `ffmpeg`, solo su salida.
- Decisión del generador: AD-25 en [ARQUITECTURA.md](ARQUITECTURA.md) §8. Diseño: `docs/specs/F-03/SPEC.md`.

## Limitación sintética

- Las imágenes son un color sólido por archivo, no fotos. La etiqueta es `positivo` o `neutro` (no existe `negativo`) y la asigna el generador por categoría (`objetos`, `paisajes`, `documentos`, `personas`) con una proporción positiva conocida. Sirven para probar el flujo y la carga, no para medir la calidad de un modelo.
- Los audios son tonos (`tono`) o ruido (`ruido`) de 5 a 300 s, sin voz. Los chats usan vocabulario fijo.
- Todo caso pesado es un video `.mpg` de al menos 200 MiB.
- Los hashes de los archivos pueden variar entre versiones de `ffmpeg`; se usó 7.1.5.

## Contenido generado (semilla 1)

Recuento desde `manifest.json`: 40 casos; 300 imágenes, 150 audios (80 ruido y 70 tono), 25 textos, 10 documentos y 5 videos; 490 archivos, 1,96 GB (1,83 GiB). Es un dato del artefacto, no una medición de SO.

| Condición | Casos | Detalle |
|---|---|---|
| Heterogéneo liviano | 5 | Con audio, documento, imagen y texto |
| Heterogéneo pesado | 5 | Con audio, imagen, texto y un video de 219 512 832 bytes (≥ 200 MiB) |
| No heterogéneo | 30 | Uno o dos tipos por caso |

Imágenes positivas por categoría: documentos 33 de 75, objetos 31 de 75, paisajes 24 de 75 y personas 14 de 75.

## Generar y validar

Desde la raíz del repo:

```bash
PYTHONPATH=. python -m scripts.dataset_sintetico --seed 1 --out dataset/sintetico
PYTHONPATH=. python -m scripts.dataset_sintetico --out dataset/sintetico --validar
```

La generación tardó 173 s (código de salida 0). Salida real del validador:

```
dataset/sintetico/manifest.json: cumple los minimos de B.3
```

`--params` acepta un JSON con campos de `DatasetParams`. El `sha256` de ese `manifest.json` fue `30bbba4583bf6fcc9906746b7793ed5e33e7e1e82643297fc631289cad73a0c6`.

## Reproducibilidad

La misma semilla produce el mismo plan y el mismo manifiesto: nombres, conteos y orden. El manifiesto no tiene marca de tiempo. Un hash de archivo solo se garantiza con la misma versión de `ffmpeg`.

## Tras un fallo

- Si la generación falla, se borran los archivos creados en esa ejecución, pero el `manifest.json` previo ya se borró y no se restaura. Tras un fallo se borra `--out` y se repite.
- No se garantiza la limpieza ante `SIGTERM` ni una señal fatal: el proceso termina con código 143 y quedan archivos huérfanos.
- Se rechaza con error cualquier enlace simbólico dentro de `--out`, aunque no sea de un caso. No se detecta uno creado durante la ejecución.
- `generate_heavy_cases` usado directo: si falla el caso N, quedan en disco los archivos de los casos anteriores; bórrelos antes de repetir.

## Ubicación y distribución

- Local: `dataset/sintetico/`, excluido del repo por `.gitignore`. Los archivos de `dataset/` del I Proyecto (`README.md`, `cases.json`, `manifest.json`) no se tocan.
- Enlace de Google Drive con los casos pesados: **pendiente: lo aporta la persona.** Sin enlace, cada integrante regenera el dataset con los comandos de arriba.
