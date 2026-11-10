# SPEC F-16: Límites por worker

**Fase:** plan
**Base:** main
**Verificación IA:** plan 94fc871
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

La decisión de presupuesto es pura, en `src/domain/node_budget.py`: suma de límites más reserva menor o igual que RAM declarada para el entorno Docker. La capa de infraestructura obtiene la configuración efectiva y la memoria del entorno donde Docker aplica el límite; nunca usa la RAM física de Windows como sustituto de la de WSL2. `scripts/check_node_budget.py` expone el preflight y termina con código distinto de cero ante exceso o configuración inválida. El procedimiento de arranque ejecuta el preflight antes de `docker compose up` y se detiene si falla.

Se aplican AD-01 (reutilizar Compose y contratos), AD-05 (cgroups v2, sin swap) y SUP-17 (parámetros calibrados con medición). No se fija ahora un límite ni una reserva numérica: serán configuración explícita y quedarán junto a la evidencia. No se incorporan decisiones sobre F-17 o F-18. La lectura de `memory.events` y la clasificación OOM quedan en F-18.

`deploy/` pertenece a Kenni según CONTRATOS: la segunda parte propone únicamente el cableado de límites y del preflight, sujeto a coordinación con su responsable antes de editar. Los Compose actuales contienen un servicio worker general; la separación por tipo exigida por AD-05 debe resolverse con Kenni antes de esa parte, sin cambiarla silenciosamente. Las pruebas de presupuesto no dependen de ese acuerdo ni del trabajo de Claude en F-09.

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

- Confirmar con Kenni el cableado mínimo de `deploy/`, el mecanismo de arranque y cómo conciliar el worker general actual con los contenedores por tipo de AD-05 antes de la parte 2. El acuerdo debe registrarse; no modifica contratos de aplicación.
- Confirmar la disponibilidad de nodos B/C/D y cgroups v2 de Docker Desktop/WSL2 para verificar y medir la parte 2. Este plan no afirma haberlos comprobado.
- Límites y reserva requieren configuración explícita sustentada por medición (SUP-17); no hay un valor predeterminado aprobado. La forma exacta de obtener la RAM efectiva en los nodos se documentará antes de implementar el preflight de arranque.
- El preflight es una comprobación de presupuesto al arranque, no una garantía de memoria libre futura ni reemplazo de F-17.
- La parte 1 es independiente de F-09; la parte 2 no debe sobrescribir los cambios de despliegue que entren entretanto.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Codex | 2026-11-10 | Revision independiente del arquitecto: contraste de SPEC con US-16, RF-24, B.5 M1, AD-05 y contratos existentes; dos partes de hasta 400 lineas; git diff origin/main...HEAD --check correcto; solo tres documentos, sin campos pendientes ni codigo. Corregidos comprobador inexistente y registro ADD/SUP. Sin pruebas de producto ni mediciones fisicas en fase plan; coordinacion de deploy y RAM WSL2 pendientes antes de parte 2. (94fc871) |
