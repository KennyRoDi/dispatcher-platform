# SPEC F-36: Cancelación en curso

**Fase:** revision
**Base:** feat/F-38-1-despliegue-en-tres-nodos
**Verificación IA:** revision 44c6c61
**Historia:** US-36 · **Requisitos:** RF-45, RF-12 · **Responsable:** J

## Objetivo

Demostrar con datos medidos que cancelar un caso pesado (archivo de al menos 200 MB) a mitad de procesamiento detiene las sub-tareas y libera procesos, memoria y temporales [B.6 Cancelación en curso]. F-12 dejó el mecanismo (`ProcessSupervisor`, `cancel:{caso}`), pero en producción es inerte: `multimedia_processor.process` no recibe el supervisor y `main()` no lo construye, de modo que FFmpeg se lanza con `subprocess.Popen` fuera de su control. F-36 cierra esa brecha y mide el antes y después.

## Alcance

**Incluye:**
- `multimedia_processor.process` y `_run` aceptan `supervisor` opcional y lanzan FFmpeg por él (grupo propio, scratch del supervisor); sin supervisor conservan el comportamiento actual.
- `Worker.main()` construye `ProcessSupervisor` con `PosixProcessRunner` y lo pasa al `Worker` (solo en POSIX).
- `ProcessSupervisor.cancel` idempotente: una segunda cancelación o un pid ya recogido no lanza `KeyError`.
- Escenario `scenarios/cancel_heavy.py`: genera un archivo sintético de 200 MB o más, lanza el caso, cancela a mitad y registra `ps`, `ls /scratch`, `memory.current` antes y después y el tiempo de liberación.
- Ficha de medición con datos reales en `docs/`.

**No incluye:** nuevos estados o transiciones del caso (F-10); cambios en `deploy/` (dueño K; `stop_grace_period` se declara, no se edita); despliegue en tres nodos (F-38); saturación de memoria (F-37).

## Criterios de aceptación

- **Dado** un caso pesado, con un archivo de al menos 200 MB, en procesamiento
- **Cuando** se cancela a mitad de procesamiento
- **Entonces** se detienen sus sub-tareas
- **Y** no quedan procesos ni archivos temporales de esas sub-tareas
- **Y** la memoria del worker disminuye
- **Y** el caso queda `cancelled`

## Diseño

- **Contratos:** `docs/CONTRATOS.md` sin cambios; usa la clave y canal `cancel:{caso}` de F-12 y el puerto `ProcessRunner`.
- **Decisiones:** AD-09 y AD-31 (supervisor, `SIGTERM`, gracia de 10 s, `SIGKILL`, `waitpid`). Sin decisión nueva.
- **Capas y archivos:** `src/workers/multimedia_processor.py` (`process`, `_run`: obtiene el pid por `supervisor.start`, lee su progreso y espera con el supervisor); `src/workers/worker_node.py` (`main()`); `src/application/process_supervisor.py` (idempotencia de `cancel`); `scenarios/cancel_heavy.py` (script, sin lógica de dominio).
- **Reutiliza:** `SubprocesosPorCaso` y `escuchar_cancelaciones` (`src/workers/cancelacion.py`), `CgroupResourceReader`, `scripts/run_load.py` para lanzar el caso.
- **Gracia frente a `stop_grace_period`:** `grace_seconds` (10 s) es mucho menor que los 31 min de `deploy/docker-compose.worker.yml`; se verifica por prueba de configuración, sin cambiar el compose.
- **Puntos abiertos de F-12 que cierra:** supervisor sin uso en producción, `main()` sin cablear y `KeyError` en segunda cancelación.
- **Riesgo de diseño:** `_run` lee el stdout de FFmpeg para el progreso; el runner POSIX debe exponer ese pipe o `_run` debe leer un archivo de progreso. El Arquitecto de la parte 1 elige la forma mínima y la anota aquí.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_cancel_dos_veces_no_lanza`, `test_cancel_pid_desconocido_no_lanza` | Cancelación idempotente |
| Unitaria | `test_run_usa_supervisor_si_se_provee`, `test_run_sin_supervisor_igual_que_antes` | `_run` lanza por el supervisor y no rompe el modo actual |
| Unitaria | `test_main_construye_supervisor_en_posix` | Cableado de producción |
| Unitaria | `test_gracia_menor_que_stop_grace_period` | La gracia cabe en el apagado del contenedor |
| Integración | Worker real con FFmpeg en Linux (WSL2 o contenedor): cancelar y comprobar sin procesos ni scratch | Sin hijos ni temporales tras cancelar |
| Aceptación | `scenarios/cancel_heavy.py` con archivo de 200 MB o más | Caso `cancelled`, recursos liberados y evidencia de B.6 |

## Mediciones

Escenario B.6, ficha `docs/escenario-B6-cancelacion.md`. Comandos exactos, en el worker, antes de cancelar, 1 s después y al estabilizarse; 5 repeticiones:
- `docker exec <w> ps -eo pid,ppid,stat,rss,cmd`
- `docker exec <w> ls -la /scratch`
- `docker exec <w> cat /sys/fs/cgroup/memory.current`
- tiempo entre `POST /cases/{id}/cancel` y el último proceso ausente.

**Medición pendiente:** requiere los nodos reales (contenedores de F-38). Hasta medirla, la ficha declara «sin dato medido» y el módulo queda con máximo 2 [Parte I §5].

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-36): cablear el supervisor en el worker` | `process`/`_run` con supervisor, `main()`, `cancel` idempotente y pruebas unitarias |
| 2 | `feat(F-36): escenario de cancelación en curso` | `scenarios/cancel_heavy.py`, integración en Linux y ficha B.6 (con «Medición pendiente» si faltan nodos) |

