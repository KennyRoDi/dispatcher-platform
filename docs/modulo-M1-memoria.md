# Módulo M1: gestión de memoria

**Responsable:** José Andrés Loría Herrera (`joselhcr`).
**Corte:** F-16, parte 2, 2026-11-10. **Mediciones de SO: pendientes.** Esta ficha todavía no acredita el módulo completo ni el límite aplicado por Docker/WSL2.

## 1. Qué se implementó

- `src/domain/node_budget.py`: `validate_node_budget` compara la suma de cada límite recibido más la reserva con la RAM declarada, en bytes. Acepta igualdad, reserva cero explícita y límites repetidos por réplica; rechaza exceso y valores inválidos mediante `ValueError`. RAM y límites deben ser enteros positivos; reserva, entero no negativo. No consulta el SO ni descubre réplicas de Compose.
- `src/infrastructure/cgroup_resources.py`: `CgroupResourceReader`, con ruta e identidad inyectadas, relee `memory.current` y `memory.max` en cada consulta. Admite uso cero y exige límite positivo; rechaza `max` y contenido no decimal ASCII. Propaga errores de lectura, permisos y UTF-8. Devuelve el `ResourceUsage` existente; su disponibilidad queda acotada a cero cuando el uso supera el límite.
- `tests/unit/test_node_budget.py`, `tests/unit/test_cgroup_resources.py` y `tests/contratos.py`: pruebas con entradas sintéticas y archivos temporales; comprobador compartido aplicado al lector y a `FakeResourceReader`, sin cambiar `ResourceReader.read()`.

La parte 2 agrega `scripts/preflight.py`, que combina el Compose efectivo (CPU o con `--gpu`), valida `NODE_NAME`, `NODE_IP`, límites y presupuesto usando `MemTotal` en bytes de `docker info --format '{{.MemTotal}}'`. En Windows, el CLI consulta el daemon Linux de Docker Desktop/WSL2, no el proceso Python ni la RAM física de Windows. `scripts/start_worker.py [--gpu]` repite la validación y solo entonces ejecuta `docker compose ... up -d --build`. `WORKER_MEM_LIMIT` es obligatorio; Compose lo aplica como `mem_limit` y `memswap_limit`, y `.env.example` lo deja vacío. Su valor debe medirse y configurarse por nodo antes de arrancar; no se proporciona ni se infiere aquí. La reserva SUP-24 es el máximo entre 1 GiB y 15 % de `MemTotal`: supuesto provisional, no medición del consumo del sistema.

Estas comprobaciones de configuración y presupuesto no acreditan ejecución real de Docker/Compose ni aplicación del límite en cgroups. `NODE_IP` se valida como IPv4 o IPv6. Compose mantiene un worker por nodo, sin `--scale`.

## 2. Concepto de Sistemas Operativos

Un cgroup v2 contabiliza memoria y permite que el kernel imponga un límite por grupo. Leer un límite no demuestra por sí solo que se haya configurado correctamente al arrancar. El presupuesto previo compara capacidades declaradas; no garantiza memoria libre futura ni reemplaza el control de admisión.

