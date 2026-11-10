# F-09: transcripción del worker de audio

Comando: `python -m scripts.comparar_transcripcion --muestra tests/datos/audio --esperadas tests/datos/audio/transcripciones.json --salida docs/evidencia/F-09_transcripcion_2026-11-10.md`

- faster-whisper: 1.2.1
- ctranslate2: 4.9.0
- Modelo: `base`, revisión `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`
- compute_type: int8
- Idioma: es

Muestra de 5 notas, con su procedencia y licencia:

- `amenaza_01.ogg`: Voz propia de José Andrés leyendo un guion sintético y ficticio, redactado con IA (Claude Code) para F-09; sin personas ni mensajes reales [B.3]; licencia CC BY 4.0
- `amenaza_02.ogg`: Voz propia de José Andrés leyendo un guion sintético y ficticio, redactado con IA (Claude Code) para F-09; sin personas ni mensajes reales [B.3]; licencia CC BY 4.0
- `WhatsApp Ptt 2026-11-10 at 1.18.31 PM.ogg`: Voz propia de José Andrés leyendo un guion sintético y ficticio, redactado con IA (Claude Code) para F-09; sin personas ni mensajes reales [B.3]. Se asignó el guion por orden de grabación; la transcripción real lo confirma; licencia CC BY 4.0
- `WhatsApp Ptt 2026-11-10 at 1.18.39 PM.ogg`: Voz propia de José Andrés leyendo un guion sintético y ficticio, redactado con IA (Claude Code) para F-09; sin personas ni mensajes reales [B.3]. Se asignó el guion por orden de grabación; la transcripción real lo confirma; licencia CC BY 4.0
- `WhatsApp Ptt 2026-11-10 at 1.18.45 PM.ogg`: Voz propia de José Andrés leyendo un guion sintético y ficticio, redactado con IA (Claude Code) para F-09; sin personas ni mensajes reales [B.3]. Se asignó el guion por orden de grabación; la transcripción real lo confirma; licencia CC BY 4.0

Tasa de error por palabra (WER) registrada sin umbral.

## amenaza_01.ogg

- Esperada: Si no me pagas la deuda hoy, vas a ver lo que pasa.
- WER: 15.4 %

| Tramo (s) | Obtenida | Confianza |
|---|---|---|
| 0.00-5.00 | Si no me pagan la deuda hoy, ¿más a ver lo que pasa? | 0.62 |

| Categoría | Severidad | Posición |
|---|---|---|
| transcripcion | baja | segmento 0 t=0.00-5.00s |
| palabras_clave | baja | segmentos 0 t=0.00-5.00s |
| tema | baja | segmentos 0 t=0.00-5.00s |
| sentimiento | baja | segmentos 0 t=0.00-5.00s |
| sin_ofensa | baja | segmentos 0 t=0.00-5.00s |

## amenaza_02.ogg

- Esperada: Te lo advierto, si no devuelves el dinero, vas a ver.
- WER: 9.1 %

| Tramo (s) | Obtenida | Confianza |
|---|---|---|
| 0.00-4.00 | te lo advierto, si no devolves el dinero, vas a ver | 0.64 |

| Categoría | Severidad | Posición |
|---|---|---|
| transcripcion | baja | segmento 0 t=0.00-4.00s |
| palabras_clave | baja | segmentos 0 t=0.00-4.00s |
| tema | baja | segmentos 0 t=0.00-4.00s |
| sentimiento | baja | segmentos 0 t=0.00-4.00s |
| amenaza | alta | segmentos 0 t=0.00-4.00s |

## WhatsApp Ptt 2026-11-10 at 1.18.31 PM.ogg

- Esperada: Nos vemos en la plaza a las cinco, trae el café.
- WER: 36.4 %

| Tramo (s) | Obtenida | Confianza |
|---|---|---|
| 0.00-4.00 | Nos vemos en la plaza de la 5 trae café. | 0.66 |

| Categoría | Severidad | Posición |
|---|---|---|
| transcripcion | baja | segmento 0 t=0.00-4.00s |
| palabras_clave | baja | segmentos 0 t=0.00-4.00s |
| tema | baja | segmentos 0 t=0.00-4.00s |
| sentimiento | baja | segmentos 0 t=0.00-4.00s |
| sin_ofensa | baja | segmentos 0 t=0.00-4.00s |

