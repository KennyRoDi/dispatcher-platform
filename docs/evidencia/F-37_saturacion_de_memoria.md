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
- Las pruebas de integración usan procesos POSIX y Redis. En Windows no se ejecutaron.
- La prueba de aceptación no se ejecutó: requiere la salida JSON de una corrida real.
- El umbral de 3 heartbeats es provisional (SUP-37).

## Mediciones en nodos reales: Medición pendiente (depende de F-38)

- Integración Linux: Medición pendiente.
- Aceptación sobre JSON de corrida real: Medición pendiente.
- Medición M1 y B.6 de saturación en tres nodos worker: Medición pendiente (depende de F-38).

No hay en esta ficha valores medidos de memoria, heartbeats ni estados finales de sub-tareas.
