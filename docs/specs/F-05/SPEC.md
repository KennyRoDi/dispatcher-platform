# SPEC F-05: Descomponer y enrutar

**Fase:** cerrada
**Base:** main
**Verificación IA:** revision 70730a9
**Historia:** US-05 · **Requisitos:** RF-04, RF-05 · **Responsable:** N

## Objetivo

El coordinador hoy no descompone un caso por tipo de contenido. Cada sub-tarea nace ya resuelta por el cliente a una de las 5 operaciones de FFmpeg y va a `queue:{operacion}` (`src/coordinator/rutas_casos.py:46-49,114`); no existen colas por texto, imagen y audio, ni la regla de que un video produce sub-tareas de audio e imagen. El enunciado exige «colas de trabajo con descomposición del caso en sub-tareas y **routing por tipo de contenido** hacia workers especializados» (B.4, línea 301) y RF-04/RF-05 piden sub-tareas trazables a su fuente y al caso, y que texto, imagen y audio lleguen solo a colas consumidas por su tipo de worker.

Esta feature entrega, para el coordinador (Nahúm) y los workers de F-07 a F-09, una función pura que descompone un caso en sub-tareas y un mapa tipo→cola, más el caso de uso que las encola por el puerto `WorkQueue`, con un log de routing como evidencia.

**Qué existe y qué falta (verificado en el código):**

| Pieza | Estado | Dónde |
|---|---|---|
| `Subtask` con `case_id`, `source_sha256`, `kind`; `ContentKind` = TEXT, IMAGE, AUDIO (sin video) | Existe | `src/domain/subtask.py:7-10,18-27` |
| Puerto `WorkQueue` y su doble `FakeWorkQueue`, con contrato `comprobar_work_queue` | Existe | `src/application/ports.py:63-69`, `tests/dobles.py:79-103`, `tests/contratos.py:21-35` |
| Routing por clase de nodo (cpu/gpu) por tipo, con alternativa | Existe (F-32); es otra cosa: elige clase de nodo, no cola | `src/domain/routing.py:13-37`, `config/routing.toml`, `src/adapters/routing_config.py` |
| Clasificación por extensión, solo `video`/`audio`/`other` | Existe, sin texto ni imagen, atada a FastAPI | `src/coordinator/router.py:35-54` |
| Enrutado a colas por operación FFmpeg, con cola `:high` | Existe, camino heredado que usa el worker FFmpeg | `src/coordinator/router.py:112-118`, `src/coordinator/rutas_casos.py:28-131`, `src/workers/config.py:16-22,176-180` |
| Selección de colas por worker (`WORKER_QUEUES`) | Existe, pero solo admite las 5 operaciones | `src/workers/config.py:74-86,136-137` |
| Descomposición de fuentes (texto, imagen, audio, video) en sub-tareas | **Falta** | n/a |
| Video → sub-tareas de audio e imagen | **Falta** | n/a |
| Mapa tipo→cola de análisis y su log de routing | **Falta** | n/a |
| Adaptador Redis de `WorkQueue` | **Falta** (lo entrega F-06, con `BLMOVE`) | n/a |
| Entidad `Case`/fuente en el dominio | **Falta** (F-01 pendiente) | n/a |

## Alcance

**Incluye:**
- Dominio puro: `SourceKind` (texto, imagen, audio, video), `CaseSource`, `classify_source(nombre)` por extensión, `decompose(...)` y el mapa `queue_for(kind)`.
- Caso de uso `DispatchCase` sobre los puertos `WorkQueue` y `Clock`, que encola cada sub-tarea en la cola de su tipo y registra un log de routing por sub-tarea.
- Adaptador Redis mínimo de `WorkQueue` para colas por tipo (`RPUSH`/`BLPOP`, límite por `LLEN`), provisional hasta que F-06 lo reemplace por `BLMOVE`, para la prueba de integración con `fakeredis`.
- Pruebas de conformidad del adaptador con `comprobar_work_queue`.

