**Resumen:** 42 historias de usuario, una por funcionalidad, con criterios Dado/Cuando/Entonces, prioridad numérica, pruebas asociadas y evidencia esperada.

# Backlog

## Prioridad

Todos los requisitos son obligatorios [B.10], por lo que MoSCoW los dejaría a todos en «Must» y no ayudaría a decidir. Se usa una prioridad numérica, justificada por hito y dependencias.

| P | Criterio | Hito | Justificación |
|---|---|---|---|
| 1 | Sin esto no se puede medir ni demostrar nada | H1 | Los tres nodos, el dataset y los workers son prerrequisito de M1 a M5 y de B.6 |
| 2 | Módulo con 8 % de la nota, con tope de 2 si no tiene ficha medida [Parte I §5] | H2, H3 | M1 a M5 suman 40 % [B.9] |
| 3 | Pipeline y estados que exige la rúbrica | H2 | Parte del 15 % de pipeline; además los usa B.6 |
| 4 | Escenarios B.6 | H3 | 10 % [B.9]; dependen de P1 a P3 |
| 5 | Vistas sobre datos ya disponibles | H3 | Menor coste y menor peso individual |

Las historias de entrega (US-38 a US-42) toman P1 o P2 según lo que bloquean: los rubros comunes suman 35 % [Parte I §8].

Pruebas: **U** unitaria, **I** integración, **A** aceptación.

El estado de cada funcionalidad está en [STATUS.md](STATUS.md). Responsables propuestos: K Kenni Rodriguez, N Nahúm Murillo, J José Andrés Loría Herrera (SUP-01).

## Área: recepción y dataset

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

## Área: cola y workers

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

## Área: estados, reporte, alertas y dashboard

### US-10 · Estados y cierre (F-10) · P3 · H2
- **Responsable:** N · **Depende de:** F-05
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
- **Responsable:** J · **Depende de:** F-06
Como supervisor, quiero cancelar un caso y liberar recursos para que no siga consumiendo.
- **Dado** un caso con una sub-tarea en ejecución
- **Cuando** se cancela
- **Entonces** el subproceso recibe `SIGTERM` y luego `SIGKILL`, no quedan zombies, los temporales se borran y el caso queda `cancelled`
- **Pruebas:** U supervisor con subproceso real de prueba. I worker en contenedor con `ps` y `ls /scratch`. A US-36.
- **Demuestra:** prueba I. **Evidencia:** salida de `ps` y `ls` antes y después.

### US-13 · Reporte consolidado (F-13) · P3 · H2
- **Responsable:** K · **Depende de:** F-07, F-10
Como analista, quiero un reporte con evidencias enlazadas para sustentar cada hallazgo.
- **Dado** un caso finalizado
- **Cuando** se consulta el reporte
- **Entonces** contiene hallazgos, categorías, línea temporal e incidencias, y cada fragmento resuelve a su fuente y timestamp
- **Pruebas:** U secciones y resolución de enlaces. I caso completo. A reporte de un caso heterogéneo.
- **Demuestra:** prueba A. **Evidencia:** JSON de ejemplo en el informe.

### US-14 · Alertas (F-14) · P5 · H3
- **Responsable:** K · **Depende de:** F-10
Como supervisor, quiero recibir alertas sin esperar a consultar para reaccionar a incidencias.
- **Dado** un caso con una incidencia alta
- **Cuando** se detecta y cuando el caso finaliza
- **Entonces** se publica una alerta por cada evento; si el consumidor falla, el pipeline continúa
- **Pruebas:** U publicación y aislamiento de fallo. I Stream con consumidor. A alerta visible en el dashboard.
- **Demuestra:** prueba A. **Evidencia:** marcas de tiempo de alerta y de cierre.

### US-15 · Dashboard (F-15) · P5 · H3
- **Responsable:** K · **Depende de:** F-16
Como operador, quiero ver el estado y los recursos por nodo para detectar problemas durante la operación.
- **Dado** tres nodos activos y una ráfaga
- **Cuando** abro el dashboard
- **Entonces** veo casos, sub-tareas, workers, colas, y CPU, memoria y GPU si existe, para cada nodo, actualizándose
- **Pruebas:** U lector de cgroup y heartbeat. I `GET /workers` con datos de cgroup. A demo.
- **Demuestra:** prueba A. **Evidencia:** captura junto al comando que generó la carga.

## Área: M1 · Memoria

