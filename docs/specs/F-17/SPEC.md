# SPEC F-17: Control de admisión

**Fase:** pr
**Base:** feat/F-16-2-limites-por-worker
**Verificación IA:** revision 670a461
**Historia:** US-17 · **Requisitos:** RF-25 · **Responsable:** J

## Objetivo

Un worker solo saca de la cola una sub-tarea si su memoria cgroup disponible cubre la huella medida más un margen. Si no cabe, no la toma y otro nodo con capacidad puede hacerlo, evitando terminaciones por OOM [B.5 M1].

## Alcance

**Incluye:**
- Función pura `admits(current, max, footprint, margin)` en `src/domain/admission.py`.
- Tabla de huellas por tipo de contenido/operación y margen, ambos en configuración, sin valores numéricos predeterminados (como AD-29).
- Compuerta en el consumidor del worker: antes de `blpop`, lee `ResourceReader` y solo consume si la sub-tarea más pequeña que atiende cabe; si no, espera y reintenta sin tocar la cola.
- Ficha M1: tabla de huella y gráfico de memoria por worker durante una ráfaga (se llena con medición real).

**No incluye:** detección o política OOM (F-18), huella RSS/PSS por modelo y estrategias de carga (F-19), límites y arranque de cgroups (F-16), cambios al contrato `WorkQueue` o `ResourceReader`.

## Criterios de aceptación

- **Dado** un worker sin memoria para otra sub-tarea según la huella medida
- **Cuando** hay trabajo en cola
- **Entonces** no la saca de la cola y otro nodo con capacidad puede tomarla

## Diseño

- **Usa:** `ResourceReader`/`ResourceUsage` (F-16, `memory_current`, `memory_max`), sin cambios. `CgroupResourceReader` de `src/infrastructure/`.
- **Capas:** dominio `src/domain/admission.py` (`admits` más `FootprintTable`, validación estricta de bytes como `node_budget.py`); configuración en `src/workers/config.py` (huellas y margen explícitos, error si faltan); compuerta en `src/workers/worker_node.py::poll_once`.
- **Decisión de compuerta:** la cola actual es `blpop` multi-cola, que ya extrae al llamarse. La compuerta va antes del `blpop`: se consulta el recurso y, si ni la huella mínima de las colas que atiende cabe, se espera (`stop_event.wait`) en lugar de consumir. Una sub-tarea nunca se saca para devolverse. Propuesta de AD-30 en `docs/ARQUITECTURA.md` §8: admisión previa al `blpop` con la huella mínima, alternativa descartada: sacar y reencolar (riesgo de pérdida y reordenamiento).
- **Fallo del lector:** error al leer el cgroup equivale a no admitir y se registra (coherente con AD-29: no omitir el chequeo ante errores).
- **Reutiliza:** validación de enteros de `node_budget.py`; sin cambios de código del I Proyecto.
- **Dueños de archivos:** `src/domain/admission.py` y `src/workers/` son de José (CONTRATOS §38).

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_rechaza_si_no_cabe_huella_con_margen` | `admits` rechaza si `max - current < footprint + margin` |
| Unitaria | `test_admite_en_el_limite_exacto`, `test_rechaza_valores_invalidos` | Borde exacto y validación de bytes |
| Unitaria | `test_configuracion_sin_huella_ni_margen_falla` | Sin valores predeterminados |
| Unitaria | `test_poll_once_no_consume_si_no_cabe` (doble de `ResourceReader`, sin red ni `sleep`) | No se llama a `blpop` sin memoria; error de lectura también rechaza |
| Integración | worker con límite bajo y dos sub-tareas: una queda en cola | Otro worker con capacidad la toma |
| Aceptación | US-37 | Excedente espera en cola durante la ráfaga, sin OOM |

## Mediciones

M1 (ficha `docs/modulo-M1-memoria.md`): huella por tipo con `docker exec <id> cat /sys/fs/cgroup/memory.current` y `memory.peak` antes, durante y después de procesar una sub-tarea de cada tipo; 5 repeticiones por tipo. Ráfaga: muestrear `memory.current` por worker cada 1 s con cola superior a la capacidad. Requiere nodos WSL2 reales y la parte 2 de F-16; si no están disponibles se declara «pendiente», nunca se estima.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-17): control de admisión por huella de memoria` | `admits`, tabla de huellas y margen en config, compuerta en el worker, AD-30, ficha M1 con el estado de la medición |

## Riesgos y preguntas abiertas

1. **Huellas sin medir.** Sin medición no hay valores; la configuración es obligatoria y la evidencia de la ficha queda pendiente hasta tener nodos. ¿Se acepta cerrar la parte 1 con la medición marcada «pendiente»?
2. **Compuerta global vs. por cola.** Se propone usar la huella mínima de las colas atendidas; es conservador pero puede dejar libre una cola pequeña. ¿Se acepta, o el worker se limita a una cola por tipo?
3. **Dependencia de F-16 parte 2** (arranque y cgroup real) para la integración con cgroups reales; las pruebas usan dobles.
4. **AD-30** requiere su aprobación.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (misma sesión, no independiente) | 2026-11-10 | SPEC completo sin campos pendientes; alcance, pruebas, pila de 1 parte y preguntas abiertas revisados contra backlog, IMPLEMENTACION §5 y AD-29 (4e97c68) |
| verificación IA de plan | Claude Code (misma sesión, no independiente) | 2026-11-10 | SPEC completo; alcance, pruebas, pila de 1 parte y preguntas abiertas revisados (1dd82fc) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | pytest | 2026-11-10 | Pruebas nuevas en tests/unit/test_admission.py y tests/test_worker_node.py; 20 fallan por módulo o API inexistente, sin código de implementación; cubren admits, tabla, config obligatoria y compuerta de poll_once (f010bc2) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | pytest | 2026-11-10 | admits, FootprintTable, load_admission_config y compuerta en poll_once antes de blpop; 69 pruebas en verde (admission, worker_node, arquitectura); ~100 líneas de código (d0c909a) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | pytest | 2026-11-10 | QA en la misma sesión (no independiente): 69 pruebas en verde, 88 líneas de código; intentos de romper: valores bool, negativos y no ASCII rechazados, error de lectura no consume. Hallazgo: memory.max=max hace que el worker nunca admita (se registra el error cada ciclo). Medición M1 pendiente, sin nodos WSL2 ni F-16 parte 2 (7e1fee3) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de documentacion | git diff --stat | 2026-11-10 | Documentación por subagente haiku: AD-30 en ARQUITECTURA, ficha M1 con medición pendiente y variables obligatorias en WORKER_CONTRACT; 3 archivos, 21 líneas, sin código (1d55da4) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de revision | revision (misma sesión, no independiente) | 2026-11-10 | Revisión del diff contra el SPEC: APROBADO. 69 pruebas en verde, capas respetadas, sin llaves ni datos reales. Observaciones no bloqueantes: CGROUP_PATH nuevo sin documentar (worker_node.py:406); con WORKER_CONCURRENCY>1 los hilos pueden pasar la compuerta a la vez (worker_node.py:189); memory.max=max nunca admite (ya en AD-30) (670a461) |
| revision | José Andrés Loría Herrera | 2026-11-10 |  |
