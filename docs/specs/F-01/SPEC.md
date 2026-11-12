# SPEC F-01: Crear caso multifuente

**Fase:** tests
**Base:** main
**Verificación IA:** tests a0ac95a
**Historia:** US-01 · **Requisitos:** RF-01, RF-02 (parcial: rechazo por extensión), RF-03 · **Responsable:** N

## Objetivo

`POST /cases` hoy exige que el cliente especifique manualmente cada sub-tarea (`SubtaskRequest.task_type` + `file_path`, una de las 5 operaciones FFmpeg). No existe una forma de crear un caso a partir de **fuentes** (texto, imagen, audio, video) que el sistema clasifique y enlace a sus objetos automáticamente, como pide RF-01. F-05 ya construyó esa lógica de dominio (`classify_source`, `decompose`, `DispatchCase`) y F-06 el adaptador confiable (`RedisTypeQueue`) — ambos a propósito desconectados de `POST /cases` hasta que F-01 definiera la entidad `Case`.

**Hallazgo clave de esta investigación (verificado en el código, cambia el diseño ingenuo):** el lado de lectura existente (`GET /cases/{id}/report`, `RedisCaseCatalog`) espera el esquema heredado (`case:{id}` hash, `case:{id}:subtasks` lista, `subtask:{id}` hash). Nada consume todavía `queue:text`/`queue:image`/`queue:audio` (F-07/F-08/F-09, ya `hecha`, entregaron solo la lógica `Analyzer.analyze()`, sin un worker que lea esas colas — verificado: ningún archivo fuera de F-05/F-06 las referencia). Si F-01 usara el camino nuevo de forma aislada, los casos quedarían huérfanos (nadie los procesa) y el reporte existente no los vería.

**Decisión del responsable (aprobada en conversación):** F-01 integra ambos mundos: usa `classify_source`/`decompose`/`DispatchCase`/`RedisTypeQueue` de F-05/F-06 para clasificar las fuentes y encolarlas de forma confiable, **pero además** persiste `case:{id}`, `case:{id}:subtasks` y `subtask:{id}` con el mismo esquema que ya usan `GET /cases/{id}`, `/report`, `list_cases` y `cancel_case`, para que seguir funcionando con casos multifuente sin tocarlos. El procesamiento real (un worker que consuma `queue:text/image/audio` y llame a los `Analyzer`) queda fuera de esta feature — F-01 solo entrega «creado y encolado de forma confiable», que es exactamente lo que pide el criterio de aceptación.

## Alcance

**Incluye:**
- `src/coordinator/modelos.py`: `SourceRef(sha256: str, name: str)` y `CaseRequest.sources: list[SourceRef] | None = None` (opcional; si se envía, no se envía `subtasks` y viceversa).
- `src/coordinator/rutas_casos.py::create_case`: si `sources` viene poblado, toma el camino nuevo:
  1. Para cada fuente, verifica `subidas.already_stored(sha256)` (reutiliza la misma instancia de `ChunkedUpload` ya configurada para `rutas_archivos.py`, inyectada con `Depends(rutas_archivos.obtener_subidas)`; **no hace falta exponer un `ObjectStore` nuevo**); si falta alguna, `422` sin encolar nada.
  2. `classify_source(name)` (F-05) por extensión; una extensión no soportada responde `422` con el nombre, sin encolar nada (RF-02 parcial: formato).
  3. `DispatchCase(RedisTypeQueue(...), clock).execute(case_id, case_sources, priority)` (F-05/F-06): decompone, verifica capacidad y encola en `queue:text/image/audio` vía `BLMOVE`-ready `RedisTypeQueue`.
  4. Persiste `case:{id}` (status `queued`, totales, `created_at`, `priority`, `metadata`), `case:{id}:subtasks` y un `subtask:{id}` hash por sub-tarea devuelta (mismos campos que el camino heredado: `status=pending`, `case_id`, `source_sha256`, `file_path`=nombre de la fuente, `task_type`=`kind.value`, `priority`), para que `GET /cases/{id}`, `/report`, `list_cases` y `cancel_case` seguir funcionando sin cambios.
  5. Registra en `cases:registry` (igual que hoy).
- `docs/ARQUITECTURA.md` §8: nueva decisión **AD-47**, coexistencia de los dos esquemas de persistencia hasta que exista un worker consumidor de `queue:text/image/audio` (F-3X futura).

