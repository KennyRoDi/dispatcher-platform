**Resumen:** Arquitectura ADD de un proyecto independiente que reutiliza código del I Proyecto (FastAPI, Redis, MinIO, workers *pull*), con límites de memoria, planificación con aging, E/S por chunks, seguridad y routing medido, en tres nodos worker.

# Arquitectura

Requisitos en `REQUERIMIENTOS.md`. **Ningún dato de rendimiento de este sistema se ha medido todavía.** Donde una decisión depende de una medición, se indica «Medición pendiente» y la ficha que la producirá. Toda decisión de ese tipo es provisional hasta tener el dato.

## 1. Código reutilizado del I Proyecto

Este proyecto es independiente: se justifica por su enunciado y reutiliza código porque [B.2] lo motiva. La tabla indica qué se toma y qué no. Origen: repositorio `nahum0804/distributed-processing-platform`, commit `bc6bab6` de `main`. Las limitaciones provienen de su `docs/DECISIONES_DISENO.md`.

| Elemento | Estado en el I Proyecto | Acción | Requisito |
|---|---|---|---|
| Coordinador FastAPI sin estado propio | Funciona; estado en Redis | Reutilizar y extender | RF-01, RF-44 |
| Barrier/join idempotente (`SADD`) | Funciona | Reutilizar | RF-10 |
| Heartbeat y reaper | Reencola en ~25 s (declarado, sin logs en `docs/evidencia/`) | Reutilizar y volver a medir | RF-43 |
| Consumo `BLPOP` + `WATCH/MULTI` | Ventana de pérdida de milisegundos | Modificar | RF-44, RNF-03 |
| Prioridad estricta `:high` | Admite inanición | Reemplazar | RF-29 |
| Cancelación | No detiene FFmpeg en curso | Reemplazar | RF-12 |
| Workers | Solo FFmpeg, sin modelos ni texto | Nuevo | RF-06 a RF-08 |
| Límites de memoria | No existen | Nuevo | RF-24 |
| TLS, autenticación | No existen; MinIO con credencial por defecto | Nuevo | RF-35, RF-36 |
| Dashboard Streamlit | Funciona | Reutilizar y extender | RF-17 |
| Evidencia en 3 máquinas | Pendiente; se probó en una sola | Obligatorio | RNF-01 |

## 2. Escenarios de atributos de calidad

| ID | Atributo | Estímulo | Entorno | Respuesta | Medida | Req. |
|---|---|---|---|---|---|---|
| QA-01 | Memoria por worker | Ráfaga que supera la capacidad de un worker | Nodo real con `memory.max` | Se admite lo que cabe; el resto espera en cola | `memory.current` por worker a lo largo del tiempo; sub-tareas admitidas contra rechazadas | M1 |
| QA-02 | Recuperación de OOM | Sub-tarea que excede el límite | Worker con límite reducido | Se detecta, se clasifica como `oom` y se reencola según la política | `oom_kill` en `memory.events`; estado final; tiempo de recuperación | M1 |
| QA-03 | Equidad sin inanición | Flujo sostenido de casos altos con casos bajos en espera | Scheduler con FIFO y con aging | Los casos bajos avanzan aunque siga llegando carga alta | Espera, turnaround y throughput por nivel; espera máxima de prioridad baja acotada | M2 |
| QA-04 | Throughput de E/S | Transferencia ≥ 200 MB | Red real entre nodos | Reensamblado correcto y verificado | MB/s para ≥ 3 tamaños de chunk; coincidencia de SHA-256 | M3 |
| QA-05 | Backpressure | Productores más rápidos que los consumidores | Ráfaga, con y sin límite | Se rechaza o bloquea al productor; la cola no crece sin límite | Profundidad de cola y tiempos de respuesta en el tiempo | M3 |
| QA-06 | Confidencialidad | Captura de tráfico o lectura directa del almacenamiento | Operación normal | Tráfico y objetos ilegibles sin llave | `tshark` muestra TLS; el objeto no contiene el texto original | M4 |
| QA-07 | Integridad de custodia | Alteración de una evidencia o de una entrada del log | Sistema detenido o activo | El verificador falla e indica la posición | Detección en cada manipulación probada | M4 |
| QA-08 | Control de acceso | Acción no permitida por el rol | API activa | Se deniega y se registra | 401 y 403 esperados por rol y acción | M4 |
| QA-09 | Routing por tipo de nodo | Sub-tarea de inferencia con nodos heterogéneos | Benchmarks completos | Se despacha según la tabla medida; hay alternativa si no hay nodo preferido | Latencia, throughput y memoria por configuración; decisión trazable | M5 |
| QA-10 | Rendimiento bajo ráfaga | ≥ 20 casos concurrentes | Tres nodos | Todos los casos alcanzan estado final | Throughput, latencia por caso, recursos por nodo | B.6 |
| QA-11 | Tolerancia a caída de worker | `docker kill` durante un caso | Tres nodos | Detección, reasignación y estado final correcto | Tiempo de detección y de reasignación; conteo de sub-tareas | B.6 |
| QA-12 | Recuperación del coordinador | Reinicio con casos en curso | Tres nodos | Continúa desde el estado persistido | Sub-tareas sin perder ni duplicar; tiempo de retoma | B.6 |
| QA-13 | Liberación de recursos | Cancelar un caso pesado en curso | Worker con sub-tarea activa | Mata procesos y libera memoria y temporales | Procesos, memoria y temporales antes y después; tiempo de liberación | B.6 |
| QA-14 | Estabilidad bajo saturación | Carga mayor que la memoria del nodo | Nodo con control de admisión | El nodo sigue operando | Heartbeats continuos; sin OOM del host | B.6, M1 |

## 3. Tácticas por atributo

| Atributo | Tácticas | Decisión |
|---|---|---|
| Memoria | cgroups v2 por contenedor; sin swap; control de admisión con huella medida; reencolado por OOM | AD-05, AD-06, AD-07 |
| Equidad | Prioridad con aging implícito; scheduler como política intercambiable | AD-04 |
| Rendimiento de E/S | Chunks de tamaño medido; almacenamiento por contenido; recepción no bloqueante | AD-10, AD-11, AD-13 |
| Disponibilidad | Colas acotadas; rechazo con `Retry-After`; heartbeat y reaper; idempotencia | AD-03, AD-12 |
| Recuperación | Coordinador sin estado; estado en Redis con AOF, que actúa como checkpoint; reconciliación al arrancar | AD-21 |
| Liberación de recursos | Sub-tarea en subproceso propio; señal a su grupo de procesos; temporales propiedad del supervisor | AD-08, AD-09 |
| Seguridad | TLS con CA privada; cifrado de sobre; log encadenado; JWT con roles; contenedores sin privilegios | AD-14 a AD-17 |
| Heterogeneidad | Routing por tabla derivada de benchmarks; alternativa si falta el nodo preferido | AD-18 |

