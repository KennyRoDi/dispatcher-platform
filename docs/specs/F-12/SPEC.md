# SPEC F-12: Cancelación real

**Fase:** documentacion
**Base:** feat/F-12-1-cancelacion-real
**Verificación IA:** verificacion f952e04
**Historia:** US-12 · **Requisitos:** RF-12, RF-45 (mecanismo) · **Responsable:** J

## Objetivo

Hoy `POST /cases/{id}/cancel` marca el caso y las sub-tareas pendientes como `cancelled`, pero el subproceso en ejecución (FFmpeg, modelos) sigue consumiendo CPU y memoria y deja temporales [B.4 Reintentos y cancelación; ARQUITECTURA §1, fila Cancelación]. Para el supervisor, cancelar debe detener de verdad el trabajo en curso y liberar procesos, memoria y archivos temporales (RF-12).

## Alcance

**Incluye:** `ProcessSupervisor` que lanza cada sub-tarea en su propio grupo de procesos y la detiene con `SIGTERM`, gracia y `SIGKILL` con `waitpid` (AD-09); aviso de cancelación al worker por clave `cancel:{caso}` más `PUBLISH`; borrado de `/scratch/{subtarea}` en `finally` del padre y de huérfanos al arrancar; manejo de `SIGTERM` del worker (Clean Shutdown 1 a 4).

**No incluye:** la comparación medida antes/después de memoria, procesos y temporales (F-36, B.6); el cambio de `stop_grace_period` y `init: true` en `deploy/` (dueño F-16, se coordina); estados y transiciones del caso (F-10); reintentos (F-11).

## Criterios de aceptación

- **Dado** un caso con una sub-tarea en ejecución, **cuando** se cancela, **entonces** el subproceso recibe `SIGTERM` y luego `SIGKILL`, no quedan zombies, los temporales se borran y el caso queda `cancelled`.

## Diseño

- **Decisiones:** AD-09 y Clean Shutdown (ARQUITECTURA §9). Sin decisión nueva.
- **Capas:** `src/application/process_supervisor.py` (lógica de señales y gracia, con reloj, `kill` y `waitpid` inyectados) y puerto `ProcessRunner` en `src/application/ports.py`; adaptador POSIX en `src/adapters/posix_process_runner.py` (`Popen(start_new_session=True)`, `os.killpg`, `os.waitpid`); integración en `src/workers/worker_node.py` (suscripción a `cancel:{caso}`, `finally` de scratch, limpieza de huérfanos al arrancar).
- **Reutiliza:** `worker_node.py` (inflight, `SIGTERM`), `recovery.py` (subtareas de caso cancelado), endpoint `cancel` existente (añade clave y `PUBLISH`), `multimedia_processor.py` (hoy usa `subprocess.run` con timeout; pasa por el supervisor).
- **Contratos:** no cambia ninguno; usa Redis y `/scratch` ya definidos.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_cancelar_envia_sigterm_y_luego_sigkill`, `test_temporal_se_borra_tras_sigkill`, `test_no_quedan_zombies` (subproceso real `sleep` en grupo propio) | Escalada de señales, limpieza y `waitpid` |
| Integración | Worker en contenedor: `ps` y `ls /scratch` antes y después de cancelar | Sin procesos ni temporales tras cancelar |
| Aceptación | US-36 (cancelación en curso) | Caso `cancelled` y recursos liberados de punta a punta |

## Mediciones

No aplica. La salida de `ps` y `ls` es evidencia de la prueba de integración; la medición B.6 es de F-36.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-12): supervisor de procesos con SIGTERM y SIGKILL` | `ProcessSupervisor`, puerto, adaptador POSIX y pruebas unitarias |
| 2 | `feat(F-12): cancelación y limpieza en el worker` | Clave y `PUBLISH` en el endpoint, suscripción en el worker, scratch en `finally`, huérfanos y `SIGTERM` del worker |

## Riesgos y preguntas abiertas