**No incluye:**
- Cambiar `Subtask`, `ContentKind` ni `RoutingTable` (contratos compartidos y F-32): el video es un tipo de fuente, no un `ContentKind`.
- Cambiar el camino heredado `POST /cases` y las colas `queue:{operacion}` del worker FFmpeg.
- Elegir la clase de nodo (cpu/gpu): es F-32; las colas de F-05 son por tipo.
- Extraer el audio o los fotogramas de un video (lo hace el worker de F-08/F-09 al recibir la sub-tarea), `BLMOVE` e `inflight` (F-06), límite y `Retry-After` (F-24), prioridad como ZSET (AD-04), documentos adjuntos y la entidad `Case` (F-01).

## Criterios de aceptación

Copiados de `docs/backlog/cola-workers.md` (US-05):

- **Dado** un caso con texto, imagen, audio y video
- **Cuando** se descompone
- **Entonces** cada sub-tarea llega a la cola de su tipo; el video genera sub-tareas de audio e imagen

Pruebas previstas por la historia: U descomposición y mapa de colas; I `fakeredis`; A worker de cada tipo consume solo lo suyo. Demuestra: prueba A. Evidencia: log de routing.

## Diseño

**Contratos.** Usa `WorkQueue`, `Clock` (`src/application/ports.py`), `Subtask`, `ContentKind` y `Priority` sin modificarlos. No implementa ningún contrato nuevo de `docs/CONTRATOS.md`. Programa contra `FakeWorkQueue` y `FakeClock` de `tests/dobles.py`; el adaptador Redis pasa por `comprobar_work_queue`. Toma AD-04 (ZSET por tipo con `puntaje = t_entrada − bono(prioridad)`) como diseño objetivo de las colas por tipo; el adaptador provisional de la parte 2 (`RPUSH`/`BLPOP` sobre listas) se aparta de AD-04 de forma temporal, hasta F-06/M2. De AD-12 usa solo `has_capacity`; el Lua atómico no se implementa aquí. La clase de nodo (AD-18) es de F-32 y no interviene.

