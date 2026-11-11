# SPEC F-10: Estados y cierre

**Fase:** verificacion
**Base:** main
**Verificación IA:** verificacion dc78bf8
**Historia:** US-10 · **Requisitos:** RF-09, RF-10 · **Responsable:** N

## Objetivo

Que el analista tenga un estado de caso confiable: los siete estados del enunciado B.4 (`queued`, `processing`, `completed`, `partially_completed`, `failed`, `retrying`, `cancelled`), transiciones validadas y un cierre tipo barrier/join que ocurre una sola vez, con el estado final que corresponde, aunque lleguen reportes duplicados o concurrentes. Hoy la lógica vive mezclada con Redis en `src/coordinator/apoyo.py` y `rutas_subtareas.py` y no hay tabla de transiciones; esta feature la extrae a dominio puro y la prueba.

## Alcance

**Incluye:**
- `CaseState` y tabla de transiciones permitidas en dominio; `InvalidTransition` ante una no permitida.
- Cálculo del estado final por combinación de sub-tareas completadas/fallidas (`final_state`).
- Barrier idempotente en dominio (`Barrier`): un reporte repetido de una sub-tarea no se cuenta dos veces y el cierre se produce una sola vez.
- Puerto `CaseStateStore` y caso de uso `ReportSubtask` en aplicación.
- Adaptador Redis con `SADD case:{id}:done` y historial de estados por caso (evidencia de la historia), y cableado en `POST /subtasks/report`.
- Prueba de frontera de `import` del dominio.

**No incluye:**
- Política de reintentos y cuándo se pasa a `retrying` (F-11); aquí `retrying` solo existe como estado y transición válida.
- Cancelación del trabajo en curso (F-12/F-36) ni alertas de cierre (F-33..F-35); solo se respeta que `cancelled` es terminal.
- Reporte consolidado (F-13), cambios de la API pública o del panel.

## Criterios de aceptación

- **Dado** un caso con sub-tareas exitosas y fallidas
- **Cuando** todas terminan, incluso con reportes duplicados
- **Entonces** cierra una sola vez, con el estado que corresponde; una transición no permitida se rechaza

Complementos de RF-09/RF-10: los 7 estados se alcanzan en pruebas; el caso solo pasa a estado final cuando todas sus sub-tareas terminaron, sin doble conteo.

## Diseño

**Contratos:** implementa el estado y cierre del caso del coordinador (B.4); usa `Clock` de `src/application/ports.py`. No cambia `WorkQueue` ni `FindingStore`.

**Dominio (`src/domain/case_state.py`, puro, sin E/S):**
- `CaseState(Enum)` con los 7 valores.
- Transiciones permitidas: `queued→{processing, cancelled}`; `processing→{completed, partially_completed, failed, retrying, cancelled}`; `retrying→{processing, failed, cancelled}`; `completed`, `partially_completed`, `failed` y `cancelled` son terminales (sin salida). `transition(actual, destino)` devuelve el destino o lanza `InvalidTransition`.
- `final_state(completed, failed)`: sin fallidas → `completed`; solo fallidas → `failed`; mezcla → `partially_completed`. Un caso `cancelled` no cambia de estado (conserva la regla del código heredado).
- `Barrier(expected: int)`: `report(subtask_id, outcome)` devuelve si el reporte es nuevo (idempotente por `subtask_id`); `is_closed()` cuando los ids únicos recibidos igualan `expected`.

**Aplicación (`src/application/report_subtask.py`):** puerto `CaseStateStore` en `ports.py` con `mark_reported(case_id, subtask_id) -> bool` (equivale a `SADD`: `True` solo la primera vez), `counts(case_id)`, `state(case_id)`, `set_state(case_id, nuevo, at)` e historial `history(case_id)`. El caso de uso aplica el barrier, calcula el estado final y transiciona; el cierre ocurre una sola vez.

**Adaptadores / infraestructura:** `src/adapters/redis_case_state.py` implementa el puerto con `SADD case:{id}:done`, el hash `case:{id}` y la lista `case:{id}:state_history`. `rutas_subtareas.py` delega en el caso de uso en lugar de calcular el cierre en línea; `apoyo.final_state` heredado se retira al moverse. Prueba de contrato en `tests/contratos.py` y doble en `tests/dobles.py`.

