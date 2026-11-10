# SPEC F-16: Límites por worker

**Fase:** verificacion
**Base:** feat/F-16-1-limites-por-worker
**Verificación IA:** verificacion 60d66a5
**Historia:** US-16 · **Requisitos:** RF-24, RNF-14 · **Responsable:** J

## Objetivo

Permitir al operador arrancar workers con un límite de memoria verificable en cgroups v2 y rechazar un presupuesto de arranque que exceda la memoria del nodo. Corresponde al límite por worker de [B.5 M1]; la ficha medirá el límite real, sin confundirlo con la huella del modelo ni con el control de admisión de F-17.

## Alcance

**Incluye:** lector de memoria de cgroup conforme a `ResourceReader`; preflight de suma de límites y reserva; configuración de límites sin swap; prueba de integración y evidencia de `memory.max` por contenedor.

**No incluye:** admisión de sub-tareas (F-17), clasificación o recuperación de OOM (F-18), carga de modelos y comparación de estrategias (F-19), heartbeat/dashboard (F-15), ni benchmark de inferencia (F-31).

## Criterios de aceptación

- **Dado** el Compose de un nodo.
- **Cuando** arranca.
- **Entonces** `memory.max` tiene el límite configurado, y el preflight rechaza si la suma supera la RAM disponible.
- Conforme a ARQUITECTURA §6 y AD-05, cada worker tiene `mem_limit == memswap_limit`; el presupuesto considera la reserva del nodo y todos los contenedores worker que se arrancan, incluidas sus réplicas.
- Una configuración ausente, no positiva o ilegible no se interpreta como capacidad ilimitada ni permite continuar silenciosamente.

## Diseño

Se conservan sin cambios `ResourceReader.read() -> ResourceUsage` (`src/application/ports.py`) y el modelo existente `src/domain/resources.py`. Un lector en `src/infrastructure/cgroup_resources.py`, con ruta de cgroup e identificador inyectados, lee `memory.current` y `memory.max` en bytes; rechaza `max`, datos inválidos y cgroups v2 ausentes mediante error explícito. Se agregará `comprobar_resource_reader` a `tests/contratos.py`, que todavía no contiene ese comprobador, y se aplicará tanto al doble existente `FakeResourceReader` como al lector real con ruta temporal, sin alterar la firma pública. AD-29 y SUP-23 registran estos comportamientos como propuestas sujetas a aprobación humana del plan.

La decisión de presupuesto es pura, en `src/domain/node_budget.py`: suma de límites más reserva menor o igual que RAM declarada para el entorno Docker. La parte 2 ejecuta `docker compose config --format json`, valida `NODE_NAME` (hostname), `NODE_IP` (IPv4 o IPv6 válida), `mem_limit` y `memswap_limit` para cada servicio worker y suma los límites efectivos. Lee `MemTotal` de `/proc/meminfo` en WSL2, no usa la RAM física de Windows. `scripts/preflight.py` termina distinto de cero ante exceso o configuración inválida; `scripts/start_worker.py` vuelve a comprobar el presupuesto y no ejecuta `docker compose up` si falla. `--gpu` agrega el override GPU a ambos comandos.

Se aplican AD-01 (reutilizar Compose y contratos), AD-05 (cgroups v2, sin swap), AD-23 (sin `--scale`) y SUP-17. `WORKER_MEM_LIMIT` es obligatorio y se inyecta como ambos límites en Compose; su valor real debe calibrarse mediante medición, por lo que no se asigna ni se declara medido en esta parte. SUP-24 propone reservar el máximo entre 1 GiB y 15 % de `MemTotal`; es un margen provisional, no una medición del consumo del sistema. No se incorporan decisiones sobre F-17 o F-18. La lectura de `memory.events` y la clasificación OOM quedan en F-18.