### US-16 · Límites por worker (F-16) · P2 · H2
- **Responsable:** J · **Depende de:** —
Como operador, quiero un límite por worker para que ninguno afecte al nodo.
- **Dado** el Compose de un nodo
- **Cuando** arranca
- **Entonces** `memory.max` tiene el límite configurado, y el preflight rechaza si la suma supera la RAM disponible
- **Pruebas:** U `test_preflight_rechaza_suma_de_limites_mayor_a_ram`. I lectura de `memory.max` en cada contenedor.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: valores por worker.

### US-17 · Control de admisión (F-17) · P2 · H2
- **Responsable:** J · **Depende de:** F-16
Como operador, quiero admitir solo lo que cabe en memoria para evitar terminaciones por OOM.
- **Dado** un worker sin memoria para otra sub-tarea según la huella medida
- **Cuando** hay trabajo en cola
- **Entonces** no la saca de la cola y otro nodo con capacidad puede tomarla
- **Pruebas:** U `test_rechaza_si_no_cabe_huella_con_margen`. I worker con límite bajo y dos sub-tareas. A US-37.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: tabla de huella y gráfico de memoria por worker.

### US-18 · Detección de OOM (F-18) · P2 · H2
- **Responsable:** J · **Depende de:** F-12, F-16
Como operador, quiero distinguir un OOM de otros fallos para aplicar la política correcta.
- **Dado** una sub-tarea que excede el límite
- **Cuando** el kernel termina el subproceso
- **Entonces** queda registrada con causa `oom` y se reencola con más reserva, hasta el máximo de la política; el supervisor sigue activo
- **Pruebas:** U `classify_exit`, `OomPolicy`. I OOM real con un asignador de memoria en contenedor.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: `memory.events` y recuperación.

### US-19 · Estrategias de carga (F-19) · P2 · H2
- **Responsable:** J · **Depende de:** F-09
Como responsable de M1, quiero ejecutar ambas estrategias para justificar la elegida con datos.
- **Dado** el parámetro de estrategia
- **Cuando** se inicia con N procesos en cada variante
- **Entonces** ambas producen el mismo resultado y se obtiene su memoria total
- **Pruebas:** U selección. I igualdad de salidas en ambas variantes.
- **Demuestra:** comparación de PSS. **Evidencia:** ficha M1: tabla comparativa y decisión AD-07.

## Área: M2 · Planificación

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

## Área: M3 · E/S y almacenamiento

### US-22 · Chunks verificados (F-22) · P2 · H2
- **Responsable:** N · **Depende de:** F-01
Como cliente, quiero enviar archivos grandes por partes para no cargarlos completos en memoria y detectar corrupción.
- **Dado** un archivo ≥ 200 MB dividido en chunks
- **Cuando** se envía y reensambla
- **Entonces** el SHA-256 coincide; un chunk alterado se rechaza
- **Pruebas:** U reensamblado, alteración y orden. I subida real entre nodos.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: MB/s para ≥ 3 tamaños.

### US-23 · Almacenamiento por contenido (F-23) · P2 · H2
- **Responsable:** N · **Depende de:** F-22
Como operador, quiero no guardar el mismo contenido dos veces para ahorrar espacio.
- **Dado** dos fuentes con el mismo contenido
- **Cuando** se almacenan
- **Entonces** existe un solo objeto, con clave SHA-256, referenciado por ambas
- **Pruebas:** U dedup y clave. I MinIO real, con subidas concurrentes del mismo contenido.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: tasa de deduplicación.

### US-24 · Backpressure (F-24) · P2 · H2
- **Responsable:** N · **Depende de:** F-20
Como operador, quiero frenar a los productores cuando las colas se llenan para proteger el sistema.
- **Dado** una cola en su límite
- **Cuando** llega más carga
- **Entonces** la API responde 503 con `Retry-After`, el scheduler no mueve más y la profundidad no supera el límite
- **Pruebas:** U cola llena y desactivación del límite. I API y Redis con cliente de carga.
- **Demuestra:** experimento con y sin límite. **Evidencia:** ficha M3: gráfico de profundidad y respuesta.

### US-25 · Recepción no bloqueante (F-25) · P2 · H2
- **Responsable:** N · **Depende de:** F-22
Como usuario, quiero que la API responda durante subidas grandes.
- **Dado** una subida lenta en curso
- **Cuando** llega otra petición
- **Entonces** responde sin esperar a que termine la subida
- **Pruebas:** U `test_subida_lenta_no_bloquea_otra_peticion`. I subida real con `curl` paralelo de `/health`.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: tiempos de respuesta durante la subida.

