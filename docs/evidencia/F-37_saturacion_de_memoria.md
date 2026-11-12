# F-37 · Evidencia de saturación de memoria

## Qué cubre el escenario

`scenarios/memory_saturation.py` valida que, con una carga mayor que `memory.max` de un worker, M1 no colapsa:

1. Planifica la carga (`planificar_carga`): cupo de sub-tareas que caben en la memoria disponible (`memory_max - margen` entre la huella por operación) y número total de sub-tareas, que supera al cupo.
2. Toma muestras (`tomar_muestra`) de `/sys/fs/cgroup/memory.current` y `/sys/fs/cgroup/memory.max`.
3. Evalúa (`evaluar`) las afirmaciones de US-37 (SUP-37): no hay huecos de heartbeat mayores que 3 × `HEARTBEAT_INTERVAL`, `memory.current` nunca supera `memory.max`, no hay `OOMKilled`, no se admiten más sub-tareas que el cupo y todas las sub-tareas llegan a estado terminal.

El módulo no lanza la corrida real: planifica, muestrea y evalúa. La corrida la hace un worker en nodos reales.

## Cómo correrlo

- **Planificar la carga** (en cualquier sistema):
  ```
  py -m scenarios.memory_saturation --memory-max-mib <MiB> --margen-mib <MiB> --huella-mib <MiB> [--factor 2] [--salida <ruta.json>]
  ```
  Los valores salen de la ficha M1 medida. Sin ella, no se usan valores inventados.

- **Unitarias** (en cualquier sistema, sin red ni nodos):
  ```
  py -m pytest tests/unit/test_memory_saturation.py -q
  ```
  Resultado en Windows: 22 pruebas pasan.

- **Integración Linux** (requiere procesos POSIX, cgroups y Redis): `tests/integration/test_saturacion_worker_linux.py`. Se omite en Windows y sin `REDIS_URL`. Comando de referencia, en Docker o WSL2:
  ```
  REDIS_URL=<url> pytest tests/integration/test_saturacion_worker_linux.py -q
  ```

- **Aceptación** (requiere la salida JSON de una corrida real): `tests/acceptance/test_memory_saturation_aceptacion.py`. Se omite sin `MEMORY_SATURATION_JSON`:
  ```
  MEMORY_SATURATION_JSON=<ruta_al_json> pytest tests/acceptance/test_memory_saturation_aceptacion.py -q
  ```

## Límites

- Las pruebas unitarias usan datos simulados; no prueban el comportamiento real del sistema operativo.
- La prueba de integración exige POSIX y `REDIS_URL`; se ejecutó en un contenedor Linux con Redis real, pero no ejercita `WorkerNode` (ver tabla). En Windows se omite.
- La aceptación se ejecutó solo sobre el JSON del arnés en contenedor (ver más abajo), no sobre nodos reales.
- El umbral de 3 heartbeats es provisional (SUP-37).

## Qué está medido y qué no

| Elemento | Estado |
|---|---|
| Lógica del escenario con muestras sintéticas | Medido: 22 unitarias pasan en Windows (más `test_arquitectura`, 26 verdes en total) |
| Corrida real con admisión, 3 repeticiones, un contenedor aislado con `memory.max` = 256 MiB | Medido el 2026-11-11, ver abajo |
| Aceptación sobre JSON de corrida real | Medido: `test_memory_saturation_aceptacion.py` pasa sobre la repetición 1 (1 pasa) |
| Comparación sin admisión (SUP-38) | Medido, una repetición, en el contenedor aislado |
| Gráfico de `memory.current` y sub-tareas admitidas | Hecho: [F-37_grafico_rep1.svg](mediciones-f36-f37/F-37_grafico_rep1.svg), repetición 1 |
| Integración Linux (`test_saturacion_worker_linux.py`) con Redis 7 real en Docker y `REDIS_URL` | Medido el 2026-11-11: pasa (1 pasa). **Alcance real:** esa prueba solo verifica `planificar_carga` y `huecos_heartbeat`; no usa `WorkerNode` ni se conecta a Redis (solo exige que `REDIS_URL` exista). Salida cruda en `mediciones-f37-integracion/` |
| Aceptación con `MEMORY_SATURATION_JSON` y `REDIS_URL` definidos, en `python:3.13` | Medido el 2026-11-11: pasa (1 pasa) sobre la repetición 1 |
| `WorkerNode` real con Redis y cola, límite bajo | Medición pendiente: ninguna prueba del repositorio lo ejercita; el arnés tampoco |
| Corrida M1 y B.6 en tres nodos WSL2 separados (F-38) | Medición pendiente: no es posible en esta máquina (un solo host Docker). Comando para quien tenga los nodos, con la ficha M1 vigente: `py -m scenarios.memory_saturation --salida docs/evidencia/F-37_<fecha>.json`, tres repeticiones |