`deploy/` pertenece a Kenni según CONTRATOS. Para esta parte se coordinó el cableado mínimo: conservar el servicio worker actual, hacerlo exigir `WORKER_MEM_LIMIT`, validar el Compose efectivo antes del arranque y no usar `--scale` conforme a AD-23. No se cambia silenciosamente la topología ni se fija un límite sin medir. Las pruebas de presupuesto no dependen del trabajo de Claude en F-09.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_preflight_rechaza_suma_de_limites_mayor_a_ram`, igualdad en el borde, reserva, réplicas y entradas inválidas | La decisión de presupuesto no permite sobreasignar; usa valores sintéticos, sin Docker, red ni reloj real |
| Unitaria | Lector con archivos temporales: valores válidos, `max`, archivo ausente y contenido inválido | Interpretación en bytes y fallo explícito sin depender del SO de desarrollo |
| Contrato | Conformidad de `ResourceReader` aplicada al doble existente y al lector con ruta temporal | Conservación del contrato consumido por M1 y dashboard |
| Integración | Lectura de `memory.max` en cada contenedor y contraste con Compose efectivo, también con override GPU | El kernel aplica el valor configurado; requiere Docker Linux con cgroups v2 |
| Aceptación | Preflight de presupuesto válido y excesivo antes del arranque, con datos sintéticos | El caso excesivo termina con error y no ejecuta `compose up`; no cubre saturación de F-37 |

## Mediciones

En cada nodo B/C/D real, con su archivo de entorno local, obtener la configuración con `docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json`; en el nodo GPU agregar `-f deploy/docker-compose.worker-gpu.yml` antes de `config`. Registrar comando, nodo, fecha UTC, RAM efectiva de WSL2, reserva y límites explícitos. Las fuentes y comandos de lectura de RAM se concretarán al coordinar el arranque de la parte 2; no se declarará medido ningún valor recibido por configuración.

Por cada contenedor worker iniciado, ejecutar `docker exec <id> cat /sys/fs/cgroup/cgroup.controllers`, `docker exec <id> cat /sys/fs/cgroup/memory.max` y `docker exec <id> cat /sys/fs/cgroup/memory.swap.max`; guardar los comandos resueltos con sus identificadores y salidas crudas en `docs/evidencia/F-16/`. Repetir la lectura en tres arranques por nodo, registrando fallos y comparando bytes con Compose efectivo. No se necesita ráfaga ni OOM para verificar este límite.

Crear la ficha `docs/modulo-M1-memoria.md` con los cinco elementos del Anexo 2, tabla de valores configurados/observados y referencia al kernel Linux (R4 de ARQUITECTURA). Declarar que se mide la VM WSL2; dejar pendientes, identificados por feature, los productos de M1 correspondientes a F-17/F-18/F-19. Si no hay nodos disponibles, registrar la limitación y solicitar decisión humana en la fase de medición; nunca sustituir datos reales por estimaciones.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-16): agregar lector de memoria y validar presupuesto` | Decisión pura, lector cgroup y pruebas unitarias/de contrato; máximo 400 líneas de producto. Sin cambios en workers de F-09 ni en deploy |
| 2 | `feat(F-16): aplicar limites y comprobar arranque de workers` | CLI de preflight, cableado mínimo coordinado en Compose/arranque, prueba de integración y evidencia por nodo; máximo 400 líneas de producto. Base: rama de parte 1; repite fases 2 a 6 |

## Riesgos y preguntas abiertas