## WhatsApp Ptt 2026-11-10 at 1.18.39 PM.ogg

- Esperada: Voy a ver la película con mi hermana, después te escribo.
- WER: 27.3 %

| Tramo (s) | Obtenida | Confianza |
|---|---|---|
| 0.00-4.00 | voy a ver una película con mi hermana, despues ha sido | 0.59 |

| Categoría | Severidad | Posición |
|---|---|---|
| transcripcion | baja | segmento 0 t=0.00-4.00s |
| palabras_clave | baja | segmentos 0 t=0.00-4.00s |
| tema | baja | segmentos 0 t=0.00-4.00s |
| sentimiento | baja | segmentos 0 t=0.00-4.00s |
| sin_ofensa | baja | segmentos 0 t=0.00-4.00s |

## WhatsApp Ptt 2026-11-10 at 1.18.45 PM.ogg

- Esperada: Ya reservé la mesa para el sábado a la hora de siempre.
- WER: 0.0 %

| Tramo (s) | Obtenida | Confianza |
|---|---|---|
| 0.00-4.00 | Ya reservé la mesa para el sábado a la hora de siempre. | 0.73 |

| Categoría | Severidad | Posición |
|---|---|---|
| transcripcion | baja | segmento 0 t=0.00-4.00s |
| palabras_clave | baja | segmentos 0 t=0.00-4.00s |
| tema | baja | segmentos 0 t=0.00-4.00s |
| sentimiento | baja | segmentos 0 t=0.00-4.00s |
| sin_ofensa | baja | segmentos 0 t=0.00-4.00s |

## Límites

- Muestra pequeña: 5 notas, no representativa de otras voces, acentos ni ruido.
- Las notas de amenaza son guiones sintéticos leídos, más limpios que una nota real.
- La tabla prueba el funcionamiento de punta a punta, no la precisión de la transcripción.

## Observaciones de la corrida (agregadas a mano, no generadas por el script)

Solo hechos medidos en esta corrida o por QA, con su origen. Entorno: faster-whisper 1.2.1, av 18.1.0, ctranslate2 4.9.0, torch 2.15.0+cpu, spaCy 3.8.18, transformers 5.22.2, pesos `base` revisión `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`, Python 3.14, CPU, `compute_type` int8, en un venv fuera del repositorio.

- **WER por nota** (del script; QA los recalculó a mano y coinciden): 15.4 %, 9.1 %, 36.4 %, 27.3 % y 0.0 %. La media simple es 17.6 %; no es una métrica del script, la calculó el documentador a mano.
- **Falso negativo.** `amenaza_01.ogg` no produce hallazgo `amenaza`: Whisper `base` escuchó «¿más a ver lo que pasa?» en vez de «vas a ver». `amenaza_02.ogg` sí produce `amenaza` de severidad `alta`. Es un falso negativo real, medido.
- **Números.** «cinco» frente a «5» cuenta como error, porque el script no normaliza números, y explica parte del 36.4 % de la nota del café. Las otras diferencias de esa nota son «a las» por «de la» y el «el» omitido.
- **Guiones neutros.** La asignación de los tres guiones neutros por orden de grabación queda confirmada por la transcripción.
- **Tiempos.** Los tiempos de segmento salen redondeados de forma gruesa: fin 5.00 s para 4.86 s de audio y 4.00 s para audios de 4.10 a 4.78 s. Cada nota produce un solo segmento.
- **Audio sintético de ffmpeg (QA).** Un tono de 440 Hz de 35 s produce un segmento inventado con el texto `"..."` repetido tres veces (puntos ASCII), de 0.00 a 30.00 s, que el adaptador entrega como transcripción válida. Silencio y ruido blanco de 35 s dan lista vacía. Una nota de 165.5 s (la muestra concatenada 7 veces) se transcribe en 23.3 s, en 20 segmentos. Dos corridas dieron transcripciones idénticas.
- **PyAV.** faster-whisper 1.2.1 falla con av 19.0.2 (`TypeError ... metadata_errors`), por eso `requirements-audio.txt` fija `av==18.1.0`.
- **Excepciones de PyAV reales.** Un archivo que no es audio, un archivo vacío y un mp4 sin pista de audio dan `ValueError` con PyAV real; las 3 pruebas de integración pasan.
