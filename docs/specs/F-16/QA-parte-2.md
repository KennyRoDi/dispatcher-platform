# QA F-16, parte 2

**Resultado: APROBADO.** Implementación revisada: `7fef365` más el fix `f8bd884` (`fix(F-16): validar dirección IP del worker`).

## Hallazgo

La revisión inicial encontró que `validate_config` aceptaba cualquier `NODE_IP` no vacío. El fix valida IPv4/IPv6 mediante `ipaddress.ip_address`; se agregaron pruebas para IPv6 válido y para rechazar `not-an-ip`. El hallazgo queda resuelto.

## Criterios y comprobaciones

| Criterio | Resultado | Evidencia |
|---|---|---|
| Falla rápida ante presupuesto excesivo | Aprobado | `validate_config` pasa la suma de límites y reserva a `validate_node_budget`; el exceso levanta `ValueError`, que `preflight.main` y `start_worker.main` capturan antes de `compose up`. `test_preflight_rechaza_suma_de_limites_mayor_a_ram` cubre el exceso. |
| Igualdad al presupuesto | Aprobado | `test_presupuesto_igual_o_menor_a_ram_es_valido` prueba igualdad exacta: `400 + 500 + 100 = 1000`. La lógica rechaza solo cuando lo requerido es mayor que la RAM. |
| Suma de límites de todos los workers | Cobertura existente | `test_preflight_suma_limites_de_todos_los_workers` agrega un segundo servicio worker y espera rechazo por exceso. |
| Reserva derivada de MemTotal | Revisión estática favorable | `_reserve_bytes` calcula el techo del 15 % y toma el máximo entre ese valor y 1 GiB. `_node_memory_bytes` rechaza MemTotal ausente o inválido. No se contrastó con un nodo real. |
| `WORKER_MEM_LIMIT` obligatorio y sin valor inventado | Revisión estática favorable | `.env.example` lo deja vacío; Compose exige la variable en ambos límites. Conforme al alcance, `config` debe fallar hasta que el operador configure el valor. No se probó Compose en ejecución. |
| Compose efectivo CPU/GPU | Cobertura estática existente; ejecución pendiente | `tests/unit/test_f16_compose_memory.py` combina el YAML base y el override GPU en orden y comprueba que ambos límites sean iguales. No se ejecutó por falta de Python accesible. No se invocó Docker. |
| Aplicación GPU del preflight | Revisión estática favorable | Ambas CLIs agregan `deploy/docker-compose.worker-gpu.yml` con `--gpu`; el archivo solo añade opciones GPU y hereda el servicio y límites base. La configuración efectiva de Compose no se ejecutó. |
| Variables obligatorias y formato de `NODE_IP` | Aprobado | La preflight exige hostname y `NODE_IP`; además valida la dirección como IPv4 o IPv6. Las pruebas cubren IPv6 válido y formato inválido. |
| Arranque bloqueado tras fallo | Revisión estática favorable | `start_worker.main` valida configuración y presupuesto antes de invocar `docker compose up`; no se ejecutó Docker ni el arranque. |

## Comandos y resultado de ejecución

Intento de ejecución focalizada:

```powershell
py -m pytest -q tests/unit/test_f16_preflight.py tests/unit/test_f16_compose_memory.py tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short
```

En este entorno QA no inició: Windows no permitió ejecutar `C:\Users\Usuario\AppData\Local\Microsoft\WindowsApps\py.exe`; `python.exe` de WindowsApps tampoco pudo iniciarse. El orquestador ejecutó la verificación tras `f8bd884` e informó 11 pruebas focalizadas aprobadas y suite completa con 1149 aprobadas, 2 omitidas y 3 deseleccionadas. Revisé estáticamente el fix, la prueba IPv4/IPv6, la suma, la reserva y la ruta de fallo previo a `compose up`; las cifras corresponden a la corrida del orquestador.

No se ejecutaron Docker/Compose ni pruebas de integración con contenedores. Las pruebas Compose combinan estáticamente los YAML CPU/GPU; no verifican la interpolación de variables con `docker compose config`. No se escribieron salidas sintéticas como evidencia medida.

## Mediciones pendientes

No hay acceso acreditado a los nodos B/C/D ni a sus cgroups; las mediciones físicas quedan **pendientes**. En cada nodo, guardar los comandos resueltos y salidas crudas en `docs/evidencia/F-16/`; repetir tres arranques por nodo. Para CPU:

```sh
docker compose --env-file .env -f deploy/docker-compose.worker.yml config --format json
```

En el nodo GPU:

```sh
docker compose --env-file .env -f deploy/docker-compose.worker.yml -f deploy/docker-compose.worker-gpu.yml config --format json
```

Por cada contenedor worker real:

```sh
docker exec <id> cat /sys/fs/cgroup/cgroup.controllers
docker exec <id> cat /sys/fs/cgroup/memory.max
docker exec <id> cat /sys/fs/cgroup/memory.swap.max
```

Registrar nodo, fecha UTC, RAM efectiva de WSL2, fuente, reserva y límites configurados/observados. No sustituirlos por estimaciones ni por la RAM física de Windows.