## Área: M4 · Seguridad

### US-26 · Autenticación y roles (F-26) · P2 · H3
- **Responsable:** K · **Depende de:** F-01
Como administrador, quiero que cada rol solo haga lo permitido para proteger la información.
- **Dado** usuarios analista, supervisor y administrador
- **Cuando** cada uno intenta cada acción, o no presenta token
- **Entonces** se cumple la matriz de permisos, con 401 sin token y 403 sin permiso
- **Pruebas:** U matriz paramétrica. I API con JWT real. A accesos denegados en demo.
- **Demuestra:** prueba I. **Evidencia:** ficha M4: `curl` y códigos por rol.

### US-27 · TLS entre nodos (F-27) · P2 · H3
- **Responsable:** K · **Depende de:** F-38
Como responsable de seguridad, quiero cifrar la comunicación entre nodos para que no pueda leerse en la red.
- **Dado** el sistema procesando un mensaje con un marcador sintético
- **Cuando** se captura el tráfico entre nodos
- **Entonces** hay handshake TLS y el marcador no aparece en la captura; un cliente sin la CA es rechazado
- **Pruebas:** I cliente sin CA falla; conexión sin TLS a Redis falla. A captura real.
- **Demuestra:** captura. **Evidencia:** ficha M4: `tcpdump`, `tshark`, `strings`.

### US-28 · Cifrado en reposo (F-28) · P2 · H3
- **Responsable:** K · **Depende de:** F-23
Como responsable de seguridad, quiero las evidencias cifradas y las llaves fuera del código para proteger el almacenamiento.
- **Dado** una evidencia almacenada con un marcador sintético
- **Cuando** se lee directo de MinIO, o se busca en el historial de Git
- **Entonces** no contiene el marcador, un byte alterado hace fallar el descifrado, falla sin KEK y no hay llaves en el historial
- **Pruebas:** U ida y vuelta, alteración, nonce y falta de KEK. I objeto real en MinIO.
- **Demuestra:** prueba I y búsqueda en historial. **Evidencia:** ficha M4: comandos y justificación de AD-16.

### US-29 · Cadena de custodia (F-29) · P2 · H3
- **Responsable:** K · **Depende de:** F-23
Como supervisor, quiero una cadena verificable para demostrar que las evidencias no se alteraron.
- **Dado** evidencias procesadas, con entrada de ingreso y de cada transformación
- **Cuando** se altera una evidencia, una entrada, o se trunca el log
- **Entonces** el verificador falla e indica la posición; sin alteraciones, pasa
- **Pruebas:** U enlace, alteración, truncamiento y evidencia alterada. A manipulación real en demo.
- **Demuestra:** prueba A. **Evidencia:** ficha M4: salida del verificador antes y después.

### US-30 · Workers sin privilegios (F-30) · P2 · H3
- **Responsable:** K · **Depende de:** F-38
Como responsable de seguridad, quiero workers sin root para limitar el daño de un compromiso.
- **Dado** los workers desplegados en los tres nodos
- **Cuando** se inspeccionan
- **Entonces** su UID es distinto de 0, la raíz es de solo lectura, se eliminan capacidades y procesan normalmente
- **Pruebas:** I `id -u` y escritura fallida en `/`. A sub-tarea completada bajo esa configuración.
- **Demuestra:** prueba I. **Evidencia:** ficha M4: `docker exec` e `inspect`.

## Área: M5 · Cómputo heterogéneo

### US-31 · Benchmark de inferencia (F-31) · P2 · H3
- **Responsable:** J · **Depende de:** F-09
Como responsable de M5, quiero medir la inferencia en varias configuraciones para decidir con datos.
- **Dado** el mismo conjunto de audio
- **Cuando** corre en al menos dos configuraciones
- **Entonces** se obtienen latencia, throughput y memoria, con repeticiones
- **Pruebas:** U agregación. I corrida corta en CPU.
- **Demuestra:** benchmark. **Evidencia:** ficha M5: tabla por configuración y conexión con Unidad 1.

