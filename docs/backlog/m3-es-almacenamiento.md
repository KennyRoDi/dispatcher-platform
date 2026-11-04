# Área: M3 · E/S y almacenamiento

### US-22 · Chunks verificados (F-22) · P2 · H2
- **Responsable:** V · **Depende de:** F-01
Como cliente, quiero enviar archivos grandes por partes para no cargarlos completos en memoria y detectar corrupción.
- **Dado** un archivo ≥ 200 MB dividido en chunks
- **Cuando** se envía y reensambla
- **Entonces** el SHA-256 coincide; un chunk alterado se rechaza
- **Pruebas:** U reensamblado, alteración y orden. I subida real entre nodos.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: MB/s para ≥ 3 tamaños.

### US-23 · Almacenamiento por contenido (F-23) · P2 · H2
- **Responsable:** V · **Depende de:** F-22
Como operador, quiero no guardar el mismo contenido dos veces para ahorrar espacio.
- **Dado** dos fuentes con el mismo contenido
- **Cuando** se almacenan
- **Entonces** existe un solo objeto, con clave SHA-256, referenciado por ambas
- **Pruebas:** U dedup y clave. I MinIO real, con subidas concurrentes del mismo contenido.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: tasa de deduplicación.

### US-24 · Backpressure (F-24) · P2 · H2
- **Responsable:** V · **Depende de:** F-20
Como operador, quiero frenar a los productores cuando las colas se llenan para proteger el sistema.
- **Dado** una cola en su límite
- **Cuando** llega más carga
- **Entonces** la API responde 503 con `Retry-After`, el scheduler no mueve más y la profundidad no supera el límite
- **Pruebas:** U cola llena y desactivación del límite. I API y Redis con cliente de carga.
- **Demuestra:** experimento con y sin límite. **Evidencia:** ficha M3: gráfico de profundidad y respuesta.

### US-25 · Recepción no bloqueante (F-25) · P2 · H2
- **Responsable:** V · **Depende de:** F-22
Como usuario, quiero que la API responda durante subidas grandes.
- **Dado** una subida lenta en curso
- **Cuando** llega otra petición
- **Entonces** responde sin esperar a que termine la subida
- **Pruebas:** U `test_subida_lenta_no_bloquea_otra_peticion`. I subida real con `curl` paralelo de `/health`.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: tiempos de respuesta durante la subida.
