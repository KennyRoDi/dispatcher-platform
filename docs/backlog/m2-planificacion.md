# Área: M2 · Planificación

### US-20 · Prioridades con aging (F-20) · P2 · H2
- **Responsable:** N · **Depende de:** F-06
Como analista, quiero que los casos críticos pasen primero sin bloquear los de baja prioridad.
- **Dado** un flujo continuo de casos altos y un caso bajo en espera
- **Cuando** corre el scheduler
- **Entonces** los altos recientes tienen preferencia, pero el bajo se despacha dentro del límite derivado de sus bonos
- **Pruebas:** U orden, inanición con reloj simulado y prioridad inválida. I con Redis.
- **Demuestra:** prueba U de inanición y medición. **Evidencia:** ficha M2: espera máxima por nivel.

### US-21 · Comparación de políticas (F-21) · P2 · H2
- **Responsable:** N · **Depende de:** F-20
Como responsable de M2, quiero cambiar de política por configuración para compararlas bajo la misma carga.
- **Dado** la misma carga con semilla fija
- **Cuando** se ejecuta con FIFO y con aging
- **Entonces** se obtienen espera, turnaround y throughput por nivel y política
- **Pruebas:** U `test_fifo_ignora_prioridad`. I corrida corta por política.
- **Demuestra:** experimento. **Evidencia:** ficha M2: tablas y gráficos.
