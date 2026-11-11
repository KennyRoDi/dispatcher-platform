# SPEC F-37: Saturación de memoria

**Fase:** documentacion
**Base:** main
**Verificación IA:** verificacion 79e10a9
**Historia:** US-37 · **Requisitos:** RF-46, RNF-09; [B.5 M1], [B.6 Saturación de memoria] · **Responsable:** J

## Objetivo

El enunciado pide que, ante una «carga que supera la memoria disponible de un nodo», el control de admisión de M1 «evite el colapso del nodo» [B.6 Saturación de memoria; B.5 M1]. RF-46 lo verifica así: «el nodo sigue respondiendo y sus heartbeats no se interrumpen». El control de admisión (F-17, AD-30), los límites de cgroup (F-16, AD-29), la detección de OOM (F-18) y el despliegue en tres nodos (F-38) ya existen. F-37 construye el **escenario** que los somete a una carga mayor que la memoria del worker y decide con datos si el nodo se mantuvo vivo, sin tocar el código de producción.

## Alcance

**Incluye:**

- `scenarios/memory_saturation.py`: genera el plan de carga, toma muestras y evalúa. Mismo patrón que `scenarios/cancel_heavy.py` (F-36): el módulo no levanta nodos; la corrida real la hace la persona.
- Plan de carga puro: dado `memory.max`, margen y huella por sub-tarea, calcula cuántas caben (`cupo`) y cuántas sub-tareas encolar para que el total supere `memory.max` (SUP-36).
- Muestras periódicas por worker: `memory.current` y `memory.max` (`/sys/fs/cgroup`), `OOMKilled` y reinicios del contenedor, instante del último heartbeat (`GET /workers`), sub-tareas en curso y en cola, y estado de cada sub-tarea.
- Evaluación pura de las cuatro afirmaciones del criterio: admite solo lo que cabe, el resto espera en cola, no hay colapso y los heartbeats continúan, todo termina al liberarse capacidad (SUP-37).
- Comparación sin control de admisión, **opcional y solo si es seguro** (SUP-38): un único worker de prueba aislado, con el mismo límite, sin tocar a los demás nodos.
- Ficha de evidencia `docs/evidencia/F-37_saturacion_de_memoria.md` y su referencia en `docs/modulo-M1-memoria.md`.

**No incluye:**

- Cambios en `src/` (admisión, lector de cgroups, OOM): son de F-16, F-17 y F-18.
- Reencolado por OOM y concurrencia por nodo (F-18, F-19).
- Backpressure del coordinador (F-24) y el escenario de ráfaga (F-33).
- Datos reales de terceros: la carga es sintética [B.3].
- Valores de huella o límite inventados: salen de la ficha M1 medida; sin ella, «Medición pendiente».

## Criterios de aceptación

Copiados de `docs/backlog/carga-fallos.md`, US-37:

- **Dado** un nodo con su control de admisión activo
- **Cuando** llega una carga superior a su memoria disponible
- **Entonces** los workers admiten solo lo que cabe
- **Y** el resto queda en cola
- **Y** el nodo no colapsa y mantiene sus heartbeats
- **Y** todos los casos terminan cuando se libera capacidad

- **Pruebas:** U admisión. I worker con límite bajo. A `scenarios/memory_saturation.py`.
- **Demuestra:** continuidad de heartbeats. **Evidencia:** gráfico de memoria y sub-tareas admitidas, y comparación sin admisión si es seguro hacerla.

## Diseño

**Capas.** Todo vive en `scenarios/` (fuera de `src/`, como F-36). La lógica es pura y recibe sus datos por parámetros y un ejecutor inyectado, así que las unitarias no usan red, `sleep` ni reloj real.

**Se reutiliza, sin modificar:**

| Pieza | Uso |
|---|---|
| `src/domain/admission.py` (`admits`, `FootprintTable`) | El plan calcula el cupo con la misma fórmula, para que escenario y worker no diverjan. |
| `Worker._fits_in_memory` y `poll_once` (AD-30) | Es lo que se pone a prueba: no consume de la cola si no cabe. |
| `src/infrastructure/cgroup_resources.py` | Lectura de `memory.current` y `memory.max` (AD-29). |
| `src/domain/oom_policy.py` (F-18) | Si pese a la admisión hay OOM, la muestra lo registra y la evaluación falla «no colapsa». |
| `scenarios/cancel_heavy.py` | Patrón de instantáneas con ejecutor inyectado y prueba de aceptación sobre un JSON. |
| `GET /workers` y `Heartbeat` (`src/workers/heartbeat.py`) | Fuente de la continuidad de heartbeats; el hilo `Heartbeat` es independiente del bucle de consumo. |
| `scripts/run_load.py` | Envío de casos y tabla por nodo. |

**Funciones previstas** (nombres explícitos, cortas, sin E/S salvo `tomar_muestra`):

- `planificar_carga(memory_max, margen, huella, factor) -> PlanCarga` (`cupo`, `subtareas`).
- `tomar_muestra(ejecutar, etiqueta, instante) -> dict`.
- `huecos_heartbeat(instantes, intervalo, tolerancia) -> list`.
- `evaluar(plan, muestras, estados_finales, intervalo_heartbeat) -> {"cumple": bool, "problemas": [...]}`.
- `main()` con salida JSON, para la Parte 2.

**Decisiones.** AD-41 (nueva, se registra en `docs/ARQUITECTURA.md` §8 en la Parte 1): la saturación se valida con un escenario basado en muestras, no con código de producción adicional. Alternativas: instrumentar el worker con métricas propias (cambia código de M1 ya aprobado); medir solo con `docker stats` (sin evaluación automática ni criterio reproducible). Supuestos nuevos en `docs/REQUERIMIENTOS.md`:

