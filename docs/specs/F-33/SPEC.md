# SPEC F-33: Ráfaga

**Fase:** implementacion
**Base:** main
**Verificación IA:** tests 1af0d27
**Historia:** US-33 · **Requisitos:** RF-42, RNF-01, RNF-09, RNF-15; QA-10; [B.6 Ráfaga de carga] · **Responsable:** K

## Objetivo

El enunciado pide una «ráfaga de carga»: envío concurrente de al menos 20 casos, con throughput, latencia por caso y uso de recursos por nodo durante la ráfaga [B.6 Ráfaga de carga]. QA-10 exige que todos alcancen estado final con tres nodos. `scripts/run_load.py` ya envía casos, monitorea y calcula las métricas, pero no decide si se cumple el criterio, no exige 20 casos ni tres nodos worker distintos y no exporta CSV. F-33 agrega un **escenario** que reutiliza `run_load`, evalúa el resultado de forma pura y exporta el CSV, sin tocar `src/`.

## Alcance

**Incluye:**

- `scenarios/burst.py`: lee el JSON que ya produce `run_load` (`metrics`, `series`), evalúa el criterio y exporta CSV. Mismo patrón que `scenarios/cancel_heavy.py` y `scenarios/memory_saturation.py`: ejecutor inyectado, evaluación pura, `main()` con salida JSON.
- Ejecución de la ráfaga: `ejecutar_rafaga(...)` llama a `run_load.run_load` con `--limit` ≥ 20 y `--concurrency` ≥ 20 (SUP-45) y devuelve el JSON. El ejecutor se inyecta en las pruebas.
- Evaluación pura (`evaluar`): (1) casos enviados ≥ 20; (2) todos en estado final (`completed`, `failed`, `cancelled`) y sin `timed_out` ni `submit_error`; (3) al menos tres hosts worker distintos en `subtasks_per_host` o en las muestras de `series`; (4) throughput, latencia por caso (`duration_s`) y recursos por nodo (`peak_cpu_by_host`, `peak_active_by_host`) presentes.
- Exportación CSV: `latencia_por_caso.csv` (caso, tipo, prioridad, estado, sub-tareas, duración) y `recursos_por_nodo.csv` (instante, host, CPU %, memoria %, sub-tareas activas), derivados de `per_case` y `series`.
- Gráficos (latencia por caso y recursos por nodo en el tiempo) a partir de los CSV, en la parte 2.
- Ficha `docs/evidencia/F-33_rafaga.md` con comando, repeticiones y resultados.

**No incluye:**

- Cambios en `src/` ni en `scripts/run_load.py` salvo lo mínimo que una prueba roja exija (se declararía en la PR).
- Backpressure del coordinador (F-24), saturación de memoria (F-37) y caída de workers (F-34).
- Desplegar los nodos (F-38). La simulación local de F-38 parte 2 (tres contenedores en una máquina, hosts `worker-sim-N`) puede servir de corrida de prueba, declarada «simulación local, no acredita B.2».
- Datos reales de terceros: se usa el dataset sintético (F-03) [B.3].
- Cifras inventadas: sin corrida real, «Medición pendiente».

## Criterios de aceptación

Copiados de `docs/backlog/carga-fallos.md`, US-33:

- **Dado** que hay tres nodos worker activos
- **Cuando** se envían al menos 20 casos de forma concurrente
- **Entonces** todos alcanzan un estado final
- **Y** se registran throughput, latencia por caso y recursos por nodo durante la ráfaga

- **Pruebas:** I cliente concurrente en corto. A `scenarios/burst.py`.
- **Demuestra:** conteo de casos finales. **Evidencia:** CSV y gráficos en el informe.

## Diseño

**Capas.** Todo vive en `scenarios/` (fuera de `src/`, como F-36 y F-37). La lógica es pura y recibe datos y ejecutor por parámetros: las unitarias no usan red, `sleep` ni reloj real.

**Se reutiliza, sin modificar:**

| Pieza | Uso |
|---|---|
| `scripts/run_load.py` (`run_load`, `submit_all`, `monitor`, `sample_workers`, `compute_metrics`) | Envío concurrente, muestreo de recursos por nodo y métricas (throughput en `throughput_subtasks_per_min`, latencia en `per_case[].duration_s`, `peak_cpu_by_host`, `peak_active_by_host`). El escenario no los duplica. |
| `FINISHED_STATUSES` de `run_load` | Definición de «estado final». |
| `scenarios/cancel_heavy.py`, `scenarios/memory_saturation.py` | Patrón de ejecutor inyectado y aceptación sobre JSON. |
| Dataset de F-03 | Casos sintéticos para la ráfaga. |

**Funciones previstas** (cortas, sin E/S salvo `ejecutar_rafaga` y `main`):

- `ejecutar_rafaga(args, ejecutor) -> dict`: valida `casos >= 20` y delega en `run_load`.
- `evaluar(resultado, minimo_casos=20, minimo_nodos=3) -> {"cumple": bool, "problemas": [...]}`.
- `filas_latencia(resultado) -> list[dict]` y `filas_recursos(resultado) -> list[dict]`.
- `escribir_csv(filas, ruta)`.
- `main()` con salida JSON y CSV.

**Decisiones.** AD-49 (provisional; se registra en `docs/ARQUITECTURA.md` §8 en la Parte 1): la ráfaga se valida con un escenario que envuelve `run_load` y evalúa su JSON, no con un segundo cliente de carga. Alternativas: reescribir un cliente concurrente en `scenarios/` (duplica `run_load`); ampliar `run_load` con la evaluación (mezcla medición con criterio y toca un script ya probado). Supuestos nuevos en `docs/REQUERIMIENTOS.md`:

