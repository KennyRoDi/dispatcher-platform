# SPEC F-43: Integración de workers tipados

**Fase:** tests
**Base:** main
**Verificación IA:** tests 206d324b
**Historia:** US-43 · **Requisitos:** RF-04 a RF-12, RF-13 y RF-14 (reporte con evidencias), RF-15, RF-16, RF-24 y RF-25 (admisión en el worker tipado); RNF-01, RNF-07, RNF-08, RNF-24, RNF-25; AD-03, AD-05, AD-06, AD-11, AD-26 a AD-28, AD-43, AD-46 a AD-49 (aplica); AD-51 a AD-54 (propone) · **Responsable:** K

## Objetivo

[B.4] pide «colas de trabajo con descomposición del caso en sub-tareas y routing por tipo de contenido hacia workers especializados» y «workers especializados para texto, imagen y audio (los tres obligatorios)»; la rúbrica B.9 asigna 15 % al «pipeline completo de B.4 operando de forma distribuida: workers de texto, imagen y audio integrados». RF-04 y RF-05 exigen sub-tareas trazables y que cada tipo llegue solo a la cola de su worker; RF-06 a RF-08 exigen los tres análisis; RF-09 a RF-12 exigen estados, barrier, reintentos con backoff y cancelación real; RF-13 a RF-16 exigen reporte con evidencias y alertas.

Hoy cada pieza existe por separado y **nadie las conecta**. Verificado en el código de `main`:

- `POST /cases` con `sources` (F-01) clasifica, descompone y encola sub-tareas en `queue:text`, `queue:image` y `queue:audio` con `RedisTypeQueue` (F-05, F-06). **Ningún proceso consume esas colas.** `Worker` (`src/workers/worker_node.py`) solo hace `BLPOP` sobre `queue:{operacion}[:high]` de las 5 operaciones FFmpeg y su `Settings` rechaza `text|image|audio` en `WORKER_QUEUES`.
- Los analizadores `TextAnalyzer`, `ImageAnalyzer` y `AudioAnalyzer` (F-07 a F-09) solo se construyen en `scripts/aciertos_texto.py`, `aciertos_imagen.py` y `comparar_transcripcion.py`; no hay fábrica reutilizable ni worker que los invoque.
- Un worker tipado se rompería con lo que ya existe: `src/workers/recovery.py` (`_requeue`) y `RedisRetryScheduler._promote` hacen `LPUSH` de un `subtask_id` plano a `queue:{operation}`, y `RedisTypeQueue.take` hace `json.loads` de cada elemento, así que un reencolado deja un elemento ilegible; `scripts/reaper.py` solo lee el SET heredado `worker:{id}:inflight` y nadie llama a `RedisTypeQueue.reencolar_huerfanas`; `CreateMultiSourceCase` encola antes de persistir `subtask:{id}`; `RedisFindingStore.add` duplica ante un reintento; `rutas_reporte.obtener_almacen` lanza 503 («pendiente F-23») y `GET /cases/{id}/consolidated-report` no responde nunca.

F-43 entrega la integración: un worker por tipo (`WORKER_KIND=text|image|audio`, AD-05) que consume su cola, analiza, escribe hallazgos sin duplicados, reporta al coordinador y se recupera de fallos; las correcciones de plataforma que eso exige; el análisis de video por fotogramas; pruebas de extremo a extremo con `fakeredis` y dobles de modelo; y el despliegue por nodo. Es una feature de **integración** (ya está en `FEATURES_DE_INTEGRACION` de `scripts/conformidad.py`): toca archivos de varios responsables, por eso se reparte por dueño de archivo (ver «Diseño»).

## Alcance

**Incluye:**

- **Plataforma con formato tipado (parte 1):** reencolado y promoción de reintentos en el formato JSON de `Subtask` hacia la cola tipada; recuperación de `inflight:{worker}` de workers tipados muertos por el reaper; persistir `subtask:{id}` antes de encolar sin dejar huérfanos; `QueueLimit.from_env` y `Retry-After` en el camino tipado; prioridad unificada en `normal`/`high` con un único mapeo en dominio; `/stats` con las tres colas tipadas; `take` tolerante a un elemento ilegible.
- **Piezas compartidas y contrato (parte 2):** `crear_almacen_lectura(env)`; fábrica `crear_analizador(kind, env)` con modelos cargados una vez por proceso; selector de parser por extensión (`.txt` a `WhatsAppParser`, `.json` a `TelegramParser`); hallazgos idempotentes por sub-tarea con alertas sin repetirse; reporte consolidado con almacén real; clasificación de fallos transitorios y permanentes; sección del worker tipado en `docs/WORKER_CONTRACT.md`.
- **Worker tipado (parte 3):** `src/workers/typed_worker.py` y el caso de uso `AnalyzeSubtask`: reclamo, admisión de memoria, descarga con verificación de SHA-256, análisis, hallazgos, reporte, confirmación en `inflight`, reintento con espera (F-11), límite de intentos al reclamar, recuperación propia al iniciar, heartbeat y cancelación cooperativa.
- **Video por fotogramas (parte 4):** en el worker de imagen, una fuente de video se descompone en fotogramas con FFmpeg (muestreo acotado y configurable), cada uno pasa por `ImageAnalyzer`, y los hallazgos quedan enlazados al video original con posición de tiempo y caja. La sub-tarea AUDIO del mismo video sigue por `AudioAnalyzer`.
- **Pruebas de extremo a extremo (parte 5):** `POST /cases` con las cuatro fuentes hasta `completed`/`partially_completed`, reintento, cancelación, muerte del worker, admisión, reporte consolidado y alertas.
- **Despliegue (parte 6):** imagen de análisis, servicios por tipo con el endurecimiento de F-30, variables, distribución de la KEK y verificadores.

**No incluye:**

- **F-20 parte 3 (aging en `rutas_subtareas.py`):** sigue siendo de Nahúm. `RedisScheduler` usa un ZSET sobre `queue:text` y choca (`WRONGTYPE`) con la LIST de `RedisTypeQueue`; hay que resolver AD-04 frente a AD-46 antes de cablearlo. Consecuencia declarada: en el camino tipado la prioridad se conserva en el mensaje y en los hashes pero **no reordena** la cola (FIFO por tipo); no existen `queue:{tipo}:high`.
- **Routing por clase de nodo (F-32):** falta quien entregue `live_classes` y el heartbeat no publica la clase.
- **Prioridades baja y crítica:** inalcanzables por la API (`CaseRequest.priority` es `normal|high`, `modelos.py`); no se exponen.
- **Custodia** (ingreso y transformación) desde el coordinador (F-29 sigue de Kenni) y las **mediciones pendientes de M1, M3 y M4**, que exigen nodos reales.
- **`fork_runtime.py` y `model_loader.py`:** son código de medición de M1 (F-19); no se conectan al pipeline.
- **Parser de `.csv`:** no se agrega. `classify_source` no cambia; el worker de texto falla de forma permanente y legible con `.csv` (SUP-47).
- Cambiar `ContentKind`, `WorkQueue` o `ObjectStore` (solo se agregan puertos), o el camino heredado `subtasks` con operaciones FFmpeg, que sigue con `Worker` sin cambios de comportamiento.
- Ejecutar en nodos reales o medir huellas de memoria: las huellas y el muestreo de video quedan como «Medición pendiente».

## Criterios de aceptación

Copiados de `docs/backlog/integracion-workers.md` (US-43):

**Dado** un caso con fuentes de texto, imagen, audio y video creado con `POST /cases` y `sources`
**Cuando** corren los workers tipados sobre `queue:text`, `queue:image` y `queue:audio`
**Entonces** cada sub-tarea se analiza, sus hallazgos quedan en el almacén sin duplicados, el caso cierra por barrier en `completed` o `partially_completed`, y el reporte consolidado sale con evidencias; un fallo transitorio se reintenta con espera, un worker caído devuelve su sub-tarea a la cola y un caso cancelado no se procesa

**Pruebas:** U fábricas de analizador y de almacén, reencolado en formato `Subtask`, selección de parser. I `POST /cases` con `fakeredis` y dobles de modelo hasta el cierre, video con fotogramas, cancelación, reintento y muerte del worker. A reporte consolidado con almacén real.
**Demuestra:** prueba I de extremo a extremo y el log de un caso completo. **Evidencia:** `docs/WORKER_CONTRACT.md` con el contrato del worker tipado y el reparto por `hostname` en `GET /workers`.

## Diseño

### Diferencias verificadas respecto al plan de la persona

