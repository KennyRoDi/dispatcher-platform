# SPEC F-11: Reintentos

**Fase:** implementacion
**Base:** main
**Verificación IA:** implementacion 8909d36
**Historia:** US-11 · **Requisitos:** RF-11 ([B.4] Reintentos y cancelación); AD-03, AD-43 (aplica); AD-48 (propone) · **Responsable:** N

## Objetivo

El enunciado pide «reintentos con *backoff* y número máximo configurable» (B.4, Reintentos y cancelación) y RF-11 exige que una sub-tarea que falla se reintente con esperas crecientes y falle al llegar al máximo. Hoy no existe esa política. Se verificó en el código:

- `src/workers/worker_node.py` (`handle_subtask`): cuando el procesamiento lanza una excepción (`StorageError` o cualquier otra) fija `status = "failed"` y reporta el fallo de inmediato. **No reintenta un fallo del analizador** y no hay espera alguna.
- `src/workers/recovery.py` (`recover_subtask`): reencola solo sub-tareas **huérfanas** (worker muerto o atascado) mientras `attempts < settings.max_attempts` (`MAX_ATTEMPTS`, 3 por defecto, `src/workers/config.py`), marca el caso `retrying` y, al agotarse, reporta `failed` con `WorkerLostError`. El reencolado es **inmediato**, sin espera creciente.
- `worker_node.py` solo tiene backoff en el bucle de conexión a Redis (`1..MAX_BACKOFF=30 s`) y `reporter.py` en la entrega HTTP (`1, 2, 4, 8, 16 s`). Ninguno reintenta una sub-tarea.
- `_reencolar_por_oom` reencola por OOM con la política de `oom_policy` (F-18), también sin espera, y devuelve el contador `attempts` a su valor previo.
- `CaseState.RETRYING` y sus transiciones ya existen (`src/domain/case_state.py`, AD-43), y `ReportSubtask` ya reabre un caso en `retrying` (F-10). Lo que falta es quién decide reintentar, con qué espera y cuándo rendirse.
- `docs/CONTRATOS.md` ya reserva `src/domain/retry.py` a Nahúm y `docs/ARQUITECTURA.md` §4 lo lista en el dominio; el archivo no existe.

F-11 entrega esa decisión como lógica pura de dominio (`next_delay` con aleatoriedad inyectada y la decisión «reintentar o fallar»), un caso de uso contra puertos y su integración mínima con el camino actual del worker y de `recovery.py`, para que un fallo transitorio de una sub-tarea se supere sin saturar el sistema y uno persistente falle de forma definida.

## Alcance

**Incluye:**
- `src/domain/retry.py`: `RetryPolicy` (máximo de intentos, base, tope y jitter validados), `next_delay(attempt, base, cap, jitter)` con la aleatoriedad inyectada (`jitter` es un `Callable[[], float]` en `[0, 1)`), y `decide_retry(attempts, policy, jitter)`, que devuelve `Retry(delay)` o `GiveUp`, al estilo de `oom_policy`.
- `src/application/retry_subtask.py`: caso de uso `RetrySubtask`. Ante el fallo de una sub-tarea decide con `decide_retry`; si reintenta, pasa el caso a `retrying` (`transition` de `case_state.py`) y programa el reencolado tras la espera; si se agotó, no reencola y deja que el fallo se reporte como `failed` por el camino de `ReportSubtask`.
- Un puerto nuevo `RetryScheduler` en `src/application/ports.py` (se agrega, no se modifica nada existente: `schedule(subtask_id, delay_s)` y `promote_due(now)`), con su doble en `tests/dobles.py` y `comprobar_retry_scheduler` en `tests/contratos.py` (procedimiento de «Cambiar un contrato» de `docs/CONTRATOS.md`).
- `src/adapters/redis_retry_scheduler.py`: adaptador del puerto. Guarda las sub-tareas en espera en un ZSET `retry:scheduled` con puntaje = instante de disponibilidad, y `promote_due` mueve las vencidas a su cola original. La espera no ocupa un slot de worker.
- Integración mínima con el camino actual: en `worker_node.py`, un fallo del analizador que sea **transitorio** (ver pregunta 3) pasa por `decide_retry`; si es `Retry`, la sub-tarea se programa con su espera en vez de reportarse `failed` y se registra un log con el intento, la espera y el motivo; si es `GiveUp`, se reporta `failed` igual que hoy.
- `recovery.py` toma la misma decisión de límite desde `decide_retry` (el «Unificar con `recovery.py`» de `docs/IMPLEMENTACION.md` §4) en lugar de su comparación propia `attempts < max_attempts`, sin cambiar su comportamiento para huérfanas (reencolado inmediato, mismos estados de caso y mismo reporte `WorkerLostError`).
- Configuración: se reutiliza `MAX_ATTEMPTS`; se agregan `RETRY_BASE_S` y `RETRY_CAP_S` en `src/workers/config.py`, con validación (> 0 y base ≤ tope).
- Evidencia de log con los tiempos entre intentos (prueba A, ver Pruebas).

