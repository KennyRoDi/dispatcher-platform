# SPEC F-34: Caída de un worker

**Fase:** plan
**Base:** main
**Verificación IA:** pendiente
**Historia:** US-34 · **Requisitos:** RF-43 (B.6 «Caída de un worker») · **Responsable:** N

## Objetivo

El enunciado (B.6) exige demostrar que, si un worker muere mientras procesa una sub-tarea, el
sistema lo detecta, reasigna la sub-tarea a otro worker y el caso cierra en el estado correcto, sin
sub-tareas perdidas ni contadas dos veces. El mecanismo que hace esto (`src/workers/heartbeat.py` +
`scripts/reaper.py` + `src/workers/recovery.py`) **ya existe y es heredado**, reutilizado sin cambios
(F-39 lo clasifica `reutilizado`/`parcial` en `docs/reutilizacion.md`). F-34 no construye ese
mecanismo: lo **demuestra con datos medidos reales**, como exige B.6 y RNF-15, algo que hoy no existe
(`docs/DEMO.md` lo describe cualitativamente — «tras ~25 s el reaper reencola» — pero sin medición
guardada en `docs/evidencia/`).

**Verificado en el código:** el worker publica `worker:{id}` con `EXPIRE heartbeat_ttl` (15 s por
defecto) en cada latido (`heartbeat_interval` 5 s); el reaper recorre `workers:registry` cada
`reaper_interval` (10 s) y, si `worker:{id}` ya no existe, reencola de inmediato todas las sub-tareas
de `worker:{id}:inflight` (`scripts/reaper.py::_process_worker`). Con los valores por defecto, el
tiempo esperado de detección + reasignación es de entre 15 y 25 s — esto es lo que F-34 mide.

## Alcance

**Incluye:**
- `scenarios/worker_crash.py`: funciones puras y probables (mismo patrón que `scenarios/cancel_heavy.py`, F-36): `evaluar(creadas, terminadas, perdidas, duplicadas, estado_caso)` para el veredicto, y `tiempo_deteccion`/`tiempo_reasignacion` a partir de muestras `(instante, dato)`.
- `correr_con_reaper_real(...)`: ejercita el `Reaper` real (`scripts/reaper.py`, sin modificar) contra Redis real, simulando la caída (el worker deja de latir) y midiendo en tiempo real cuánto tarda en detectar y reencolar. No requiere Docker ni nodos físicos: el heartbeat y el reaper son lógica sobre Redis, independiente de dónde corra el proceso que lo activa.
- Medición real ejecutada con los valores por defecto de configuración (`heartbeat_ttl=15`, `reaper_interval=10`), guardada en `docs/evidencia/`.
- `tests/unit/test_worker_crash.py`: funciones puras, con reloj simulado (sin `sleep`).
- `tests/integration/test_worker_crash_reaper_real.py`: el `Reaper` real contra Redis real (`fakeredis`, que implementa `EXPIRE`/TTL con reloj real) detecta y reencola, con tiempos de espera cortos para que la prueba sea rápida.
- `tests/acceptance/test_worker_crash_aceptacion.py`: mismo patrón que `test_cancel_heavy_aceptacion.py` — lee un JSON de una corrida real (`WORKER_CRASH_JSON`), se omite si no está definida.
- Ficha de evidencia `docs/evidencia/F-34_caida_worker_<fecha>.md` con el tiempo medido real.

**No incluye:**
- Modificar `scripts/reaper.py`, `src/workers/heartbeat.py`, `src/workers/recovery.py` ni el esquema de claves de Redis que usan (son del camino heredado, ya clasificado y aceptado en F-39; cambiarlos es otra feature).
- `docker kill` literal sobre un contenedor real ni despliegue en los tres nodos físicos (eso es F-38, ya `hecha`, y la validación final de B.6 en producción); aquí se simula la caída deteniendo los latidos del worker, que es el evento que el reaper realmente observa.
- Reasignación para el camino nuevo de F-05/F-06 (`RedisTypeQueue`/`BLMOVE`): ese camino no tiene consumidor en producción todavía (AD-47); F-34 mide el camino heredado, que es el que corre en producción hoy.
- Cambios de configuración de `heartbeat_ttl`/`reaper_interval` (se mide con los valores por defecto).

## Criterios de aceptación

Copiado de `docs/backlog/carga-fallos.md` (US-34):

```gherkin
Dado un caso en proceso con una sub-tarea en un worker
Y otro worker del mismo tipo en otro nodo
Cuando se ejecuta docker kill sobre el primer worker
Entonces el sistema detecta la caída por heartbeat
Y reasigna sus sub-tareas
Y el caso termina en el estado correcto, sin sub-tareas perdidas ni contadas dos veces
```