El plan (`majestic-juggling-ember.md`) se contrastó con el código. Coincide en lo esencial; estas son las diferencias o precisiones, que el diseño ya incorpora:

1. **`Dockerfile.worker` está en la raíz, no en `deploy/`**; `verificar_workers.py` y `test_despliegue_compose.py` lo leen de ahí. Además, el `docker-compose.yml` del Nodo A **no pasa `KEK_FILE`, `OBJECTS_BUCKET` ni `STAGING_DIR` al coordinador** (solo `deploy/docker-compose.local.yml` los pasa): sin ellos `POST /cases` con `sources` no puede comprobar fuentes ni el coordinador cifrar subidas en producción.
2. **`RedisTypeQueue(capacity=0)` rechaza todo:** `has_capacity` es `llen < capacity`, y `QueueLimit` define `max_depth == 0` como «sin límite». Conectar `QueueLimit.from_env` tal cual dejaría el límite desactivado como «siempre lleno». No estaba en el plan.
3. **`reencolar_huerfanas` ignora los intentos:** una sub-tarea que mata al worker (por ejemplo por OOM) volvería a la cola indefinidamente. No estaba en el plan; se resuelve aplicando `decide_retry` al reclamar (AD-51).
4. **`take` deja el elemento en `inflight` si no se puede decodificar:** `BLMOVE` ya lo movió antes de `json.loads`. Un id plano reencolado por `recovery`/`RedisRetryScheduler` queda atascado. Se corrige en la parte 1.
5. **`Worker._claim_subtask` no se puede reutilizar tal cual:** hace `SADD` al SET heredado `worker:{id}:inflight`. Se extrae el reclamo sin ese paso (mismo `WATCH/MULTI`, mismo cambio de caso a `processing`).
6. **Evidencia de video:** `ImageAnalyzer.analyze` calcula el SHA-256 del archivo que recibe; con un fotograma extraído sería el del fotograma y no el del video, y el reporte marcaría `EVIDENCIA_SIN_FUENTE`. Además la posición `caja x1,y1,x2,y2` no lleva tiempo y cualquier otro formato cae en `POSICION_DESCONOCIDA` (`evidence_position.py`). Se re-sella el SHA al del video y se agrega un localizador de fotograma (AD-52).
7. **Cancelación:** `SubprocesosPorCaso` solo cancela subprocesos FFmpeg. Los analizadores corren **dentro del proceso del worker** y no hay hijo que matar; solo la extracción de fotogramas es cancelable por grupo de procesos. Ver pregunta 1.
8. **Prioridad:** el desajuste está en los dos hashes (`case:{id}` y `subtask:{id}` guardan `media`/`alta`, de `priority.name.lower()`) y no afecta al JSON de la cola, que usa los nombres del enum (sin pérdida) y se mantiene.
9. **`RetrySubtask` es código muerto** (sin llamadas en `src/` ni `scripts/`) y es utilizable aquí: opera sobre `CaseStateStore` (`RedisCaseState`) y `RetryScheduler`. El worker tipado lo usa, con lo que además deja de ser código muerto.
10. **Hallazgos idempotentes sin Lua:** el SPEC de F-11 documenta que `fakeredis` no ejecuta Lua `eval` en este entorno; la puerta se hace con `WATCH/MULTI`, como `RedisCaseState.set_state` y `_requeue`.
11. **El plan decía 5 partes; la estimación obliga a 6:** el worker tipado más la extracción de fotogramas superan 400 líneas, así que el video pasa a una parte propia (ver «Plan de pila»).
12. **Un proceso por tipo con concurrencia 1:** no hay evidencia de que spaCy, transformers, YOLO o CTranslate2 sean seguros entre hilos con el mismo modelo; `WORKER_CONCURRENCY` > 1 se rechaza con `WORKER_KIND`.

Verificados sin diferencia: `rutas_casos.py` fija `PROFUNDIDAD_POR_DEFECTO` (1000) y no llama a `QueueLimit.from_env` en el camino `sources`; `create_case.py` encola (`DispatchCase.execute`) antes de `_persistir`; `rutas_monitoreo.get_stats` itera `VALID_TASK_TYPES` (solo las 5 operaciones FFmpeg); `Settings` rechaza tipos fuera de `OPERATIONS` y `load_admission_config` exige `FOOTPRINT_<OP>_BYTES` sin valor por defecto; `work_dir / subtask_id` con `:` en el id (`{case}:{sha}:{kind}`); `obtener_almacen` lanza 503; el `analyzer` de cada tipo no tiene fábrica; `deploy/docker-compose.worker.yml` tiene un solo servicio `worker` con el endurecimiento de F-30.

### Contratos que usa (sin modificar)

`WorkQueue` (`RedisTypeQueue`: `take`, `acknowledge`, `in_flight`, `reencolar_huerfanas`), `ObjectStore` (`exists`, `open`; `open` de una clave inexistente lanza `KeyError`), `Analyzer`, `FindingStore`, `CaseStateStore` (`RedisCaseState`), `RetryScheduler` (`RedisRetryScheduler`, F-11), `AlertPublisher` y `SafeAlertPublisher`, `ResourceReader` (admisión, F-16/F-17), `CaseCatalog`, `Clock`, `Subtask`/`ContentKind`/`QueueFull`, `Finding`/`EvidenceRef`, `CaseState` y `transition`.

### Contratos que agrega (aditivos, sin modificar los existentes)

Se siguen los pasos de «Cambiar un contrato» de `docs/CONTRATOS.md` (PR del cambio, `tests/contratos.py` y `tests/dobles.py`, aviso a los de la tabla):

- **`SubtaskFindingStore(FindingStore)`** en `src/application/ports.py`: `add_once(case_id, subtask_id, findings) -> bool`; devuelve `False` si esa sub-tarea ya escribió y no agrega nada. Lo implementa `RedisFindingStore` (Kenni, F-13) y lo respeta `AlertingFindingStore`, que no repite la alerta de una escritura ignorada. Conformidad: `comprobar_finding_store_idempotente` en `tests/contratos.py`; doble: `FakeFindingStore.add_once`. Avisar a Kenni (dueño) y a José (lo usa).
- **`FrameExtractor`** en `ports.py` (parte 4): `extract(path, out_dir) -> list[Frame]` con `Frame(path, t_s)`. Sin adaptador compartido; lo implementa el worker.
- **`Priority.to_contract()` y `Priority.from_contract(texto)`** en `src/domain/priority.py` («Compartido»): `MEDIA` a `normal` y `ALTA` a `high`; cualquier otro texto lanza `ValueError`; `BAJA` y `CRITICA` no tienen palabra de contrato y `to_contract` lanza `ValueError` hasta que RF-28 las exponga (inalcanzables por la API).
- **`FrameLocator(t_s, box)`** en `src/domain/evidence_position.py` (parte 4, dueño K del reporte): posición `fotograma t=<segundos>s caja x1,y1,x2,y2`; `report_json` la serializa como `{"tipo": "fotograma", ...}`.
- **Mensaje y hash del worker tipado** (documentados en `docs/WORKER_CONTRACT.md`): el mensaje de la cola es `Subtask.to_dict()`; el hash `subtask:{id}` agrega el campo `payload` (ese mismo JSON, usado para reencolar sin reconstruirlo) y guarda `priority` en `normal|high`.

### Capas y archivos

Dueños según `docs/CONTRATOS.md`. Donde una parte toca archivos de varios dueños, el responsable (K) avisa y pide revisión a cada uno.

