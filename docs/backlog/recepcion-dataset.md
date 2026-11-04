# Área: recepción y dataset

### US-01 · Crear caso multifuente (F-01) · P1 · H1
- **Responsable:** N · **Depende de:** —
Como analista, quiero crear un caso con varias fuentes para analizarlas en conjunto.
- **Dado** un analista autenticado y fuentes de texto, imagen, audio y video
- **Cuando** crea el caso
- **Entonces** el caso queda `queued` con 4 fuentes enlazadas a sus objetos
- **Pruebas:** U `test_crear_caso_con_varias_fuentes_las_registra`. I API con Redis y MinIO. A caso heterogéneo por el cliente de carga.
- **Demuestra:** prueba A. **Evidencia:** respuesta de `GET /cases/{id}`.

### US-02 · Validar y normalizar (F-02) · P1 · H1
- **Responsable:** N · **Depende de:** F-01
Como analista, quiero que se rechacen formatos no válidos y se normalicen las exportaciones para analizar datos uniformes.
- **Dado** una exportación de WhatsApp o Telegram y un archivo no admitido
- **Cuando** se reciben
- **Entonces** la exportación produce mensajes con timestamp UTC, remitente y UTF-8, y el archivo se rechaza con error explícito
- **Pruebas:** U parsers y validador. I subida por API. A todas las conversaciones del dataset se analizan sin errores.
- **Demuestra:** prueba A. **Evidencia:** conteo de mensajes válidos frente a rechazados.

### US-03 · Dataset sintético (F-03) · P1 · H1
- **Responsable:** K · **Depende de:** —
Como equipo, queremos un dataset reproducible para probar con volumen sin usar datos de terceros.
- **Dado** el generador con una semilla
- **Cuando** se ejecuta
- **Entonces** hay ≥ 40 casos, ≥ 10 heterogéneos, ≥ 20 000 mensajes, ≥ 300 imágenes, ≥ 150 audios y ≥ 5 casos con archivos ≥ 200 MB
- **Pruebas:** U `test_generador_cumple_minimos_de_b3`. A validador sobre el dataset completo.
- **Demuestra:** validador. **Evidencia:** salida del validador en `docs/dataset.md`.

### US-04 · Verdad de referencia y procedencia (F-04) · P1 · H1
- **Responsable:** K · **Depende de:** F-03
Como evaluador, quiero conocer el origen de cada fuente y los aciertos del análisis para confiar en el dataset.
- **Dado** el manifiesto con etiquetas, procedencia y licencia
- **Cuando** se comparan las salidas con las etiquetas
- **Entonces** se reportan aciertos y errores por categoría, y una fuente sin licencia hace fallar la validación
- **Pruebas:** U comparador y validador. A comparación sobre la muestra etiquetada.
- **Demuestra:** comparador. **Evidencia:** tabla en el informe y `docs/dataset.md`.
