# SPEC F-35: Reinicio del coordinador

**Fase:** cerrada
**Base:** main
**Verificación IA:** revision 04c618c
**Historia:** US-35 · **Requisitos:** RF-44 (B.6 «Reinicio del coordinador») · **Responsable:** N

## Objetivo

AD-21 (`docs/ARQUITECTURA.md`) ya decidió que el coordinador es **sin estado propio**: todo vive en
Redis con AOF, que actúa como checkpoint, y las operaciones de registro son idempotentes (`SADD`).
La misma fila de AD-21 declara explícitamente: **«Medición pendiente, F-35»**. Esta feature no
construye reconciliación nueva — verificado en el código: no existe ninguna función de
«reconciliación» para el coordinador (`git grep reconcili` no encuentra nada en `src/`), porque no
hace falta: el coordinador no guarda nada en memoria entre peticiones, así que un proceso nuevo que
arranca contra el mismo Redis ve exactamente el mismo estado, sin ningún paso de recuperación.

F-35 **demuestra esa afirmación con datos medidos**, que es justo lo que AD-21 dejó pendiente: crea
casos en curso, «reinicia» el coordinador (construye un proceso/instancia nueva contra el mismo
Redis) y mide que ninguna sub-tarea se pierde ni se cuenta dos veces, más el tiempo de retoma.

## Alcance

**Incluye:**
- `scenarios/coordinator_restart.py`: funciones puras `evaluar(creadas, contadas_antes, contadas_despues)` y `tiempo_de_arranque(inicio, listo)`, más `correr_con_app_real(...)` que construye una instancia de `crear_app()` (`src/coordinator/main.py`), crea casos, reporta algunas sub-tareas, **descarta esa instancia y construye una completamente nueva contra el mismo Redis** (simula el reinicio del proceso), y compara los conteos antes/después vía la API de la instancia nueva.
- Medición real (mínimo 1 corrida, con Redis real o `fakeredis` según disponibilidad, igual que F-34).
- `tests/unit/test_coordinator_restart.py`: funciones puras.
- `tests/integration/test_coordinator_restart_real.py`: reinicio simulado contra `fakeredis`, con `TestClient` nuevo sobre `crear_app()` nuevo.
- `tests/acceptance/test_coordinator_restart_aceptacion.py`: mismo patrón que F-34/F-36 — lee `COORDINATOR_RESTART_JSON` de una corrida real, se omite si no está definida.
- Ficha `docs/evidencia/F-35_reinicio_coordinador_<fecha>.md`.
- Referencia a `tests/test_coordinator.py::test_report_after_cancel_keeps_case_cancelled_and_is_idempotent` como la prueba de idempotencia «U» ya existente que exige el criterio (no se reescribe).

**No incluye:**
- Construir un mecanismo de reconciliación nuevo: no existe porque el coordinador no lo necesita (sin estado propio, AD-21).
- Reiniciar un contenedor Docker real ni los tres nodos físicos de F-38; se simula construyendo una instancia de proceso nueva contra el mismo Redis, que es la parte observable del reinicio (el proceso del coordinador en sí no retiene nada entre arranques).
- Cambios en `src/coordinator/main.py`, `conexion.py` ni ningún `rutas_*.py` (se usan tal cual, sin modificar).
- Medir el reinicio de Redis en sí (eso es un escenario distinto, de disponibilidad de Redis, no del coordinador; AD-21 ya distingue ambos).

## Criterios de aceptación

Copiado de `docs/backlog/carga-fallos.md` (US-35):

```gherkin
Dado que hay casos en curso
Cuando el coordinador se reinicia
Entonces retoma desde el estado persistido
Y ninguna sub-tarea se pierde ni se duplica
Y los casos alcanzan su estado final
```

**Pruebas:** U idempotencia y reconciliación. I reinicio con Redis real. A `scenarios/coordinator_restart.py`.
**Demuestra:** conteo por `subtask_id`. **Evidencia:** tiempo de retoma y conteos antes y después.

## Diseño

**Contratos usados (sin modificar):** ninguno de `docs/CONTRATOS.md` propio; reutiliza
`src/coordinator/main.py::crear_app` y las rutas existentes (`rutas_casos.py`, `rutas_subtareas.py`)
tal cual, sin tocarlas.

**Archivos a crear:**
- `scenarios/coordinator_restart.py` (nuevo)
- `tests/unit/test_coordinator_restart.py`, `tests/integration/test_coordinator_restart_real.py`, `tests/acceptance/test_coordinator_restart_aceptacion.py` (nuevos)
- `docs/evidencia/F-35_reinicio_coordinador_2026-11-12.md` (nuevo, en fase de documentación)

**Decisión:** no propone AD nueva; completa la medición que AD-21 dejó pendiente. Se actualizará la
fila de AD-21 en la fase de documentación para quitar «Medición pendiente» y enlazar la ficha.