## 4. Capas (Clean Architecture)

Las dependencias apuntan hacia el dominio. El dominio no importa `redis`, `fastapi`, `minio` ni modelos. Una prueba analiza los `import` para hacer cumplir esta regla.

```mermaid
flowchart TB
    INF["Infraestructura: uvicorn, Docker Compose, Redis, MinIO, cgroups, certificados"]
    ADP["Adaptadores: API REST, colas Redis, almacén MinIO, analizadores, parsers, Streamlit"]
    APP["Aplicación: casos de uso y puertos"]
    DOM["Dominio: estados, planificación, admisión, reintentos, custodia, RBAC"]
    INF --> ADP --> APP --> DOM
```

| Capa | Ruta | Contenido |
|---|---|---|
| Dominio | `src/domain/` | `case_state`, `scheduling`, `admission`, `retry`, `oom_policy`, `routing`, `custody_chain`, `rbac`, `severity`, `chat_message`, `text_analysis`, `image_detection`, `transcription` |
| Aplicación | `src/application/` | `create_case`, `dispatch_next`, `report_result`, `cancel_case`, `build_report`, `verify_custody`, `analyze_text`, `analyze_image`, `analyze_audio`, `ports` |
| Adaptadores | `src/adapters/` | `api/`, `redis_queue`, `redis_case_repository`, `minio_object_store`, `whatsapp_parser`, `telegram_parser`, `text_analyzer`, `spacy_hf_text_models`, `image_analyzer`, `yolo_detector`, `hashing`, `audio_analyzer`, `whisper_transcriber`, `ffmpeg_media` |
| Infraestructura | `src/infrastructure/`, `deploy/` | Composición, configuración, lectura de cgroups, TLS, Compose por nodo |

**Contratos compartidos.** Ver [CONTRATOS.md](CONTRATOS.md): definen cada punto de contacto entre módulos, con dobles en `tests/dobles.py` y pruebas de conformidad en `tests/contratos.py`.

**Coordinador.** `src/coordinator/` se divide en `rutas_casos`, `rutas_subtareas`, `rutas_monitoreo`, `modelos`, `conexion` y `apoyo`; `main.py` solo compone la aplicación.

**Código reutilizado.** No se reescribe en bloque, porque hay poco tiempo y sus pruebas son la red de seguridad. La lógica nueva nace en `domain` y `application`; el código reutilizado se mueve a `adapters` solo cuando se toca.

## 5. Diagrama de componentes

```mermaid
flowchart LR
    CL["Cliente de carga"] -->|"HTTPS: chunks"| API
    UI["Dashboard Streamlit"] -->|"HTTPS"| API
    subgraph COORD["Coordinador"]
        API["API REST con JWT"]
        SCH["Scheduler y política"]
        RCV["Barrier y estados"]
        REP["Reportes"]
        CUS["Custodia"]
        ALR["Alertas"]
    end
    REA["Reaper"]
    API --> SCH
    SCH -->|"TLS: cola acotada"| RED[("Redis con AOF")]
    RCV --> RED
    REA --> RED
    ALR -->|"Stream"| RED
    API -->|"TLS: objetos cifrados"| MIN[("MinIO")]
    CUS --> LOG[("Log encadenado")]
    subgraph WRK["Worker: texto, imagen o audio"]
        SUP["Supervisor: admisión, heartbeat, señales"]
        CHD["Subproceso de análisis"]
        SUP -->|"fork y señales"| CHD
    end
    RED -->|"BLMOVE"| SUP
    SUP -->|"HTTPS: resultado y hash"| API
    CHD -->|"TLS"| MIN
```

## 6. Diagrama de despliegue

```mermaid
flowchart TB
    subgraph A["Nodo A: Linux, sin workers"]
        A1["Coordinador 8443 + Reaper"]
        A2["Redis 6380 TLS"]
        A3["MinIO 9000 TLS"]
        A4["Log de custodia + Dashboard"]
    end
    subgraph B["Nodo B: Windows 11, Docker Desktop sobre WSL2"]
        B1["Workers: texto, imagen, audio"]
    end
    subgraph C["Nodo C: Windows 11, con GPU si existe"]
        C1["Workers: texto, imagen, audio con GPU"]
    end
    subgraph D["Nodo D: Windows 11, Docker Desktop sobre WSL2"]
        D1["Workers: texto, imagen, audio"]
    end
    B1 -->|"TLS"| A1
    B1 -->|"TLS"| A2
    B1 -->|"TLS"| A3
    C1 -->|"TLS"| A1
    C1 -->|"TLS"| A2
    C1 -->|"TLS"| A3
    D1 -->|"TLS"| A1
    D1 -->|"TLS"| A2
    D1 -->|"TLS"| A3
```

Restricciones de despliegue:

- Cada contenedor worker tiene `mem_limit` igual a `memswap_limit`, de modo que el límite no se evade con swap.
- La suma de límites de un nodo no supera su RAM menos una reserva. Un script lo comprueba antes del arranque.
- **Cada tipo de worker debe existir en al menos dos nodos.** Sin eso, la caída de un worker no tiene a quién reasignar sus sub-tareas [B.6].
- El Nodo A concentra servicios. Es un punto único de falla aceptado: [B.6] solo exige reiniciar el coordinador, no alta disponibilidad.
- Las cuatro máquinas se comunican por Tailscale. **Tailscale no sustituye a TLS:** RF-36 exige una captura entre nodos que muestre TLS. Las flechas y los puertos del diagrama son el estado final, tras F-27.
- Los tres nodos worker operan con Docker Desktop sobre WSL2. Sus cgroups son los de la VM de WSL2. **Como ningún worker corre en un nodo Linux, la ficha M1 declara que los cgroups medidos son los de la VM de WSL2.** El Nodo A no ejecuta workers, tampoco para M1. Sin comprobar: que esa VM exponga cgroups v2, que es lo que suponen RF-24 y los comandos de medición de M1.

## 7. Flujo de un caso