**Capas y archivos (todos nuevos; ningún archivo ajeno se toca):**

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/decomposition.py` | `SourceKind`, `CaseSource(sha256, name, kind)`, `classify_source`, `decompose`, `queue_for`, `QUEUE_BY_KIND` |
| Aplicación | `src/application/dispatch_case.py` | `DispatchCase(queue, clock).execute(case_id, sources, priority)` y log de routing |
| Adaptador | `src/adapters/redis_type_queue.py` | `RedisTypeQueue(redis, capacity)` que implementa `WorkQueue` (provisional hasta F-06) |

**Reglas de `decompose`** (decisiones propuestas, ver preguntas abiertas):
- Texto, imagen y audio dan una sub-tarea del mismo `ContentKind`; el video da dos: una `AUDIO` y una `IMAGE`, ambas con el `source_sha256` del video.
- Id determinista `{case_id}:{sha256}:{kind}`: trazable a caso, fuente y tipo, y la misma fuente repetida en un caso produce una sola sub-tarea (sin duplicar evidencia idéntica).
- Orden estable: el de las fuentes y, por fuente, imagen antes que audio.
- `classify_source` reconoce por extensión (sin distinguir mayúsculas): texto `.txt`, `.csv`, `.json`; imagen `.jpg`, `.jpeg`, `.png` (ambas propuesta nuestra); audio `.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`, `.opus`, `.wma`; video `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.m4v`. Una extensión desconocida lanza `ValueError` con el nombre (nunca se descarta en silencio). Las extensiones de audio y video incluyen todas las de `src/coordinator/router.py:35-40`, que no se modifica, para no rechazar lo que el camino heredado acepta.
- Mapa de colas: TEXT→`queue:text`, IMAGE→`queue:image`, AUDIO→`queue:audio`; nombres distintos de los de las operaciones FFmpeg, de modo que no se mezclan con el camino heredado. Se define en dominio como constante; el refactor de IMPLEMENTACION §4 («pasar el mapa a configuración») queda fuera de esta feature.

**`DispatchCase`.** Fija `enqueued_at` con `Clock.now()`, descompone, comprueba `has_capacity` de cada cola destino antes de encolar y, si alguna está llena, lanza `QueueFull` sin haber encolado nada (la comprobación no es atómica entre procesos; es aceptable porque F-24 hace el límite real). Después encola en el orden de `decompose` y emite por sub-tarea un log INFO `routing case=<id> subtask=<id> kind=<tipo> source=<sha256> queue=<cola>`. Devuelve la lista de `(cola, Subtask)`.

**Worker por tipo.** «Consume solo lo suyo» se cumple porque cada worker toma de una única cola por tipo vía `WorkQueue.take(queue, ...)`; la selección de colas del worker FFmpeg (`WORKER_QUEUES`) no cambia. Cablear los workers de F-07 a F-09 a `queue:{tipo}` es de esas features.

**Reutiliza** `Subtask.to_dict`/`from_dict` (serialización en Redis del adaptador), `Priority.from_name`, `FakeWorkQueue` y `comprobar_work_queue`.

**Decisión nueva propuesta** (se registra en `docs/ARQUITECTURA.md` §8 en la fase de documentación, no ahora, junto a AD-04 y no respaldada por AD-18): descomposición por tipo con colas `queue:{tipo}` y video como fuente que se expande, sin ampliar `ContentKind`. Alternativa rechazada: añadir `VIDEO` a `ContentKind`, porque rompe `RoutingTable`, que exige regla por cada `ContentKind` (`src/domain/routing.py:13-20`), y es contrato compartido.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_video_genera_subtareas_de_audio_e_imagen` | Un video da exactamente una sub-tarea `AUDIO` y una `IMAGE` con el `source_sha256` del video |
| Unitaria | `test_caso_heterogeneo_da_una_subtarea_por_fuente_y_dos_por_video` | Texto, imagen, audio y video dan 5 sub-tareas con `case_id`, ids deterministas y orden estable |
| Unitaria | `test_fuente_repetida_no_duplica_subtarea`, `test_extension_desconocida_se_rechaza`, `test_caso_sin_fuentes_da_lista_vacia` | Casos borde de la descomposición y de `classify_source` |
| Unitaria | `test_tipo_enruta_a_su_cola` | `queue_for` cubre todos los `ContentKind` con colas distintas entre sí y distintas de las 5 operaciones FFmpeg |
| Unitaria | `test_dispatch_encola_cada_subtarea_en_la_cola_de_su_tipo`, `test_dispatch_con_cola_llena_no_encola_nada`, `test_dispatch_registra_log_de_routing` | `DispatchCase` con `FakeWorkQueue` y `FakeClock`, sin red ni reloj real; el log trae caso, sub-tarea, tipo, fuente y cola |
| Contrato | `comprobar_work_queue` sobre `RedisTypeQueue` con `fakeredis` | El adaptador cumple el mismo contrato que el doble |
| Integración | `test_dispatch_con_fakeredis_deja_cada_subtarea_en_su_lista` | Con `fakeredis`, `DispatchCase` + `RedisTypeQueue` deja en `queue:text`, `queue:image` y `queue:audio` los payloads esperados y recuperables con `Subtask.from_dict` (marcador `integration`) |
| Aceptación | `test_worker_de_cada_tipo_consume_solo_lo_suyo` | Dado un caso con texto, imagen, audio y video, tres consumidores, uno por cola, toman solo sub-tareas de su `kind`; el video aporta una a audio y otra a imagen; no queda nada sin consumir (marcador `acceptance`, `FakeWorkQueue`) |

## Mediciones