- El adaptador es POSIX; en Windows (desarrollo local) las pruebas con `sleep` real requieren WSL2. ¿Se marcan `skipif` en Windows?
- La gracia por defecto (propuesta: 10 s, configurable) debe ser menor que `stop_grace_period`, que hoy es de 31 min en `deploy/` y pertenece a F-16.
- Si el hijo ya terminó entre la señal y `killpg`, se ignora `ProcessLookupError`.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code | 2026-11-10 | SPEC sin campos pendientes; 2 PR; verificación no independiente (sin subagente) (767ac98) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | pytest tests/unit/test_process_supervisor.py -q | 2026-11-10 | 6 pruebas con dobles fallan por ModuleNotFoundError (falta process_supervisor); 4 con sleep real saltadas en Windows (requieren WSL2), no ejecutadas. Sin código de implementación. Verificación NO independiente: sin subagente. (5c51d61) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | pytest | 2026-11-10 | pytest tests/unit/test_process_supervisor.py y test_arquitectura: 10 passed, 4 skipped (reales POSIX, sin WSL con Python). Diff de tests/ revisado: solo SIGKILL portable en Windows, sin debilitar. Verificación NO independiente (sin subagente). (2151127) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), sin subagentes: NO independiente | 2026-11-10 | pytest tests/unit/test_process_supervisor.py y test_arquitectura.py: 10 pasan, 4 POSIX reales omitidos (win32, sin WSL con python). SPEC sin mediciones. Prueba manual: cancel(pid) repetido o con pid desconocido lanza KeyError (hallazgo, fuera del SPEC). Diff 356 lineas. (66d5f1e) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de documentacion | git diff --stat; flujo.py verificar | 2026-11-10 | Documentador (haiku) no cambió nada: SPEC dice Mediciones No aplica y Sin decisión nueva (AD-09 ya existe); reutilizacion.md no existe; README sin cambio. Verificación no independiente: solo comprobé árbol limpio y SPEC. (fa4b353) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de revision | pytest tests/unit/test_process_supervisor.py y test_arquitectura; git diff origin/main...HEAD | 2026-11-10 | Revision hecha por el orquestador sin subagente: verificacion NO independiente. Diff de parte 1 (5 archivos, 360 lineas con SPEC y pruebas) releido contra SPEC: supervisor, puerto y adaptador POSIX dentro de alcance. Hallazgo abierto: cancel lanza KeyError en doble cancel o pid desconocido (fuera del SPEC). 4 pruebas POSIX no ejecutadas aqui (Windows). (8b9b543) |
| revision | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | pytest tests/test_coordinator.py tests/test_worker_cancelacion.py -k cancel | 2026-11-10 | 5 pruebas nuevas fallan por falta de funcionalidad (sin clave/PUBLISH en cancel; Worker sin supervisor), no por errores de prueba; sin codigo de implementacion. SIGTERM del worker ya existe (_handle_signal), sin prueba nueva. Verificacion NO independiente: sin subagente. (aebee8a) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code (Sonnet 5.5), sin subagente: verificación NO independiente | 2026-11-10 | Releí SPEC y diff. pytest test_coordinator, test_worker_cancelacion, test_worker_node, test_arquitectura: 86 passed. git diff de tests/ vacío (sin debilitar). Nuevo src/workers/cancelacion.py; +26 líneas en worker_node y rutas_casos. No verificado: ffmpeg real vía supervisor ni main() cableado. (8c85862) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), sin subagente: verificación NO independiente | 2026-11-10 | Docker python:3.13-slim (Linux): pytest test_process_supervisor + test_worker_cancelacion + test_coordinator = 49 passed, incluidos los 4 @posix de la parte 1 (nunca corridos en Windows). Demo ps/ls en contenedor con supervisor real: antes 3 procesos 'sleep 60' (shell ignora SIGTERM + 2 hijos) y /scratch/t1; despues 0 procesos, sin zombies, /scratch vacio. Diff src parte 2 = ~102 lineas (<=400). (f952e04) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 |  |
