# SPEC F-06: Cola confiable

**Fase:** revision
**Base:** main
**Verificación IA:** revision 0ea8476
**Historia:** US-06 · **Requisitos:** RF-04, RF-05 (confiabilidad de la cola de B.4 Cola y distribución), AD-03 · **Responsable:** N

## Objetivo

F-05 dejó declarado, en su propio SPEC y en `docs/CONTRATOS.md`, que el adaptador Redis real del puerto `WorkQueue` lo entrega F-06 con `BLMOVE`. Hoy ese adaptador **no existe**: `src/domain/decomposition.py` y `src/application/dispatch_case.py` (F-05) encolan sub-tareas por tipo (`queue:text`, `queue:image`, `queue:audio`) contra el puerto `WorkQueue`, pero nada en el repositorio implementa ese puerto sobre Redis todavía — solo el doble `FakeWorkQueue` (`tests/dobles.py`) lo satisface. Sin un adaptador real, una sub-tarea de este camino no puede sobrevivir ni demostrar nada sobre un worker que muere al tomarla.

F-06 entrega ese adaptador real (`RedisTypeQueue`) y resuelve la causa de pérdida declarada en AD-03 para **este** camino nuevo (F-05 a F-09, aún no conectado a `POST /cases`): tomar una sub-tarea y marcarla en vuelo deben ser la **misma operación atómica** de Redis (`BLMOVE`), no dos pasos separados. Si el worker muere entre tomarla y procesarla, la sub-tarea sigue en `inflight:{worker_id}` y un mecanismo de reencolado la recupera.

**Nota importante de alcance, verificada en el código:** el worker FFmpeg heredado (`src/workers/worker_node.py`) usa un camino **distinto y preexistente** (`queue:{operacion}[:high]`, con `BLPOP` + `SADD` separados a un `inflight:{worker}` que es un *set*, más `scripts/reaper.py`/`src/workers/recovery.py`). Ese camino heredado tiene la misma clase de ventana de pérdida, pero F-07/F-08/F-09 (ya `hecha`) siguen usándolo en producción; tocarlo es un cambio de mayor riesgo sobre código que ya sirve casos reales. F-06 no lo modifica: entrega el adaptador confiable para el camino nuevo de F-05, que es exactamente lo que esa feature dejó pendiente y lo que pide el criterio de aceptación de US-06 en términos de puerto (`WorkQueue`), no de implementación heredada. La limitación del camino heredado queda declarada como riesgo abierto (ver más abajo) para que F-34 (bloqueada por F-06) decida si la hereda o la corrige también.

## Alcance

**Incluye:**
- `src/adapters/redis_type_queue.py`: `RedisTypeQueue(redis, capacity)` que implementa `WorkQueue` (`src/application/ports.py:64-69`) con:
  - `has_capacity(queue)`: `LLEN queue < capacity`
  - `enqueue(queue, subtask)`: `RPUSH` del JSON de `Subtask.to_dict()`, `QueueFull` si no hay capacidad
  - `take(queue, worker_id, timeout)`: **`BLMOVE queue inflight:{worker_id} LEFT RIGHT timeout`** — atómico, sin ventana de pérdida
  - `in_flight(worker_id)`: `LRANGE inflight:{worker_id}` deserializado a `Subtask`
  - `acknowledge(worker_id, subtask)`: `LREM inflight:{worker_id} 1 <json>` tras procesar
  - `reencolar_huerfanas(worker_id, limite=None)`: mueve, de una en una y atómicamente (`LMOVE`), cada sub-tarea de `inflight:{worker_id}` de vuelta a su cola original (derivada de `Subtask.kind` vía `queue_for`, reutilizando `src/domain/decomposition.py`); devuelve cuántas movió. Es el mecanismo de reencolado que el criterio de aceptación llama «el reaper». Quien decide que un worker murió es quien llama a este método (no es un daemon ni requiere un registro de workers vivos: eso es trabajo de F-34, que depende de F-06). `limite` (opcional) acota cuántas mueve en una llamada, para poder demostrar que una interrupción a medias no pierde ni duplica nada: lo no movido sigue intacto en `inflight` y una llamada posterior retoma donde quedó.
