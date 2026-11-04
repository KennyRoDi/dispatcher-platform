# Área: pruebas de carga y tolerancia a fallos [B.6]

Todas se ejecutan en los tres nodos reales. Prueba: **A** escenario con script `scripts/scenarios/`, por crear. La evidencia se integra en el informe con métricas, gráficos e interpretación [B.6].

### US-33 · Ráfaga (F-33) · P4 · H3
- **Responsable:** K · **Depende de:** F-08, F-09, F-20, F-24, F-38
```gherkin
Dado que hay tres nodos worker activos
Cuando se envían al menos 20 casos de forma concurrente
Entonces todos alcanzan un estado final
Y se registran throughput, latencia por caso y recursos por nodo durante la ráfaga
```
- **Pruebas:** I cliente concurrente en corto. A `scenarios/burst.py`.
- **Demuestra:** conteo de casos finales. **Evidencia:** CSV y gráficos en el informe.

### US-34 · Caída de un worker (F-34) · P4 · H3
- **Responsable:** N · **Depende de:** F-06, F-38
```gherkin
Dado un caso en proceso con una sub-tarea en un worker
Y otro worker del mismo tipo en otro nodo
Cuando se ejecuta docker kill sobre el primer worker
Entonces el sistema detecta la caída por heartbeat
Y reasigna sus sub-tareas
Y el caso termina en el estado correcto, sin sub-tareas perdidas ni contadas dos veces
```
- **Pruebas:** U recovery existente. I reaper con Redis. A `scenarios/worker_crash.py`.
- **Demuestra:** comparación de sub-tareas creadas y terminadas. **Evidencia:** tiempos de detección y reasignación.

### US-35 · Reinicio del coordinador (F-35) · P4 · H3
- **Responsable:** N · **Depende de:** F-06, F-10
```gherkin
Dado que hay casos en curso
Cuando el coordinador se reinicia
Entonces retoma desde el estado persistido
Y ninguna sub-tarea se pierde ni se duplica
Y los casos alcanzan su estado final
```
- **Pruebas:** U idempotencia y reconciliación. I reinicio con Redis real. A `scenarios/coordinator_restart.py`.
- **Demuestra:** conteo por `subtask_id`. **Evidencia:** tiempo de retoma y conteos antes y después.

### US-36 · Cancelación en curso (F-36) · P4 · H3
- **Responsable:** J · **Depende de:** F-12, F-38
```gherkin
Dado un caso pesado, con un archivo de al menos 200 MB, en procesamiento
Cuando se cancela a mitad de procesamiento
Entonces se detienen sus sub-tareas
Y no quedan procesos ni archivos temporales de esas sub-tareas
Y la memoria del worker disminuye
Y el caso queda cancelled
```
- **Pruebas:** U supervisor. I worker real. A `scenarios/cancel_heavy.py`.
- **Demuestra:** comparación de recursos. **Evidencia:** `ps`, `ls /scratch`, `memory.current` antes y después, y tiempo de liberación.

### US-37 · Saturación de memoria (F-37) · P4 · H3
- **Responsable:** J · **Depende de:** F-17, F-38
```gherkin
Dado un nodo con su control de admisión activo
Cuando llega una carga superior a su memoria disponible
Entonces los workers admiten solo lo que cabe
Y el resto queda en cola
Y el nodo no colapsa y mantiene sus heartbeats
Y todos los casos terminan cuando se libera capacidad
```
- **Pruebas:** U admisión. I worker con límite bajo. A `scenarios/memory_saturation.py`.
- **Demuestra:** continuidad de heartbeats. **Evidencia:** gráfico de memoria y sub-tareas admitidas, y comparación sin admisión si es seguro hacerla.
