# Área: estados, reporte, alertas y dashboard

### US-10 · Estados y cierre (F-10) · P3 · H2
- **Responsable:** N · **Depende de:** —
Como analista, quiero un estado de caso confiable para saber cuándo terminó realmente.
- **Dado** un caso con sub-tareas exitosas y fallidas
- **Cuando** todas terminan, incluso con reportes duplicados
- **Entonces** cierra una sola vez, con el estado que corresponde; una transición no permitida se rechaza
- **Pruebas:** U transiciones, combinaciones y barrier. I reportes concurrentes con Redis. A los 7 estados se alcanzan.
- **Demuestra:** prueba I. **Evidencia:** historial de estados por caso.

### US-11 · Reintentos (F-11) · P3 · H2
- **Responsable:** N · **Depende de:** F-10
Como operador, quiero reintentos con backoff para superar fallos transitorios sin saturar.
- **Dado** una sub-tarea que falla, con máximo configurado N
- **Cuando** se reintenta
- **Entonces** las esperas crecen, el caso pasa por `retrying` y falla al llegar a N
- **Pruebas:** U `test_backoff_crece_y_respeta_maximo`. I analizador que falla N veces.
- **Demuestra:** prueba I. **Evidencia:** log con tiempos entre intentos.

### US-12 · Cancelación real (F-12) · P3 · H2
- **Responsable:** J · **Depende de:** —
Como supervisor, quiero cancelar un caso y liberar recursos para que no siga consumiendo.
- **Dado** un caso con una sub-tarea en ejecución
- **Cuando** se cancela
- **Entonces** el subproceso recibe `SIGTERM` y luego `SIGKILL`, no quedan zombies, los temporales se borran y el caso queda `cancelled`
- **Pruebas:** U supervisor con subproceso real de prueba. I worker en contenedor con `ps` y `ls /scratch`. A US-36.
- **Demuestra:** prueba I. **Evidencia:** salida de `ps` y `ls` antes y después.

### US-13 · Reporte consolidado (F-13) · P3 · H2
- **Responsable:** K · **Depende de:** —
Como analista, quiero un reporte con evidencias enlazadas para sustentar cada hallazgo.
- **Dado** un caso finalizado
- **Cuando** se consulta el reporte
- **Entonces** contiene hallazgos, categorías, línea temporal e incidencias, y cada fragmento resuelve a su fuente y timestamp
- **Pruebas:** U secciones y resolución de enlaces. I caso completo. A reporte de un caso heterogéneo.
- **Demuestra:** prueba A. **Evidencia:** JSON de ejemplo en el informe.

### US-14 · Alertas (F-14) · P5 · H3
- **Responsable:** K · **Depende de:** —
Como supervisor, quiero recibir alertas sin esperar a consultar para reaccionar a incidencias.
- **Dado** un caso con una incidencia alta
- **Cuando** se detecta y cuando el caso finaliza
- **Entonces** se publica una alerta por cada evento; si el consumidor falla, el pipeline continúa
- **Pruebas:** U publicación y aislamiento de fallo. I Stream con consumidor. A alerta visible en el dashboard.
- **Demuestra:** prueba A. **Evidencia:** marcas de tiempo de alerta y de cierre.

### US-15 · Dashboard (F-15) · P5 · H3
- **Responsable:** V · **Depende de:** F-16
Como operador, quiero ver el estado y los recursos por nodo para detectar problemas durante la operación.
- **Dado** tres nodos activos y una ráfaga
- **Cuando** abro el dashboard
- **Entonces** veo casos, sub-tareas, workers, colas, y CPU, memoria y GPU si existe, para cada nodo, actualizándose
- **Pruebas:** U lector de cgroup y heartbeat. I `GET /workers` con datos de cgroup. A demo.
- **Demuestra:** prueba A. **Evidencia:** captura junto al comando que generó la carga.
