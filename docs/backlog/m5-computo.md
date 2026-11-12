# Área: M5 · Cómputo heterogéneo

### US-31 · Benchmark de inferencia (F-31) · P2 · H3
- **Responsable:** J · **Depende de:** —
Como responsable de M5, quiero medir la inferencia en varias configuraciones para decidir con datos.
- **Dado** el mismo conjunto de audio
- **Cuando** corre en al menos dos configuraciones
- **Entonces** se obtienen latencia, throughput y memoria, con repeticiones
- **Pruebas:** U agregación. I corrida corta en CPU.
- **Demuestra:** benchmark. **Evidencia:** ficha M5: tabla por configuración y conexión con Unidad 1.

### US-32 · Routing por tipo de nodo (F-32) · P2 · H3
- **Responsable:** J · **Depende de:** F-31
Como coordinador, quiero asignar según la tabla medida para aprovechar cada nodo.
- **Dado** la tabla de routing y clases de nodo activas
- **Cuando** llega una sub-tarea, o el nodo preferido no está activo
- **Entonces** se dirige a la clase indicada, o a la alternativa
- **Pruebas:** U clase, alternativa y tabla inválida. I dos clases de worker.
- **Demuestra:** prueba I. **Evidencia:** ficha M5: justificación con referencia a la medición.