**No incluye:**
- Un worker que consuma `queue:text/image/audio` y llame a `Analyzer.analyze()` (gap real, declarado como riesgo abajo; es una feature de integración aparte, probablemente F-33 a F-37).
- F-02 (validar y normalizar contenido real de las fuentes, ej. exportaciones de WhatsApp/Telegram): F-01 solo rechaza por **extensión** no soportada (ya lo hace `classify_source`), no valida el contenido.
- Cambiar `SubtaskRequest`/el camino `subtasks` existente, ni los endpoints `/cases/{id}/cancel`, `/report`, `list_cases` (se reutilizan sin modificar su lógica interna; solo deben seguir leyendo datos que ahora también puede escribir el camino nuevo).
- Subida de archivos (ya existe vía F-22-25, `POST /uploads` + chunks + `complete` devuelve el `sha256` que este SPEC consume).
- Autenticación/autorización: `("POST", "/cases")` → `Action.CREAR_CASO` → `Role.ANALISTA` ya está completamente cableado en `src/coordinator/seguridad.py`; no se toca.

## Criterios de aceptación

Copiado de `docs/backlog/recepcion-dataset.md` (US-01):

**Dado** un analista autenticado y fuentes de texto, imagen, audio y video
**Cuando** crea el caso
**Entonces** el caso queda `queued` con 4 fuentes enlazadas a sus objetos

**Pruebas:** U `test_crear_caso_con_varias_fuentes_las_registra`. I API con Redis y MinIO. A caso heterogéneo por el cliente de carga.
**Demuestra:** prueba A. **Evidencia:** respuesta de `GET /cases/{id}`.

## Diseño

**Contratos usados (sin modificar):**
- `classify_source`, `decompose`, `queue_for`, `CaseSource` (`src/domain/decomposition.py`, F-05)
- `DispatchCase` (`src/application/dispatch_case.py`, F-05)
- `RedisTypeQueue` (`src/adapters/redis_type_queue.py`, F-06)
- `ChunkedUpload.already_stored(sha256)` (`src/application/chunked_upload.py`, F-22/F-23, instancia ya configurada en `rutas_archivos.py`): valida que la fuente ya se subió, sin exponer un `ObjectStore` nuevo
- `Role.ANALISTA` → `Action.CREAR_CASO` (`src/domain/rbac.py`, ya cableado en `seguridad.py`)

**Archivos a crear/modificar** (todos de Nahúm, M2/coordinador):
- `src/coordinator/modelos.py` (existente): agregar `SourceRef`, campo `sources` opcional en `CaseRequest`
- `src/coordinator/rutas_casos.py` (existente): rama nueva en `create_case` para `sources`
- `tests/unit/test_rutas_casos_multifuente.py` (nuevo): U del camino nuevo con dobles
- `tests/integration/test_rutas_casos_multifuente_fakeredis.py` (nuevo): I con `fakeredis`/doble de `ChunkedUpload`
- `tests/acceptance/test_caso_heterogeneo_cliente_de_carga.py` (nuevo): A, caso con 4 fuentes

**Decisión nueva propuesta (AD-47, se registra en `docs/ARQUITECTURA.md` §8 en la fase de documentación):**
- Mientras no exista un worker consumidor de `queue:text/image/audio`, cada sub-tarea del camino nuevo se persiste **dos veces**: como `Subtask` JSON en la cola de su tipo (para que `WorkQueue`/F-06 funcione y, a futuro, un worker real la tome) y como `subtask:{id}` hash heredado (para que el reporte/consulta existente siga funcionando). Alternativa rechazada: migrar `GET /cases/{id}/report` a leer directamente las colas tipadas — se descarta porque rompería casos creados por el camino heredado (`subtasks` manual), que siguen en uso, y porque el reporte necesita leer sub-tareas ya *despachadas y en progreso*, no solo encoladas.