## Riesgos y preguntas abiertas

- El adaptador es POSIX: en Windows las pruebas con procesos reales se omiten; se corren en Docker o WSL2.
- La lectura de progreso por stdout puede obligar a ampliar el puerto `ProcessRunner` (`src/application/ports.py`); se decide en la parte 1.
- La medición real depende de F-38 (nodos de K) y de 200 MB sintéticos; no se usan datos reales de terceros.
- La parte 2 no sigue TDD (escenario); la parte 1 sí.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5), sin subagente: NO independiente | 2026-11-10 | SPEC sin campos pendientes (sin marcadores); 2 PR de pila; cubre puntos abiertos de F-12 (supervisor inerte, main sin cablear, KeyError en doble cancel, gracia 10 s < stop_grace_period 31m); medicion B.6 marcada Medicion pendiente (nodos reales). Rama con origin/main fusionado. (d2cbae0) |
| verificación IA de plan | Claude Code (Sonnet 5.5), sin subagente: NO independiente | 2026-11-10 | SPEC completo; 2 PR de pila; cubre puntos abiertos de F-12; medicion B.6 como Medicion pendiente. Rama con origin/main fusionado. (7a7f81d) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Claude Code (Sonnet 5.5), sin subagente: NO independiente | 2026-11-10 | 9 pruebas nuevas en tests/unit/test_cancelacion_en_curso.py, sin codigo de produccion; 8 en rojo por la razon esperada, 1 (run sin supervisor) en verde por conservar el comportamiento (ab8cd75) |
| tests | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de implementacion | Claude Code (Sonnet 5.5), verificación no independiente | 2026-11-10 | 1256 pruebas unitarias en verde; supervisor cableado en process/_run y main() (d80b225) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 | tamaño medido contra rama F-38 obsoleta (3814 líneas); contra origin/main son 97 líneas en src. Aprobación delegada por José en el chat |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | Criterios OK. Docker Linux: 1731 passed. Intentos de romper: doble cancel, hijo que ignora SIGTERM con nieto (SIGKILL tras gracia, sin sobrevivientes), cancel tras terminar: sin fallos. Hallazgo menor: modo supervisado pierde stderr de FFmpeg (respaldo NVENC->CPU no se activa). (5843974) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat; el límite de 400 líneas se mide contra la rama F-38 sin fusionar (3814 líneas); contra main el código son ~100 líneas |
| verificación IA de documentacion | Claude Code Sonnet 5.5 (no independiente) | 2026-11-10 | diff --stat: ARQUITECTURA AD-31 y reutilizacion; sin datos inventados, medicion real pendiente (f34bbae) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de revision | Claude Code Sonnet 5.5 (no independiente) | 2026-11-10 | Revisor: diff cumple SPEC parte 1 (supervisor en process/_run, main cableado, cancel idempotente, gracia 10s). Hallazgo menor ya registrado: stderr FFmpeg perdido en modo supervisado (44c6c61) |