| Parte | Archivo | Dueño | Capa | Acción |
|---|---|---|---|---|
| 1 | `src/domain/priority.py` | Compartido | Dominio | agrega `to_contract` y `from_contract` |
| 1 | `src/application/create_case.py`, `src/application/dispatch_case.py` | N (F-01, F-05) | Aplicación | comprobar capacidad, persistir y luego encolar; compensar si falla; guarda `payload`; prioridad en contrato |
| 1 | `src/coordinator/rutas_casos.py` | N | Adaptador | `QueueLimit.from_env`, `Retry-After`, mapeo desde dominio |
| 1 | `src/coordinator/rutas_monitoreo.py` | N | Adaptador | `/stats` incluye `queue:text`, `queue:image`, `queue:audio` |
| 1 | `src/adapters/redis_type_queue.py` | N (F-06) | Adaptador | `capacity=0` sin límite; `take` descarta y registra un elemento ilegible |
| 1 | `src/adapters/redis_retry_scheduler.py` | N (F-11) | Adaptador | promoción de sub-tareas tipadas con el `payload` a `queue_for(kind)` |
| 1 | `src/workers/recovery.py`, `scripts/reaper.py` | J | Adaptador, Infraestructura | `_requeue` en formato tipado; el reaper recupera `inflight:{worker}` de workers tipados muertos (aviso a J) |
| 2 | `src/infrastructure/object_store.py` | V y K (F-23, F-28) | Infraestructura | extrae `crear_almacen_lectura(env)`; `crear_subidas` la reutiliza |
| 2 | `src/infrastructure/analizadores.py` (nuevo) | J | Infraestructura | `crear_analizador(kind, env)` |
| 2 | `src/adapters/parser_por_extension.py` (nuevo) | J (usa parsers de N, F-02) | Adaptador | `.txt` a WhatsApp, `.json` a Telegram, otra extensión `ValueError` |
| 2 | `src/application/ports.py`, `tests/dobles.py`, `tests/contratos.py` | Compartido | Aplicación, pruebas | `SubtaskFindingStore` y su conformidad |
| 2 | `src/adapters/redis_finding_store.py`, `src/application/alerting.py` | K (F-13, F-14) | Adaptador, Aplicación | `add_once` y alertas sin repetirse |
| 2 | `src/coordinator/rutas_reporte.py` | K | Adaptador | `obtener_almacen` con `crear_almacen_lectura` |
| 2 | `src/workers/fallos.py` (nuevo) | J | Adaptador | `es_transitorio(error)` |
| 3 | `src/workers/config.py` | J | Infraestructura | `WORKER_KIND`; huellas `FOOTPRINT_TEXT_BYTES`, `FOOTPRINT_IMAGE_BYTES`, `FOOTPRINT_AUDIO_BYTES` |
| 3 | `src/application/analyze_subtask.py` (nuevo) | J | Aplicación | `AnalyzeSubtask`: descargar, verificar, analizar, escribir |
| 3 | `src/workers/typed_worker.py` (nuevo) | J | Adaptador | bucle, reclamo, reintento, recuperación, heartbeat |
| 4 | `src/domain/frame_sampling.py` (nuevo) | J | Dominio | `FrameSampling` y marcas de tiempo del muestreo |
| 4 | `src/workers/multimedia_processor.py` | J | Adaptador | `extract_frames` (no cambia `SUPPORTED_OPERATIONS`) |
| 4 | `src/application/analyze_video.py` (nuevo) | J | Aplicación | analiza fotogramas y re-sella al SHA del video |
| 4 | `src/domain/evidence_position.py`, `src/application/report_json.py` | K | Dominio, Aplicación | `FrameLocator` |
| 5 | `tests/integration/`, `tests/acceptance/` | K | Pruebas | extremo a extremo |
| 6 | `Dockerfile.analisis` (nuevo), `deploy/docker-compose.analisis.yml` (nuevo), `docker-compose.yml`, `scripts/verificar_workers.py`, `scripts/preflight.py` | K | Infraestructura | imagen y servicios por tipo; KEK y bucket al coordinador |

### Reutilización del código existente

`Worker` y sus piezas (`_programar_reintento`, `_fits_in_memory`, `Heartbeat`, `WorkerStats`, `Reporter`, `SubprocesosPorCaso` y `escuchar_cancelaciones`); `decide_retry` y `RetryPolicy` (F-11) con `RetrySubtask`; `RedisCaseState` (F-10); `RedisTypeQueue` y `queue_for` (F-05, F-06); `FootprintTable` y `admits` (F-17); `TextAnalyzer.from_config`, `ImageAnalyzer.from_config`, `AudioAnalyzer.from_config`, `SpacyHfTextModels.from_config`, `YoloDetector.from_config`, `WhisperTranscriber.from_config` y `config/*.toml` (F-07 a F-09); `WhatsAppParser` y `TelegramParser` (F-02); `EncryptedObjectStore`, `MinioObjectStore`, `EnvelopeCipher` y `FileKeyProvider` (F-23, F-28); `AlertingFindingStore` y `SafeAlertPublisher` (F-14); `build_report` (F-13); el hardening de F-30 (`user 10001`, `read_only`, `cap_drop: ALL`, `no-new-privileges`, `scratch`, `tmpfs`). No se reescribe nada de F-07 a F-09.

### Flujo del worker tipado (AD-51)

1. Arranque: `Settings` con `WORKER_KIND`; carga de la huella del tipo; `crear_analizador` una sola vez (la KEK se lee al construir el almacén: sin llave el proceso no arranca); `reencolar_huerfanas(worker_id)` de su propio `inflight` (mismo `worker_id` tras reiniciar); limpieza del directorio de trabajo; heartbeat y escucha de `cancel:*`.
2. Bucle: admisión de memoria (AD-06) antes de `take`; `RedisTypeQueue.take(queue_for(kind), worker_id, timeout)` mueve el elemento a `inflight:{worker_id}` de forma atómica.
3. Reclamo (`WATCH/MULTI` sobre `subtask:{id}` y `case:{id}`): inexistente, terminal o de caso cancelado se confirma (`acknowledge`) sin procesar; si `decide_retry(attempts, policy)` da `GiveUp` (la sub-tarea ya consumió los N intentos, por ejemplo por muertes del worker) se reporta `failed` con `WorkerLostError` sin procesar; si no, `status=assigned`, `attempts+1`, `worker_id`, y el caso pasa a `processing` con `transition` y `RedisCaseState.set_state`.
4. `AnalyzeSubtask`: abre el objeto (`ObjectStore.open(source_sha256)`) a un archivo temporal en `WORK_DIR` con nombre `fuente<extensión>` (la extensión sale del nombre guardado en `file_path` y nunca se usa el nombre como ruta), calcula el SHA-256 mientras copia y lo compara con `source_sha256` (distinto es fallo permanente); ejecuta `Analyzer.analyze`; si el caso sigue sin cancelarse escribe `add_once(case_id, subtask_id, findings)`; borra el directorio en `finally`. El directorio usa el id con `:` sustituido, porque `:` no es válido en Windows.
5. Reporte: `Reporter.report` con `outputs=[]`, `status` `completed`/`failed`, `error_type` y `attempts`; el coordinador cierra el barrier; después `acknowledge`. Reporte antes de confirmar: si el worker muere en medio, la sub-tarea vuelve y el reporte duplicado se ignora por idempotencia (AD-03, AD-21).
6. Fallo transitorio (`fallos.es_transitorio`): `RetrySubtask` programa la espera, el hash vuelve a `pending`, se confirma el elemento y `RedisRetryScheduler.promote_due` (llamado por el reaper) lo devuelve a `queue_for(kind)` con su `payload`. Fallo permanente: reporte `failed` inmediato.
7. Cancelación: antes del reclamo (el JSON sigue en cola) se confirma sin procesar; en curso, `cancel:{caso}` cancela el grupo de procesos FFmpeg de la extracción de fotogramas y el worker comprueba la clave entre fotogramas y antes de escribir hallazgos; un análisis ya iniciado en el proceso termina y su resultado se descarta (ver pregunta 1).

### Clasificación de fallos (SUP-50, provisional)

**Transitorios** (reintento con espera): `TimeoutError`, `MemoryError`, `BlockingIOError`, `InterruptedError`, `PermissionError` (los de F-11 y los que F-09 deja propagar), errores de red hacia MinIO (`ConnectionError`, `urllib3.exceptions.HTTPError`, `minio.error.S3Error` con 5xx) y `KeyUnavailable`. **Permanentes** (`failed` de inmediato): `ValueError` (entrada ilegible), `FormatoDeChatInvalido`, extensión sin parser (`.csv`), `UnicodeDecodeError`, `KeyError` (objeto inexistente), `DecryptionError`, SHA-256 distinto, y cualquier `ProcessingError` de FFmpeg (consistente con F-11, riesgo 15). Lo no clasificado es permanente, para no repetir un error de lógica N veces.

### Decisiones propuestas (se registran en `docs/ARQUITECTURA.md` §8 en la fase de documentación; AD-50 ya existe, el siguiente libre es AD-51)