### US-32 · Routing por tipo de nodo (F-32) · P2 · H3
- **Responsable:** J · **Depende de:** F-05, F-31
Como coordinador, quiero asignar según la tabla medida para aprovechar cada nodo.
- **Dado** la tabla de routing y clases de nodo activas
- **Cuando** llega una sub-tarea, o el nodo preferido no está activo
- **Entonces** se dirige a la clase indicada, o a la alternativa
- **Pruebas:** U clase, alternativa y tabla inválida. I dos clases de worker.
- **Demuestra:** prueba I. **Evidencia:** ficha M5: justificación con referencia a la medición.

## Área: pruebas de carga y tolerancia a fallos [B.6]

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

## Área: entrega y proceso

### US-38 · Despliegue en tres nodos (F-38) · P1 · H1
- **Responsable:** K · **Depende de:** —
Como equipo, queremos desplegar en tres máquinas para cumplir la distribución real.
- **Dado** tres máquinas en red con Docker
- **Cuando** se siguen las instrucciones y se levanta el Compose de cada nodo
- **Entonces** tres `hostname` distintos aparecen como workers activos y procesan sub-tareas
- **Pruebas:** I `scripts/check_connectivity.py` existente. A corrida con reparto por nodo.
- **Demuestra:** tabla de sub-tareas por `hostname`. **Evidencia:** log de `GET /workers` e IP por nodo.

### US-39 · Reutilización y correcciones (F-39) · P1 · H1
- **Responsable:** N · **Depende de:** —
Como evaluador, quiero saber qué es reutilizado y qué es nuevo para evaluar lo nuevo.
- **Dado** el repositorio del I Proyecto
- **Cuando** se revisa `docs/reutilizacion.md`
- **Entonces** cada componente aparece como reutilizado, modificado o nuevo, con ruta, y cada deficiencia tiene corrección enlazada
- **Pruebas:** A revisión contra `ARQUITECTURA.md` §1.
- **Demuestra:** el documento. **Evidencia:** `docs/reutilizacion.md`.

### US-40 · Matriz, historial y bitácora (F-40) · P1 · H1
- **Responsable:** K · **Depende de:** —
Como evaluador, quiero ver responsabilidades, proceso y uso de IA para valorar la contribución individual.
- **Dado** el repositorio
- **Cuando** se revisan la matriz, el historial y la bitácora
- **Entonces** cada módulo tiene responsable, cada integrante tiene al menos un módulo y commits propios, hay entradas por módulo y ≥ 2 errores reales de la IA documentados
- **Pruebas:** A `git shortlog -sn --all`; revisión contra Anexos 1 y 3.
- **Demuestra:** comandos y documentos. **Evidencia:** `docs/responsabilidades.md`, `docs/bitacora_ia.md`.

### US-41 · Fichas de evidencia (F-41) · P2 · H3
- **Responsable:** Cada responsable · **Depende de:** F-19, F-21, F-25, F-29, F-30, F-32
Como evaluador, quiero fichas con datos medidos para calificar cada módulo.
- **Dado** los cinco módulos
- **Cuando** se revisa cada ficha
- **Entonces** tiene los cinco elementos, con comandos exactos, resultados, interpretación y referencia bibliográfica
- **Pruebas:** A lista de comprobación contra RNF-09 a RNF-14; repetir un comando por ficha en otra máquina.
- **Demuestra:** comprobación. **Evidencia:** `docs/modulo-M1-memoria.md`, `docs/modulo-M2-planificacion.md`, `docs/modulo-M3-es-almacenamiento.md`, `docs/modulo-M4-seguridad.md`, `docs/modulo-M5-computo.md`.

### US-42 · Informe, README, demo y defensa (F-42) · P1 · H3
- **Responsable:** Todos, coordina K · **Depende de:** F-33, F-34, F-35, F-36, F-37, F-41
Como evaluador, quiero el informe y una demo real para verificar el sistema y la comprensión de cada integrante.
- **Dado** el sistema en los tres nodos
- **Cuando** se presenta
- **Entonces** el PDF tiene ≤ 20 páginas sin anexos e integra B.6; la demo es en vivo; cada responsable explica y modifica su componente
- **Pruebas:** A ensayo completo de la demo y simulacro cruzado de preguntas.
- **Demuestra:** ensayo. **Evidencia:** informe PDF y README con mapa del repositorio.

## Cobertura de hitos

| Hito | Historias |
|---|---|
| H1 | US-01 a US-09, US-38, US-39, US-40 |
| H2 | US-10 a US-13, US-16 a US-25 |
| H3 | US-14, US-15, US-26 a US-37, US-41, US-42 |