**No incluye:**
- Cambiar la tabla de transiciones ni `CaseState` (AD-43, F-10).
- Reintentos del reporte HTTP (`reporter.py`) ni del bucle de conexión a Redis: ya tienen su propio backoff y no son sub-tareas.
- Cambiar la política de OOM (`oom_policy`, F-18) ni su contador `oom_count`.
- Clasificar con detalle cada excepción de cada analizador: F-11 define el criterio general y los analizadores de F-07 a F-09 no se modifican (ver pregunta 3).
- Cancelación (F-12). Un caso `cancelled` no se reintenta: se reutiliza la comprobación que ya hacen `_requeue` y `_claim_subtask`.
- Un daemon propio: `promote_due` lo invoca el reaper existente (`scripts/reaper.py`) en su ciclo (ver pregunta 2).
- Conectar `POST /cases` al camino nuevo de F-05/F-06 (F-01); el reintento funciona sobre el camino actual del worker y sobre los puertos para cuando se conecten.

## Criterios de aceptación

Copiados de `docs/backlog/estados-reporte-dashboard.md` (US-11):

**Dado** una sub-tarea que falla, con máximo configurado N
**Cuando** se reintenta
**Entonces** las esperas crecen, el caso pasa por `retrying` y falla al llegar a N

**Pruebas:** U `test_backoff_crece_y_respeta_maximo`. I analizador que falla N veces.
**Demuestra:** prueba I. **Evidencia:** log con tiempos entre intentos.

Interpretación (SUP-44, provisional): N es el **número total de intentos** de la sub-tarea, igual que `attempts < max_attempts` en `recovery.py`. Con N = 3 hay el intento inicial y 2 reintentos; el tercer fallo marca `failed`. Entre los intentos hay N − 1 esperas.

## Diseño

**Contratos que usa (sin modificar):**
- `CaseStateStore` y `Clock` (`src/application/ports.py`): para pasar el caso a `retrying` y leer la hora.
- `CaseState`, `transition`, `InvalidTransition` (`src/domain/case_state.py`, F-10): `processing → retrying → processing`, `retrying → failed`.
- `ReportSubtask` (`src/application/report_subtask.py`): ya reabre `retrying`; solo recibe el fallo definitivo, así que el `Barrier` no cuenta los intentos intermedios.

**Contrato que agrega:** `RetryScheduler` en `ports.py` (cambio aditivo; avisar a quienes aparecen en la tabla de `docs/CONTRATOS.md`: ninguno depende de él todavía).

**Capas y archivos** (`retry.py` es de Nahúm según `docs/CONTRATOS.md`; `src/workers/` y `src/workers/config.py` son de José Andrés, ver pregunta 1):

| Archivo | Capa | Acción |
|---|---|---|
| `src/domain/retry.py` | Dominio | nuevo: `RetryPolicy`, `next_delay`, `decide_retry`, `Retry`, `GiveUp` |
| `src/application/retry_subtask.py` | Aplicación | nuevo: `RetrySubtask` |
| `src/application/ports.py` | Aplicación | agrega `RetryScheduler` (compartido: cambio aditivo) |
| `src/adapters/redis_retry_scheduler.py` | Adaptador | nuevo: ZSET `retry:scheduled` |
| `src/workers/worker_node.py` | Adaptador | modifica `handle_subtask`: decide reintento ante un fallo transitorio |
| `src/workers/recovery.py` | Adaptador | modifica `recover_subtask`: el límite sale de `decide_retry` |
| `src/workers/config.py` | Infraestructura | agrega `retry_base_s`, `retry_cap_s` |
| `scripts/reaper.py` | Infraestructura | una llamada a `promote_due` por ciclo |
| `tests/dobles.py`, `tests/contratos.py` | Pruebas | `FakeRetryScheduler` y `comprobar_retry_scheduler` |