**Método de medición (reproducible sin Docker):**
1. Construir una instancia `app1 = crear_app(env)` y un `TestClient(app1)`; crear 2-3 casos (varias sub-tareas), reportar algunas como completadas (API real, sin tocar Redis a mano).
2. Contar sub-tareas por `subtask_id` y su estado, leyendo directo de Redis (fuente de verdad, no de la app).
3. Medir `t0 = time.perf_counter()`, descartar `app1`/`TestClient`, construir `app2 = crear_app(env)` nuevo contra el **mismo** Redis, y un `TestClient(app2)` nuevo; medir `t1` en cuanto `GET /stats` responde 200 (primera petición exitosa = «listo»).
4. Volver a contar sub-tareas por `subtask_id` vía `app2` y comparar con el paso 2: mismos IDs, mismos estados, mismo total.
5. Reportar un caso pendiente a través de `app2` y confirmar que el caso avanza (prueba que la app nueva opera con normalidad, no solo que lee lo viejo).

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria (existente) | `test_report_after_cancel_keeps_case_cancelled_and_is_idempotent`, `test_report_for_cancelled_subtask_is_ignored` | `tests/test_coordinator.py` | Reportar dos veces la misma sub-tarea no duplica el conteo (idempotencia vía `SADD` en `case:{id}:done`) — ya cubierto, no se reescribe |
| Unitaria | `test_evaluar_detecta_perdidas_y_duplicadas_entre_antes_y_despues` | `tests/unit/test_coordinator_restart.py` | El veredicto marca problema si los `subtask_id` de «antes» y «después» no coinciden exactamente (perdidos o duplicados) |
| Unitaria | `test_tiempo_de_arranque_es_la_diferencia_entre_instantes` | `tests/unit/test_coordinator_restart.py` | `tiempo_de_arranque(inicio, listo)` es una resta simple, sin `sleep` |
| Integración | `test_coordinator_restart_real_conserva_subtareas` | `tests/integration/test_coordinator_restart_real.py` | Con `fakeredis`, una instancia nueva de `crear_app()` ve exactamente los mismos `subtask_id` y estados que la instancia anterior, y puede seguir operando (reportar una sub-tarea nueva) |
| Aceptación | `test_coordinator_restart_aceptacion` | `tests/acceptance/test_coordinator_restart_aceptacion.py` | Mismo patrón que F-34/F-36: lee `COORDINATOR_RESTART_JSON` de una corrida real, se omite si no está definida |

## Mediciones

**Comando exacto:**
```bash
python -m scenarios.coordinator_restart --out docs/evidencia/F-35_corrida_2026-11-12.json
```
Repeticiones: 3. Ficha de destino: `docs/evidencia/F-35_reinicio_coordinador_2026-11-12.md`, referenciada en `docs/modulo-M2-planificacion.md`.

Métricas a registrar: tiempo de retoma (desde que se descarta la instancia vieja hasta que la nueva
responde), sub-tareas creadas vs. contadas antes y después (deben coincidir exactamente, mismos
`subtask_id`), 0 perdidas, 0 duplicadas.

