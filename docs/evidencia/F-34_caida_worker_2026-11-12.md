# F-34 · Evidencia de caída de un worker

## Qué cubre el escenario

`scenarios/worker_crash.py` mide, contra el mecanismo heredado real (`scripts/reaper.py`,
`src/workers/heartbeat.py`, sin modificar), cuánto tarda el sistema en detectar que un worker murió
y reencolar su sub-tarea:

1. Registra un worker en `workers:registry` con `worker:{id}` (heartbeat con `EXPIRE heartbeat_ttl`,
   igual que `src/workers/heartbeat.py::beat()`) y una sub-tarea `assigned` en su `inflight`.
2. Deja de refrescar el heartbeat — simula `docker kill`: el proceso ya no manda latidos.
3. Ejecuta `Reaper.run_once()` real en un bucle, muestreando cada `--intervalo-muestreo` segundos,
   hasta que la sub-tarea reaparece en su cola original.
4. Mide el tiempo transcurrido desde el último latido hasta la detección y hasta la reasignación.

No usa Docker ni nodos físicos: el heartbeat y el reaper son lógica sobre Redis, independiente de
dónde corra el proceso que lo activa. El `docker kill` real sobre los 3 nodos de F-38 es la
validación final de B.6, declarada fuera de alcance de esta feature.

## Cómo correrlo

- **Unitarias** (cualquier sistema, sin red):
  ```
  python -m pytest tests/unit/test_worker_crash.py -q
  ```
  Resultado: 11 pruebas.

- **Integración** (con `fakeredis`, el `Reaper` real sin reimplementar):
  ```
  python -m pytest tests/integration/test_worker_crash_reaper_real.py -q
  ```

- **Aceptación** (requiere la salida JSON de una corrida real):
  ```
  WORKER_CRASH_JSON=<ruta_al_json> python -m pytest tests/acceptance/test_worker_crash_aceptacion.py -q
  ```

- **Medición real:**
  ```
  python -m scenarios.worker_crash --intervalo-muestreo 0.5 --out corrida.json
  python -m scenarios.worker_crash --intervalo-muestreo 10 --out corrida.json
  ```
  Si no hay Redis real alcanzable en `redis://localhost:6379/0`, cae a `fakeredis` automáticamente
  y lo declara en el campo `fuente_redis` de la salida (igual que ocurrió en esta medición).

## Medición real (2026-11-12)

**Entorno:** 1 host (Windows/WSL2), sin Redis real disponible en el entorno de medición —
`fakeredis`, que implementa `EXPIRE`/TTL con el reloj real del sistema, declarado en
`fuente_redis`. **No son tres nodos**: la validación con `docker kill` en los nodos reales de F-38
queda como medición pendiente, fuera de alcance de esta feature. Configuración: valores por
defecto (`heartbeat_ttl=15 s`, `reaper_interval=10 s`, `heartbeat_interval=5 s`).

**Con muestreo rápido (0.5 s), aísla el `heartbeat_ttl` puro — 3 repeticiones:**

| Repetición | Tiempo de detección/reasignación (s) |
|---|---|
| 1 | 15.053 |
| 2 | 15.049 |
| 3 | 15.054 |

Media: **15.05 s**, consistente con `heartbeat_ttl=15`: con muestreo casi continuo, el reaper
reencola prácticamente en cuanto la llave expira.

**Con el `reaper_interval` real de producción (10 s) — 3 repeticiones:**

| Repetición | Tiempo de detección/reasignación (s) |
|---|---|
| 1 | 20.003 |
| 2 | 20.003 |
| 3 | 20.003 |

Media: **20.0 s**, exacta y reproducible: el reaper solo revisa cada 10 s, así que detecta en el
primer sondeo después de que `heartbeat_ttl` (15 s) ya expiró — `ceil(15/10) × 10 = 20`. Esto
**refina** la estimación informal de `docs/DEMO.md` («tras ~25 s el reaper reencola») con un dato
medido: con los valores de configuración por defecto, el tiempo real es 20.0 s, no ~25 s (la cifra
de `DEMO.md` era una observación cualitativa, no una medición guardada).

**Sub-tareas:** 1 creada, 1 terminada, 0 perdidas, 0 duplicadas, caso `completed`, en las 6
repeticiones. Veredicto de `evaluar`: `cumple = true`, sin problemas, en todas.

Salida cruda: `docs/evidencia/F-34_corrida_rapida_1.json` a `_3.json` y
`F-34_corrida_produccion_1.json` a `_3.json`.

## Límites

- Medido con `fakeredis`, no Redis real (no estaba disponible en el entorno de medición); el
  comando funciona igual con Redis real si está accesible, y lo declara en `fuente_redis`.
- No es un `docker kill` literal sobre un contenedor; se simula deteniendo los latidos, que es el
  único evento que el reaper observa. La demostración con `docker kill` real en los 3 nodos de F-38
  es la validación final de B.6, pendiente.
- Una sola sub-tarea por corrida (no una ráfaga concurrente); es suficiente para medir el tiempo de
  detección/reasignación del mecanismo, no su comportamiento bajo carga (eso es RF-42, otra
  historia).
- El tiempo de detección y de reasignación coinciden en esta medición porque el reaper hace ambas
  cosas en la misma pasada (`_process_worker`) apenas nota que `worker:{id}` ya no existe; no hay
  un paso intermedio que distinga «ya lo noté» de «ya lo reencolé».
