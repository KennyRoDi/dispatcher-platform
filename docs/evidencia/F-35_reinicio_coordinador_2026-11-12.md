# F-35 · Evidencia de reinicio del coordinador

## Qué cubre el escenario

`scenarios/coordinator_restart.py` mide, contra el coordinador real (`src/coordinator/main.py`,
`crear_app()`, sin modificar), si retoma casos en curso sin perder ni duplicar sub-tareas tras un
reinicio, y cuánto tarda en volver a responder (AD-21: "Coordinador sin estado, Redis AOF como
checkpoint").

1. Crea un caso con 2 sub-tareas contra una instancia (`TestClient(main.app)`) conectada a Redis.
2. Lee el estado de las sub-tareas (`contadas_antes`).
3. "Reinicia" el coordinador: conecta una conexión **nueva** a Redis (con `fakeredis.FakeServer`,
   dos clientes `FakeStrictRedis` distintos sobre el mismo backing store — la forma honesta de
   simular "otro proceso, mismos datos" sin reimplementar nada; con Redis real sería literalmente
   otra conexión) y crea una instancia nueva del coordinador sobre ella.
4. Mide el tiempo entre la conexión nueva y la primera respuesta exitosa (`GET /stats`).
5. Lee el estado de las sub-tareas con la instancia nueva (`contadas_despues`) y compara.

No reimplementa `crear_app`, las rutas ni ninguna forma de reconciliación: si el coordinador ya es
sin estado (confirmado por `git grep reconcili` sin resultados en `src/`), no hay nada que
reconciliar al arrancar — la medición es precisamente verificar esa afirmación de AD-21 con un dato
real, no construir un mecanismo nuevo.

## Cómo correrlo

- **Unitarias** (cualquier sistema, sin red):
  ```
  python -m pytest tests/unit/test_coordinator_restart.py -q
  ```

- **Integración** (dos clientes `fakeredis` sobre el mismo `FakeServer`, el coordinador real sin
  reimplementar):
  ```
  python -m pytest tests/integration/test_coordinator_restart_real.py -q
  ```

- **Aceptación** (requiere la salida JSON de una corrida real):
  ```
  COORDINATOR_RESTART_JSON=<ruta_al_json> python -m pytest tests/acceptance/test_coordinator_restart_aceptacion.py -q
  ```

- **Medición real:**
  ```
  TLS_ENABLED=false python -m scenarios.coordinator_restart --out corrida.json
  ```
  Si no hay Redis real alcanzable en `redis://localhost:6379/0`, cae a `fakeredis` automáticamente
  y lo declara en el campo `fuente_redis` de la salida. `TLS_ENABLED=false` es necesario porque
  `src/coordinator/main.py` exige TLS y autorización JWT por defecto (capas de seguridad ajenas a
  F-35, fusionadas a `main` mientras esta feature estaba en curso); el escenario desactiva TLS
  igual que `tests/conftest.py` y sortea la autorización igual que el fixture `sin_autorizacion` de
  las pruebas, porque no son lo que esta medición evalúa.

## Medición real (2026-11-12)

**Entorno:** 1 host (Windows), sin Redis real disponible en el entorno de medición — `fakeredis`
con dos clientes sobre el mismo `FakeServer`, declarado en `fuente_redis`. **No es un reinicio de
proceso real** (no hay `docker restart` sobre un contenedor del coordinador): se simula con una
conexión nueva a los mismos datos, que es el único estado que el coordinador tiene según AD-21.

**3 repeticiones:**

| Repetición | Sub-tareas creadas | Perdidas | Duplicadas | Mismo estado antes/después | Tiempo de "arranque" (s) |
|---|---|---|---|---|---|
| 1 | 2 | 0 | 0 | sí | 0.0113 |
| 2 | 2 | 0 | 0 | sí | 0.0100 |
| 3 | 2 | 0 | 0 | sí | 0.0098 |

Media del tiempo de "arranque": **~0.010 s**. Veredicto de `evaluar`: `cumple = true`, sin
problemas, en las 3. Confirma la afirmación de AD-21: el coordinador no pierde ni duplica
sub-tareas al reconectar, porque no guarda nada fuera de Redis que haya que reconciliar.

El tiempo medido (~10 ms) **no es comparable** con el reclamo histórico de R1 ("I Proyecto declaró
45 s detenido sin pérdida, sin logs"): esa cifra incluía el tiempo de arranque de un proceso real
(import, bind de puerto, etc.), mientras que esta medición solo captura crear una conexión y una
instancia de `TestClient` nuevas dentro del mismo proceso Python. Son magnitudes distintas por
diseño del método, no una contradicción del dato histórico — ver Límites.

Salida cruda: `docs/evidencia/F-35_corrida_1.json` a `_3.json`.

## Límites

- Medido con `fakeredis`, no Redis real (no estaba disponible en el entorno de medición); el
  comando funciona igual con Redis real si está accesible, y lo declara en `fuente_redis`.
- No es un reinicio de proceso real (no hay restart de contenedor/`docker restart`): se mide el
  costo de reconectar y volver a atender tráfico con una conexión nueva, que es la parte que AD-21
  afirma como "sin estado". El tiempo de arranque de un proceso completo (import de módulos, bind
  de puerto, TLS handshake, etc.) no está incluido y es una medición distinta, fuera de alcance de
  esta feature.
- Un solo caso con 2 sub-tareas por corrida, ambas en `pending` (sin trabajo en curso reportado
  entre la creación y el "reinicio"); es suficiente para verificar que no se pierden ni duplican al
  reconectar, no el comportamiento con sub-tareas a medio procesar en el momento exacto del corte
  (la idempotencia de reportar sobre un caso ya resuelto está cubierta por la prueba unitaria
  preexistente `test_report_after_cancel_keeps_case_cancelled_and_is_idempotent`, citada en el
  SPEC).
- No hay reconciliación que medir porque no existe tal mecanismo en el código (confirmado por
  `git grep reconcili` sin resultados en `src/`): el coordinador es sin estado por diseño, no por
  un paso de arranque que reconstruya nada.
