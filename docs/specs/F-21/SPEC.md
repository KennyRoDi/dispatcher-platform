# SPEC F-21: Comparación de políticas

**Fase:** plan
**Base:** main
**Verificación IA:** plan 3683020
**Historia:** US-21 · **Requisitos:** RF-30, RNF-10 · **Responsable:** N

## Objetivo

Permitir elegir la política de planificación (FIFO o aging) por configuración, sin cambiar otro código, y comparar ambas bajo la misma carga con semilla fija. Esto demuestra con datos que FIFO dejar entrar sin orden de prioridad produce inanición potencial de los casos críticos bajo ráfaga, mientras que aging (F-20, ya en `main`) acota la espera de los casos de baja prioridad sin bloquear indefinidamente a los demás.

## Alcance

**Incluye:**
- Selección de política por configuración (variable de entorno `SCHED_POLICY`), reutilizando `SchedulingPolicy` y `SchedulerState` de F-20 (RF-30)
- Prueba unitaria que confirma que FIFO ignora la prioridad al ordenar
- Prueba unitaria que confirma que la política se elige correctamente según la configuración
- Script de medición `scripts/measure/m2_sched.py`: simula carga sintética con tasa alta continua y casos de baja prioridad, bajo cada política, y registra espera, turnaround y throughput por nivel
- Script `scripts/measure/m2_plot.py`: genera gráficos comparativos desde los CSV producidos
- Ficha `docs/modulo-M2-planificacion.md` con tablas y gráficos de la comparación (RNF-10)

**No incluye:**
- Cambios al algoritmo de aging en sí (ya implementado y aprobado en F-20)
- Nuevos niveles de prioridad
- Integración con Redis o con workers reales: la medición es una simulación en memoria de la lógica de `SchedulerState`, igual que las pruebas unitarias de F-20
- Routing heterogéneo o backpressure (F-24, F-32)

## Criterios de aceptación

**Dado** la misma carga con semilla fija
**Cuando** se ejecuta con FIFO y con aging
**Entonces** se obtienen espera, turnaround y throughput por nivel y política

**Pruebas:** U `test_fifo_ignora_prioridad`, `test_politica_se_elige_por_configuracion`.
**Demuestra:** experimento. **Evidencia:** ficha M2: tablas y gráficos.

## Diseño

**Contratos usados:**
- `SchedulingPolicy`, `SchedulerState` (`src/domain/scheduling.py`, F-20, ya en `main`): no se modifican, solo se ejercitan ambos valores del enum

**Archivos a crear/modificar** (CONTRATOS.md, sección Quién toca qué — todos de Nahúm, M2):
- `tests/unit/test_scheduling.py` (existente): agregar `test_fifo_ignora_prioridad` y `test_politica_se_elige_por_configuracion`
- `scripts/measure/m2_sched.py` (nuevo): simulador de carga con política seleccionable por `SCHED_POLICY`, produce CSV
- `scripts/measure/m2_plot.py` (nuevo): genera gráficos desde los CSV
- `docs/modulo-M2-planificacion.md` (nuevo): ficha con las cinco secciones (qué se implementó, concepto de SO, método, resultados, interpretación)

**Decisión aplicada:**
- **AD-04** (ya registrada en F-20): "scheduler como política intercambiable". No se propone una decisión nueva; este SPEC ejecuta la medición que AD-04 declaró pendiente ("Medición pendiente: ficha M2, comparada con FIFO").

**Reutilización del I Proyecto:**
- Ninguna adicional a la ya declarada en F-20

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_fifo_ignora_prioridad` | `tests/unit/test_scheduling.py` | Con política FIFO, un caso crítico que entra después no adelanta a uno de baja que ya esperaba |
| Unitaria | `test_politica_se_elige_por_configuracion` | `tests/unit/test_scheduling.py` | Una cadena de configuración (`"fifo"` / `"aging"`) se traduce al `SchedulingPolicy` correcto |
| Integración | `test_medicion_corta_produce_csv_por_politica` | `tests/integration/test_m2_sched.py` | Corrida corta del simulador con ambas políticas produce un CSV con columnas de espera, turnaround y throughput por nivel |

## Mediciones

**Comando exacto:**
```bash
SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate 20 --low 1 --seed 42 --out m2_fifo.csv
SCHED_POLICY=aging python scripts/measure/m2_sched.py --high-rate 20 --low 1 --seed 42 --out m2_aging.csv
python scripts/measure/m2_plot.py m2_fifo.csv m2_aging.csv
```

Repeticiones: 3 con semillas distintas (42, 43, 44).
Ficha de destino: `docs/modulo-M2-planificacion.md` (nueva).

Métricas a registrar:
- Espera por nivel (ms), FIFO vs aging
- Turnaround por nivel (ms), FIFO vs aging
- Throughput por nivel (casos/s), FIFO vs aging
- Espera máxima de la prioridad baja bajo cada política (ausencia de inanición)

**Nota de alcance de la medición:** esta es una simulación en memoria de la lógica de `SchedulerState` (CPU y decisión de orden), no una corrida distribuida sobre los tres nodos reales — coherente con que F-20/F-21 son puramente de dominio, sin E/S de red. Si la persona responsable considera que esto no sustituye una medición en los nodos reales, se marca «Pendiente de medir en los nodos» y se declara la diferencia.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-21): selección de política por configuración y comparación medida` | Pruebas de FIFO/configuración, `scripts/measure/m2_sched.py`, `scripts/measure/m2_plot.py`, ficha M2 | ~300 |

## Riesgos y preguntas abiertas

1. **¿La medición en memoria basta como evidencia de RNF-10?** M2 es lógica de planificación pura (no E/S); se documenta la limitación en la ficha y queda a criterio del responsable ampliarla con los nodos reales en F-41.
2. **¿`SCHED_POLICY` o reutilizar `aging_bonus_ms`/parámetros ya existentes?** Se usa una variable de entorno nueva y específica (`SCHED_POLICY`) porque ya está documentada así en `docs/IMPLEMENTACION.md` §5.
3. **¿Conflicto de nombre con `SCHEDULER_POLICY` mencionado en el SPEC de F-20?** El SPEC de F-20 (mediciones, ahora obsoleto en ese punto) usaba un nombre provisional distinto; este SPEC fija `SCHED_POLICY` como el nombre definitivo, documentado en `docs/IMPLEMENTACION.md`.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-11 | SPEC F-21 completado: objetivo, alcance, criterios de aceptación, diseño (reutiliza AD-04 de F-20, sin nueva decisión), pruebas (U, I), mediciones (SCHED_POLICY, scripts/measure/m2_sched.py y m2_plot.py) y plan de pila de 1 parte (3683020) |