```mermaid
sequenceDiagram
    actor U as Analista
    participant API as Coordinador
    participant ST as MinIO
    participant R as Redis
    participant W as Worker
    participant C as Custodia
    U->>API: Crear caso con prioridad (JWT)
    U->>API: Enviar chunks con hash
    API->>API: Verificar hash, normalizar y validar
    API->>ST: Guardar objeto cifrado por SHA-256
    API->>C: Anexar entrada de ingreso
    API->>R: Crear sub-tareas en ZSET por tipo
    API->>R: Mover a cola acotada según la política
    W->>W: Verificar admisión de memoria
    W->>R: BLMOVE de la cola a inflight
    W->>ST: Leer y descifrar en temporal
    W->>W: Analizar en subproceso
    W->>API: Reportar resultado y hash
    API->>C: Anexar entrada de transformación
    API->>R: SADD idempotente y decrementar pendientes
    alt Pendientes en cero
        API->>R: Cerrar caso y publicar alerta
        U->>API: Consultar reporte con evidencias
    end
```

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> processing
    queued --> cancelled
    processing --> retrying
    retrying --> processing
    processing --> completed
    processing --> partially_completed
    processing --> failed
    retrying --> partially_completed
    retrying --> failed
    processing --> cancelled
    retrying --> cancelled
    completed --> [*]
    partially_completed --> [*]
    failed --> [*]
    cancelled --> [*]