## Medición real en un contenedor aislado (2026-11-11)

**Entorno:** un único host Docker Desktop (Linux, WSL2 kernel 6.18.33.2, 16 CPUs, 15,6 GB), cgroup v2, un contenedor con `--memory=256m --memory-swap=256m` (`memory.max` = 268 435 456 B), Python 3.13.18, usuario no root, commit base `63f6b62`. **No son tres nodos.** El OOM de la comparación queda contenido en ese contenedor (SUP-38 cumplida en esta corrida: aislamiento confirmado, contenedor con memoria limitada y sin otros nodos; José autorizó terminar las mediciones).

**Qué es el arnés** (`mediciones-f36-f37/medir_f37.py`): usa la admisión real (`admits`, `CgroupResourceReader`, `read_memory_events`) y `scenarios.memory_saturation` (plan, muestras, `evaluar`). **No es `WorkerNode`**: no hay Redis ni cola, el heartbeat es un hilo del arnés (no la clase `Heartbeat`) y las sub-tareas son procesos hijos que reservan y tocan 64 MiB reales. Huella 64 MiB y margen 32 MiB son **valores declarados, no medidos** (la huella M1/F-17 sigue pendiente). Plan: cupo 3, 7 sub-tareas. Heartbeat cada 1 s.

```
docker build -f docs/evidencia/mediciones-f36-f37/Dockerfile.medicion -t medicion-f36-f37 .
docker run --rm --memory=256m --memory-swap=256m -v "<repo>:/app:ro" -w /app -e PYTHONPATH=/app medicion-f36-f37 python docs/evidencia/mediciones-f36-f37/medir_f37.py --huella-mib 64 --margen-mib 32 [--sin-admision]
```

| Corrida | Pico `memory.current` | Pico en curso | `oom_kill` | Estados finales | `evaluar` |
|---|---|---|---|---|---|
| Con admisión, rep 1 | 224 387 072 B | 3 | 0 | 7 completed | cumple |
| Con admisión, rep 2 | 223 793 152 B | 3 | 0 | 7 completed | cumple |
| Con admisión, rep 3 | 223 817 728 B | 3 | 0 | 7 completed | cumple |
| **Sin admisión** | 239 824 896 B | 7 lanzadas a la vez | 4 | 3 completed, 4 failed | **no cumple**: «hubo OOMKilled», «se admitieron más sub-tareas que el cupo (3)» |

JSON crudos: `mediciones-f36-f37/F-37_corrida_con_admision_rep{1,2,3}_2026-11-11.json` y `F-37_corrida_sin_admision_2026-11-11.json`. Cada corrida con admisión dura unos 12,8 s con 64 muestras cada 0,2 s. Sin ningún hueco de heartbeat mayor que 3 s (tolerancia SUP-37).

**Lectura:** con admisión, el contenedor nunca superó 224 MB de 256 MiB, admitió como máximo 3 sub-tareas simultáneas y las 7 terminaron al liberarse capacidad. Sin admisión, el kernel mató 4 de 7 procesos. **Límites:** un host, sin cola real ni worker completo; el heartbeat del arnés solo prueba que el proceso principal no se bloquea, no la clase `Heartbeat`; los umbrales siguen siendo provisionales (SUP-36 y SUP-37).

## Integración con Redis real (2026-11-11)

Redis `redis:7-alpine` en una red Docker local sin puertos publicados, y `python:3.13` (3.13.18, uid 0, kernel Linux de Docker Desktop) con el repositorio montado:

```ndocker run --rm --network f37net -e REDIS_URL=redis://f37redis:6379/0 -e MEMORY_SATURATION_JSON=docs/evidencia/mediciones-f36-f37/F-37_corrida_con_admision_rep1_2026-11-11.json -v "<repo>:/app" -w /app python:3.13 python -m pytest tests/integration/test_saturacion_worker_linux.py tests/acceptance/test_memory_saturation_aceptacion.py -v
```n
Resultado: 2 pasan en 0,55 s ([salida cruda](mediciones-f37-integracion/salida_cruda_2026-11-11.txt)). Hallazgo: la prueba de integración no usa `WorkerNode` ni Redis, así que no sustituye una prueba con el worker real.