- Pruebas de conformidad del adaptador con `comprobar_work_queue` (ya existe en `tests/contratos.py:21-35`, sin modificar).
- `docs/ARQUITECTURA.md` §8: refinar AD-03 declarando que, para el camino de F-05, el adaptador real usa `BLMOVE` a una *lista* `inflight:{worker_id}` (no un *set*, porque `BLMOVE` exige listas en ambos extremos).
- **Corrección de bug encontrado al escribir las pruebas de F-06** (aprobado por la persona para incluir aquí, no en PR aparte): `src/domain/scheduling.py` define su propia clase `Priority(Enum)` (con `bonus_ms`/`next_priority`, agregada en F-20) en vez de reutilizar la clase `Priority` canónica y «Compartida» (`docs/CONTRATOS.md`) de `src/domain/priority.py`, que ya existía desde antes de F-20 y es la que usa `Subtask`. Son dos clases distintas con los mismos miembros: `scheduling.Priority.ALTA != priority.Priority.ALTA`. Se corrige moviendo `bonus_ms`/`next_priority` a la clase canónica y haciendo que `scheduling.py` la reimporte (`from src.domain.priority import Priority`), sin cambiar ninguna firma pública: todo el código que hace `from src.domain.scheduling import Priority` (p. ej. `src/application/ports.py:14`) sigue funcionando igual, porque sigue siendo el mismo objeto reexportado.

**No incluye:**
- Modificar `src/workers/worker_node.py`, `scripts/reaper.py` ni `src/workers/recovery.py` (camino heredado de F-07/F-08/F-09, en producción; ver nota de alcance arriba).
- Conectar `POST /cases` a `DispatchCase`/`RedisTypeQueue` (lo deja explícitamente para F-01, que aún no define la entidad `Case`).
- Un registro de workers vivos o un daemon que llame `reencolar_huerfanas` automáticamente (es F-34, bloqueada por esta feature).
- El límite real de capacidad atómico entre procesos (lo entrega F-24; aquí `has_capacity`/`enqueue` no son atómicos entre sí, mismo límite ya declarado y aceptado en el SPEC de F-05).

## Criterios de aceptación

Copiado de `docs/backlog/cola-workers.md` (US-06):

**Dado** un worker que toma una sub-tarea
**Cuando** muere justo después de sacarla
**Entonces** la sub-tarea sigue en `inflight:{worker}` y el reaper la reencola

**Pruebas:** U `test_muerte_tras_blmove_deja_subtarea_en_inflight`. I reaper con Redis real (`fakeredis`).
**Demuestra:** prueba I. **Evidencia:** entrada en `docs/ARQUITECTURA.md` (AD-03 refinada) con la limitación corregida.

## Diseño

**Contratos usados (sin modificar):**
- `WorkQueue` (`src/application/ports.py:64-69`): puerto que este adaptador implementa
- `Subtask`, `ContentKind`, `QueueFull` (`src/domain/subtask.py`): serialización con `to_dict`/`from_dict`, ya probada en `test_subtarea_viaja_serializada_sin_perder_datos`
- `queue_for` (`src/domain/decomposition.py`, F-05): deriva la cola original de un `ContentKind`, reutilizado por `reencolar_huerfanas`

**Archivos a crear/modificar** (todos de Nahúm, M2/coordinador; `docs/CONTRATOS.md` ya lista `WorkQueue` como suyo):
- `src/adapters/redis_type_queue.py` (nuevo): `RedisTypeQueue`
- `tests/unit/test_redis_type_queue.py` (nuevo): conformidad con `comprobar_work_queue` sobre `fakeredis`, prueba de atomicidad `BLMOVE`
- `tests/integration/test_redis_type_queue_reaper.py` (nuevo): `reencolar_huerfanas` con `fakeredis`
- `src/domain/priority.py` (existente): agregar `bonus_ms()` y `next_priority()` (movidos desde `scheduling.py`)
- `src/domain/scheduling.py` (existente): quitar la clase `Priority` duplicada, reimportar la canónica