**`next_delay(attempt, base, cap, jitter)`**: `attempt` desde 1; espera exponencial `min(cap, base · 2^(attempt − 1))` multiplicada por `0.5 + 0.5 · jitter()` («jitter igual», acota la espera entre la mitad y el total de la exponencial). Nunca supera `cap`; con `jitter()` fijo es monótona creciente hasta el tope; sin `random` ni reloj dentro del dominio. Rechaza con `ValueError` `attempt < 1`, `base <= 0`, `cap < base` o un `jitter()` fuera de `[0, 1)`.

**`decide_retry(attempts, policy, jitter)`**: `attempts` es el número de intentos ya realizados. Si `attempts < policy.max_attempts` devuelve `Retry(delay=next_delay(attempts, ...))`; si no, `GiveUp`. Es la única comparación del límite en todo el código, usada por el worker y por `recovery.py`.

**Decisión nueva propuesta, AD-48 (provisional), a registrar en `docs/ARQUITECTURA.md` §8 en la fase de documentación:**
- *Decisión:* reintento con backoff exponencial y jitter acotado, decidido por una función pura de dominio y ejecutado con una **espera programada fuera del worker** (ZSET `retry:scheduled` más promoción por el reaper), con N como total de intentos.
- *Alternativas:* (a) dormir en el worker con `stop_event.wait(delay)`, como el bucle de conexión: simple, pero el worker ocupa un slot sin trabajar y pierde la espera si muere; (b) reencolar de inmediato como hace `recovery.py`: no cumple «esperas crecientes» y satura ante un fallo persistente; (c) backoff lineal o sin jitter: sincroniza reintentos de muchos casos a la vez.
- *Criterio:* RF-11 pide esperas crecientes y máximo configurable; la espera programada no consume memoria ni slot, coherente con AD-06 (admisión antes de sacar de la cola) y AD-03 (entrega al menos una vez); el jitter evita reintentos simultáneos tras un fallo común.
- *Fuente:* AWS Architecture Blog, «Exponential Backoff And Jitter» (para citar en código y documentación, Parte I §9); `docs/ARQUITECTURA.md` AD-03, AD-43.
- *Medición pendiente:* base y tope provisionales; el SPEC no fija valores numéricos medidos (ver pregunta 4).

**Reutilización:** `_requeue` de `recovery.py` (cambio de estado y cola en una transacción `WATCH/MULTI`, ya cubierto por `tests/test_recovery.py`), `case_state.transition`, `oom_policy` como modelo de decisión `Retry/GiveUp`, `FakeClock` y `FakeWorkQueue` de `tests/dobles.py`. No se reescribe nada de F-07/F-08/F-09 ni de F-10.

