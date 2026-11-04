# Área: cola y workers

### US-05 · Descomponer y enrutar (F-05) · P1 · H1
- **Responsable:** N · **Depende de:** F-01
Como coordinador, quiero separar un caso en sub-tareas por tipo para enviarlas a workers especializados.
- **Dado** un caso con texto, imagen, audio y video
- **Cuando** se descompone
- **Entonces** cada sub-tarea llega a la cola de su tipo; el video genera sub-tareas de audio e imagen
- **Pruebas:** U descomposición y mapa de colas. I `fakeredis`. A worker de cada tipo consume solo lo suyo.
- **Demuestra:** prueba A. **Evidencia:** log de routing.

### US-06 · Cola confiable (F-06) · P1 · H1
- **Responsable:** N · **Depende de:** —
Como coordinador, quiero que ninguna sub-tarea se pierda si un worker muere al tomarla.
- **Dado** un worker que toma una sub-tarea
- **Cuando** muere justo después de sacarla
- **Entonces** la sub-tarea sigue en `inflight:{worker}` y el reaper la reencola
- **Pruebas:** U `test_muerte_tras_blmove_deja_subtarea_en_inflight`. I reaper con Redis real.
- **Demuestra:** prueba I. **Evidencia:** entrada en `docs/reutilizacion.md` con la limitación corregida.

### US-07 · Worker de texto (F-07) · P1 · H1
- **Responsable:** J · **Depende de:** F-05
Como analista, quiero palabras clave, tema, sentimiento y lenguaje ofensivo o amenazas para encontrar conversaciones relevantes.
- **Dado** una conversación etiquetada
- **Cuando** se procesa
- **Entonces** cada lote produce las cuatro salidas con referencia a sus mensajes
- **Pruebas:** U con analizador falso. I con modelo real sobre muestra. A aciertos contra verdad de referencia.
- **Demuestra:** prueba A. **Evidencia:** tabla de aciertos.

### US-08 · Worker de imagen (F-08) · P1 · H1
- **Responsable:** J · **Depende de:** F-05
Como analista, quiero detectar contenido sensible en imágenes para incluirlo como hallazgo.
- **Dado** una imagen con contenido positivo conocido
- **Cuando** se procesa
- **Entonces** se reportan categoría y confianza
- **Pruebas:** U con detector falso. I con modelo real. A aciertos sobre muestra etiquetada.
- **Demuestra:** prueba A. **Evidencia:** tabla de aciertos.

### US-09 · Worker de audio (F-09) · P1 · H1
- **Responsable:** J · **Depende de:** F-07
Como analista, quiero transcribir y analizar notas de voz para tratarlas como texto con timestamps.
- **Dado** una nota de voz con transcripción conocida
- **Cuando** se procesa
- **Entonces** se obtiene la transcripción con timestamps y el análisis de US-07
- **Pruebas:** U composición. I con modelo real. A comparación con la transcripción esperada.
- **Demuestra:** prueba A. **Evidencia:** muestra en el informe.