- **AD-51 (provisional): worker tipado, un proceso por tipo.** *Decisión:* un proceso por `WORKER_KIND` que consume `queue:{kind}` con `BLMOVE` (AD-03), con concurrencia 1, modelos cargados una vez, el hash `subtask:{id}` como fuente de verdad del reclamo y del reporte (resuelve el «provisional» de AD-47: el hash no pasa a solo-lectura), reencolado siempre en formato `Subtask` (el hash guarda `payload`) y límite de intentos aplicado al reclamar. *Alternativas:* (a) un solo proceso con los tres tipos, que no aísla un OOM por tipo (AD-05) y suma las huellas de los tres modelos; (b) un subproceso por sub-tarea (AD-08), que cancela de verdad pero recarga los modelos en cada sub-tarea o exige `fork` tras la carga (F-19, medición pendiente de M1); (c) ampliar `Worker` con `text|image|audio`, que mezcla dos caminos con colas, reintentos y SET/LIST de `inflight` distintos. *Criterio:* aísla fallos por tipo, reutiliza `RedisTypeQueue`, F-11 y la admisión sin reescribirlos, y es el cambio mínimo que cumple US-43. *Fuente:* AD-03, AD-05, AD-06, AD-08, AD-47. *Medición pendiente:* huellas de los modelos (M1) y concurrencia segura de cada modelo.
- **AD-52 (provisional): video como fotogramas muestreados en el worker de imagen.** *Decisión:* FFmpeg extrae un fotograma cada `FRAME_EVERY_S` segundos con un tope de `FRAME_MAX`; cada uno pasa por `ImageAnalyzer`; los hallazgos se enlazan al SHA del video con la posición `fotograma t=<s>s caja x1,y1,x2,y2`; el audio sigue en la sub-tarea AUDIO. *Alternativas:* analizar solo un fotograma (miniatura): pierde casi todo el video; un fotograma por segundo sin tope: el costo crece con la duración (RF-22 pide videos de 200 MB o más); un worker de video aparte: amplía alcance. *Criterio:* acota el costo de CPU y memoria, reutiliza el invocador con grupo de procesos de `multimedia_processor` y cumple SUP-11 («se extraen audio y fotogramas con FFmpeg»). *Fuente:* SUP-11, AD-46, `multimedia_processor._run_supervised`. *Medición pendiente:* cadencia y tope se fijan sin medir.
- **AD-53 (provisional): prioridad unificada `normal`/`high`.** *Decisión:* `Priority` sigue con cuatro niveles; `to_contract`/`from_contract` en dominio son el único mapeo, y los hashes y la API usan `normal|high`; el JSON de la cola conserva los nombres del enum para no perder `BAJA`/`CRITICA`. *Alternativas:* migrar el contrato a `media`/`alta` (rompe `recovery`, `RedisRetryScheduler`, `docs/WORKER_CONTRACT.md` y la API); mapeo duplicado en cada módulo. *Criterio:* el contrato ya publicado manda y el mapeo único evita las divergencias actuales. *Fuente:* `docs/WORKER_CONTRACT.md`, RF-28.
- **AD-54 (provisional): hallazgos idempotentes por sub-tarea.** *Decisión:* `add_once` escribe la lista de hallazgos y marca la sub-tarea en un SET de control dentro de una sola transacción `WATCH/MULTI`; una segunda escritura de la misma sub-tarea no agrega nada ni repite la alerta. *Alternativas:* `HSETNX` o `SADD` seguidos de `RPUSH` (no atómicos: si el worker muere en medio se pierden los hallazgos y el reintento no los repone); script Lua (no probable con `fakeredis` en este entorno); deduplicar al leer (oculta pero no evita el crecimiento y distorsiona los conteos). *Criterio:* cumple AD-21/AD-03 (entrega al menos una vez compensada con idempotencia) y es verificable sin Lua. *Fuente:* AD-03, AD-21.

### Supuestos propuestos (se registran en `docs/REQUERIMIENTOS.md` §3; el último es SUP-46, el siguiente libre es SUP-47)

- **SUP-47 (provisional):** una fuente `.csv` se admite en la descomposición (SUP-40) pero no tiene parser; su sub-tarea de texto falla de forma permanente con un mensaje legible. No se amplía el alcance.
- **SUP-48 (provisional, Medición pendiente):** muestreo de video: un fotograma cada `FRAME_EVERY_S=5` segundos y como máximo `FRAME_MAX=20` fotogramas, ambos configurables y validados (> 0). Sin dato medido que los fundamente.
- **SUP-49 (provisional):** un video sin pista de audio no es un error: su sub-tarea AUDIO termina `completed` sin hallazgos. El video se identifica por la extensión de la fuente y la ausencia de pista se comprueba con `ffprobe`.
- **SUP-50 (provisional):** la clasificación de fallos transitorios y permanentes del worker tipado (sección anterior).
- **SUP-51 (provisional):** el límite de intentos N (SUP-45) se aplica al reclamar: una sub-tarea que llega a N reclamos sin reportar falla con `WorkerLostError`, igual que `recover_subtask` en el camino heredado.

### Despliegue (parte 6)

- **Imagen:** `Dockerfile.worker` queda para el worker FFmpeg, el reaper y el coordinador. Se crea `Dockerfile.analisis` (Python 3.13, AD-22) con `ARG KIND` que instala `requirements-texto.txt`, `requirements-imagen.txt` o `requirements-audio.txt` (el de audio incluye el de texto), `torch` CPU antes que el resto (como indican esos archivos), FFmpeg, `src`, `scripts` y `config`. El UID 10001 y `WORK_DIR=/scratch` se mantienen; `verificar_workers.py` la comprueba.
- **Servicios:** `deploy/docker-compose.analisis.yml` con `worker-texto`, `worker-imagen` y `worker-audio`, cada uno con `profiles` para que cada nodo active los tipos que le tocan, `hostname` desde `NODE_NAME`, `mem_limit` igual a `memswap_limit` por servicio (variables obligatorias, sin valor por defecto), `read_only`, `cap_drop: ALL`, `no-new-privileges`, `user: 10001:10001`, `scratch`, `tmpfs`, y sin `--scale` (AD-23). Con `read_only` los pesos van a un volumen dedicado (`HF_HOME`, y el directorio de pesos de YOLO).
- **Variables** (`.env.example` y `docs/DEPLOY_WORKERS.md`): `WORKER_KIND`, `OBJECTS_BUCKET`, `KEK_FILE`, `FOOTPRINT_TEXT_BYTES`, `FOOTPRINT_IMAGE_BYTES`, `FOOTPRINT_AUDIO_BYTES`, `ADMISSION_MARGIN_BYTES`, `FRAME_EVERY_S`, `FRAME_MAX`, rutas de modelos y `CONFIG_DIR`.
- **KEK:** se documenta el procedimiento para generarla fuera del repositorio (repositorio público, RNF-08, B.5 M4), copiarla a los tres nodos y montarla `:ro` con modo `0400` o `0600`. `FileKeyProvider` rechaza cualquier otro modo; ver pregunta 6 sobre bind mounts desde Windows.
- **Nodo A:** `docker-compose.yml` pasa `OBJECTS_BUCKET`, `STAGING_DIR` y `KEK_FILE` (montada `:ro`) al coordinador, que hoy no los recibe.
- **Redundancia:** cada tipo en al menos dos nodos (ARQUITECTURA §6), para reasignar tras una caída.
- **Verificadores:** `scripts/verificar_workers.py` y `scripts/preflight.py` incluyen el nuevo compose y el nuevo Dockerfile; `tests/unit/test_despliegue_compose.py` conserva el servicio `worker`.

## Pruebas

Las unitarias no usan red, `sleep` ni reloj real (reloj, jitter, supervisor y analizadores inyectados; `fakeredis` y dobles de `tests/dobles.py`). Las de integración usan `fakeredis`, modelos falsos y, donde se indica, FFmpeg real. Los datos son sintéticos (RNF-04, RNF-05). Los contratos existentes (`comprobar_work_queue`, `comprobar_finding_store`, `comprobar_analyzer`, `comprobar_object_store`, `comprobar_retry_scheduler`, `comprobar_case_state_store`) deben seguir pasando sin cambios.

