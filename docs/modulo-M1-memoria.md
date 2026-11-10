# Módulo M1: gestión de memoria

**Responsable:** José Andrés Loría Herrera (`joselhcr`).
**Corte:** F-16, parte 1, 2026-11-10. **Mediciones de SO: pendientes.** Esta ficha todavía no acredita el módulo completo ni el límite aplicado por Docker/WSL2.

## 1. Qué se implementó

- `src/domain/node_budget.py`: `validate_node_budget` compara la suma de cada límite recibido más la reserva con la RAM declarada, en bytes. Acepta igualdad, reserva cero explícita y límites repetidos por réplica; rechaza exceso y valores inválidos mediante `ValueError`. RAM y límites deben ser enteros positivos; reserva, entero no negativo. No consulta el SO ni descubre réplicas de Compose.
- `src/infrastructure/cgroup_resources.py`: `CgroupResourceReader`, con ruta e identidad inyectadas, relee `memory.current` y `memory.max` en cada consulta. Admite uso cero y exige límite positivo; rechaza `max` y contenido no decimal ASCII. Propaga errores de lectura, permisos y UTF-8. Devuelve el `ResourceUsage` existente; su disponibilidad queda acotada a cero cuando el uso supera el límite.
- `tests/unit/test_node_budget.py`, `tests/unit/test_cgroup_resources.py` y `tests/contratos.py`: pruebas con entradas sintéticas y archivos temporales; comprobador compartido aplicado al lector y a `FakeResourceReader`, sin cambiar `ResourceReader.read()`.

La parte 1 no conecta estos componentes al arranque ni al heartbeat. La CLI `scripts/check_node_budget.py`, los límites Compose sin swap, la expansión efectiva de réplicas y la evidencia real pertenecen a la parte 2 del [SPEC](specs/F-16/SPEC.md). No se modificaron workers ni `deploy/`.

## 2. Concepto de Sistemas Operativos

Un cgroup v2 contabiliza memoria y permite que el kernel imponga un límite por grupo. Leer un límite no demuestra por sí solo que se haya configurado correctamente al arrancar. El presupuesto previo compara capacidades declaradas; no garantiza memoria libre futura ni reemplaza el control de admisión.

Referencia bibliográfica: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed., capítulo 10, «Virtual Memory»; edición del curso por confirmar según SUP-16. Referencia específica: documentación del Kernel Linux, *Control Group v2*, sección «Memory», R4 de [ARQUITECTURA](ARQUITECTURA.md#10-referencias), para `memory.current`, `memory.max` y `memory.swap.max`. Son fundamentos del diseño; esta parte aún no contrasta teoría con mediciones del kernel.

## 3. Método de medición

**No ejecutado en parte 1.** Se mantiene el protocolo aprobado para parte 2: tres arranques por nodo B/C/D real, Docker Linux con cgroups v2 dentro de la VM WSL2. El nodo A no ejecuta workers. Registrar nodo, fecha UTC, versión/entorno, configuración efectiva, RAM efectiva de WSL2 y su fuente, reserva y límites. No sustituir esa RAM por la física de Windows ni tratar valores configurados como medidos.

Desde la raíz del repositorio, con `.env` local sin incorporarlo al historial:

```sh
docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json
```

En el nodo GPU, obtener en su lugar la configuración con el override:

```sh
docker compose --env-file .env -f deploy/docker-compose.worker.yml -f deploy/docker-compose.worker-gpu.yml config --format json
```

Por cada contenedor worker iniciado, sustituir `<id>` por su identificador real y conservar comando resuelto y salida cruda en `docs/evidencia/F-16/`:

```sh
docker exec <id> cat /sys/fs/cgroup/cgroup.controllers
docker exec <id> cat /sys/fs/cgroup/memory.max
docker exec <id> cat /sys/fs/cgroup/memory.swap.max
```

Comparar bytes observados con Compose efectivo y verificar ausencia de swap. Antes de implementar parte 2, coordinar con Kenni el arranque, la separación por tipo de worker, cómo enumerar réplicas y el comando exacto/fuente de RAM efectiva de WSL2. También deben concretarse los comandos del preflight que detendrán el arranque ante exceso o configuración inválida. Esos comandos y salidas aún no existen como evidencia; no se ha creado una carpeta de resultados vacía como sustituto.

## 4. Resultados

| Entorno | RAM efectiva observada | Reserva configurada | Límites configurados por contenedor | `memory.max` / `memory.swap.max` observados | Repeticiones realizadas |
|---|---|---|---|---|---|
| Nodo B, VM WSL2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Ninguna |
| Nodo C, VM WSL2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Ninguna |
| Nodo D, VM WSL2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Pendiente parte 2 | Ninguna |

La evidencia de software es distinta de esta tabla: [QA-parte-1.md](specs/F-16/QA-parte-1.md) registra 1138 pruebas aprobadas, 2 omitidas y 3 deseleccionadas; seis regresiones introducidas en copias temporales fueron detectadas. Esos conteos describen pruebas de lógica y contrato, no huellas de memoria ni mediciones de Docker/WSL2. No hay cifras sintéticas presentadas como mediciones.

## 5. Interpretación

Las pruebas respaldan el cálculo de presupuesto y la lectura estricta de archivos con el contrato actual. Sin mediciones reales no se puede concluir que el kernel aplique un límite, que los valores elegidos sean adecuados ni que los nodos soporten la carga. AD-29/SUP-23 tienen aprobación de diseño; la calibración de límites y reserva sigue pendiente según SUP-17.

F-16 parte 2 debe completar arranque y evidencia de límites. Los demás productos obligatorios de M1 siguen pendientes por feature: F-17, admisión basada en huella y memoria durante ráfaga; F-18, OOM provocado y recuperación; F-19, huella RSS/PSS por modelo y comparación de estrategias de carga. F-37 cubre saturación del nodo (B.6). No se atribuyen estos resultados a la parte 1.