**No rompe F-07/F-08/F-09:** los analizadores no cambian. Su `ValueError` ante entrada ilegible es permanente y no se reintenta; las excepciones transitorias que F-09 deja propagar a propósito (`MemoryError`, `TimeoutError`, `BlockingIOError`, `InterruptedError`, `PermissionError`) son las que el reintento cubre (AD-28 ya las declara como reintentables por F-12 y F-18).

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_backoff_crece_y_respeta_maximo` | `tests/unit/test_retry.py` | Con `jitter` fijo, las esperas de los intentos 1..k crecen y ninguna supera `cap` |
| Unitaria | `test_agota_intentos_y_falla` | `tests/unit/test_retry.py` | `decide_retry` devuelve `Retry` mientras `attempts < max` y `GiveUp` al llegar a `max` |
| Unitaria | `test_jitter_inyectado_acota_la_espera` | `tests/unit/test_retry.py` | Con `jitter` en 0 y casi 1 la espera queda entre la mitad y el total de la exponencial, sin `random` real |
| Unitaria | `test_politica_invalida_se_rechaza` | `tests/unit/test_retry.py` | `attempt < 1`, `base <= 0`, `cap < base`, `max_attempts < 1` y `jitter` fuera de rango lanzan `ValueError` |
| Unitaria | `test_reintento_pasa_el_caso_por_retrying` | `tests/unit/test_retry_subtask.py` | Con dobles, un fallo con intentos restantes deja el caso en `retrying`, programa la sub-tarea con su espera y no reporta `failed` |
| Unitaria | `test_fallo_agotado_no_reencola_y_reporta_failed` | `tests/unit/test_retry_subtask.py` | Al llegar a N no se programa nada y el resultado de la sub-tarea es `failed` |
| Unitaria | `test_caso_cancelado_no_se_reintenta` | `tests/unit/test_retry_subtask.py` | Un caso `cancelled` no cambia de estado ni se reencola |
| Unitaria | `test_retry_scheduler_cumple_el_contrato` | `tests/unit/test_redis_retry_scheduler.py` | El adaptador sobre `fakeredis` y el doble pasan `comprobar_retry_scheduler`; `promote_due` mueve solo lo vencido a su cola original y no duplica |
| Unitaria | `test_recovery_usa_la_misma_decision_de_limite` | `tests/test_recovery.py` | Con el mismo `max_attempts`, `recover_subtask` reencola o falla exactamente donde `decide_retry` indica; el comportamiento de huérfanas no cambia |
| Unitaria | `test_fallo_transitorio_programa_reintento_y_permanente_falla` | `tests/test_worker_node.py` | Un `TimeoutError` del procesador programa reintento y un `ValueError` se reporta `failed`, sin red ni `sleep` |
| Integración | `test_analizador_que_falla_n_veces_agota_y_falla_el_caso` | `tests/integration/test_reintentos_analizador.py` | Con `fakeredis`, `FakeClock` y un analizador que falla siempre: N intentos, N − 1 esperas crecientes, el caso pasa por `retrying` y termina `failed` al llegar a N |
| Integración | `test_analizador_que_falla_y_luego_acierta_cierra_completed` | `tests/integration/test_reintentos_analizador.py` | Un fallo transitorio se supera: el caso vuelve a `processing` y cierra `completed` una sola vez |
| Aceptación | `test_reintentos_registran_tiempos_entre_intentos` | `tests/acceptance/test_reintentos_log.py` | Con `base` y `tope` pequeños y reloj real, el log de las N − 1 esperas muestra tiempos entre intentos crecientes; se guarda en `docs/evidencia/F-11_reintentos_<fecha>.md` |

Las unitarias y de integración no usan red, `sleep` ni reloj real: la aleatoriedad (`jitter`) y la hora (`Clock`) se inyectan. Solo la prueba de aceptación usa tiempo real, con esperas de décimas de segundo, para la evidencia.

## Mediciones

No aplica: F-11 no es M1–M5 ni B.6. La evidencia que pide US-11 es un log funcional de comportamiento con los tiempos entre intentos, no una medición de SO. Los valores de `base` y `tope` usados en él son configuración, no un dato medido, y la ficha lo declara así.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-11): política de reintento con backoff en el dominio` | `src/domain/retry.py` (`RetryPolicy`, `next_delay`, `decide_retry`) y `src/application/retry_subtask.py`; puerto `RetryScheduler` con su doble y su prueba de contrato; sin Redis ni cambios en el worker | ~170 |
| 2 | `feat(F-11): reintentar sub-tareas fallidas en el worker y el reaper` | `RedisRetryScheduler`, integración en `worker_node.py` y `recovery.py`, configuración, llamada en `scripts/reaper.py`, prueba de integración con analizador que falla N veces y log de evidencia; registro de AD-48 y SUP-44 en la documentación | ~230 |

## Riesgos y preguntas abiertas

