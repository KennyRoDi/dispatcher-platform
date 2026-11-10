# SPEC F-12: Cancelación real

**Fase:** plan
**Base:** main
**Verificación IA:** plan 767ac98
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