**Decisiones:** reutiliza AD de barrier idempotente con `SADD` (ARQUITECTURA §4, «Funciona / Reutilizar»). Se propone una decisión nueva, **AD-XX tabla de transiciones de `CaseState`**, a registrar en `docs/ARQUITECTURA.md` §8 en la fase de documentación.

**Código del I Proyecto que reutiliza:** la regla de `final_case_status`, el `SADD` por `case:{id}:done` y la guarda de caso cancelado.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_transicion_invalida_se_rechaza` | Una transición fuera de la tabla lanza `InvalidTransition`; los terminales no tienen salida |
| Unitaria | `test_barrier_no_cuenta_dos_veces` | Un reporte duplicado no avanza el conteo ni reabre el cierre |
| Unitaria | `test_estado_final_por_combinacion` | Todas OK, todas falla y mezcla dan `completed`, `failed`, `partially_completed`; `cancelled` no cambia |
| Unitaria | `test_dominio_no_importa_capas_externas` | Frontera de `import` del dominio (`tests/unit/test_arquitectura.py`) |
| Unitaria | `test_caso_de_uso_cierra_una_sola_vez` | Con doble de `CaseStateStore`, el cierre se aplica una vez y queda historial |
| Integración | `test_reportes_concurrentes_cierran_una_vez` (Redis) | N hilos con ids repetidos: un único cierre y conteo exacto |
| Contrato | `CaseStateStore` en `tests/contratos.py` | Doble y adaptador Redis se comportan igual |
| Aceptación | `test_los_siete_estados_se_alcanzan` | Cada estado se alcanza por un camino del flujo real |

## Mediciones

No aplica. Es lógica de dominio; no hay medición M1–M5 ni B.6.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-10): máquina de estados y barrier en dominio` | `case_state.py`: `CaseState`, transiciones, `final_state`, `Barrier`; pruebas unitarias y de frontera |
| 2 | `feat(F-10): caso de uso de reporte y puerto de estado` | `CaseStateStore`, `ReportSubtask`, doble y prueba de contrato |
| 3 | `feat(F-10): adaptador Redis, historial y cableado del reporte` | `redis_case_state.py`, historial de estados, `rutas_subtareas.py` delega, prueba I concurrente y A de los 7 estados |

## Riesgos y preguntas abiertas

- F-10 es de N (Nahúm) y se toma como apoyo; la persona responsable debe poder defenderlo.
- La prueba de integración con Redis necesita Redis disponible en CI; si no lo hay, se marca `integration` y se corre localmente.
- Decisión a confirmar: se asume que `retrying→processing` es válida y que `queued→cancelled` también; el enunciado no define la tabla completa (se registrará como `SUP-XX` si se aprueba).
- La parte 3 toca `src/coordinator/` heredado, posiblemente compartido con otros módulos; coordinar con quien lo edite en paralelo.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5, misma sesión, no independiente) | 2026-11-11 | SPEC F-10 completo sin campos pendientes, 3 partes, criterios copiados del backlog (62abaae) |
| verificación IA de plan | Claude Code (Sonnet 5.5, misma sesión, no independiente) | 2026-11-11 | SPEC F-10 completo, 3 partes, criterios copiados del backlog (722c524) |
| plan | José Andrés Loría Herrera | 2026-11-11 |  |
| verificación IA de tests | Claude Code (Sonnet 5.5, misma sesión, no independiente) | 2026-11-11 | Pruebas nuevas en rojo (ModuleNotFoundError case_state), sin código de producción (f935d6e) |
| tests | José Andrés Loría Herrera | 2026-11-11 |  |
| verificación IA de implementacion | Claude Code (Sonnet 5.5, misma sesión, no independiente) | 2026-11-11 | case_state.py en dominio, 67 pruebas en verde (test_case_state, test_arquitectura), 52 líneas (e929c9a) |
| implementacion | José Andrés Loría Herrera | 2026-11-11 | aprobación delegada por José en el chat; suite completa falla en 3 pruebas TLS ajenas a F-10 (Windows); pruebas del módulo 67 en verde |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), verificación no independiente | 2026-11-11 | QA parte 1: criterios del dominio verificados; 7 pruebas de borde añadidas (duplicado con otro resultado, orden, caso vacío, autotransición, cancelado). 75 pruebas verdes. Hallazgo: caso de uso/CaseStateStore (parte 2) y adaptador Redis/cableado (parte 3) pendientes por plan de pila; Barrier(0) cierra de inmediato y final_state(0,0)=completed. (dc78bf8) |