- **SUP-36.** «Carga superior a la memoria disponible»: huella total de las sub-tareas encoladas ≥ 2 × (`memory.max` × (1 − margen)). El factor es configurable y provisional.
- **SUP-37.** «Heartbeats no se interrumpen»: ningún intervalo entre heartbeats consecutivos del worker supera 3 × `HEARTBEAT_INTERVAL` durante la saturación; el 3 es provisional. «Admite solo lo que cabe»: en ninguna muestra `memory.current` supera `memory.max` ni hay `OOMKilled`. «Terminan»: todas las sub-tareas llegan a estado terminal antes del plazo de la corrida.
- **SUP-38.** La comparación sin admisión se hace solo si la persona confirma que el worker de prueba está aislado y que un OOM no afecta a otro nodo; si no, se declara «no realizada».

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_memory_saturation.py`: `planificar_carga` (cupo igual al de `admits`, margen, parámetros inválidos, total mayor que `memory.max`) | La carga supera la memoria y el cupo coincide con la admisión |
| Unitaria | `huecos_heartbeat` y `evaluar` con muestras sintéticas (sin hueco, con hueco, `memory.current` mayor que `memory.max`, `OOMKilled`, sub-tarea sin terminar) | La evaluación detecta cada incumplimiento del criterio |
| Integración | `tests/integration/test_saturacion_worker_linux.py`: worker real con límite bajo y Redis, solo POSIX | Con límite bajo el worker deja sub-tareas en cola y sigue enviando heartbeats |
| Aceptación | `tests/acceptance/test_memory_saturation_aceptacion.py` sobre `MEMORY_SATURATION_JSON`; se omite sin él | La corrida real cumple las cuatro afirmaciones de US-37 |

TDD aplica a la lógica de `scenarios/` (Parte 1). La corrida en nodos no lleva TDD.

## Mediciones

M1 y B.6, a cargo de la persona en los nodos WSL2 de F-38. **Medición pendiente:** hoy no hay datos.

1. Con la ficha M1 vigente (huella y límite medidos): `py -m scenarios.memory_saturation --salida docs/evidencia/F-37_<fecha>.json`.
2. Tres repeticiones; se reporta cada una, no solo la mejor.
3. Comparación sin admisión: una repetición en un worker aislado (SUP-38), o «no realizada».
4. Gráfico de `memory.current` y sub-tareas admitidas con los datos del JSON.
5. Ficha de destino: `docs/evidencia/F-37_saturacion_de_memoria.md` y `docs/modulo-M1-memoria.md`.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-37): escenario de saturacion de memoria con evaluacion` | `scenarios/memory_saturation.py` (plan, muestras, evaluación y `main`, unas 150 líneas), unitarias, aceptación sobre JSON e integración Linux. Registra AD-41 y SUP-36 a SUP-38 |
| 2 | `docs(F-37): evidencia de saturacion de memoria en nodos` | Corrida real con su JSON, gráfico, comparación sin admisión si es segura, ficha de evidencia y referencia en M1. Sin código; F-38 ya está fusionada, falta correr en los nodos |

## Riesgos y preguntas abiertas

- **Corrida real:** requiere nodos WSL2 y a la persona. Hasta entonces la Parte 2 queda «Medición pendiente» y no se inventan cifras.
- **Huella:** el cupo depende de la huella por operación (ficha M1, AD-30). Sin esa medición, el plan usa valores de configuración declarados provisionales.
- **Umbrales provisionales:** el factor 2 (SUP-36) y la tolerancia de 3 intervalos (SUP-37) son criterio propio; confirmar con quien aprueba.
- **Comparación sin admisión:** puede disparar un OOM del cgroup; se aísla en un solo worker (AD-05) y la persona decide si se hace (SUP-38).
- **Límite conocido de AD-30:** con `memory.max = max` el worker nunca admite; el escenario exige un límite finito (F-16).

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5), no independiente | 2026-11-11 | SPEC sin campos pendientes; reutiliza admission, cgroup_resources, oom_policy y cancel_heavy; pila de 2 partes; ejecutado en la misma sesion (14adff5) |
| plan | José Andrés Loría Herrera | 2026-11-11 |  |
| verificación IA de tests | Claude Code (Sonnet 5.5), sin subagente: verificación no independiente | 2026-11-11 | 22 pruebas unitarias nuevas fallan por ModuleNotFoundError de scenarios.memory_saturation; sin código de producción (52dee88) |
| tests | José Andrés Loría Herrera | 2026-11-11 | aprobación delegada por José en el chat |
| verificación IA de implementacion | Claude Code (Sonnet 5.5) | 2026-11-11 | 22 unitarias + arquitectura en verde; verificacion no independiente (c00f66f) |
| implementacion | José Andrés Loría Herrera | 2026-11-11 | aprobación delegada por José en el chat; suite completa no recolecta en Windows (os.geteuid/fcntl, 11 módulos ajenos a F-37); 26 pruebas del módulo y arquitectura en verde |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), no independiente | 2026-11-11 | 26 pruebas verdes; bordes probados (muestras vacías, hueco exacto 3x, memory.max=max, OOM, parámetros inválidos); 91 líneas; Docker: 3435 pasan, fallos solo TLS/certs/permisos ajenos. Mediciones en nodos: Medición pendiente (79e10a9) |
| verificacion | José Andrés Loría Herrera | 2026-11-11 | suite completa no recolecta en Windows; en Docker fallos solo en TLS/certs/permisos, ajenos a F-37. Aprobación delegada por José en el chat |