| Parte | Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|---|
| 1 | Unitaria | `test_prioridad_se_mapea_a_normal_y_high_en_un_solo_lugar` | `tests/unit/test_priority_contrato.py` | `MEDIA` y `ALTA` ida y vuelta con `normal` y `high`; otro texto o `BAJA` lanzan `ValueError` |
| 1 | Unitaria | `test_recovery_reencola_en_formato_subtask_en_la_cola_tipada` | `tests/test_recovery.py` | Una sub-tarea tipada vuelve a `queue:{kind}` como el JSON del `payload`, no como id plano, y `RedisTypeQueue.take` la lee |
| 1 | Unitaria | `test_promocion_del_reintento_encola_el_json_de_subtask_en_la_cola_tipada` | `tests/unit/test_redis_retry_scheduler.py` | `promote_due` de una sub-tarea tipada encola el `payload` en `queue_for(kind)`; la FFmpeg sigue con el id plano |
| 1 | Unitaria | `test_reaper_devuelve_a_la_cola_el_inflight_tipado_de_un_worker_muerto` | `tests/test_reaper.py` | Con el worker sin heartbeat, lo de `inflight:{worker}` vuelve a su cola, la sub-tarea queda `pending` y el caso `retrying` |
| 1 | Unitaria | `test_reaper_no_toca_el_inflight_tipado_de_un_worker_vivo` | `tests/test_reaper.py` | Un worker con heartbeat conserva su `inflight` |
| 1 | Unitaria | `test_create_case_persiste_los_hashes_antes_de_encolar` | `tests/unit/test_create_case.py` | Con una cola que registra el orden, `subtask:{id}` existe cuando se hace `enqueue` |
| 1 | Unitaria | `test_create_case_no_deja_huerfanos_si_encolar_falla` | `tests/unit/test_create_case.py` | Si `enqueue` falla a medias no quedan `case:{id}`, `subtask:{id}` ni entrada en `cases:registry` |
| 1 | Unitaria | `test_create_case_guarda_prioridad_normal_o_high_en_los_hashes` | `tests/unit/test_create_case.py` | `case:{id}` y `subtask:{id}` guardan `normal` o `high`, y el JSON de la cola conserva el nombre del enum |
| 1 | Integración | `test_cola_tipada_respeta_queue_max_depth_y_responde_retry_after` | `tests/integration/test_rutas_casos_multifuente_fakeredis.py` | Con `QUEUE_MAX_DEPTH` bajo, el caso que no cabe responde 503 con `Retry-After` |
| 1 | Integración | `test_cola_tipada_con_limite_cero_no_rechaza` | `tests/integration/test_rutas_casos_multifuente_fakeredis.py` | `QUEUE_MAX_DEPTH=0` desactiva el límite (AD-12) en vez de rechazar todo |
| 1 | Integración | `test_stats_incluye_las_colas_tipadas` | `tests/integration/test_rutas_casos_multifuente_fakeredis.py` | `GET /stats` informa `queue:text`, `queue:image` y `queue:audio` |
| 1 | Unitaria | `test_take_descarta_un_elemento_ilegible_sin_dejarlo_en_inflight` | `tests/unit/test_redis_type_queue.py` | Un id plano en la cola se registra, se quita de `inflight` y `take` devuelve `None` o el siguiente |
| 2 | Unitaria | `test_crear_almacen_lectura_arma_el_almacen_cifrado_sin_staging` | `tests/unit/test_object_store_fabrica.py` | `EncryptedObjectStore(MinioObjectStore)` con la KEK del entorno, sin `STAGING_DIR` |
| 2 | Unitaria | `test_crear_almacen_lectura_exige_variables_y_tls` | `tests/unit/test_object_store_fabrica.py` | Faltan variables o TLS inválido: `ValueError`, sin valores por defecto inseguros |
| 2 | Unitaria | `test_crear_subidas_sigue_igual_tras_extraer_la_fabrica` | `tests/unit/test_object_store_fabrica.py` | `crear_subidas` conserva su comportamiento y reutiliza la fábrica de lectura |
| 2 | Unitaria | `test_crear_analizador_devuelve_el_analizador_de_cada_tipo` | `tests/unit/test_fabrica_analizadores.py` | Con constructores falsos de modelos, `text`, `image` y `audio` devuelven un `Analyzer` que pasa `comprobar_analyzer` |
| 2 | Unitaria | `test_crear_analizador_rechaza_un_tipo_desconocido` | `tests/unit/test_fabrica_analizadores.py` | Un tipo fuera de `text|image|audio` lanza `ValueError` |
| 2 | Unitaria | `test_crear_analizador_carga_los_modelos_una_sola_vez` | `tests/unit/test_fabrica_analizadores.py` | Dos `analyze` no vuelven a construir los modelos |
| 2 | Unitaria | `test_parser_por_extension_elige_whatsapp_para_txt_y_telegram_para_json` | `tests/unit/test_parser_por_extension.py` | Selección por extensión sin distinguir mayúsculas |
| 2 | Unitaria | `test_parser_por_extension_rechaza_csv_con_error_permanente` | `tests/unit/test_parser_por_extension.py` | `.csv` y cualquier otra extensión lanzan un error clasificado como permanente con mensaje legible (SUP-47) |
| 2 | Unitaria | `test_add_once_agrega_una_sola_vez_por_subtarea` | `tests/unit/test_redis_finding_store.py` | Dos `add_once` de la misma sub-tarea dejan una sola copia de los hallazgos y la segunda devuelve `False` |
| 2 | Unitaria | `test_add_once_cumple_el_contrato_idempotente` | `tests/unit/test_redis_finding_store.py` | `RedisFindingStore` sobre `fakeredis` y `FakeFindingStore` pasan `comprobar_finding_store_idempotente` |
| 2 | Unitaria | `test_add_once_es_atomico_si_la_clave_de_control_cambia_durante_la_transaccion` | `tests/unit/test_redis_finding_store.py` | Un `WatchError` se reintenta y no duplica ni pierde hallazgos |
| 2 | Unitaria | `test_alertas_no_se_repiten_ante_un_add_once_ignorado` | `tests/unit/test_alerting.py` | Una incidencia alta publica una sola alerta aunque la sub-tarea se reintente |
| 2 | Unitaria | `test_clasificacion_de_fallos_separa_transitorios_y_permanentes` | `tests/unit/test_fallos_worker.py` | Cada excepción de «Clasificación de fallos» cae del lado indicado; lo desconocido es permanente |
| 2 | Unitaria | `test_reporte_consolidado_usa_el_almacen_de_lectura` | `tests/unit/test_rutas_reporte.py` | Con el almacén inyectado, `GET /cases/{id}/consolidated-report` responde 200 y no 503 |
| 2 | Unitaria | `test_reporte_consolidado_responde_503_sin_configuracion_del_almacen` | `tests/unit/test_rutas_reporte.py` | Sin variables del almacén responde 503 legible y sin filtrar el entorno |
| 3 | Unitaria | `test_settings_acepta_worker_kind_y_rechaza_valores_invalidos` | `tests/test_config.py` | `WORKER_KIND` acepta `text|image|audio` y rechaza otro valor; sin él, `Worker` no cambia |
| 3 | Unitaria | `test_settings_tipado_exige_la_huella_del_tipo_sin_valor_por_defecto` | `tests/test_config.py` | Sin `FOOTPRINT_TEXT_BYTES` (o su tipo) el arranque falla con mensaje claro |
| 3 | Unitaria | `test_settings_tipado_rechaza_concurrencia_mayor_que_uno` | `tests/test_config.py` | `WORKER_CONCURRENCY` > 1 con `WORKER_KIND` es `ValueError` |
| 3 | Unitaria | `test_directorio_de_trabajo_no_contiene_dos_puntos` | `tests/unit/test_typed_worker.py` | El directorio de una sub-tarea `{caso}:{sha}:{kind}` es válido en Windows y no escapa de `WORK_DIR` |
| 3 | Unitaria | `test_analyze_subtask_descarga_verifica_sha_y_analiza` | `tests/unit/test_analyze_subtask.py` | Con `FakeObjectStore` y `FakeAnalyzer`, el análisis recibe el contenido correcto y los hallazgos se escriben con `add_once` |
| 3 | Unitaria | `test_analyze_subtask_sha_distinto_es_fallo_permanente` | `tests/unit/test_analyze_subtask.py` | Un objeto cuyo SHA no coincide no se analiza y se clasifica permanente |
| 3 | Unitaria | `test_analyze_subtask_objeto_inexistente_es_fallo_permanente` | `tests/unit/test_analyze_subtask.py` | `KeyError` del almacén es permanente |
| 3 | Unitaria | `test_analyze_subtask_borra_el_temporal_aunque_falle` | `tests/unit/test_analyze_subtask.py` | No queda directorio de la sub-tarea tras un éxito ni tras un fallo |
| 3 | Unitaria | `test_analyze_subtask_usa_solo_la_extension_del_nombre_de_la_fuente` | `tests/unit/test_analyze_subtask.py` | Un nombre con `../` o separadores no cambia la ruta del temporal |
| 3 | Unitaria | `test_analyze_subtask_caso_cancelado_no_escribe_hallazgos` | `tests/unit/test_analyze_subtask.py` | Si `cancel:{caso}` aparece durante el análisis, los hallazgos se descartan |
| 3 | Unitaria | `test_reclamo_pasa_el_caso_a_processing_y_cuenta_el_intento` | `tests/unit/test_typed_worker.py` | `status=assigned`, `attempts+1`, `worker_id` y caso `processing` con `started_at` solo la primera vez |
| 3 | Unitaria | `test_subtarea_inexistente_se_confirma_sin_procesar` | `tests/unit/test_typed_worker.py` | Sin hash, se hace `acknowledge` y no se analiza ni se reporta |
| 3 | Unitaria | `test_subtarea_terminal_se_confirma_sin_procesar` | `tests/unit/test_typed_worker.py` | Una sub-tarea `completed`, `failed` o `cancelled` se confirma sin reprocesar |
| 3 | Unitaria | `test_caso_cancelado_en_cola_marca_la_subtarea_cancelada_y_confirma` | `tests/unit/test_typed_worker.py` | El JSON de un caso cancelado no se procesa y `inflight` queda vacío |
| 3 | Unitaria | `test_exito_reporta_completed_y_confirma_el_inflight` | `tests/unit/test_typed_worker.py` | El reporte lleva `completed`, `outputs=[]`, `attempts` y el `acknowledge` ocurre después del reporte |
| 3 | Unitaria | `test_fallo_permanente_reporta_failed_con_su_tipo_de_error` | `tests/unit/test_typed_worker.py` | Un `ValueError` se reporta `failed` con `error_type` y sin reintento |
| 3 | Unitaria | `test_fallo_transitorio_programa_reintento_y_confirma` | `tests/unit/test_typed_worker.py` | Un `TimeoutError` programa la espera con `RetrySubtask`, el hash queda `pending`, el caso `retrying` y no se reporta |
| 3 | Unitaria | `test_intentos_agotados_al_reclamar_reportan_worker_lost_sin_procesar` | `tests/unit/test_typed_worker.py` | Con `attempts` igual a `MAX_ATTEMPTS` se reporta `failed` con `WorkerLostError` y no se llama al analizador |
| 3 | Unitaria | `test_admision_de_memoria_deja_la_subtarea_en_cola` | `tests/unit/test_typed_worker.py` | Sin memoria para la huella del tipo no se llama a `take` |
| 3 | Unitaria | `test_al_iniciar_reencola_su_propio_inflight` | `tests/unit/test_typed_worker.py` | Con el mismo `worker_id`, lo que quedó en `inflight` vuelve a la cola antes de consumir |
| 3 | Unitaria | `test_stop_event_termina_la_subtarea_en_curso_y_no_toma_otra` | `tests/unit/test_typed_worker.py` | Con `stop_event` activo el bucle sale sin tomar otro elemento |
| 4 | Unitaria | `test_muestreo_de_fotogramas_acota_cantidad_y_cadencia` | `tests/unit/test_frame_sampling.py` | Para una duración dada se devuelven marcas cada `FRAME_EVERY_S` y nunca más de `FRAME_MAX` |
| 4 | Unitaria | `test_muestreo_rechaza_parametros_invalidos` | `tests/unit/test_frame_sampling.py` | Cadencia o tope no positivos, o no finitos, lanzan `ValueError` |
| 4 | Unitaria | `test_comando_de_fotogramas_usa_cadencia_tope_y_salida_en_scratch` | `tests/test_multimedia_processor.py` | El comando FFmpeg incluye la cadencia, el tope y escribe solo bajo el directorio de la sub-tarea |
| 4 | Unitaria | `test_extraer_fotogramas_usa_el_supervisor_de_la_subtarea_para_poder_cancelar` | `tests/test_multimedia_processor.py` | Con un supervisor falso, el proceso se lanza por el supervisor y se cancela con él |
| 4 | Unitaria | `test_video_analiza_cada_fotograma_y_une_los_hallazgos_con_posicion_de_tiempo` | `tests/unit/test_analyze_video.py` | Con extractor y analizador falsos, cada hallazgo lleva `fotograma t=<s>s caja x1,y1,x2,y2` |
| 4 | Unitaria | `test_hallazgos_de_fotograma_apuntan_al_sha_del_video_original` | `tests/unit/test_analyze_video.py` | El `EvidenceRef` de cada hallazgo usa el SHA del video, no el del fotograma |
| 4 | Unitaria | `test_video_sin_fotogramas_es_fallo_permanente` | `tests/unit/test_analyze_video.py` | Cero fotogramas extraídos no se reporta como éxito vacío |
| 4 | Unitaria | `test_video_ilegible_es_fallo_permanente` | `tests/unit/test_analyze_video.py` | Un `ProcessingError` de FFmpeg se clasifica permanente |
| 4 | Unitaria | `test_fotogramas_se_borran_aunque_falle_el_analisis` | `tests/unit/test_analyze_video.py` | No quedan fotogramas en `/scratch/<subtarea>` tras éxito ni fallo |
| 4 | Unitaria | `test_cancelacion_entre_fotogramas_detiene_el_analisis` | `tests/unit/test_analyze_video.py` | Con `cancel:{caso}` activo no se analizan los fotogramas restantes |
| 4 | Unitaria | `test_audio_de_video_sin_pista_termina_completed_sin_hallazgos` | `tests/unit/test_analyze_subtask.py` | Una fuente con extensión de video sin pista de audio da lista vacía y no un fallo (SUP-49) |
| 4 | Unitaria | `test_posicion_de_fotograma_se_interpreta_como_localizador_de_fotograma` | `tests/unit/test_evidence_position.py` | `parse_position` devuelve `FrameLocator` y no `UnknownLocator` |
| 4 | Unitaria | `test_reporte_serializa_el_localizador_de_fotograma` | `tests/unit/test_report_json.py` | `report_to_dict` emite `{"tipo": "fotograma", ...}` |
| 4 | Integración | `test_extraer_fotogramas_de_un_video_sintetico_con_ffmpeg_real` | `tests/integration/test_fotogramas_ffmpeg.py` | Con FFmpeg real y un video generado con `testsrc`, se extraen los fotogramas esperados (se omite sin FFmpeg) |
| 5 | Integración | `test_caso_multifuente_se_procesa_de_punta_a_punta_y_cierra_completed` | `tests/integration/test_pipeline_tipado.py` | `POST /cases` con texto, imagen, audio y video, tres workers tipados y `POST /subtasks/report`: caso `completed` y hallazgos en `case:{id}:findings` |
| 5 | Integración | `test_video_cierra_el_caso_solo_cuando_terminan_la_imagen_y_el_audio` | `tests/integration/test_pipeline_tipado.py` | Con solo la sub-tarea IMAGE terminada el caso sigue `processing` |
| 5 | Integración | `test_video_con_fotogramas_produce_hallazgos_con_posicion_de_tiempo` | `tests/integration/test_pipeline_tipado.py` | Los hallazgos del video tienen posición de tiempo y su evidencia resuelve a la fuente |
| 5 | Integración | `test_video_sin_pista_de_audio_cierra_completed` | `tests/integration/test_pipeline_tipado.py` | El caso cierra `completed` con la sub-tarea AUDIO vacía |
| 5 | Integración | `test_video_ilegible_cierra_partially_completed` | `tests/integration/test_pipeline_tipado.py` | Un video ilegible falla sus dos sub-tareas o solo la IMAGE y el caso cierra con el estado que corresponde por SUP-05 |
| 5 | Integración | `test_texto_txt_y_json_se_analizan_con_su_parser` | `tests/integration/test_pipeline_tipado.py` | Una exportación de WhatsApp y una de Telegram producen hallazgos por mensaje |
| 5 | Integración | `test_texto_csv_falla_de_forma_permanente_y_legible` | `tests/integration/test_pipeline_tipado.py` | `.csv` termina `failed` con `error_type` legible y el caso cierra `partially_completed` o `failed` |
| 5 | Integración | `test_extension_invalida_se_rechaza_al_crear_el_caso` | `tests/integration/test_pipeline_tipado.py` | Una extensión no admitida da 422 y no encola nada (RF-02) |
| 5 | Integración | `test_utf8_invalido_falla_de_forma_permanente` | `tests/integration/test_pipeline_tipado.py` | Un texto con bytes no UTF-8 termina `failed` sin reintentos |
| 5 | Integración | `test_cancelacion_con_el_json_en_cola_no_procesa_la_subtarea` | `tests/integration/test_pipeline_tipado.py` | Tras `POST /cases/{id}/cancel` el worker confirma sin analizar y `inflight` queda vacío |
| 5 | Integración | `test_cancelacion_con_ffmpeg_en_curso_termina_el_subproceso_y_borra_los_fotogramas` | `tests/integration/test_pipeline_tipado.py` | Con un supervisor falso, `cancel:{caso}` cancela el grupo de procesos y no quedan temporales (RF-12) |
| 5 | Integración | `test_fallo_transitorio_se_reintenta_con_espera_y_vuelve_a_la_cola_con_formato_subtask` | `tests/integration/test_pipeline_tipado.py` | Con `FakeClock` el caso pasa por `retrying`, el reaper promueve y la sub-tarea se procesa y cierra una sola vez |
| 5 | Integración | `test_reintentos_agotados_cierran_el_caso_con_el_estado_correcto` | `tests/integration/test_pipeline_tipado.py` | Tras N intentos la sub-tarea queda `failed` y el barrier cierra |
| 5 | Integración | `test_worker_muerto_su_inflight_lo_recupera_el_reaper_y_otro_worker_cierra_el_caso` | `tests/integration/test_pipeline_tipado.py` | Un worker que deja un elemento en `inflight` sin heartbeat: el reaper lo devuelve, otro worker lo procesa y el caso cierra con los hallazgos una sola vez |
| 5 | Integración | `test_subtarea_veneno_agota_los_intentos_y_falla_sin_bucle` | `tests/integration/test_pipeline_tipado.py` | Una sub-tarea que mata siempre al worker falla con `WorkerLostError` al llegar a N reclamos |
| 5 | Integración | `test_admision_de_memoria_deja_en_cola_a_los_tres_tipos` | `tests/integration/test_pipeline_tipado.py` | Con memoria insuficiente cada worker tipado deja su cola intacta (RF-25) |
| 5 | Integración | `test_hallazgos_sin_duplicados_tras_reintento_y_doble_entrega` | `tests/integration/test_pipeline_tipado.py` | Una entrega repetida y un reintento no duplican hallazgos ni alertas |
| 5 | Integración | `test_reporte_consolidado_resuelve_evidencias_con_almacen_cifrado` | `tests/integration/test_pipeline_tipado.py` | Con `EncryptedObjectStore` sobre un almacén en memoria y una KEK de prueba, el reporte contiene las cuatro secciones y cada fragmento resuelve a su objeto (RF-13, RF-14) |
| 5 | Integración | `test_incidencia_alta_publica_alerta_antes_del_cierre` | `tests/integration/test_pipeline_tipado.py` | Una amenaza en texto o un arma en imagen publican la alerta antes de que el caso cierre (RF-16) |
| 5 | Integración | `test_cierre_del_caso_publica_la_alerta_de_cierre` | `tests/integration/test_pipeline_tipado.py` | Al cerrar el barrier se publica la alerta de cierre (RF-15) |
| 5 | Aceptación | `test_caso_completo_registra_el_log_de_punta_a_punta` | `tests/acceptance/test_pipeline_tipado_aceptacion.py` | Con dobles de modelo, el log de un caso de cuatro fuentes se guarda en `docs/evidencia/F-43_caso_completo_<fecha>.md` |
| 5 | Aceptación | `test_tres_workers_de_nodos_distintos_aparecen_en_get_workers` | `tests/acceptance/test_pipeline_tipado_aceptacion.py` | Tres workers con distinto `NODE_NAME` procesan sub-tareas y `GET /workers` muestra tres `hostname`; es una simulación con `fakeredis`, no la evidencia de tres nodos reales |
| 6 | Unitaria | `test_compose_de_analisis_mantiene_el_endurecimiento_de_los_workers` | `tests/unit/test_despliegue_compose.py` | Cada servicio de análisis tiene `read_only`, `cap_drop: ALL`, `no-new-privileges`, usuario 10001, `scratch` y `tmpfs` con tamaño |
| 6 | Unitaria | `test_compose_de_analisis_exige_limites_y_huellas_sin_valor_por_defecto` | `tests/unit/test_despliegue_compose.py` | `mem_limit` y `memswap_limit` obligatorios y sin `--scale` |
| 6 | Unitaria | `test_dockerfile_de_analisis_usa_uid_fijo_y_scratch` | `tests/unit/test_despliegue_compose.py` | El nuevo Dockerfile cumple `incumplimientos_dockerfile` |
| 6 | Unitaria | `test_nodo_a_pasa_kek_bucket_y_staging_al_coordinador` | `tests/unit/test_despliegue_compose.py` | `docker-compose.yml` define `KEK_FILE`, `OBJECTS_BUCKET` y `STAGING_DIR` para el coordinador, sin valores secretos |
| 6 | Unitaria | `test_preflight_acepta_los_servicios_de_analisis` | `tests/unit/test_f16_preflight.py` | `preflight` valida el nuevo compose con límites y huellas obligatorios |