**Pruebas:** U recovery existente. I reaper con Redis. A `scenarios/worker_crash.py`.
**Demuestra:** comparación de sub-tareas creadas y terminadas. **Evidencia:** tiempos de detección y reasignación.

## Diseño

**Contratos usados (sin modificar):** ninguno de `docs/CONTRATOS.md` propio; reutiliza el mecanismo
heredado de heartbeat/reaper/recovery (claves `workers:registry`, `worker:{id}`,
`worker:{id}:inflight`, `subtask:{id}`).

**Archivos a crear:**
- `scenarios/worker_crash.py` (nuevo)
- `tests/unit/test_worker_crash.py`, `tests/integration/test_worker_crash_reaper_real.py`, `tests/acceptance/test_worker_crash_aceptacion.py` (nuevos)
- `docs/evidencia/F-34_caida_worker_2026-11-12.md` (nuevo, en fase de documentación)

**Decisión:** no propone AD nueva; aplica AD-21 (reconciliación/idempotencia ya decidida) y confirma
con datos la limitación `parcial` que F-39 ya declaró para el camino heredado (ventana `BLPOP` sigue
abierta, pero el **reencolado por heartbeat perdido** —que es lo que pide este criterio, distinto de
la ventana de milisegundos entre `BLPOP` y `WATCH/MULTI`— si funciona y queda medido aquí).

**Método de medición (reproducible sin Docker):**
1. Registrar un worker falso en Redis (`workers:registry`, `worker:{id}` con `EXPIRE heartbeat_ttl`) y una sub-tarea `assigned` en `worker:{id}:inflight`.
2. Dejar de refrescar el heartbeat (simula `docker kill`: el proceso ya no manda latidos).
3. Lanzar `Reaper.run_forever` real en un hilo, con los `reaper_interval`/`heartbeat_ttl` por defecto, y muestrear cada 0.5 s si la sub-tarea sigue en el `inflight` del worker caído o ya se reencoló.
4. Medir el instante de reencolado menos el instante en que dejó de latir.

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_evaluar_detecta_perdidas_y_duplicadas` | `tests/unit/test_worker_crash.py` | El veredicto marca problema si `creadas != terminadas + perdidas` o si hay duplicadas, y si el caso no cierra en estado correcto |
| Unitaria | `test_tiempo_deteccion_y_reasignacion_con_muestras_simuladas` | `tests/unit/test_worker_crash.py` | Con muestras `(instante, dato)` sintéticas (sin `sleep`), calcula el instante de detección y de reasignación |
| Integración | `test_reaper_real_detecta_y_reencola_heartbeat_perdido` | `tests/integration/test_worker_crash_reaper_real.py` | Con `fakeredis` y el `Reaper` real (no se reimplementa), un worker que deja de latir hace que su sub-tarea `inflight` se reencole en la cola original, dentro de un tiempo acotado por `heartbeat_ttl + reaper_interval` |
| Aceptación | `test_worker_crash_aceptacion` | `tests/acceptance/test_worker_crash_aceptacion.py` | Mismo patrón que F-36: lee `WORKER_CRASH_JSON` de una corrida real, se omite si no está definida |

## Mediciones

**Comando exacto** (no requiere Docker; corre en cualquier máquina con Redis real o se adapta a `fakeredis` para la corrida local, declarado así):
```bash
python -m scenarios.worker_crash --out docs/evidencia/F-34_corrida_2026-11-12.json
```
Repeticiones: 3. Ficha de destino: `docs/evidencia/F-34_caida_worker_2026-11-12.md` (y referencia en `docs/modulo-M2-planificacion.md`, ya que la cola y el reaper son del área de Nahúm).

Métricas a registrar: tiempo de detección (desde el último latido hasta que `worker:{id}` expira),
tiempo de reasignación (desde la expiración hasta que la sub-tarea reaparece en la cola), sub-tareas
creadas vs. terminadas (deben coincidir, 0 perdidas, 0 duplicadas).

## Plan de pila

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-34): escenario y medicion real de caida de worker` | `scenarios/worker_crash.py`, pruebas U/I/A, ficha de evidencia | ~140 |

## Riesgos y preguntas abiertas

1. **No es `docker kill` literal.** Se simula deteniendo los latidos (que es lo único que el reaper observa); un `docker kill` real en los 3 nodos de F-38 es la validación final de B.6, fuera de alcance aquí. Se declara explícitamente en la ficha.
2. **Mide el camino heredado, no el nuevo de F-05/F-06.** Es el que está en producción; el nuevo no tiene consumidor todavía (AD-47).
3. **`fakeredis` para la corrida reproducible vs. Redis real para la medición final.** `fakeredis` implementa `EXPIRE` con el reloj real del sistema, así que el tiempo medido es representativo; si se dispone de Redis real al momento de medir, se prefiere, y se declara cuál se usó en la ficha.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