**Decisión aplicada (refina AD-03, no es una alternativa nueva):**
- AD-03 ya decidió `BLMOVE` a `inflight:{worker}` como la forma de cerrar la ventana de pérdida; este SPEC fija el detalle que AD-03 no explicitaba: `inflight:{worker_id}` debe ser una **lista** (no un *set*, como usa el camino heredado) porque `BLMOVE` solo opera sobre listas. Se registra como adición a la fila AD-03 en la fase de documentación, citando que esto aplica al camino de F-05/F-06, no al heredado.

**Reutilización del I Proyecto:**
- `Subtask.to_dict`/`from_dict`, `queue_for`, `comprobar_work_queue` y `FakeWorkQueue` (todos de F-05, sin modificar)

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_redis_type_queue_cumple_el_contrato` | `tests/unit/test_redis_type_queue.py` | `RedisTypeQueue` pasa `comprobar_work_queue`, igual que `FakeWorkQueue` |
| Unitaria | `test_muerte_tras_blmove_deja_subtarea_en_inflight` | `tests/unit/test_redis_type_queue.py` | Tras `take()`, la sub-tarea está en `in_flight(worker_id)` aunque el worker no haga nada más (simula la muerte): no hay ventana en la que no esté en ninguna parte |
| Unitaria | `test_take_en_cola_vacia_no_bloquea_mas_del_timeout` | `tests/unit/test_redis_type_queue.py` | `take` con cola vacía devuelve `None` tras el timeout, sin colgarse |
| Integración | `test_reaper_reencola_huerfanas_a_su_cola_original` | `tests/integration/test_redis_type_queue_reaper.py` | Con varias sub-tareas de distinto `kind` en `inflight:{worker}`, `reencolar_huerfanas` las devuelve cada una a su cola (`queue_for`), vacía `inflight` y no duplica ni pierde ninguna |
| Unitaria | `test_priority_es_la_misma_clase_en_scheduling_y_en_subtask` | `tests/unit/test_scheduling.py` | `scheduling.Priority is priority.Priority` (una sola clase, no dos compatibles por casualidad) |
| Integración | `test_reaper_no_pierde_nada_si_se_interrumpe_a_medias` | `tests/integration/test_redis_type_queue_reaper.py` | Simulando una interrupción tras mover solo parte de las huérfanas, ninguna sub-tarea queda fuera de `inflight` o de su cola (nunca en ningún punto intermedio inexistente) |

## Mediciones

No aplica: F-06 es lógica de un adaptador de colas (dominio/aplicación con Redis), no hay medición de SO prevista para M2 fuera de F-20/F-21 (ya cerradas con ficha propia).

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-06): adaptador Redis confiable de WorkQueue con BLMOVE` | `src/adapters/redis_type_queue.py`, pruebas de conformidad y de atomicidad, mecanismo de reencolado, refinamiento de AD-03 | ~150 |

## Riesgos y preguntas abiertas

