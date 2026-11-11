# SPEC F-18: Detección de OOM

**Fase:** implementacion
**Base:** main
**Verificación IA:** implementacion d20fcae
**Historia:** US-18 · **Requisitos:** RF-26, RNF-09, SUP-14 · **Responsable:** J

## Objetivo

El operador distingue una terminación por OOM de otros fallos y el sistema aplica la política SUP-14: reencola con más reserva sin gastar intentos normales, hasta 2 veces; luego falla con causa `oom`. El supervisor y el worker siguen vivos [B.5 M1].

## Alcance

**Incluye:** `classify_exit(code, oom_delta)` y `OomPolicy` (dominio puro); `read_memory_events(path)` sobre `memory.events`; integración en `WorkerNode.handle_subtask` (línea base de `oom_kill` antes del proceso, delta después); reencolado con `mem_reserve` creciente que `_fits_in_memory` suma mientras corre esa sub-tarea; causa `oom` en el reporte final.

**No incluye:** ficha M1 con datos medidos del OOM provocado en nodos WSL2 (requiere nodos reales, F-41); cambiar `mem_limit` (F-16); control de admisión nuevo (F-17).

## Criterios de aceptación

- **Dado** una sub-tarea que excede el límite, **cuando** el kernel termina el subproceso, **entonces** queda registrada con causa `oom` y se reencola con más reserva hasta el máximo de la política; el supervisor sigue activo.
- Código de salida -9 (o 137) con `oom_kill` incrementado es `oom`; -9 sin incremento es `killed` (p. ej. cancelación F-12, AD-31) y no se reencola por esta vía.

## Diseño

- Dominio `src/domain/oom_policy.py` (dueño J): `ExitCause` (`ok`, `oom`, `killed`, `failed`); `classify_exit(code, oom_delta)`; `OomPolicy(max_requeues=2, step_factor=1.5)` con `decide(oom_count, reserve)` que devuelve `Requeue(reserve)` o `GiveUp`. Sin I/O.
- Infraestructura `src/infrastructure/cgroup_resources.py`: `read_memory_events(path) -> MemoryEvents(oom_kill)` junto al lector existente (F-16).
- Worker `src/workers/worker_node.py` y `multimedia_processor.py`: `ProcessingError` gana `exit_code` opcional (`None` por defecto, compatible). `handle_subtask` lee la línea base, clasifica al fallar y, en `oom`, reencola con `requeue_reason=oom`, `mem_reserve` y `attempts` sin incrementar (reutiliza `recovery._requeue`); agotado, reporta `error_type=oom`.
- Aplica AD-05, AD-06, AD-08 (el OOM del hijo no mata al supervisor), AD-30 (la reserva se suma a la huella) y SUP-14. Sin AD nueva: la política ya es SUP-14.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_codigo_menos_9_con_oom_kill_es_oom`, `test_menos_9_sin_oom_kill_es_killed`, `test_oom_aumenta_reserva_y_no_gasta_intentos`, `test_oom_agotado_falla_con_causa_oom`, `test_parsea_memory_events_oom_kill` | Clasificación y política sin red ni reloj |
| Integración | Worker con `memory.events` simulado en archivo temporal: primer intento OOM reencola con reserva mayor; tras 2 reencolados falla con `oom`. OOM real con asignador en contenedor (marca `integration`, requiere Docker/WSL2) | Cumple RF-26 |
| Aceptación | No aplica: sin criterio de extremo a extremo propio | — |

## Mediciones

M1 (OOM provocado): `docker exec <w> cat /sys/fs/cgroup/memory.events` y `docker inspect -f '{{.State.OOMKilled}}' <w>` tras bajar `mem_limit` y lanzar audio largo; 3 repeticiones; ficha `docs/modulo-M1-memoria.md`. Pendiente de nodos reales: no se inventa ningún dato.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-18): clasificar OOM y política de reencolado` | `oom_policy.py`, `read_memory_events`, pruebas unitarias |
| 2 | `feat(F-18): reencolar sub-tareas terminadas por OOM` | Integración en `worker_node`, `exit_code` en `ProcessingError`, prueba de integración |

## Riesgos y preguntas abiertas

- Se asume factor 1.5 y reserva inicial igual a la huella de la operación (configurables, provisionales hasta medir).
- El OOM real en contenedor no se prueba en Windows sin Docker/WSL2; queda como ficha M1 pendiente.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code | 2026-11-10 | SPEC completo, plan de pila en 2 partes; verificación no independiente (e190b38) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Claude Code | 2026-11-10 | Pruebas nuevas en rojo (ModuleNotFound/ImportError), sin código; verificación no independiente (7b0f5ac) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code | 2026-11-10 | 44 pruebas en verde (oom, cgroup, arquitectura); verificación no independiente (d20fcae) |