## Mediciones

No aplica: F-43 no es M1 a M5 ni B.6. La evidencia que pide US-43 es funcional: la prueba de extremo a extremo y el log de un caso completo. Se declara explícitamente que:

- **Las huellas de memoria de los tres tipos** (`FOOTPRINT_*_BYTES`) y el margen de admisión no se miden aquí: siguen como «Medición pendiente» de M1 (F-17, F-19). El worker tipado no trae valores por defecto, igual que el worker FFmpeg; el Compose de demostración local usa valores marcados como provisionales.
- **La cadencia y el tope del muestreo de video** (`FRAME_EVERY_S`, `FRAME_MAX`) son configuración provisional sin medir (SUP-48).
- **El log de un caso completo** de la prueba de aceptación usa dobles de modelo: demuestra el pipeline, no la precisión ni el rendimiento de los modelos reales (eso es de las fichas de F-07 a F-09).
- **El reparto por `hostname` en nodos reales** y las pruebas B.6 (F-33 a F-37) con el camino tipado quedan pendientes hasta tener los tres nodos; no se inventan datos.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Las estimaciones son aproximadas: se ajustan al implementar, y si una parte las excede se divide en otra de la pila. Cada parte repite las fases 2 a 6 y la PR se apila sobre la anterior.

| Parte | PR (título en Conventional Commits) | Contenido | Dueño | Líneas aprox |
|---|---|---|---|---|
| 1 | `feat(F-43): plataforma con formato tipado en reencolado, límite y persistencia` | `Priority.to_contract`/`from_contract`; `CreateMultiSourceCase` persiste antes de encolar y compensa; `QueueLimit.from_env` y `Retry-After`; `RedisTypeQueue` con `capacity=0` y `take` tolerante; `_requeue` y `_promote` en formato tipado con `payload`; el reaper recupera `inflight:{worker}` tipado; `/stats` con las tres colas | N, con aviso a J por `recovery.py` y el reaper | ~200 |
| 2 | `feat(F-43): fábricas de almacén y analizadores, hallazgos idempotentes y reporte consolidado` | `crear_almacen_lectura`; `crear_analizador`; `parser_por_extension`; `SubtaskFindingStore` con `add_once` y alertas sin repetirse; `obtener_almacen` real; `es_transitorio`; contrato del worker tipado en `docs/WORKER_CONTRACT.md` | mixta: K (almacén de lectura, hallazgos, alertas, reporte), J (analizadores, parser, fallos) | ~300 |
| 3 | `feat(F-43): worker tipado de texto, imagen y audio` | `Settings` con `WORKER_KIND` y huellas por tipo; `AnalyzeSubtask`; `typed_worker.py` con reclamo, admisión, reintento con `RetrySubtask`, límite al reclamar, recuperación propia, heartbeat y cancelación cooperativa | J | ~330 |
| 4 | `feat(F-43): video por fotogramas en el worker de imagen` | `FrameSampling`; `extract_frames` y `FrameExtractor`; `AnalyzeVideo` con re-sellado del SHA; `FrameLocator` y su serialización; audio de video sin pista | J, con aviso a K por `evidence_position.py` | ~180 |
| 5 | `test(F-43): pruebas de extremo a extremo del pipeline tipado` | Las pruebas I y A de la tabla de la parte 5; el log de un caso completo en `docs/evidencia/` | K | ~0 a 30 (solo pegamento de pruebas si hace falta) |
| 6 | `feat(F-43): despliegue de workers de análisis por nodo` | `Dockerfile.analisis`; `deploy/docker-compose.analisis.yml`; KEK, bucket y staging en el Nodo A; `verificar_workers.py` y `preflight.py` | K | ~200 |

