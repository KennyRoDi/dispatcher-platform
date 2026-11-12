# F-43: caso completo de punta a punta (2026-11-12)

Generado por `tests/acceptance/test_pipeline_tipado_aceptacion.py` con el coordinador real, tres workers tipados (`text`, `image`, `audio`), fakeredis, un almacén cifrado en memoria y dobles de modelo. Los hallazgos salen de dobles: este registro prueba el cableado y el cierre del caso, no la exactitud ni el rendimiento de los modelos (eso lo miden F-07, F-08 y F-09 con los modelos reales).

Caso `22f4690a-2126-4c8c-ad93-fc2be333ffb8` con cinco fuentes (texto de WhatsApp, texto de Telegram, imagen, audio y video).

Colas tras `POST /cases`: `{"queue:text": 2, "queue:image": 2, "queue:audio": 2}` (el video se expande en una sub-tarea de imagen y otra de audio).

| Sub-tarea | Fuente | Estado | Worker | Intentos |
|---|---|---|---|---|
| audio | `clip.mp4` | completed | w-audio | 1 |
| audio | `voz.mp3` | completed | w-audio | 1 |
| image | `clip.mp4` | completed | w-image | 1 |
| image | `foto.jpg` | completed | w-image | 1 |
| text | `chat.json` | completed | w-text | 1 |
| text | `nota.txt` | completed | w-text | 1 |

Sub-tareas procesadas: 6. Estado final del caso: `completed`.
Hallazgos en `case:{id}:findings`: 23 (amenaza: 1, arma: 3, ofensivo: 1, palabras_clave: 4, sentimiento: 4, sin_ofensa: 2, tema: 4, transcripcion: 4).
Alertas en orden de emisión: incidencia_alta, incidencia_alta, incidencia_alta, incidencia_alta, caso_finalizado.
Reporte consolidado: 23 hallazgos, 8 categorías, 2 eventos en la línea temporal, 4 incidencias.