- **SUP-45 (provisional).** «Concurrente»: concurrencia de envío ≥ número de casos (mínimo 20), para que todos estén en vuelo a la vez. «Estado final»: `completed`, `failed` o `cancelled`; un caso `failed` cuenta como final pero se reporta aparte. «Tres nodos activos»: tres `host` distintos con sub-tareas procesadas (o visibles en `series`). El plazo de la corrida es el `--timeout` de `run_load`.

Numeración AD-49 y SUP-45: siguiente libre en `main`; confirmar al integrar si otra rama usó el número.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_burst.py`: `evaluar` con JSON sintético (cumple; menos de 20 casos; caso sin estado final; `timed_out`; solo dos hosts; falta throughput o recursos) | Cada incumplimiento del criterio se detecta |
| Unitaria | `filas_latencia`, `filas_recursos`, `escribir_csv` (columnas, una fila por caso y por muestra, casos sin duración) | El CSV refleja el JSON |
| Unitaria | `ejecutar_rafaga` con ejecutor falso (rechaza menos de 20 casos, pasa concurrencia) | El escenario respeta SUP-45 sin red |
| Integración | `tests/integration/test_burst_cliente_concurrente.py`: 20 casos concurrentes contra la app del coordinador en proceso con Redis (o fakeredis) y workers falsos, corto | El cliente concurrente lleva 20 casos a estado final |
| Aceptación | `tests/acceptance/test_burst_aceptacion.py` sobre `BURST_JSON`; se omite sin él | La corrida real cumple las afirmaciones de US-33 |

TDD aplica a la lógica de `scenarios/burst.py` (Parte 1). La corrida en nodos no lleva TDD.

## Mediciones

B.6 Ráfaga. **Medición pendiente:** corrida en tres nodos worker reales (F-38 parte 2 sin nodos reales) y la ficha `docs/evidencia/F-33_rafaga.md`. Sin cifras inventadas.

1. Con los tres workers activos (`GET /workers` muestra tres hosts): `PYTHONPATH=. python -m scenarios.burst --dataset dataset --limit 20 --concurrency 20 --timeout 1800 --out docs/evidencia/F-33_<fecha>`.
2. Tres repeticiones; se reporta cada una, no solo la mejor. Opcional: 40 casos para ver saturación.
3. Corrida de prueba en la simulación local de F-38 parte 2, declarada «simulación local, no acredita B.2».
4. CSV y gráficos de latencia por caso y de recursos por nodo, generados con los CSV.
5. Ficha de destino: `docs/evidencia/F-33_rafaga.md`.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-33): escenario de rafaga con evaluacion y csv` | `scenarios/burst.py` (ejecutor, evaluación, CSV y `main`, unas 150 líneas), unitarias, integración corta y aceptación sobre JSON. Registra AD-49 y SUP-45 |
| 2 | `docs(F-33): evidencia de rafaga en nodos` | Corrida (simulación local declarada o tres nodos reales si hay) con su JSON, CSV, gráficos y ficha. Sin código; lo no corrido queda «Medición pendiente» |

## Riesgos y preguntas abiertas

Recomendación entre paréntesis; el orquestador las acepta por autonomía delegada.

1. **Reutilizar `run_load` en lugar de un cliente nuevo.** (Sí, AD-49.)
2. **Mínimo de 20 casos y concurrencia igual al número de casos.** (Aceptar SUP-45; el enunciado dice «al menos 20».)
3. **Un caso `failed` cuenta como estado final.** (Sí, pero se reporta aparte; el criterio habla de estado final, no de éxito.)
4. **Tres hosts distintos como prueba de tres nodos.** (Sí; la simulación local lo cumple con hosts declarados y no acredita B.2.)
5. **Gráficos:** se generan a partir de los CSV con matplotlib si ya es dependencia; si no, solo CSV y tabla en la ficha. (Verificar dependencias antes de la parte 2.)
6. **Corrida real:** depende de F-38 con nodos reales y del dataset de F-03; hasta entonces «Medición pendiente».
7. **Dependencias de F-24 (backpressure):** una ráfaga puede recibir 429 del coordinador; `submit_error` hace fallar la evaluación. (Dejarlo así y documentarlo; reintentos serían decisión de F-24.)
8. **Costo de la ráfaga en una sola máquina:** puede saturar el equipo de desarrollo. (Usar `--limit 20` y poco tamaño en simulación local.)

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5), subagente arquitecto lanzado; verificación del orquestador | 2026-11-12 | SPEC sin campos pendientes; criterios de US-33 copiados; campos de run_load citados existen (grep); AD-49 y SUP-45 libres en todas las ramas remotas; matplotlib en requirements-dev; pila de 2 partes; sin cambios fuera del SPEC (8afff1d) (8afff1d) |
| plan | Kenni Rodriguez | 2026-11-12 | aprobación delegada por la persona (autonomía total en /trabajar F-33) |
| verificación IA de tests | Claude Code (Sonnet 5.5), subagente developer; verificación del orquestador | 2026-11-12 | pytest de los 3 archivos nuevos falla con ImportError: cannot import name 'burst' (falta la funcionalidad); diff solo en tests/ (354 líneas), sin scenarios/burst.py; 33 pruebas unitarias cubren evaluar, filas, csv y ejecutar_rafaga (1af0d27) (1af0d27) |
| tests | Kenni Rodriguez | 2026-11-12 | aprobación delegada por la persona (autonomía total en /trabajar F-33) |