**Reutilización del I Proyecto:**
- Ninguna adicional a la ya declarada en F-05/F-06

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_crear_caso_con_varias_fuentes_las_registra` | `tests/unit/test_rutas_casos_multifuente.py` | Con `fakeredis` y un doble de `ChunkedUpload`, un caso con 4 fuentes (texto, imagen, audio, video) persiste `case:{id}` en `queued`, 5 `subtask:{id}` (video expande a audio+imagen) y encola cada una en su cola |
| Unitaria | `test_fuente_sin_objeto_subido_rechaza_sin_encolar_nada` | `tests/unit/test_rutas_casos_multifuente.py` | Si `already_stored(sha256)` es `False` para alguna fuente, responde 422 y no se encola ni persiste ninguna sub-tarea (todo o nada) |
| Unitaria | `test_extension_no_soportada_rechaza_sin_encolar_nada` | `tests/unit/test_rutas_casos_multifuente.py` | Una fuente con extensión desconocida responde 422 (RF-02), nada queda encolado |
| Integración | `test_caso_multifuente_con_fakeredis_queda_consultable` | `tests/integration/test_rutas_casos_multifuente_fakeredis.py` | Con `fakeredis` y un doble de `ChunkedUpload`, tras crear el caso, `GET /cases/{id}` y `/report` (código sin modificar) devuelven las 4 fuentes enlazadas y el estado `queued` |
| Aceptación | `test_caso_heterogeneo_cliente_de_carga` | `tests/acceptance/test_caso_heterogeneo_cliente_de_carga.py` | Un cliente sube 4 fuentes (texto, imagen, audio, video) por el flujo real de `POST /uploads` + `complete`, crea el caso y `GET /cases/{id}` muestra las 4 (5 con el video expandido) enlazadas a sus objetos |

## Mediciones

No aplica: F-01 es lógica de aplicación/API (dominio ya construido en F-05), no hay medición de SO prevista para M2 fuera de F-20/F-21.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-01): crear caso multifuente integrando F-05/F-06 con el esquema heredado` | `modelos.py`, `rutas_casos.py` (reutiliza `ChunkedUpload` ya configurado), AD-47 | ~150 |

## Riesgos y preguntas abiertas

1. **No existe worker consumidor de `queue:text/image/audio`.** F-01 deja casos correctamente `queued` y encolados, pero nada los procesará hasta que exista ese worker (gap real, fuera de alcance, probablemente de integración F-33+). Se declara explícitamente para que no se confunda con un defecto de F-01.
2. **Persistencia doble (cola tipada + hash heredado).** Es deliberada (AD-47) mientras conviven los dos caminos; si en el futuro se migra a un worker que solo lee de `queue:text/image/audio`, hay que decidir si el hash heredado se vuelve solo-lectura/caché o se elimina.
3. **RF-02 solo parcial.** F-01 rechaza por extensión (ya construido en F-05); la validación de contenido real (formato de exportación de chat, etc.) es F-02, no se duplica aquí.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-11 | SPEC F-01 completado tras investigacion profunda del codigo: hallazgo clave es que GET /cases/{id}/report (RedisCaseCatalog) espera el esquema heredado, y que nadie consume aun queue:text/image/audio (F-07/08/09 solo entregaron Analyzer.analyze(), sin worker). Decision aprobada por el responsable: integrar ambos mundos (encolar con F-05/F-06, persistir con el esquema heredado para no romper el reporte existente). Nueva decision AD-47 propuesta. Plan de 1 parte, ~180 lineas (baf29c4) |
| plan | Nahúm Murillo | 2026-11-11 |  |
| verificación IA de tests | claude | 2026-11-11 | 5 pruebas en rojo (U x3, I x2, A x1): todas fallan por ModuleNotFoundError (falta src/application/create_case.py y SourceRef en modelos.py) o 422 porque CaseRequest no acepta sources todavia. Resto de la suite (77 passed en coordinador, decomposition, dispatch_case, redis_type_queue) intacto. Nota: test_fuente_sin_subir_responde_422_en_la_api pasa accidentalmente ahora (pydantic rechaza por subtasks requerido), pero seguira pasando por la razon correcta tras implementar (9a12eb8) |
| verificación IA de tests | claude | 2026-11-11 | Implementacion completa: CreateMultiSourceCase (77 lineas) integra DispatchCase/RedisTypeQueue con persistencia heredada; SourceRef en modelos.py; rutas_casos.py con dependencia opcional _obtener_subidas_opcional (no rompe el camino heredado). 6 tests nuevos verdes a la primera tras un ajuste (el Depends inicial rompio 24 tests heredados por ser obligatorio; corregido a opcional). Regresion amplia: 287 passed, 2 fallos preexistentes confirmados no relacionados (classify_source identico a origin/main, TLS ambiental). 148 lineas de codigo (a0ac95a) |