Referencia bibliográfica: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed., capítulo 10, «Virtual Memory»; edición del curso por confirmar según SUP-16. Referencia específica: documentación del Kernel Linux, *Control Group v2*, sección «Memory», R4 de [ARQUITECTURA](ARQUITECTURA.md#10-referencias), para `memory.current`, `memory.max` y `memory.swap.max`. Son fundamentos del diseño; esta parte aún no contrasta teoría con mediciones del kernel.

## 3. Método de medición

**No ejecutado en los nodos B/C/D.** En cada nodo real, registrar la salida de `docker info --format '{{.MemTotal}}'`, que devuelve bytes de la RAM del daemon Linux donde Docker aplica los límites. Registrar fecha UTC y entorno; no usar la RAM física de Windows. Calcular y anotar la reserva SUP-24 como supuesto. Medir y decidir `WORKER_MEM_LIMIT` por nodo antes de ponerlo en el `.env`; el proyecto no prescribe su valor. Hacer tres arranques por nodo con `python scripts/start_worker.py` o `python scripts/start_worker.py --gpu`, según corresponda. El nodo A no ejecuta workers.

Desde la raíz del repositorio, con `.env` local sin incorporarlo al historial:

```sh
python scripts/preflight.py
```

El preflight ejecuta internamente `docker compose config --format json` y `docker info --format '{{.MemTotal}}'`. Para nodo GPU, pasar `--gpu`. El arranque recomendado vuelve a comprobar el presupuesto antes de levantar el worker:

```sh
python scripts/preflight.py --gpu
python scripts/start_worker.py --gpu
```

En cada uno de los tres arranques por nodo, guardar primero el comando y la salida de configuración efectiva: `docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json`; para GPU agregar `-f deploy/docker-compose.worker-gpu.yml` antes de `config`. El wrapper usa esos mismos archivos y ejecuta `up -d --build` solo tras pasar la validación. Guardar comandos resueltos y salidas crudas en `docs/evidencia/F-16/`.

Por cada contenedor worker iniciado, sustituir `<id>` por su identificador real y guardar estas tres lecturas con el ID:

```sh
docker exec <id> cat /sys/fs/cgroup/cgroup.controllers
docker exec <id> cat /sys/fs/cgroup/memory.max
docker exec <id> cat /sys/fs/cgroup/memory.swap.max
```

Comparar `memory.max` con `mem_limit` y verificar que `memory.swap.max` coincida con `memswap_limit` (el Compose fija ambos al mismo valor). Registrar también fallos de configuración o arranque; no estimar los valores faltantes.

## 4. Resultados

| Entorno | RAM efectiva observada | Reserva configurada | Límites configurados por contenedor | `memory.max` / `memory.swap.max` observados | Repeticiones realizadas |
|---|---|---|---|---|---|
| Nodo B, VM WSL2 | Pendiente de medición | Pendiente de medición | Pendiente de medición | Pendiente de medición | Ninguna |
| Nodo C, VM WSL2 | Pendiente de medición | Pendiente de medición | Pendiente de medición | Pendiente de medición | Ninguna |
| Nodo D, VM WSL2 | Pendiente de medición | Pendiente de medición | Pendiente de medición | Pendiente de medición | Ninguna |

**Validación local complementaria, no atribuida a B/C/D.** El 2026-11-10, en el host `DESKTOP-796L2A2`, contexto Docker `desktop-linux`, `docker info --format '{{.MemTotal}}'` devolvió `16728616960` bytes. Con configuración sintética (`NODE_NAME=qa-local`, `NODE_IP=127.0.0.1`, `WORKER_MEM_LIMIT=1g`), el preflight pasó y tres contenedores efímeros de Compose CPU reportaron `memory.max=1073741824`, `memory.swap.max=0` y UID/GID `1000(appuser)`. No se inició el worker de larga duración ni se ejecutó carga B.3; este dato solo comprueba el cableado local del límite en cgroups v2. Los IDs, comandos y salidas están en [QA-parte-2.md](specs/F-16/QA-parte-2.md).

La evidencia de software es distinta de esta tabla: [QA-parte-1.md](specs/F-16/QA-parte-1.md) registra 1138 pruebas aprobadas, 2 omitidas y 3 deseleccionadas; seis regresiones introducidas en copias temporales fueron detectadas. [QA-parte-2.md](specs/F-16/QA-parte-2.md) informa la suite final con 1162 aprobadas, 2 omitidas y 3 deseleccionadas. Estos conteos no sustituyen las tres lecturas de B/C/D ni la calibración de límites bajo carga real. No hay cifras sintéticas presentadas como mediciones de B/C/D.

## 5. Interpretación

Las pruebas respaldan el cálculo de presupuesto, la validación estática del cableado y la lectura estricta de archivos con el contrato actual. Sin mediciones reales no se puede concluir que el kernel aplique un límite, que los valores elegidos sean adecuados ni que los nodos soporten la carga. AD-29 tiene aprobación de diseño; SUP-24 sigue siendo supuesto pendiente de validación y la calibración de límites sigue pendiente según SUP-17.

La evidencia real del arranque y los límites de F-16 parte 2 sigue pendiente hasta medir B/C/D bajo la carga definida y decidir `WORKER_MEM_LIMIT` por nodo. La validación local con 1 GiB sintético no acredita esos valores. Los demás productos obligatorios de M1 siguen pendientes por feature: F-17, admisión basada en huella y memoria durante ráfaga; F-18, OOM provocado y recuperación; F-19, huella RSS/PSS por modelo y comparación de estrategias de carga. F-37 cubre saturación del nodo (B.6).