1. **Dueño de `recovery.py`, `worker_node.py` y `config.py`.** `docs/CONTRATOS.md` asigna `src/workers/` a José Andrés, no a Nahúm; solo `src/domain/retry.py` es de Nahúm. La parte 2 modifica archivos de José y F-18 ya tocó `worker_node.py` (OOM). ¿Se avisa a José y se pide su revisión en la PR de la parte 2, o prefiere que él aplique ese cambio? Esta feature se toma como apoyo a Nahúm.
2. **Quién promueve las sub-tareas vencidas.** Se propone que el reaper existente llame a `promote_due` en su ciclo, lo que añade una dependencia de que el reaper corra y retrasa cada reintento hasta un ciclo (`REAPER_INTERVAL`) más allá de la espera. Alternativa: dormir en el worker (más simple, ocupa el slot y se pierde si muere). ¿Se acepta la resolución gruesa del reaper o se prefiere el sueño en el worker en la parte 2?
3. **Qué fallos son transitorios.** Propuesta: reintentar `TimeoutError`, `MemoryError`, `BlockingIOError`, `InterruptedError`, `PermissionError`, `StorageError` y el `ProcessingError` de FFmpeg con código de salida distinto de entrada inválida; no reintentar `ValueError` (entrada ilegible, permanente). Hoy `handle_subtask` trata todo igual. ¿Se aprueba esa lista, o se reintenta cualquier excepción hasta N, a riesgo de repetir fallos permanentes?
4. **Valores por defecto de `base` y `tope`.** No hay un dato medido que los fundamente. Se proponen provisionales `RETRY_BASE_S=1` y `RETRY_CAP_S=30` (el mismo orden que `MAX_BACKOFF` del worker) y se marca «Medición pendiente» en AD-48. ¿Se aceptan?
5. **Semántica de N (SUP-44).** Se toma como total de intentos, igual que `recovery.py`; «N reintentos» daría un intento más. ¿Se acepta?
6. **Camino nuevo vs camino actual.** Hoy el worker real usa `queue:{operacion}`, `attempts` en el hash `subtask:{id}` y estado en el hash `case:{id}`, mientras que `RetrySubtask` opera sobre `CaseStateStore` (F-10) para el camino de F-05/F-06 aún sin conectar a `POST /cases`. Se implementan ambos con la misma decisión de dominio, pero el camino actual escribe el estado `retrying` por el hash, como ya hace `_requeue`. ¿Se acepta ese doble cableado hasta que F-01 conecte el camino nuevo?
7. **Entrega al menos una vez.** Un reintento vuelve a ejecutar el análisis; la idempotencia por id de sub-tarea (AD-21, citada en AD-03) debe evitar hallazgos duplicados. F-13 aún no persiste `Finding` desde los workers, así que no se prueba aquí; queda declarado como límite.
8. **Ramas relacionadas.** Se revisó `git branch -r`: no hay ramas de F-11 de Nahúm distintas de la actual; `feat/F-10-3-estados-y-cierre` es la base (estados) y `feat/F-18-*` toca el reencolado por OOM. SUP-44 y AD-48 se numeran contra `main` (último AD-47, último SUP-43); si otra rama los usa antes, se renumeran en la parte 2.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Sonnet 5.5, subagente arquitecto | 2026-11-12 | Subagente independiente. Verifiqué: 0 campos … restantes; cada criterio de US-11 y RF-11 presente; diff solo toca docs/specs/F-11/SPEC.md; contrastado en código que max_attempts=3 en config.py y recovery.py:66 usa attempts<max_attempts, que src/domain/retry.py no existe y que CONTRATOS asigna retry.py a Nahúm y src/workers a José; último SUP-43 confirmado en REQUERIMIENTOS; pila de 2 PR (~170 y ~230 líneas). No verificado: líneas reales, solo estimadas. (13e5689) |
| plan | Kenni Rodriguez | 2026-11-12 | El único … del SPEC está en el texto de la fila de verificación IA (mi resumen decía 'campos … restantes'), no en un campo sin completar; autorizado por la persona |
| verificación IA de tests | Claude Sonnet 5.5, subagente developer | 2026-11-12 | Subagente independiente. Ejecuté yo: test_retry.py 10 failed y test_retry_subtask.py error de colección, ambos por ImportError de lo no implementado; test_arquitectura 5 passed. Diff vs main solo toca tests/ y el SPEC, sin código en src/. Cada prueba de la parte 1 del SPEC con su nombre exacto. No verifiqué: los 119 fallos de la suite completa (el subagente los atribuye a entorno Windows/fakeredis tras comparar solo 2 archivos). (f9a8d62) |
| tests | Kenni Rodriguez | 2026-11-12 |  |
| verificación IA de implementacion | Claude Sonnet 5.5, subagente developer | 2026-11-12 | Subagente independiente. Ejecuté yo: test_retry, test_retry_subtask y test_arquitectura, 19 passed. git diff f9a8d62 -- tests vacío: pruebas sin debilitar. Leí retry.py (41 líneas) y retry_subtask.py (30): dominio puro, capas correctas, cita de fuente. Desviación declarada: decide_retry calcula la espera con next_delay(attempts+1) porque así lo exige la prueba; ajustar SPEC en documentación. No verifiqué la comparación de la suite completa (121 vs 144 fallos de entorno), que es del subagente. (8909d36) |