No aplica.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-05): descomponer caso y enrutar por tipo` | Dominio `decomposition.py` y caso de uso `dispatch_case.py` con log de routing, contra los puertos y dobles. Estimado 110 a 140 líneas |
| 2 | `feat(F-05): encolar sub-tareas por tipo en redis` | `redis_type_queue.py`, adaptador provisional de `WorkQueue`, con su contrato y la prueba de integración con `fakeredis`. Estimado 70 a 90 líneas |

## Riesgos y preguntas abiertas

**Decisiones propuestas por el Arquitecto (criterio delegado: la más conveniente y menos problemática):**
1. **Video no entra a `ContentKind`.** Se trata como fuente que se expande; evita cambiar un contrato compartido y romper `RoutingTable` y su TOML.
2. **Colas `queue:text|image|audio`, separadas de las FFmpeg.** No se toca el camino heredado ni a su worker; los dos mundos conviven hasta integrarlos.
3. **Id `{case_id}:{sha256}:{kind}` con deduplicación por fuente.** Es determinista, trazable y reintentable sin duplicar.
4. **Sin cambios al `POST /cases` heredado.** El enganche del coordinador a `DispatchCase` queda para cuando F-01 defina la entidad `Case` con fuentes (de Nahúm también); F-05 entrega lo que ese enganche necesita.
5. **Adaptador Redis provisional en la parte 2.** Es la única forma de cumplir «I `fakeredis`» sin esperar a F-06; se acota a `RPUSH`/`BLPOP` y F-06 lo reemplaza por `BLMOVE` e `inflight`.

**Riesgos y preguntas abiertas:**
- **Solape con F-06.** Ambas son de Nahúm y F-06 también entrega un adaptador Redis de `WorkQueue`. Si F-06 se fusiona antes, la parte 2 se reduce a su prueba de integración y se elimina `redis_type_queue.py`. La persona decide si prefiere eso o mantener la parte 2 como está.
- **Cómo sabe el worker que debe extraer pistas.** `Subtask` no distingue «imagen propia» de «fotogramas de un video»; ambos tienen el mismo `kind` y el `source_sha256` del video. El worker detecta el contenedor por el archivo. Si se quiere explícito, hay que agregar un campo a `Subtask`, que es un cambio de contrato (PR aparte, con aviso a José y Nahúm). No se resuelve aquí.
- **Documentos adjuntos.** El enunciado menciona «video/documento» en casos heterogéneos pero B.4 solo pide routing para texto, imagen, audio y video; quedan fuera y una extensión de documento lanza `ValueError`. Confirmar.
- **Lista de extensiones** de texto, imagen, audio y video es propuesta nuestra; F-02 puede fijar los formatos de chat admitidos. Se alineará cuando exista.
- **Cola llena a mitad de caso.** La comprobación previa de capacidad no es atómica entre procesos y puede dejar un caso parcialmente encolado si hay concurrencia; F-24 (backpressure, en PR) y F-06 lo resuelven. Se declara como límite, sin medición.
- **Desviación de AD-04.** AD-04 prevé ZSET por tipo; el adaptador provisional de la parte 2 usa listas (`RPUSH`/`BLPOP`) y no aplica el puntaje por prioridad. Es temporal, hasta F-06/M2; la persona debe aceptarlo o pedir otro enfoque.
- **Prioridad.** `Subtask.priority` viaja en el payload pero no separa colas (la prioridad como ZSET es AD-04, de M2). El camino heredado sí usa `:high`; no se replica aquí.
- **Evidencia «log de routing».** Se guardará como salida del log de la prueba de aceptación en `docs/evidencia/` en la fase de documentación; no se inventa ni se estima ningún dato.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Claude Sonnet 5.5), subagente arquitecto independiente | 2026-11-11 | Leí el SPEC completo y comprobé con grep y sed: sin marcadores pendientes; criterio de US-05 copiado de docs/backlog/cola-workers.md; RF-04 y RF-05 en REQUERIMIENTOS.md; cita de B.4 en ENUNCIADO.md línea 301; tipos y puertos existentes (ContentKind sin video, QueueFull en src/domain/subtask.py:14, WorkQueue, FakeWorkQueue, comprobar_work_queue, Priority.from_name, RoutingTable exige regla por ContentKind). Hallé 2 defectos (AD-18 mal citado: es routing por clase de nodo de F-32; extensiones no alineadas con router.py:35-40) y los devolví al subagente; verifiqué el diff 572fb48..836a12e: AD-18 fuera, AD-04 como diseño objetivo con la desviación declarada, extensiones completas. Solo cambia docs/specs/F-05/SPEC.md. No ejecuté pruebas: la fase no tiene código. (836a12e) |
| verificación IA de plan | Claude Code (Claude Sonnet 5.5), subagente arquitecto independiente | 2026-11-11 | Releí el SPEC completo y comprobé con grep y sed: sin marcadores pendientes; criterio de US-05 copiado de docs/backlog/cola-workers.md; RF-04 y RF-05 en REQUERIMIENTOS.md; cita de B.4 en ENUNCIADO.md línea 301; tipos y puertos existentes (ContentKind sin video, QueueFull en src/domain/subtask.py:14, WorkQueue, FakeWorkQueue, comprobar_work_queue, Priority.from_name, RoutingTable exige regla por ContentKind). Hallé 2 defectos (AD-18 mal citado, es routing por clase de nodo de F-32; extensiones no alineadas con router.py:35-40), los devolví al subagente y verifiqué el diff 572fb48..836a12e. Solo cambia docs/specs/F-05/SPEC.md. Sin pruebas: la fase no tiene código. (29cda02) |
| plan | Kenni Rodriguez | 2026-11-11 |  |
| verificación IA de tests | Claude Code (Claude Sonnet 5.5), subagente developer independiente | 2026-11-11 | Leí los 3 archivos de prueba completos (235 lineas) y los contraste con la tabla de pruebas del SPEC: cada criterio tiene su prueba (video a audio e imagen, caso heterogeneo, fuente repetida, extension desconocida, caso vacio, mapa de colas, encolado por tipo, cola llena sin encolar nada con la llena no primera, log de routing, aceptacion de un consumidor por cola). Ejecute pytest sobre los 3 archivos: 3 errors por ModuleNotFoundError de src.domain.decomposition y src.application.dispatch_case, es decir rojo por funcionalidad ausente. git diff main..HEAD: solo SPEC y 3 archivos de tests, 0 archivos en src/, dobles.py y contratos.py intactos. Priority.ALTA/MEDIA/BAJA y FakeWorkQueue.take(queue, worker_id, timeout) existen como las usan las pruebas. Las 22 extensiones parametrizadas coinciden con las listas del SPEC. Observacion: el informe del subagente contaba 28 casos y 19 extensiones; el recuento real es 35 casos y 22 extensiones. No verifique que las pruebas pasen al implementar; eso es de la fase siguiente. test_auth_habilitada.py pasa solo (20 passed); no ejecute la suite completa. (32f5896) |
| tests | Kenni Rodriguez | 2026-11-11 |  |
| verificación IA de implementacion | Claude Code (Claude Sonnet 5.5), subagente developer independiente | 2026-11-11 | Lei los dos archivos nuevos completos (src/domain/decomposition.py 69 lineas y src/application/dispatch_case.py 35) contra el SPEC: reglas de decompose, id caso:sha256:tipo, video a imagen y audio en ese orden, mapa de colas, capacidad comprobada antes de encolar y log de routing con el formato pedido; dominio sin imports de infraestructura. git diff 32f5896..HEAD -- tests esta vacio: no se debilito ninguna prueba. Solo cambian 2 archivos de src, 104 lineas, por debajo del limite de 400. Ejecute yo: 43 passed (test_decomposition, test_dispatch_case, test_arquitectura) y 1 passed de aceptacion. Suite rapida completa con el .env local apartado y --basetemp propio: 3467 passed, 86 skipped, 0 failed. Con mi .env local y el disco lleno la suite dio fallos ajenos a F-05, ya diagnosticados: test_auth_habilitada falla porque dotenv.load_dotenv() de src/workers/config.py:129 vuelca en os.environ el MINIO_ENDPOINT del Nodo A cuando ese nodo esta apagado, y los de test_heavy_case_generator fallan por No space left on device (17.8 GB de directorios temporales de pytest, ya borrados); el informe del subagente los llamaba intermitentes. No verificado: la comprobacion de capacidad usa has_capacity booleano, asi que un caso que necesite mas de una plaza en una cola con una sola libre podria encolar parte antes de QueueFull; el SPEC solo declara no atomicidad entre procesos. Se deja para la fase de verificacion. (3c7babd) |
| implementacion | Kenni Rodriguez | 2026-11-11 |  |
| verificación IA de verificacion | Claude Code (Claude Sonnet 5.5), subagente qa-tester independiente | 2026-11-11 | El QA devolvio DEVUELTO con 2 hallazgos; verifique yo mismo: git diff 3c7babd..HEAD -- src vacio (el QA no toco produccion), el arbol queda limpio, 70 passed y 2 xfailed en test_decomposition, test_dispatch_case, los dos archivos _qa y test_arquitectura, mas 1 passed de aceptacion. Reproduje con un script propio QA-1 (FakeWorkQueue(capacidad=1), AUDIO+VIDEO: queda 1 en queue:audio y 1 en queue:image y luego QueueFull en queue:audio) y QA-2 (case_id con salto de linea produce 2 lineas fisicas que empiezan por 'routing case=EVIL'). Reproduje la mutacion que sobrevivio (revisar solo la primera cola): ahora falla test_cola_llena_en_cualquier_posicion_no_encola_nada[queue:image] y al restaurar con git restore pasan 11. Decision del orquestador, aceptando criterio delegado por la persona: QA-1 (media) no se puede cerrar dentro del SPEC porque WorkQueue.has_capacity es booleano; hace falta una consulta de plazas libres en el puerto, que es contrato compartido y trabajo de F-06 y F-24; el codigo cumple el SPEC literal (lanza QueueFull sin encolar si alguna cola esta llena). QA-2 (baja): el case_id lo asigna el coordinador y su validacion es de F-01. Ambos quedan como pruebas xfail estrictas, para documentarlos como limites en la fase de documentacion y en el informe final. Mediciones: No aplica. No ejecute la suite completa en esta verificacion; la ejecuta aprobar. (ec5834f) |
| verificacion | Kenni Rodriguez | 2026-11-11 |  |
| verificación IA de documentacion | Claude Code (Claude Sonnet 5.5), subagente documentador independiente | 2026-11-11 | Verifique el diff b57cde4..686c2e8: solo 3 archivos de docs (ARQUITECTURA.md +1, REQUERIMIENTOS.md +4, docs/evidencia/F-05_log_de_routing_2026-11-11.md nuevo) y 0 archivos fuera de docs; no tocaron src, tests, README, reutilizacion.md ni STATUS.md. AD-46 y SUP-40 a SUP-43 no aparecen en ninguna otra rama remota (git grep sobre todas) y siguen a AD-45 y SUP-39. Lei la fila AD-46 completa: coincide con el codigo y el SPEC, declara AD-04 como diseno objetivo, aclara que AD-18 no la respalda, marca provisional la parte 2 y registra QA-1 y QA-2 como limites con sus pruebas xfail. SUP-40 a SUP-43 coinciden con las listas de extensiones y reglas implementadas. La evidencia es salida cruda real de pytest (1 passed, 5 lineas routing, commit b57cde4, Python 3.13.17) con alcance declarado: FakeWorkQueue en Windows, no Redis ni nodos reales. Recuento real de casos de test_decomposition.py: 35 colectados y 22 de extensiones, como dice el borrador. El AD-44 duplicado en ARQUITECTURA.md lineas 255 y 256 ya esta en origin/main y no es de F-05. Corregi el borrador de bitacora antes de publicarlo: decia aprobaciones de la persona en cada fase, y la persona delego esta ronda de corrido y el orquestador ejecuto aprobar bajo esa delegacion. (686c2e8) |
| documentacion | Kenni Rodriguez | 2026-11-11 |  |
| verificación IA de revision | Claude Code (Claude Sonnet 5.5), subagente revisor independiente | 2026-11-11 | El revisor devolvio APROBADO sin hallazgos bloqueantes tras leer SPEC y diff con contexto nuevo. Relei yo el diff contra origin/main: 11 archivos, 739 insertions y 0 deletions (2 de src con 104 lineas, 5 de tests, SPEC y 3 de docs); todos los commits no-merge en Conventional Commits; busqueda de claves y secretos en el diff: 0; test_arquitectura pasa. Ejecute 70 passed y 2 xfailed en las pruebas de la feature y el QA, mas 1 passed de aceptacion, y la suite completa dio 3467 passed y 0 failed en la fase de implementacion sin cambios posteriores en src. Hallazgo propio: la evidencia incluia la ruta local con el nombre de usuario de Windows (rootdir) en un repositorio publico; ninguna otra evidencia de main tiene rutas locales. Lo devolvi al documentador, que lo anonimizo en 2 commits (0d79298 y 70730a9); verifique que git diff a2ce02e..HEAD toca solo ese archivo y que git grep da 0 menciones en el arbol. Limite que no se puede reparar con un commit: la ruta sigue en el historial de la rama, en el commit 686c2e8; quitarla exige reescribir historia con force push, que no se hizo. Observacion menor del revisor aceptada: sources se anota como list pero acepta cualquier iterable, sin efecto en el comportamiento. Los limites QA-1 y QA-2 siguen documentados con pruebas xfail estrictas. (70730a9) |
| revision | Kenni Rodriguez | 2026-11-11 |  |
