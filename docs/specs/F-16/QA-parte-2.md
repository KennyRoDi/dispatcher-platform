# QA F-16, parte 2

**Resultado: APROBADO para el funcionamiento local verificado.** La lectura de memoria, el preflight, la configuración CPU/GPU y la aplicación de límites en cgroups v2 pasaron en el daemon local Docker Desktop. La evidencia de los nodos B/C/D sigue pendiente; este informe no los identifica con el host local ni afirma que se hayan medido.

## Hallazgos

### Identidad del worker desde PowerShell: corregida

La revisión final detectó que el preflight aceptaba `service.hostname` distinto de `service.environment.NODE_NAME`, posible cuando una variable de PowerShell sobrescribe el valor interpolado desde `.env`. El fix `7d7ce7b` exige que ambos valores existan y coincidan. `test_preflight_rechaza_node_name_distinto_del_hostname` falló antes del fix con `DID NOT RAISE ValueError`; ahora el conjunto focal pasa.

### Lectura de MemTotal desde Windows

La QA anterior detectó que Python desde PowerShell no puede abrir `/proc/meminfo`. El fix `9e5343e` usa `docker info --format '{{.MemTotal}}'` para consultar al daemon Linux de Docker Desktop. En la sesión local posterior, el comando devolvió `16728616960` bytes. El host reportó `DESKTOP-796L2A2`, contexto `desktop-linux`; su identidad como B, C o D no está confirmada.

### Límite real aplicado en el daemon local

Con configuración `.env` sintética (`NODE_NAME=qa-local`, `NODE_IP=127.0.0.1`, `WORKER_MEM_LIMIT=1g`), `py scripts/preflight.py` aprobó. Se crearon tres contenedores de prueba con Compose `run --rm --no-deps`; cada uno expuso `memory.max=1073741824`, `memory.swap.max=0` y UID/GID `1000(appuser)`. Son contenedores efímeros de prueba, no workers productivos ni mediciones de B/C/D.

## Criterios y comprobaciones

| Criterio | Resultado | Evidencia |
|---|---|---|
| Rechazo de presupuesto excesivo | Aprobado | Pruebas unitarias cubren suma excesiva; `test_start_worker_no_invoca_compose_si_el_presupuesto_excede_ram` comprueba retorno 1 y ninguna llamada de arranque. |
| Igualdad en el borde, reserva y suma de workers | Aprobado | `test_presupuesto_igual_o_menor_a_ram_es_valido`, pruebas de suma de workers y `_reserve_bytes` cubren el borde y la reserva provisional. |
| MemTotal y compatibilidad PowerShell/Windows | Aprobado localmente | El CLI consulta el daemon mediante `docker info`; el host `DESKTOP-796L2A2` devolvió `16728616960` bytes. |
| Compose CPU/GPU aplica límites iguales | Aprobado en configuración; aplicación local comprobada para CPU | La configuración efectiva CPU y CPU más override GPU resolvió límites iguales. Los tres contenedores ejecutados con Compose base CPU reportaron `memory.max=1073741824`, `memory.swap.max=0`; no se ejecutó override GPU. |
| Usuario no root | Aprobado en contenedores de prueba | Los tres comandos `id` devolvieron `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)`. |
| Variables e IP inválidas | Aprobado | `validate_config` exige hostname, IPv4/IPv6 válida, límites positivos e igualdad `mem_limit`/`memswap_limit`; hay pruebas para campos ausentes, `not-an-ip` y swap desigual. |
| Fallo cerrado antes de `compose up` | Aprobado | Prueba unitaria verifica que presupuesto excesivo devuelve error sin invocar Compose. El código captura error de daemon/config antes de construir y ejecutar `up`. |
| Tres arranques medidos en cada nodo B/C/D | Pendiente | Tailscale alcanza por ping a `hp-nahum` y `magdalena`, pero el puerto SSH 22 no responde y no hay canal shell remoto; tampoco está disponible el `.env` de cada nodo. El host local no se identificó como B/C/D. |

## Pruebas

Pruebas focalizadas, reproducidas en el HEAD actual:

```powershell
py -m pytest -q tests/unit/test_f16_preflight.py tests/unit/test_f16_compose_memory.py tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short
```

Resultado tras el fix `7d7ce7b`: `77 passed in 0.55s`.

Suite completa, reproducida por el orquestador en el mismo HEAD:

```powershell
py -m pytest -q -m "not integration and not acceptance"
```

Resultado tras el fix `7d7ce7b`: `1162 passed, 2 skipped, 3 deselected, 1 warning` (advertencia preexistente de Starlette; 47.17 s).

## Evidencia de Docker local

Contexto `desktop-linux`, hostname informado `DESKTOP-796L2A2`, fecha UTC `2026-11-10`. `docker info --format '{{.MemTotal}}'` devolvió `16728616960` bytes. Configuración local sintética: `NODE_NAME=qa-local`, `NODE_IP=127.0.0.1`, `WORKER_MEM_LIMIT=1g`. El preflight aprobó; el `.env` temporal se eliminó.

Comando usado para cada contenedor efímero:

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm --no-deps -T --entrypoint sh worker -c 'printf "memory.max="; cat /sys/fs/cgroup/memory.max; printf "memory.swap.max="; cat /sys/fs/cgroup/memory.swap.max; id'
```

| ID de contenedor | memory.max | memory.swap.max | id |
|---|---:|---:|---|
| `deploy-worker-run-808542141a96` | `1073741824` | `0` | `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)` |
| `deploy-worker-run-99715c8ac44e` | `1073741824` | `0` | `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)` |
| `deploy-worker-run-0ed2ee2f5c75` | `1073741824` | `0` | `uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)` |

Estos datos prueban el límite en contenedores `run --rm` del daemon local. No corresponden a la identidad B/C/D ni reemplazan los tres arranques de cada nodo. No se arrancó el worker de larga duración ni servicios dependientes.

Con `.env` temporal sintético y `WORKER_MEM_LIMIT=4g`, Compose CPU y CPU más override GPU normalizaron `mem_limit` y `memswap_limit` a `4294967296` bytes cada uno mediante:

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json
docker compose --env-file .env -f deploy/docker-compose.worker.yml -f deploy/docker-compose.worker-gpu.yml config --format json
```

Esta comprobación resuelve configuración sin arrancar GPU ni workers; la aplicación real observada arriba es de Compose CPU.

## Mediciones pendientes de B/C/D

En cada nodo real registrar `docker info --format '{{.MemTotal}}'`, `.env` y configuración Compose efectiva; hacer tres arranques mediante `python scripts/start_worker.py` (GPU: `--gpu`) y guardar IDs/salidas crudas de:

```powershell
docker exec <id> cat /sys/fs/cgroup/cgroup.controllers
docker exec <id> cat /sys/fs/cgroup/memory.max
docker exec <id> cat /sys/fs/cgroup/memory.swap.max
```

Guardar nodo, fecha UTC, MemTotal, límites configurados y observados en `docs/evidencia/F-16/`. No extrapolar los resultados del daemon local a B/C/D ni presentar un límite configurado como medido.
