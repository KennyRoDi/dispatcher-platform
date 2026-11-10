# QA F-16, parte 2

**Resultado: DEVUELTO A DECISIÓN HUMANA.** Las comprobaciones de software y Compose config pasaron, pero falta la evidencia de integración exigida por el SPEC: observar `memory.max` y `memory.swap.max` en workers reales B/C/D. No se afirma que cgroups haya aplicado los límites.

## Hallazgos

### Lectura de MemTotal desde Windows: corregida

La QA anterior halló que Python ejecutado desde PowerShell no puede abrir `/proc/meminfo`: `Test-Path /proc/meminfo` dio `False` y la función anterior producía `FileNotFoundError`. El commit `9e5343e` usa `docker info --format '{{.MemTotal}}'`, consultando el daemon Linux de Docker Desktop. Los tests de `38af737` comprueban comando, parseo de bytes positivos, salidas inválidas y error del daemon.

No se obtuvo una salida real válida del daemon en esta sesión: el comando terminó con código 1 porque el pipe `dockerDesktopLinuxEngine` no existe. Docker imprimió `0` junto al error; no es medición y no se registra como tal.

### Integración de cgroups: pendiente por falta de daemon y acceso a nodos

El SPEC requiere contrastar límites efectivos en contenedores y repetir tres arranques por nodo B/C/D. No hay daemon activo ni acceso a esos nodos. Compose config abajo solo verifica resolución de configuración; no prueba la aplicación por el kernel. Hace falta acceso a nodos/daemon para completar esa evidencia, o una decisión humana explícita de mantenerla pendiente.

## Criterios y comprobaciones

| Criterio | Resultado | Evidencia |
|---|---|---|
| Rechazo de presupuesto excesivo | Aprobado en software | Unitarias cubren suma excesiva; `test_start_worker_no_invoca_compose_si_el_presupuesto_excede_ram` comprueba código 1 y que no se ejecute `subprocess.run` para `up`. |
| Igualdad al borde y reserva | Aprobado en software | Prueba existente `test_presupuesto_igual_o_menor_a_ram_es_valido`; `_reserve_bytes` toma el máximo entre 1 GiB y techo de 15 %. |
| Suma de todos los workers | Aprobado en software | `test_preflight_suma_limites_de_todos_los_workers` agrega un worker y espera rechazo por exceso. |
| MemTotal del daemon desde proceso Windows | Aprobado en software; llamada real pendiente | Pruebas comprueban el comando `docker info`, bytes decimales positivos, salida vacía/inválida/cero/negativa y error subprocess. Docker daemon no disponible en esta sesión. |
| Compose CPU y GPU con `mem_limit == memswap_limit` | Aprobado en configuración | `docker compose config --format json` resolvió ambos a `4294967296` para CPU y para el override GPU usando `WORKER_MEM_LIMIT=4g` sintético. No inició contenedores. |
| Variables e IP inválidas | Aprobado en software | `validate_config` exige hostname, IPv4/IPv6 válida, límite positivo e igualdad de límites; pruebas cubren ausencia de campos, `not-an-ip` y swap desigual. |
| Fallo cerrado antes de `compose up` | Aprobado en software | `start_worker.py` con daemon ausente devolvió 1 y mostró rechazo del preflight. La prueba unitaria además asegura cero llamadas a `subprocess.run` para el arranque ante exceso. |
| `memory.max` y `memory.swap.max` observados en cgroups v2 B/C/D | Pendiente; impide afirmar aceptación completa del criterio de integración | No se ejecutaron workers reales ni se leyeron cgroups. |

## Pruebas focalizadas

```powershell
py -m pytest -q tests/unit/test_f16_preflight.py tests/unit/test_f16_compose_memory.py tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short
```

Resultado: `72 passed in 0.61s`.

Suite completa reproducida por el orquestador después del fix:

```powershell
py -m pytest -q -m "not integration and not acceptance"
```

Resultado: `1157 passed, 2 skipped, 3 deselected, 1 warning` (advertencia preexistente de Starlette; 45.88 s).

## Comprobaciones Docker

```powershell
docker info --format '{{.MemTotal}}'
```

Resultado: código 1; pipe `dockerDesktopLinuxEngine` ausente. La salida `0` no es un valor válido.

Con `.env` temporal creado desde `.env.example` y variables de prueba `NODE_NAME=qa-node`, `NODE_IP=100.64.0.2`, `WORKER_MEM_LIMIT=4g`, estos comandos:

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json
docker compose --env-file .env -f deploy/docker-compose.worker.yml -f deploy/docker-compose.worker-gpu.yml config --format json
```

devolvieron `mem_limit=4294967296` y `memswap_limit=4294967296` en ambos casos. El `.env` de prueba se eliminó; no se arrancó ningún contenedor.

Con esa misma configuración temporal, `py scripts/start_worker.py` terminó en código 1 y reportó fallo de `docker info`; no llegó a `compose up`. Se eliminó el `.env` temporal.

## Mediciones pendientes

No hay resultados crudos de nodos B/C/D. En cada nodo, guardar `docker info --format '{{.MemTotal}}'`, configuración Compose efectiva, tres arranques y salidas por contenedor:

```powershell
docker exec <id> cat /sys/fs/cgroup/cgroup.controllers
docker exec <id> cat /sys/fs/cgroup/memory.max
docker exec <id> cat /sys/fs/cgroup/memory.swap.max
```

Registrar nodo, fecha UTC, ID del contenedor, límites configurados y fuente de memoria en `docs/evidencia/F-16/`. No estimar `WORKER_MEM_LIMIT` ni usar la RAM física de Windows como MemTotal de WSL2.