```

## 8. Registro de decisiones

«Fuente» distingue referencia consultable de medición. Referencias en §10.

| ID | Decisión | Alternativas | Criterio de elección | Fuente |
|---|---|---|---|---|
| AD-01 | Reutilizar código del I Proyecto donde sirva, en un proyecto independiente | Escribir todo desde cero | [B.2] motiva reutilizar y evalúa lo nuevo; tiempo disponible | Medición del repo: 18 archivos, 387 funciones de prueba, 474 casos pasan y 3 se omiten |
| AD-02 | Cuatro máquinas físicas en Tailscale: servicios en el Nodo A y tres nodos worker | Tres máquinas con servicios y workers juntos en el Nodo A; VMs en un solo equipo; red local | [B.2] exige tres nodos worker en entidades separadas, de preferencia una computadora por integrante, y rechaza una sola máquina. El equipo tiene cuatro. Tailscale conecta máquinas que no compartan red local | [B.2]; SUP-04 |
| AD-03 | Redis con `BLMOVE` a lista `inflight:{worker}` | Redis Streams; RabbitMQ | Cierra la ventana de pérdida con el menor cambio; conserva `recovery.py` y reaper | R1; limitación declarada del I Proyecto. Entrega al menos una vez, compensada por AD-21 |
| AD-04 | ZSET por tipo con `puntaje = t_entrada − bono(prioridad)`, el menor sale primero | Prioridad estricta; WFQ; MLFQ | Aging implícito sin temporizadores: un caso de prioridad baja solo puede ser adelantado por casos que entren hasta `bono(crítica) − bono(baja)` después de él; con llegadas finitas, su espera queda acotada. Selección O(log n) | R2 cap. 5; R3. **Medición pendiente:** ficha M2, comparada con FIFO |
| AD-05 | Un contenedor por tipo de worker con `mem_limit`, sin swap | `systemd MemoryMax=`; un solo contenedor para todos | Reutiliza Compose; aísla un OOM a un tipo; cgroups v2 lo aplica el kernel | R4, R5; [B.5 M1] |
| AD-06 | Admisión en el worker antes de sacar de la cola: `memory.current + huella(modelo) ≤ memory.max × (1 − margen)` | Concurrencia fija; reservas en el coordinador | Encaja con el modelo *pull*: lo que no se saca sigue en cola y otro nodo puede tomarlo. No centraliza el estado de memoria | R4. **Medición pendiente:** huella de ficha M1 |
| AD-07 | Comparar carga independiente por proceso con pesos compartidos por CTranslate2 en un único proceso mediante `inter_threads`; elegir con datos, provisionalmente por proceso. **ADD F-19 (2026-11-10, autorización delegada por José):** se descarta fork de un modelo CTranslate2 ya cargado porque la prueba real Linux se bloqueó aunque se limitara a un hilo; no hay una API documentada de CTranslate2 para mapear sus pesos en memoria. Se conserva Whisper CPU, N=1/N=2 y supervisor incluido en PSS; no generalizar a texto/imagen. CTranslate2 documenta que sus workers comparten pesos y permite fijar `inter_threads`, proporcionando una alternativa soportada. Las fases pendientes de F-19 adaptan la selección, runtime, SPEC y medición a esta alternativa; la equivalencia y el aislamiento por timeout siguen siendo puertas obligatorias | `fork` tras cargar; carga independiente por proceso; `inter_threads` con pesos compartidos en una instancia; `mmap` propio | Evita heredar hilos nativos y mide una capacidad soportada por el backend. Se compara PSS de procesos independientes contra proceso y threads compartidos, con el mismo modelo/parámetros/carga; RSS no representa memoria física exclusiva. No se atribuye a mmap una API que CTranslate2 no documenta | CTranslate2, [parallelism](https://opennmt.net/CTranslate2/parallel.html); Python, [os.fork](https://docs.python.org/3.14/library/os.html#os.fork); R2 cap. 10; R4. **Medición pendiente:** ficha M1 |
| AD-08 | Cada sub-tarea corre en un subproceso con grupo propio; el supervisor es dueño de sus temporales | Hilos (actual); sin aislamiento | Un hilo de Python no se puede matar desde fuera. Si un hijo recibe `SIGKILL` no puede limpiar: debe hacerlo el padre. Un OOM del hijo no mata al supervisor | R2 cap. 3; limitación declarada del I Proyecto |
| AD-09 | Cancelación con clave `cancel:{caso}` y `PUBLISH`; `SIGTERM`, gracia, `SIGKILL`, `waitpid` | Solo Pub/Sub; solo sondeo | Pub/Sub aporta inmediatez pero no persiste; la clave cubre al suscriptor que estaba reconectando | R1 |
| AD-10 | Protocolo propio por chunks; tamaño fijado con datos, provisional 4 MiB | Subida directa a MinIO; protocolo tus | Permite medir y variar el chunk [B.5 M3]; simple de explicar | **Medición pendiente:** ficha M3, 256 KiB, 1 MiB, 4 MiB y 16 MiB |
| AD-11 | Dedup a nivel de archivo, clave SHA-256 del texto en claro | Chunks de tamaño fijo o variable | Mantiene separados los experimentos (SUP-13). El hash del contenido en claro es necesario, porque el cifrado aleatorio impide deduplicar sobre el texto cifrado. Revela si dos objetos son iguales: riesgo aceptado y declarado, porque el acceso al almacén es restringido | R9 (nonce aleatorio en GCM). **Medición pendiente:** tasa en ficha M3 |
| AD-12 | Dos niveles: API responde 503 con `Retry-After`; scheduler mueve solo si `LLEN < límite`, con script Lua atómico | Bloquear al productor; colas sin límite | Rechazar no retiene conexiones. El bloqueo en el scheduler conserva el orden de prioridad en el ZSET. Un parámetro desactiva el límite para el experimento | R1. **Medición pendiente:** ficha M3 |
| AD-13 | Recepción `async` en uvicorn; escritura en hilo acotado | Escritura síncrona; servicio separado | Reutiliza FastAPI; no bloquea el bucle de eventos | R7. **Medición pendiente:** RF-34 |
| AD-14 | JWT firmado con rol y `Depends` de FastAPI | Sesiones; Keycloak | Sin estado y sin un servicio más; B.7 lo sugiere | [B.7 Seguridad]; R2 cap. 16 y 17 |
| AD-15 | TLS 1.3 con CA privada y certificado por nodo, en API, Redis y MinIO | WireGuard; malla de servicios | La captura muestra TLS, como pide la evidencia; lo soportan los tres componentes de forma nativa | R8; [B.7 Seguridad] |
| AD-16 | AES-256-GCM en la aplicación, llave por objeto (DEK) envuelta por una KEK en archivo montado, permisos `0400`; nonce único por chunk | MinIO SSE; LUKS; Vault | Protege también contra quien lee MinIO. Vault agrega un servicio que operar con el tiempo disponible. Limitar a una DEK por objeto evita el límite de nonces aleatorios por llave | R9; [B.7 Seguridad] |
| AD-17 | JSONL de solo-anexión con `entry_hash = SHA-256(prev_hash ‖ datos)`, un solo escritor con `O_APPEND` y `fsync`; cabeza sellada con HMAC | Log en Redis; Merkle; blockchain | Es lo que pide [B.5 M4]. **Una cadena sin llave se puede recalcular por completo y no detecta truncamiento: el sello HMAC lo cubre** | R10 |
| AD-18 | Tabla `config/routing.yaml` generada del benchmark; colas por clase de nodo; alternativa si no hay nodo vivo | Estimación dinámica; asignación manual | [B.5 M5] exige que la decisión provenga de datos; una tabla es trazable y explicable | **Medición pendiente:** ficha M5 |
| AD-19 | faster-whisper, YOLO (variante nano), spaCy y un modelo preentrenado de HuggingFace para sentimiento y ofensas | Modelos mayores; Vosk | Pesos pequeños para el límite de memoria; variantes `int8` para M5; [B.7] los sugiere. Ultralytics usa AGPL-3.0: se cita. Modelos definitivos sujetos a medición | [B.7 Texto/Imagen/Audio]. **Medición pendiente:** ficha M1 |
| AD-20 | Extender el dashboard Streamlit; datos de cgroups en el heartbeat | Prometheus y Grafana | Reutiliza código; evita servicios y TLS adicionales. Los gráficos de las fichas salen de CSV producidos por scripts | [B.2]; R4 |
| AD-21 | Coordinador sin estado, Redis AOF como checkpoint; `SADD` idempotente; reconciliación al arrancar | PostgreSQL; snapshots propios | Ya funciona. Con `appendfsync everysec` un fallo de **Redis** puede perder hasta 1 s; [B.6] exige reinicio del **coordinador**, no de Redis | R1. I Proyecto declaró 45 s detenido sin pérdida, sin logs: **Medición pendiente**, F-35 |
| AD-22 | Imágenes de workers ML con Python 3.13, igual que CI; la imagen heredada usa `3.14` | 3.12; mantener 3.14 | El código heredado usa `os.process_cpu_count`, disponible desde 3.13, así que 3.12 no sirve. Las dependencias nativas de inferencia pueden no publicar *wheels* para 3.14 | `src/workers/config.py:176`; CI. Verificar *wheels* al construir la imagen |
| AD-23 | Compose fija `hostname` con `NODE_NAME` y el heartbeat publica `NODE_IP`, la IP de Tailscale de la máquina | `network_mode: host`; usar solo `host` y capturar la IP aparte | En contenedor, `hostname` es el ID del contenedor y `ip` es la IP bridge: tres réplicas en un equipo darían tres `hostname` y no probarían [B.2], y RNF-01 no se podría demostrar en `GET /workers`. `network_mode: host` en Docker Desktop actúa sobre su VM, no sobre Windows. Consecuencia: `--scale` deja de ofrecerse y cada servicio de un nodo necesita su `WORKER_ID` | RNF-01; `src/workers/heartbeat.py:88` y `:148`. Comportamiento de `network_mode: host` tomado de la documentación general de Docker, sin probar. Aprobada por Kenni. F-38 |
| AD-24 | Coordinador en el Compose del Nodo A | Proceso nativo | US-38 pide levantar el Compose de cada nodo; [B.8] menciona Docker Compose por nodo | US-38; [B.8]. Aprobada por Kenni. F-38 |
| AD-25 | Generador nuevo y determinista del dataset sintético (`scripts/dataset_sintetico.py`, con plan, chats, `ffmpeg` y manifiesto con validador) | Ampliar `scripts/build_dataset.py` | RF-18 a RF-22 exigen texto e imágenes y reproducibilidad; `build_dataset.py` solo cubre video y audio, no tiene texto ni imágenes y su manifiesto trae `generated_at`, que no es reproducible. Misma semilla, mismo plan y manifiesto planeado (los hash de archivo dependen de la versión de `ffmpeg`). Licencia MIT, origen `sintetico`. Detalle en [dataset.md](dataset.md). Aprobada por la persona | `docs/specs/F-03/SPEC.md`; [B.3]. FFmpeg, ffmpeg.org. F-03 |
| AD-26 | Análisis de texto por lote: palabras clave por frecuencia de lemas de spaCy; tema por léxico configurable; sentimiento y ofensa con un modelo preentrenado de HuggingFace; amenaza por patrones del `Matcher` de spaCy; severidad por reglas en TOML | Clasificación temática *zero-shot* con un modelo NLI; amenaza solo con un clasificador de toxicidad; un LLM | Un solo modelo grande cabe mejor en el límite de memoria (AD-06); léxico y patrones son explicables y se ajustan sin entrenar (RNF-25); coincide con el recorte 4 de IMPLEMENTACION §1.3. **Provisional:** plan de F-07 aprobado por José Andrés. La parte 1 implementa, con modelos falsos, la severidad por reglas en `config/texto.toml` con regla de `amenaza` obligatoria (SUP-07) y umbrales validados en [0, 1]; el tema por léxico comparado sin tildes ni mayúsculas (la `ñ` se compara como `n`), y el rechazo de un modelo que no devuelva un análisis por mensaje. La parte 2 fija los modelos en `config/texto.toml`: spaCy `es_core_news_sm` 3.8.0 (GPL-3.0) para lemas y `Matcher`; `pysentimiento/robertuito-sentiment-analysis` y `pysentimiento/robertuito-hate-speech` con revisión fijada, entrenados con datasets de uso no comercial, admitido solo por el uso académico (R11, R12). El puntaje de ofensa es el máximo de `hateful` y `aggressive`; `targeted` no cuenta, porque indica a quién va el mensaje y no si ofende. Los patrones de amenaza comparan `LOWER`, no `LEMMA`, para no depender del lematizador ante mayúsculas. La parte 3 ejecutó por primera vez los modelos reales el 2026-11-07, con lotes de 10 mensajes sobre una conversación sintética de 40 mensajes redactada con IA: tema 4/4, sentimiento 4/4, amenaza 1/1, ofensivo 1/1 y sin ofensa 2/2 ([docs/evidencia/F-07_aciertos_2026-11-07.md](evidencia/F-07_aciertos_2026-11-07.md)). Es una medición funcional, de punta a punta, no de precisión: la muestra es pequeña y la conversación se redactó conociendo el léxico y los patrones. Las pruebas exploratorias de QA mostraron que el modelo de odio no detecta la mayoría de insultos genéricos, que los patrones no detectan amenazas sin patrón y que la ironía se lee como positiva. El patrón `vas_a_ver` quedó en «vas» y «van», porque «voy» y «vamos a ver» daban amenazas altas falsas. AD-25 queda para la rama de F-03 | [B.7 Texto]; AD-19; SUP-07. **Medición pendiente:** calidad sobre datos etiquetados independientes (F-04), calibración de `umbral_ofensa` y de los umbrales de severidad, que siguen provisionales en 0.5 porque, en la exploración de QA, los puntajes de ofensa de la muestra quedan en 0.133 o menos y en 0.981 o más, sin valores intermedios con que calibrar, y huella de F-17 |
| AD-27 | Detección de contenido sensible en imagen con Ultralytics YOLO11n preentrenado en COCO, solo inferencia en CPU; clases sensibles por mapa en `config/imagen.toml` (inicialmente `knife` → `arma`, SUP-22); un hallazgo por categoría con la detección de mayor confianza y su caja como posición; severidad con las reglas de F-07 | Clasificador de imagen completo (ImageNet o NSFW de HuggingFace); pesos YOLO ajustados por terceros para armas de fuego; OpenCV DNN con ONNX | Un solo modelo pequeño para el límite de memoria (AD-06); la caja da la posición que pide RF-14; COCO trae `knife`, que cubre el arma en imagen de SUP-07 sin entrenar (RNF-25); los pesos de terceros para armas de fuego tienen licencia y procedencia dudosas. Ultralytics y sus pesos usan AGPL-3.0, compatible con el repositorio público; se cita (Parte I §9). **Provisional:** plan de F-08 aprobado por José Andrés, con YOLO11n y `knife` → `arma`. La parte 1 implementa, con un detector falso, la conversión de detecciones en hallazgos: filtro por mapa y umbral mínimo inclusivo, un hallazgo por categoría con la detección de mayor confianza (desempate por caja) y `caja x1,y1,x2,y2` como posición; regla de `arma` obligatoria, y `SeverityRules` rechaza con `ValueError` reglas duplicadas, campos faltantes o una sección que no sea lista, lo que también aplica al texto de F-07. La parte 2 agrega `YoloDetector`, que infiere en CPU, convierte la salida a tipos nativos y rechaza con `ValueError` una imagen ilegible; fija en `config/imagen.toml` los pesos `yolo11n.pt` de la release v8.4.0 de ultralytics/assets con su SHA-256, que se comprueba antes de cargarlos, y `ultralytics==8.4.208` con `torch==2.15.0` CPU en `requirements-imagen.txt` (R13). Rechaza además cajas invertidas y etiquetas vacías, copia el mapa de clases y exige `[clases]` y `umbral_minimo`. La parte 3 ejecutó YOLO real por primera vez el 2026-11-09, en Python 3.14.0 y no en el 3.13 de AD-22, sobre 20 fotos propias de José Andrés con un mismo cuchillo: `arma` VP 4, FP 0, FN 6, VN 10 con `umbral_minimo = 0.25` ([docs/evidencia/F-08_aciertos_2026-11-09.md](evidencia/F-08_aciertos_2026-11-09.md)). Es una medición funcional, de punta a punta, no de precisión. Los 6 fallos tienen el cuchillo en vertical; en 3 YOLO detecta `tie` y en 2 `knife` con 0.15, bajo el umbral, que José Andrés mantuvo en 0.25 para no calibrar con la misma muestra. Una imagen que no decodifica da lista vacía con aviso en ultralytics 8.4.208, y `YoloDetector` la convierte en `ValueError`. AD-25 y AD-26 quedan para F-03 y F-07 | [B.7 Imagen]; AD-19; SUP-07. Ultralytics, docs.ultralytics.com. **Medición pendiente:** calidad sobre datos etiquetados independientes, con más de un cuchillo, calibración de `umbral_minimo` y huella de F-17 |
| AD-28 | Transcripción con faster-whisper `base` preentrenado, CPU e `int8`, idioma `es` fijo; un hallazgo `transcripcion` por segmento con su texto y timestamps; los segmentos pasan como mensajes por el análisis de texto de F-07 (AD-26), con posiciones de segmento y timestamp | Vosk; whisper de OpenAI sobre torch; modelo `tiny` o `small`; analizar la transcripción completa como un solo mensaje | faster-whisper es el que fija AD-19; usa CTranslate2 sin torch (AD-06, F-17); `int8` es la variante que compara M5 y `base` coincide con el comando de F-31; reutiliza F-07 sin duplicarlo y da el timestamp de RF-14. faster-whisper (SYSTRAN) y los pesos de Whisper (OpenAI) usan licencia MIT; se citan (Parte I §9). **Provisional:** plan de F-09 aprobado por José Andrés, con faster-whisper `base` y un hallazgo por segmento. La parte 1 implementa, con un transcriptor falso, `TranscriptSegment` con tiempos finitos y `0 <= inicio <= fin` y confianza validada en [0, 1]; un hallazgo `transcripcion` de severidad baja por segmento no vacío, con los segmentos renumerados tras descartar los vacíos; el análisis de F-07 reutilizado con el parámetro `posiciones` de `analyze_conversation`, que da `segmento i t=a-bs`, `segmentos i-j t=a-bs` y la lista `segmentos i,j t=a-bs,c-ds`; una nota sin voz da lista vacía. La parte 2 agrega `WhisperTranscriber`, que transcribe en CPU con importación diferida de faster-whisper y carga el modelo una vez por instancia; fija en `config/audio.toml` la revisión de `Systran/faster-whisper-base` como commit de 40 dígitos hexadecimales, exige un `idioma` que sea uno de los 100 códigos de Whisper copiados de `_LANGUAGE_CODES` de faster-whisper v1.2.1, sin espacios ni mayúsculas, y rechaza con `ValueError` cualquier valor que no sea texto, acepta solo `compute_type` `int8` o `float32` y con `hilos = 0` delega el número de hilos en CTranslate2; `faster-whisper==1.2.1` va en `requirements-audio.txt` (R14). Convierte la salida a tipos nativos, calcula la confianza como `exp(min(0, avg_logprob))` y rechaza un `avg_logprob` NaN, y ordena los segmentos por inicio. Ante un audio ilegible lanza `ValueError` con la ruta: captura `OSError`, `ValueError`, el `IndexError` de un archivo sin pista de audio y `av.error.FFmpegError`, según el código fuente de PyAV 19.0.2; la parte 3 confirmó con PyAV 18.1.0 real que un archivo que no es audio, uno vacío y un mp4 sin pista de audio dan `ValueError`. `MemoryError`, `TimeoutError`, `BlockingIOError`, `InterruptedError` y `PermissionError`, incluidos los de `av.error` que también heredan de `FFmpegError`, se propagan sin convertirse, porque son transitorios y F-12 y F-18 pueden reintentar; `FileNotFoundError` y otros `OSError` siguen dando `ValueError` `TranscriptSegment` rechaza además tiempos `bool` y mayores que el rango de `datetime`. La parte 2 no ejecutó faster-whisper real; la parte 3 sí lo ejecutó. La parte 3 agrega `scripts/comparar_transcripcion.py`, que transcribe una muestra de 5 notas propias con su transcripción esperada, calcula la tasa de error por palabra (WER) tras normalizar mayúsculas, tildes (con la `ñ` conservada) y puntuación, la registra sin umbral y escribe la tabla en `docs/evidencia/`, con una sección de límites de texto fijo; los errores de entorno salen como `error:` con código 1. La comparación se midió el 2026-11-10 con faster-whisper 1.2.1, av 18.1.0 y los pesos `base` fijados (Python 3.14, CPU, `int8`), sobre 5 notas propias y sintéticas: WER de 15.4, 9.1, 36.4, 27.3 y 0.0 %, en `docs/evidencia/F-09_transcripcion_2026-11-10.md`. Límites medidos: `amenaza_01` es un falso negativo (Whisper `base` oyó «más a ver» en vez de «vas a ver»); un tono sostenido de 35 s produce un segmento inventado de `...` que el adaptador acepta; no se normalizan números; la muestra no es representativa. `requirements-audio.txt` fija `av==18.1.0` porque faster-whisper 1.2.1 falla con PyAV 19.0.2 | [B.7 Audio]; AD-19; SUP-07. **Medición pendiente:** huella de memoria de F-17. La comparación de transcripción de F-09 está medida (parte 3) |

| AD-29 | **Aprobada en el plan de F-16 por José Andrés Loría Herrera (2026-11-10):** rechazar `memory.max = max`, cgroups ausentes y configuración inválida; exigir límites y reserva explícitos sin valores numéricos predeterminados | Aceptar memoria ilimitada; omitir el chequeo ante errores; fijar límites por estimación | Evitar que un error de lectura permita arrancar sin el límite de RF-24; conservar parámetros calibrables y trazables. SUP-23; no cambia el contrato `ResourceReader`. Parte 1 implementa lector y validación pura; cableado de arranque pendiente en parte 2. Ficha: [M1](modulo-M1-memoria.md) | [B.5 M1]; RF-24; AD-05; SUP-17. **Medición pendiente:** límites, reserva y RAM efectiva de WSL2 |
| AD-30 | Control de admisión antes de `blpop` en `Worker.poll_once`: se lee `ResourceReader` y solo se consume una sub-tarea si `admits(current, max, footprint, margin)` cabe con la huella mínima de las colas que atiende; si no cabe o la lectura falla, se espera (`stop_event.wait`) y se registra; huellas y margen vienen de configuración (`FOOTPRINT_<OP>_BYTES`, `ADMISSION_MARGIN_BYTES`) sin valores predeterminados | Sacar la sub-tarea y reencolarla (riesgo de pérdida y reordenamiento); huella global fija; valores por defecto estimados | `blpop` multi-cola extrae al llamarse, así que la compuerta debe ir antes; coherente con AD-29 (no omitir el chequeo ante errores). La reserva de memoria de una sub-tarea reencolada por OOM se suma a la huella mientras corre (SUP-14, F-18). Limitación conocida: con `memory.max = max` el lector lanza `ValueError` y el worker nunca admite (se registra cada ciclo); F-16 exige límite. Estado: propuesta, pendiente de aprobación de José Andrés Loría Herrera. Ficha: [M1](modulo-M1-memoria.md) | [B.5 M1]; RF-25; US-17; AD-29. **Medición pendiente:** huella por tipo de operación |
| SUP-24 | Reserva provisional del preflight: máximo entre 1 GiB y 15 % de `MemTotal`; obtener bytes con `docker info --format '{{.MemTotal}}'` desde el daemon Linux que aplica los límites | Reserva cero; porcentaje fijo; consultar `/proc/meminfo` desde un proceso dentro de WSL2 | El preflight ya requiere el daemon para Compose; su CLI reporta la memoria de la VM Linux también cuando Python se ejecuta desde PowerShell en Windows, y evita confundirla con la RAM física del host | Ajuste de método en F-16 parte 2 tras confirmar que B/C/D se operan desde PowerShell y que `/proc/meminfo` no existe para Python de Windows. **Provisional; validar la salida del daemon y la reserva con mediciones reales.** |
| AD-31 | El worker cancela el grupo de procesos del caso: `SIGTERM`, espera la gracia (`grace_seconds`, 10 s por defecto), `SIGKILL` si sigue vivo, recoge el proceso y borra su directorio `/scratch`. La orden llega por Redis (`cancel:*`) y la subtarea queda `cancelled` (caso `case_cancelled`) | Solo `SIGKILL`; sin gracia; borrar sin esperar la salida | Permite que FFmpeg cierre, sin zombies ni temporales (RF-12, RNF-03). La gracia debe ser menor que `stop_grace_period` (31 m en `deploy/docker-compose.worker.yml`, F-16); si no, Docker mata el worker antes de limpiar. **F-36 parte 1:** `process`, `_run` y `main()` (solo POSIX) cablean el `ProcessSupervisor` en `multimedia_processor.py` y `worker_node.py`; `cancel` es idempotente. La evidencia con worker y Redis en nodos reales es «Medición pendiente» (F-36 parte 2, depende de F-38) | RF-12; RNF-03; [evidencia F-12](evidencia/F-12_cancelacion_2026-11-10.md) |
| AD-32 | Routing por tipo de nodo: `RoutingTable` (dominio, implementa `RoutingPolicy`) guarda para cada `ContentKind` una lista ordenada de clases (preferida primero, luego alternativas). `route` devuelve la primera clase viva o lanza `NoLiveNodeClass` (`ValueError`) sin mutar la sub-tarea. La tabla está en `config/routing.toml` (`[rutas]`, con `[evidencia]`), la carga `src/adapters/routing_config.py` con `tomllib` y se valida al arranque: rechaza una ruta escrita como cadena, tipos desconocidos, listas vacías, clases vacías o duplicadas. Valores provisionales: audio `gpu` y luego `cpu`; texto e imagen `cpu`. **Medición pendiente:** valores en nodos WSL2 reales (F-38) y GPU | Elegir clase por carga instantánea del nodo (acopla con M1 y no es reproducible); codificar la preferencia en el coordinador (no cita la medición de F-31); heurística dinámica | Tabla estática, auditable y reproducible; cambiar un valor exige editar configuración y pasar la validación, sin tocar código. El coordinador (M2) debe invocar `route`; `docs/CONTRATOS.md` no cambia. Ficha: [M5](modulo-M5-computo.md) | RF-41; B.5 M5; SPEC F-32; medición F-31 |
| AD-38 | El reporte consolidado se calcula bajo demanda desde `FindingStore`, `CaseCatalog` y `ObjectStore.exists`; no se materializa al cerrar el caso. Dominio (`evidence_position.py`, `consolidated_report.py`) puro y sin E/S. Límites declarados de la parte 1: las posiciones que se leen son las que emiten hoy los analizadores; un rango de lote (`mensajes 0-49`) es posición de resumen y no de evidencia; una posición no reconocida queda como `UnknownLocator` y sale como incidencia; el evento sin hora absoluta (audio, imagen) va aparte en `sin_marca_absoluta`, sin inventar hora; un índice repetido en `detail` es ambiguo y se deja sin marca; las incidencias son de 5 clases (`severidad_alta`, `subtarea_fallida`, `evidencia_sin_fuente`, `objeto_inexistente`, `posicion_desconocida`). Límites declarados de la parte 2: el extracto solo se arma para la categoría `transcripcion`, con tope `MAX_EXCERPT_CHARS=10_000` y marca de truncado; un almacén de objetos caído (`ObjectStore.exists` que lanza) se reporta como incidencia `objeto_inexistente` («no existe en el almacén») y no como «no verificable», porque distinguirlo exige un tipo nuevo en el dominio; los surrogates sueltos se sustituyen por «?»; la fuente se une por `sha256` o `file_path` (un `sha256` vacío no une); el catálogo expone `file_path` por diseño, de modo que un adaptador que lo llene con rutas absolutas las filtraría al reporte; `generated_at` va en UTC. Límites declarados de la parte 3: `obtener_almacen` responde 503 «pendiente F-23» hasta que Melany aporte un adaptador `ObjectStore` (la ruta real no sirve en producción hasta entonces); los workers de José aún no persisten `Finding` (la lista `case:{id}:findings` queda vacía hasta que cableen la escritura; F-13 entrega el adaptador); el hash de subtarea no trae `source_sha256` (la fuente se une por `file_path`) ni `kind` (se lee `task_type`); los hallazgos corruptos se omiten con un warning de recuento, sin incidencia; `case_id` debe encajar `[A-Za-z0-9_-]{1,128}`; Redis caído responde 503; sin paginación ni tope de hallazgos (20000 ≈ 11,7 MB); el `error_type` escrito por un worker pasa tal cual a las incidencias; la ruta debe clasificarse en la matriz de permisos de F-26 al fusionarse esa feature (aún no está en esta base); la parte 3 editó `build_report.py` de la parte 2. El JSON de ejemplo `docs/ejemplos/F-13_reporte_consolidado_ejemplo.json` es sintético y lo genera la prueba de aceptación con `F13_EJEMPLO_JSON`. Estado: propuesta, provisional | Materializarlo al cerrar el caso (exige un gancho en el barrier de Nahúm y queda desactualizado si un hallazgo llega tarde); guardarlo en el almacén de objetos (copia mutable de la evidencia, fuera de F-29) | La evidencia sigue siendo la referencia al objeto original y el reporte es una vista reproducible. Costo: se recalcula en cada consulta (**Medición pendiente:** solo si el reporte lo exige; no es medición de SO). Ficha: [SPEC F-13](specs/F-13/SPEC.md) | RF-14; US-13; SUP-34; SPEC F-13 |
| AD-39 (provisional) | Las alertas se publican en un Redis Stream acotado (`MAXLEN ~`) y se leen sin grupo de consumidores; el aislamiento de fallo vive en `SafeAlertPublisher` y la incidencia alta se detecta al agregar hallazgos con `AlertingFindingStore`, decorador de `FindingStore`. Alternativas: Pub/Sub de Redis (sin retención, una alerta sin lector se pierde); lista con `LPUSH`/`LTRIM` (sin identificadores ni orden por tiempo); llamar al publicador desde cada worker y el coordinador (duplica la regla y acopla módulos ajenos); tarea que sondea casos cerrados (más piezas y retraso). Criterio: §5 ya fija «Alertas → Stream → Redis» y el enunciado pide notificación asíncrona; el Stream retiene alertas para quien se conecte tarde. Costo: entrega a lo sumo una vez y retención acotada. Medición pendiente: ninguna. Límites de la parte 1: incidencia = `Finding.severity` ALTA sin recalcular reglas; `detail` sin texto de mensajes (JSON con `categoria`, `confianza`, `sha256`, `posicion`); `cancelled` no alerta; `AlertingFindingStore` envuelve el publicador en `SafeAlertPublisher`; este absorbe `Exception` (no `BaseException`), registra con `%r` y cierra las corrutinas que devuelva un publicador async; sin idempotencia (un reintento del worker repite alertas); sin timeout (un publicador bloqueante frena `add`); `case_id` vacío o `None` sin validar; los workers aún no persisten `Finding`, así que en operación real solo habría alerta de cierre hasta que José lo cablee. Límites de la parte 2: Stream `alerts` con `XADD MAXLEN ~` (aproximado; maxlen 1000 sin medir; fakeredis recorta exacto y el recorte real lo cubre la prueba de integración); `GET /alerts?limit=` de 1 a 200 (50 por defecto), sin paginación más allá de `limit`; `detail` sin tope (1 MB pasa); el 503 lleva `detail` fijo sin host, puerto ni texto de redis-py (no usa `conexion.redis_unavailable`, que sí los filtra: código previo de Nahúm, pendiente fuera de F-14); cualquier `RedisError` da 503; las entradas corruptas, sin campos, con fecha sin zona o con bytes no UTF-8 se omiten con un warning de recuento (la relectura en crudo ante bytes no UTF-8 solo se probó con fakeredis); entrega a lo sumo una vez; `emitted_at` en UTC y un reloj ingenuo se toma como hora local; la ruta debe clasificarse en la matriz de permisos de F-26 al fusionarse esa feature (aún no está en esta base); la vista en el dashboard es de Melany. Fuente: `docs/specs/F-14/SPEC.md`, `docs/ARQUITECTURA.md` §5, documentación de Redis Streams (redis.io/docs/latest/develop/data-types/streams). Límites de la parte 3: el cierre de caso publica una sola alerta (`kind` `caso_finalizado`, `detail` `{"estado": ...}`) tras marcar el caso terminal, dentro de `try/except`; `cancelled` no alerta; un fallo del publicador o de Redis no cambia la respuesta ni el estado; `redis_client` no tiene timeout, así que un `xadd` colgado bloquearía la respuesta, igual que el resto del coordinador; se tocó `rutas_subtareas.py` de Nahúm (+12/-2): avisarle. Defectos previos a F-14, fuera de su alcance y declarados con xfail estricto en `tests/unit/test_cierre_alertas_qa.py`: `report_subtask` no valida que `case_id` sea el de la sub-tarea (cierra otro caso o crea uno fantasma y alerta); carrera entre cancelar y el HSET terminal (un caso cancelado pasa a `completed` y alerta); el log previo `Caso %s finalizado` admite inyección de líneas. `AlertingFindingStore` no está cableado en ningún sitio de `src/` (solo lo usan las pruebas) y los workers de José aún no persisten `Finding`: en operación real solo habría alerta de cierre hasta que cableen la escritura. La ruta `GET /alerts` y su dependencia deben clasificarse en la matriz de F-26 al fusionarse. Prueba A: `pytest -q -m acceptance tests/acceptance/test_alerta_de_cierre.py` (opcional `F14_EJEMPLO_JSON`); usa `FakeClock`, el intervalo de 12 minutos es el avance inyectado, no una medición de latencia ni de rendimiento; no hay JSON de ejemplo versionado. |
| AD-40 | Comparador de aciertos y errores (`src/domain/ground_truth.py`) y validador de procedencia y licencia en dominio puro, con entrada por datos: reciben etiquetas y salidas ya producidas, no ejecutan modelos ni leen archivos; los lectores de JSON y la CLI viven en `src/adapters/dataset_truth_files.py` y `scripts/dataset_verdad.py`. Estado: propuesta; la decisión de la persona sobre SUP-26 y SUP-27 sigue pendiente | Migrar los `aciertos_*` de `scripts/` al comparador común (invade el módulo de José Andrés; queda como otra feature); un comparador que ejecute los modelos (acopla F-04 a F-07/F-08/F-09 y a modelos pesados) | «Módulos independientes» y pruebas sin red, reloj ni modelos; el comparador no puede inventar resultados porque solo lee datos [B.3 Dataset mínimo]. El criterio VP/FP/FN/VN sigue a `scripts/aciertos_imagen.py` sin importarlo | [B.3]; `docs/specs/F-04/SPEC.md`; RF-23; US-04 |

## 9. Reglas de diseño obligatorias

**Clean Shutdown** (RF-12, RF-45):

1. El supervisor maneja `SIGTERM`: deja de consumir, envía `SIGTERM` al grupo de cada hijo, espera la gracia y envía `SIGKILL`.
2. Tras cada señal llama a `waitpid`, de modo que no queden zombies. El contenedor usa `init: true`.
3. Devuelve lo que estaba en `inflight` y borra `/scratch/{subtarea}` en `finally`, en el padre.
4. Al arrancar elimina temporales huérfanos.
5. `stop_grace_period` baja de los 31 min actuales a un valor mayor que la gracia.

**Clean Data** (SUP-15): los parsers de WhatsApp y Telegram producen `ChatMessage(timestamp_utc, sender, text, source_ref)` en UTF-8. La línea original se conserva en `source_ref`, necesaria para enlazar evidencias (RF-14). Procedencia y licencia se documentan en `docs/dataset.md`.

**Temporales en claro.** El worker debe descifrar para analizar. Un `tmpfs` se contabiliza en el cgroup, así que un video de 200 MB consumiría el límite. Por eso, `/scratch` es un volumen que se borra por sub-tarea. Es una limitación declarada: durante el análisis existe texto en claro en disco.

## 10. Referencias

| ID | Referencia |
|---|---|
| R1 | Redis, documentación oficial de `BLMOVE`, Pub/Sub y persistencia: redis.io/docs |
| R2 | Silberschatz, Galvin, Gagne. *Operating System Concepts*, 10.ª ed. Verificar capítulos con la edición del curso (SUP-16). |
| R3 | Demers, Keshav, Shenker. «Analysis and Simulation of a Fair Queueing Algorithm», SIGCOMM 1989. |
| R4 | Kernel Linux, *Control Group v2*: docs.kernel.org/admin-guide/cgroup-v2.html |
| R5 | Docker, *Resource constraints*: docs.docker.com/engine/containers/resource_constraints |
| R6 | Python, `gc.freeze` y `os.fork`: docs.python.org/3/library; `proc_pid_smaps(5)` para PSS. |
| R7 | FastAPI y uvicorn, documentación oficial. |
| R8 | RFC 8446, TLS 1.3. |
| R9 | NIST SP 800-38D, modo GCM. |
| R10 | Schneier, Kelsey. «Secure Audit Logs to Support Computer Forensics», 1999. |
| R11 | spaCy, modelo `es_core_news_sm` 3.8.0, Explosion AI, licencia GPL-3.0: spacy.io/models/es |
| R12 | Pérez et al. «pysentimiento: A Python Toolkit for Opinion Mining and Social NLP tasks», 2021; modelos `pysentimiento/robertuito-sentiment-analysis` y `pysentimiento/robertuito-hate-speech`: github.com/pysentimiento/pysentimiento y huggingface.co/pysentimiento |
| R13 | Ultralytics YOLO 8.4.208, licencia AGPL-3.0: docs.ultralytics.com; pesos `yolo11n.pt` de la release v8.4.0 de github.com/ultralytics/assets, AGPL-3.0 |
| R14 | faster-whisper 1.2.1, SYSTRAN, licencia MIT: github.com/SYSTRAN/faster-whisper; pesos de Whisper de OpenAI, MIT (github.com/openai/whisper), convertidos a CTranslate2 en huggingface.co/Systran/faster-whisper-base, MIT, revisión `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` |