- Se acordó para la parte 2 `scripts/preflight.py`, `scripts/start_worker.py`, `WORKER_MEM_LIMIT`, la comprobación de `NODE_NAME`/`NODE_IP` y la omisión de `--scale` por AD-23.
- Confirmar la disponibilidad de nodos B/C/D y cgroups v2 de Docker Desktop/WSL2 para verificar y medir la parte 2. Este plan no afirma haberlos comprobado.
- El valor de `WORKER_MEM_LIMIT` y la reserva requieren medición; SUP-24 fija solo un margen provisional para el preflight. La RAM se lee desde `/proc/meminfo` del entorno Linux que aplica los cgroups.
- El preflight es una comprobación de presupuesto al arranque, no una garantía de memoria libre futura ni reemplazo de F-17.
- La parte 1 es independiente de F-09; la parte 2 no debe sobrescribir los cambios de despliegue que entren entretanto.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Codex | 2026-11-10 | Revision independiente del arquitecto: contraste de SPEC con US-16, RF-24, B.5 M1, AD-05 y contratos existentes; dos partes de hasta 400 lineas; git diff origin/main...HEAD --check correcto; solo tres documentos, sin campos pendientes ni codigo. Corregidos comprobador inexistente y registro ADD/SUP. Sin pruebas de producto ni mediciones fisicas en fase plan; coordinacion de deploy y RAM WSL2 pendientes antes de parte 2. (94fc871) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Codex | 2026-11-10 | Revision independiente del developer: diff 995914d..HEAD solo agrega pruebas y comprobador en tests; git diff --check correcto. py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short: 50 failed por ausencia de src.domain.node_budget y src.infrastructure.cgroup_resources, 3 passed del doble, sin errores de coleccion. py -m pytest -q tests/unit/test_contratos.py: 9 passed. Baseline antes de cambios: 1085 passed, 2 skipped, 3 deselected. Revisados presupuesto, reserva, replicas, valores invalidos, lectura temporal y conformidad; sin implementacion ni mediciones fisicas, parte 2 fuera de esta fase. (adbb225) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Codex | 2026-11-10 | Revision independiente del developer sobre c19dc26: solo node_budget.py y cgroup_resources.py, 52 lineas de producto; logica pura en dominio y lectura de archivos en infraestructura, contratos conservados. git diff 2a84751..HEAD -- tests/ vacio: pruebas aprobadas sin cambios; git diff --check correcto y arbol limpio. Ejecute py -m pytest -q -m not-integration/not-acceptance mediante expresion de marcadores del proyecto: 1138 passed, 2 skipped, 3 deselected, una advertencia preexistente de Starlette, 42.50s. Sin Docker ni mediciones fisicas en parte 1; cableado y evidencia quedan para parte 2. (c19dc26) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | Codex | 2026-11-10 | Revision independiente de QA parte 1 sobre e5cb8cf: leido QA-parte-1.md y diff; sin cambios de src ni tests desde aprobacion implementacion, arbol limpio y diff --check correcto. Reproduje py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py tests/unit/test_arquitectura.py: 57 passed. Reproduje mutacion en memoria que acepta cualquier presupuesto: test_preflight_rechaza_suma_de_limites_mayor_a_ram falla como esperado, 1 failed y 26 deselected. QA documento suite 1138 passed, 2 skipped, 3 deselected y seis mutaciones detectadas. Sin hallazgos parte 1; no hubo mediciones SO, Docker/WSL2 y cableado corresponden a parte 2. (e5cb8cf) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de documentacion | Codex | 2026-11-10 | Revision independiente del documentador sobre d76552a: leidos cuatro documentos contra src/domain/node_budget.py, src/infrastructure/cgroup_resources.py, SPEC, QA y Anexos 2/3. Ficha con cinco secciones comprobadas por Select-String, sin mediciones SO inventadas y parte 2 pendiente. AD-29/SUP-23 reflejan aprobacion humana del plan existente. Bitacora borrador con tres consultas y dos errores reales de plan corregidos, sin publicacion hasta aprobacion humana. git diff 9c7d20e..HEAD --check correcto; solo docs, diff src/tests vacio, arbol limpio. Conteos de pruebas coinciden con QA; no se repitio suite al no cambiar producto. (d76552a) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de revision | Codex | 2026-11-10 | Revision independiente del revisor sobre 060aaaa: releido diff completo origin/main...HEAD contra SPEC y plan de parte 1, sin hallazgos. Leido REVISION-parte-1.md, pruebas focalizadas del revisor 66 passed. Comprobe 52 lineas de producto, contratos y capas conservados, tests sin cambios desde adbb225, tres entradas de bitacora en origin/estado, diff --check correcto y arbol limpio; ultimo commit solo informe. Main actualizado 691846cf y ancestro comun a96bbe29. No repeti suite sin cambios producto. Aprobacion IA solo parte 1; CLI, Compose y mediciones Docker/WSL2 quedan pendientes parte 2. (060aaaa) |
| revision | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Codex | 2026-11-10 | Revision independiente fase tests parte 2: diff solo agrega tests unitarios YAML de Compose CPU/GPU y aclara en SPEC interfaz de arranque pendiente; no toca codigo ni deploy. git diff --check correcto y arbol limpio. py -m pytest -q tests/unit/test_f16_compose_memory.py --tb=short: 2 failed, ambas por mem_limit ausente, sin errores de coleccion. Pruebas no fijan nombres de CLI, wrapper ni replicas. Pruebas heredadas parte1: 53 passed en ejecucion focalizada. Aun pendiente coordinar con Kenni contrato del preflight/arranque antes de implementación; no hay mediciones SO en fase tests. (50b3069) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Codex | 2026-11-10 | Revision independiente parte2 implementacion sobre 7fef365: inspeccionadas Compose, preflight, wrapper, SUP-24 y SPEC; WORKER_MEM_LIMIT obligatorio sin valor medido, Compose GPU hereda worker, sin --scale; start_worker valida antes de compose up. git diff --check correcto, arbol limpio. Suite completa py -m pytest -q -m not integration and not acceptance: 1147 passed, 2 skipped, 3 deselected, una advertencia Starlette, 42.54s. Focalizadas CPU/GPU, preflight y parte1: 62 passed. No ejecutar Docker ni hacer mediciones de nodos; límites medidos y M1 pendientes hasta carga pesada B/C/D. Código/tests añadidos dentro scope, no pruebas debilitadas. commit 7fef365 publicado. (7fef365) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| devuelta de verificacion | José Andrés Loría Herrera | 2026-11-10 | QA encontró que NODE_IP no valida formato IP; agregar prueba y rechazar valor inválido |
| verificación IA de implementacion | Codex | 2026-11-10 | QA parte2 revisado independientemente tras fix f8bd884: informe a980c3c verifica fallo inicial NODE_IP y correccion ipaddress. git diff --check y arbol limpio. Orquestador reprodujo tras fix 11 pruebas focalizadas y suite completa 1149 passed,2 skipped,3 deselected. Leido codigo y pruebas; preflight valida Compose antes de up, reserva SUP-24 sigue supuesto, WORKER_MEM_LIMIT obligatorio sin default. No hay Docker/Compose real ni nodos B/C/D, por tanto evidencia física pendiente y explícita en QA-parte-2.md. No se repitieron pruebas sin cambios posteriores al run 1149. (a980c3c) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | Codex | 2026-11-10 | QA de F-16 parte 2 tras fix de NODE_IP; 11 focalizadas y suite completa 1149 passed, 2 skipped, 3 deselected; informe a980c3c; sin Docker ni mediciones físicas, pendientes y documentadas. (60d66a5) |