Orden: 1, 2, 3, 4, 5, 6 de abajo hacia arriba; ninguna PR se fusiona sin todos los checks en verde. Si las partes 1 y 2 se confirman independientes del resto, pueden fusionarse antes de empezar la 3.

Documentación de la fase 5 de cada parte: `docs/WORKER_CONTRACT.md` (contrato del worker tipado), `docs/ARQUITECTURA.md` §8 (AD-51 a AD-54 y la nota sobre AD-47), `docs/REQUERIMIENTOS.md` §3 (SUP-47 a SUP-51), `docs/CONTRATOS.md` (filas de `FindingStore` y de los puertos nuevos, `Priority`), `docs/DEPLOY_WORKERS.md`, `docs/IMPLEMENTACION.md` §4 y §5 (prueba roja y comandos de F-43), `.env.example` y `docs/BITACORA_IA.md`.

## Riesgos y preguntas abiertas

La persona que aprueba debe decidir estos puntos; el SPEC propone una opción para cada uno y no la da por resuelta.

1. **Cancelación real de un análisis en curso (RF-12).** Los analizadores corren dentro del proceso del worker (AD-51). Solo la extracción de fotogramas, que es un subproceso, se cancela por grupo de procesos; texto, imagen y audio ya iniciados terminan y se descartan, y la memoria no baja hasta que el análisis acaba. AD-08 prevé un subproceso por sub-tarea. Propuesta: aceptar el límite en esta feature, declararlo en `docs/WORKER_CONTRACT.md` y en la ficha, y dejar un subproceso con `fork` tras cargar el modelo para cuando F-19 mida las estrategias de carga. Alternativa: un subproceso por sub-tarea que recarga el modelo cada vez (más lento y con mayor pico de memoria). ¿Se acepta el límite?
2. **Prioridad sin efecto en el orden (F-20).** En el camino tipado `high` no adelanta a `normal`: la cola es una LIST por tipo y el aging es de F-20 (Nahúm). ¿Se acepta que `priority=high` solo se conserve y se reporte hasta que F-20 decida AD-04 frente a AD-46, o se pide a Nahúm una cola `queue:{tipo}:high` provisional?
3. **Conformidad con «Una feature de módulo no puede depender de otro responsable» (AGENTS.md).** F-43 es de integración y toca archivos de N, J, V y K. ¿Se confirma que K coordina la pila y que cada dueño revisa su parte? La persona ya avisará a los demás; falta confirmar la asignación de la parte 1 (de N, con apoyo de K) y de las partes 3 y 4 (de J).
4. **Parte 5 sin pruebas en rojo.** Las pruebas de extremo a extremo se escriben cuando las partes 1 a 4 ya existen y pasan en verde desde el principio, y no hay código nuevo: la fase `tests` exige que fallen y la de `implementacion` exige código. Se prevé `aprobar --excepcion` en ambas con motivo registrado. Alternativa: que cada parte 1 a 4 agregue su prueba de integración en rojo y la parte 5 solo complete los casos transversales.
5. **Clasificación de fallos (SUP-50).** `PermissionError` es transitorio por F-11, pero un `PermissionError` al escribir el directorio de trabajo no mejora con reintentos; `KeyUnavailable` se reintenta aunque el operador deba corregir la KEK. ¿Se aprueba la lista, o `KeyUnavailable` es permanente? Hoy `StorageError` (camino heredado) es transitorio aunque el objeto falte (F-11, riesgo 16); en el camino tipado el objeto inexistente es `KeyError`, permanente.
6. **KEK y permisos desde Windows.** Los nodos B, C y D son Windows con Docker Desktop sobre WSL2 (SUP-04) y `FileKeyProvider` solo acepta archivos `0400` o `0600`. **No verificado:** un bind mount desde NTFS suele mostrar modo 0777 en el contenedor, y el worker rechazaría la llave. Propuesta: la KEK vive en el sistema de archivos de la distro WSL2 (con `chmod 0400`) y se monta desde ahí; probarlo en un nodo real antes de documentarlo como procedimiento. La variable `KEK` en base64 queda solo para desarrollo (SUP-30).
7. **Memoria por nodo y reparto de tipos.** Cada tipo debe estar en al menos dos nodos, pero tres procesos con torch, dos modelos de HuggingFace, YOLO y Whisper pueden no caber juntos en un nodo. Sin huellas medidas (M1 pendiente) no se puede decidir qué tipo va a qué nodo. Propuesta: `profiles` en el Compose y `COMPOSE_PROFILES` en el `.env` de cada nodo; la asignación se fija al medir. ¿Quién decide la asignación inicial?
8. **Pesos de modelos y red.** Los pesos de HuggingFace (unos 870 MB según el plan, **no medido aquí**) y de YOLO no están en el repositorio. Con `read_only` van a un volumen, y la primera carga descarga de internet. Propuesta: precargarlos al desplegar y fijar `HF_HUB_OFFLINE=1` después. ¿Se admite internet en la primera carga, o hay un espejo?
9. **Hasta dónde llega la recuperación de sub-tareas atascadas.** El reaper recupera el `inflight` tipado solo de workers sin heartbeat. Una sub-tarea colgada en un worker vivo (por ejemplo una inferencia que no termina) no se recupera por `REAPER_MAX_AGE`, que solo mira el SET heredado. Propuesta: no cubrirlo aquí; queda como límite conocido para F-34.
10. **Entrega al menos una vez.** Si el worker muere después de programar un reintento y antes de confirmar el elemento, el reaper devuelve el elemento y `promote_due` puede encolar un duplicado. El segundo reclamo reprocesa; los hallazgos (AD-54) y el reporte (SADD) son idempotentes, pero se pierde cómputo. Se declara como límite; no se corrige con transacciones entre una LIST y un ZSET.
11. **Ventana entre comprobar la cancelación y escribir hallazgos.** Un caso cancelado justo entre ambos pasos puede dejar hallazgos de una sub-tarea cancelada. El estado del caso sigue siendo `cancelled` (terminal) y el reporte los muestra. Se declara como límite.
12. **Orden de pila 1 y 2 respecto de F-20.** La parte 1 toca `rutas_casos.py`, `redis_type_queue.py` y `redis_retry_scheduler.py`, que F-20 parte 3 también puede tocar. No se verificó con Nahúm si hay una rama abierta; `git branch -r` no muestra ninguna de F-20 parte 3. Si aparece, se coordina antes de la parte 1.
13. **Duplicado de `include_router(rutas_archivos.router)` en `main.py`.** Se observa que `rutas_archivos.router` se registra dos veces en `crear_app`; no es de F-43 y no se corrige aquí, pero puede producir rutas repetidas en la documentación de OpenAPI. Se informa a Melany.
14. **Numeración.** AD-50 y SUP-46 están en `main`; AD-51 a AD-54 y SUP-47 a SUP-51 se numeran contra `main` y contra las ramas remotas actuales (ninguna los usa). Si otra rama los toma antes, se renumeran en la parte 2.
15. **Fuentes citadas (Parte I §9, RNF-24).** El código nuevo cita las fuentes que ya citan los analizadores (Ultralytics AGPL-3.0, faster-whisper MIT, pysentimiento, spaCy) y FFmpeg para el muestreo; el artículo de AWS «Exponential Backoff And Jitter» sigue citado en `retry.py`. Las licencias de los pesos no cambian respecto a AD-26 a AD-28.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Sonnet 5.5, subagente arquitecto | 2026-11-12 | Subagente independiente. Verifiqué: sin caracteres de puntos suspensivos Unicode; diff solo toca docs/specs/F-43/SPEC.md; AD-50 y SUP-46 ya existen en main, por lo que AD-51 a AD-54 y SUP-47 a SUP-51 no colisionan; los nombres de prueba y archivos por parte cubren cada elemento del plan aprobado; la pila de 6 partes divide la parte 3 del plan para respetar 400 líneas. Decisiones del supervisor sobre las preguntas abiertas: se aceptan el límite de cancelación de analizadores en curso, que high no reordene la cola (F-20 es de otro responsable) y la clasificación de fallos; la parte 5 usará aprobar con excepcion; KEK, reparto por nodo y pesos de modelos quedan como pendientes de despliegue real. No verifiqué las afirmaciones de código una por una, solo las que fundamentan AD y SUP. (becaaf37) |
| plan | Kenni Rodriguez | 2026-11-12 |  |
| verificación IA de tests | Claude Sonnet 5.5, subagente developer | 2026-11-12 | Subagente independiente. Ejecuté yo los 7 archivos de prueba: 15 failed y 48 passed, todos los fallos por funcionalidad faltante (to_contract, hashes antes de encolar, formato tipado, capacidad cero, stats). Diff fuera de tests solo toca el SPEC (fila de verificación). Nombres exactos de la tabla del SPEC. Decisión del supervisor: se acepta que la compensación al fallar enqueue borre también lo ya encolado, por el criterio sin huérfanos. Dos pruebas pasan hoy a propósito (guarda de regresión del reaper con worker vivo y una endurecida). (206d324b) |
