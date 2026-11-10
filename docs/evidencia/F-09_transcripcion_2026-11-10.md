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