1. **¿El camino heredado (`worker_node.py`/`reaper.py`, `inflight` como *set*) también debería migrar a `BLMOVE`?** Tiene la misma ventana de pérdida teórica, pero está en producción (F-07/F-08/F-09 ya `hecha`) y tocarlo es mayor riesgo. F-06 lo deja igual y declara la limitación; si se quiere corregir, es una feature aparte con su propio SPEC, no parte de esta.
2. **`docs/reutilizacion.md` vs `ARQUITECTURA.md` para la evidencia.** El backlog dice «entrada en `docs/reutilizacion.md` con la limitación corregida», pero ese archivo está dedicado a licencias de terceros (sus dos entradas existentes dicen «Sin terceros»). No hay terceros nuevos en F-06 (solo Redis, ya dependencia). Se interpreta que la evidencia real pedida es la corrección de AD-03 en `ARQUITECTURA.md` (que sí es donde se documentan decisiones y sus límites), y se añade a `docs/reutilizacion.md` solo la línea estándar «Sin terceros en F-06» por consistencia con F-12/F-36. La persona puede pedir lo contrario.
3. **Nombre `reencolar_huerfanas` vs un `scripts/reaper_tipos.py` separado.** Se eligió un método del adaptador (más simple, sin inventar un daemon fuera de alcance); F-34 decidirá si lo envuelve en un proceso periódico con detección real de workers muertos.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-11 | SPEC F-06 completado tras investigar el codigo real: hallazgo clave es que F-05 dejo el adaptador real de WorkQueue pendiente para F-06 (declarado en su propio SPEC y en CONTRATOS.md), y que el camino heredado (worker_node.py) es un sistema de colas DISTINTO que no se toca (mayor riesgo, en produccion via F-07/08/09 ya hecha). Diseno: RedisTypeQueue con BLMOVE atomico a inflight (lista), reencolar_huerfanas reutilizando queue_for de F-05. Plan de 1 parte, ~150 lineas (8538cea) |
| plan | Nahúm Murillo | 2026-11-11 |  |
| verificación IA de tests | claude | 2026-11-11 | 7 pruebas en rojo: contrato comprobar_work_queue, atomicidad BLMOVE (muerte tras take deja en inflight), timeout en cola vacia, acknowledge, reencolar_huerfanas completo e interrumpido a medias, y unificacion de Priority (scheduling.Priority vs priority.Priority). Todas fallan por ModuleNotFoundError o la duplicacion real detectada. Resto de la suite (32 passed) intacto (585cdd0) |
| tests | Nahúm Murillo | 2026-11-11 |  |
| verificación IA de implementacion | claude | 2026-11-11 | Implementacion completa: RedisTypeQueue con BLMOVE/LMOVE (67 lineas), Priority unificada (bonus_ms/next_priority movidos a priority.py canonica, scheduling.py reexporta). 6 tests nuevos verdes a la primera, 91 passed en suite ampliada (scheduling, decomposition, dispatch_case, arquitectura, redis_type_queue). 109 lineas de codigo, dentro del limite de 400 (3f2e4ae) |
| implementacion | Nahúm Murillo | 2026-11-11 | errores de coleccion preexistentes en TLS/seguridad del entorno local, ajenos a F-06 |
| verificación IA de verificacion | claude | 2026-11-11 | QA: acknowledge de subtarea inexistente no revienta (no-op), reencolar_huerfanas en inflight vacio devuelve 0, capacidad exacta rechaza con QueueFull y libera tras take, dos workers no se contaminan entre si, reencolar con kinds mixtos (image/audio) va a sus colas correctas. Criterio de aceptacion verificado: BLMOVE atomico deja la subtarea en inflight tras take, sin ventana de perdida (943e82f) |
| verificacion | Nahúm Murillo | 2026-11-11 | errores de coleccion preexistentes en TLS/seguridad del entorno local, ajenos a F-06 |
| verificación IA de documentacion | claude | 2026-11-11 | Documentacion completa: AD-03 refinada con BLMOVE a lista para camino nuevo, limitacion del heredado declarada; docs/reutilizacion.md con linea estandar; bitacora registrada en rama estado DECLARANDO el error real de F-20 (Priority duplicada) via --error-ia (a7fe69e) |
| documentacion | Nahúm Murillo | 2026-11-11 | errores de coleccion preexistentes en TLS/seguridad del entorno local, ajenos a F-06 |
| verificación IA de revision | claude | 2026-11-11 | Diff F-06 vs SPEC: objetivo OK (adaptador real entregado), alcance OK (incluye correccion de Priority aprobada), criterios OK (atomicidad BLMOVE), diseno OK, pruebas OK (nombres exactos), plan de pila OK (1 parte, 109 lineas). APROBADO (0ea8476) |