## Plan de pila

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-35): escenario y medicion real de reinicio del coordinador` | `scenarios/coordinator_restart.py`, pruebas U/I/A, ficha de evidencia, actualizar AD-21 | ~140 |

## Riesgos y preguntas abiertas

1. **No es un reinicio de proceso del sistema operativo real.** Se simula construyendo una instancia
   de aplicación nueva en el mismo proceso Python, contra el mismo Redis — es la parte observable
   correcta (el coordinador no tiene estado de proceso que perder), pero no mide tiempo de arranque
   de un contenedor Docker real ni reconexión de red entre nodos (eso es F-38/B.2, fuera de alcance).
2. **Tiempo de retoma medido es el de construir `crear_app()` + primera respuesta**, no el de un
   `systemctl restart` o `docker restart` real; se declara así explícitamente en la ficha, igual que
   F-34 declaró que no era un `docker kill` literal.
3. **AD-21 también distingue el caso de que Redis mismo falle** (puede perder hasta 1 s con
   `appendfsync everysec`); ese escenario no es «reinicio del coordinador» y no se mide aquí.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-12 | SPEC F-35 completado tras verificar en el codigo que no existe ninguna funcion de reconciliacion para el coordinador (git grep reconcili sin resultados en src/) porque AD-21 ya decidio que es stateless; F-35 mide con datos reales lo que AD-21 dejo como 'Medicion pendiente'. Diseno: simular el reinicio construyendo una instancia nueva de crear_app() contra el mismo Redis, mismo patron que F-34/cancel_heavy.py. Plan de 1 parte, ~140 lineas (51ca420) |
| plan | Nahúm Murillo | 2026-11-12 |  |
| verificación IA de tests | claude | 2026-11-12 | 6 pruebas unitarias en rojo (falta scenarios/coordinator_restart.py). 1 prueba de integracion pasa de inmediato (dos clientes fakeredis sobre el mismo FakeServer, simulando reconexion real; valida crear_app/rutas heredadas sin codigo nuevo). 1 aceptacion omitida (sin COORDINATOR_RESTART_JSON). 44 passed en regresion (83b294a) |
| tests | Nahúm Murillo | 2026-11-12 |  |
| verificación IA de implementacion | claude | 2026-11-12 | Implementacion completa: scenarios/coordinator_restart.py (116 lineas) con evaluar/tiempo_de_arranque puras y correr_con_app_real que crea una conexion Redis nueva (simula reinicio) y compara estado antes/despues. 7 passed, 1 skipped a la primera (sin ajustes). 49 passed en regresion amplia. 116 lineas de codigo (88bd2c6) |
| implementacion | Nahúm Murillo | 2026-11-12 | 3 fallos preexistentes en TLS/cableado del entorno local (encoding), identicos a los de F-34, confirmados ajenos a F-35; 3628 passed |
| verificación IA de verificacion | claude | 2026-11-12 | QA de edge cases en evaluar()/tiempo_de_arranque() de scenarios/coordinator_restart.py: vacios, progreso normal de estado (no se marca problema), discrepancia de conteo (se marca), arranque instantaneo (0.0s, no falla); sin bugs. Se detecto que main (fusionado por otra sesion) ahora exige TLS_ENABLED y autorizacion JWT por defecto; se ajusto el script de medicion para desactivar TLS (TLS_ENABLED=false, igual que conftest.py) y sortear la autorizacion (dependency_overrides[autorizar], igual que el fixture sin_autorizacion de las pruebas) ya que F-35 no mide esos aspectos. 3 corridas reales con fakeredis.FakeServer (redis real no disponible): 0 perdidas, 0 duplicadas, mismos subtask_id antes/despues en las 3; tiempo_arranque_s ~0.01s (crear una conexion/TestClient nuevos, no un reinicio real de proceso, limite ya declarado en el SPEC). Prueba de aceptacion pasa contra la corrida 1. (34460e9) |
| verificacion | Nahúm Murillo | 2026-11-12 | flujo.py no puede correr la suite completa el (UnicodeDecodeError en su captura de salida, causado por los 3 fallos preexistentes de TLS/cableado por encoding). Corri la suite yo mismo: 3 failed (los mismos 3 de TLS/cableado, ajenos a F-35, idénticos a F-34), 3596 passed, 86 skipped, 138 deselected, 37 xfailed, 32 errors en tests/test_multimedia_processor.py por agotamiento transitorio de handles de Windows bajo carga (OSError WinError 50 en _winapi.DuplicateHandle, misma familia de flakiness de Windows ya conocida); confirmado NO relacionado con F-35 al correr ese archivo aislado: 77 passed. Disco con poco espacio libre (11GB/476GB) durante la corrida, no causado por mis cambios. |
| verificación IA de documentacion | claude | 2026-11-12 | Documentacion completa: docs/evidencia/F-35_reinicio_coordinador_2026-11-12.md con metodo, 3 repeticiones reales (0 perdidas/duplicadas, ~0.010s) y limites declarados honestamente (no es reinicio de proceso real, no comparable con los 45s historicos de I Proyecto); AD-21 en ARQUITECTURA.md actualizada: se quito 'Medicion pendiente', se aclaro que no hay reconciliacion propia porque no hay nada fuera de Redis que reconciliar (confirmado por git grep), y se enlazo la ficha; docs/modulo-M2-planificacion.md referencia la medicion; bitacora de la rama registrada con el hallazgo de TLS/autorizacion nuevos (ajeno a la logica de F-35). (9cf7bef) |
| documentacion | Nahúm Murillo | 2026-11-12 |  |
| verificación IA de revision | claude | 2026-11-12 | Revision contra el SPEC: diff (11 archivos, 522 inserciones) coincide exactamente con el alcance declarado - scenarios/coordinator_restart.py, 3 archivos de pruebas (U/I/A), ficha de evidencia, AD-21 y modulo-M2-planificacion.md actualizados. Ninguna de las exclusiones del SPEC se violo: no se toco src/coordinator/main.py, conexion.py ni ningun rutas_*.py; no se construyo reconciliacion nueva; no se midio el reinicio de Redis. Los 5 pasos del metodo de medicion se siguieron. Unica diferencia menor: la tabla de Pruebas del SPEC agrupa el caso de perdidas/duplicadas en un solo nombre de prueba, mientras el archivo real lo separa en 4 pruebas unitarias mas especificas (cumple, pierde, duplica, discrepancia de conteo) - mas cobertura que lo minimo descrito, no un incumplimiento. (04c618c) |
| revision | Nahúm Murillo | 2026-11-12 |  |
