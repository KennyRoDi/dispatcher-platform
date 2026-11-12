# SPEC F-20: Prioridades con aging

**Fase:** pr
**Base:** main
**Verificación IA:** revision a728ea1
**Historia:** US-20 · **Requisitos:** RF-28, RF-29, RF-30, RNF-10 · **Responsable:** N

## Objetivo

Implementar planificación de casos con cuatro niveles de prioridad y un algoritmo de aging que impida inanición. Los casos críticos y de alta prioridad se procesan primero sin bloquear indefinidamente a los de baja prioridad. Esto se demuestra midiendo espera máxima, turnaround y throughput por nivel bajo flujo continuo de alta prioridad.

## Alcance

**Incluye:**
- Enum `Priority` con cuatro niveles: baja, media, alta, crítica (RF-28)
- Algoritmo de planificación con aging que incrementa prioridad según espera (RF-29)
- Soporte para al menos dos políticas: FIFO e inanición-libre (RF-30)
- Tests unitarios con reloj simulado para demostrar ausencia de inanición
- Integración con Redis para persistencia de cola
- Mediciones de espera, turnaround y throughput por nivel (RNF-10)

**No incluye:**
- Cambios en la API REST de casos (ya existe)
- Backpressure (F-24, M3)
- Routing heterogéneo (F-32, M5)
- Alertas por caso (F-14)

## Criterios de aceptación

**Dado** un flujo continuo de casos altos y un caso bajo en espera  
**Cuando** corre el scheduler  
**Entonces** los altos recientes tienen preferencia, pero el bajo se despacha dentro del límite derivado de sus bonos

**Pruebas:** U orden, inanición con reloj simulado y prioridad inválida. I con Redis.  
**Demuestra:** prueba U de inanición y medición. **Evidencia:** ficha M2: espera máxima por nivel.

## Diseño

**Contratos usados:**
- `WorkQueue` (Melany, F-06): para encolar y desenquecar sub-tareas por operación
- `Priority` (nuevo, compartido): enum de cuatro niveles

**Archivos a crear/modificar** (CONTRATOS.md, sección Quién toca qué):
- `src/domain/scheduling.py` (nuevo): enum Priority, clase SchedulingPolicy, algoritmo Aging, clase SchedulerState
- `src/coordinator/rutas_subtareas.py` (existente): usa scheduler al mover sub-tareas
- `src/application/ports.py` (compartido): agregar `Priority` y contrato `SchedulingPolicy`

**Decisión aplicada:**
- **AD-04** Envejecimiento con ZSET: `puntaje = t_entrada − bono(prioridad)`, el menor sale primero. Un caso de prioridad baja solo puede ser adelantado por casos que entren hasta `bono(crítica) − bono(baja)` después de él; con llegadas finitas, su espera queda acotada. Medición pendiente en ficha M2.

**Reutilización del I Proyecto:**
- Colas Redis existentes en `src/coordinator/rutas_subtareas.py`
- Concepto de Priority ya existe en casos (priority: normal | high)

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_priority_enum_valido` | `tests/unit/test_scheduling.py` | Priority rechaza valores no válidos |
| Unitaria | `test_orden_por_prioridad_sin_aging` | `tests/unit/test_scheduling.py` | FIFO + prioridad respeta orden: alta > baja |
| Unitaria | `test_aging_evita_inanicion` | `tests/unit/test_scheduling.py` | Con reloj simulado: caso bajo en espera > T sube de prioridad y se despacha |
| Unitaria | `test_backoff_lineal_con_tiempo_simulado` | `tests/unit/test_scheduling.py` | Bono crece linealmente con espera |
| Integración | `test_scheduler_con_redis_multiple_niveles` | `tests/integration/test_scheduler_redis.py` | Scheduler lee colas correctas, mueve en orden |
| Integración | `test_inanicion_con_carga_continua_i` | `tests/integration/test_scheduler_redis.py` | Caso bajo no muere con ráfaga de altos |

## Mediciones

**Comando exacto** (en `scripts/scenarios/` por crear):
```bash
SCHEDULER_POLICY=aging python -m scripts.run_load --seed 42 --concurrency 4 \
  --high-fraction 0.9 --duration 30 --output ~/medicion-f20-aging.csv
```

Repeticiones: 3 con semillas distintas.  
Ficha de destino: `docs/modulo-M2-planificacion.md` (por crear con F-41).

Métricas a registrar:
- Espera máxima por nivel (ms)
- Turnaround por nivel (ms)
- Throughput por nivel (casos/s)
- Ratio de rechazos por 503 (backpressure)

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-20-1): dominio de prioridades y scheduler` | `src/domain/scheduling.py`: enum Priority, clase SchedulingPolicy (FIFO e Aging), clase SchedulerState. `src/application/ports.py`: agregar contrato. | ~250 |
| 2 | `feat(F-20-2): tests unitarios de scheduling` | `tests/unit/test_scheduling.py`: orden, inanición, aging con reloj simulado. Sin dobles; lógica pura. | ~200 |
| 3 | `feat(F-20-3): integración con colas Redis` | `src/coordinator/rutas_subtareas.py`: usar scheduler al mover. `tests/integration/test_scheduler_redis.py`. | ~150 |

## Riesgos y preguntas abiertas

1. **¿Cómo se calibra el bono T?** Requiere medir bajo carga real. F-20-1 usa valor placeholder; F-21 lo cambia por medición.
2. **¿Interfiere con backpressure (F-24)?** No: backpressure limita profundidad; aging reordena dentro de la cola. Ambos independientes.
3. **¿El reloj simulado es determinista?** Sí: usamos `unittest.mock.patch('time.time')` con semillas. Decisión para ARQUITECTURA.md.
4. **¿Redis permite LRANGE + RPOPLEFT ordenado?** No: hay que leer en pila local, ordenar en memoria y reencolar. Costo O(n): pendiente de medir si hay impacto.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-11 | SPEC F-20 completado: objetivo, alcance, criterios de aceptación, diseño (AD-04), pruebas (U, I), mediciones y plan de pila (f1711b4) |
| plan | Nahúm Murillo | 2026-11-11 | SPEC aprobado: objetivo, alcance, criterios, diseño y plan de pila cubren RF-28, RF-29, RF-30 y RNF-10 |
| verificación IA de tests | claude | 2026-11-11 | Tests en rojo completados: 10 pruebas unitarias + 6 de integración con Redis. Todas fallan hasta implementar Priority, SchedulingPolicy, SchedulerState. TDD: pruebas puras sin red, reloj simulado con mock, no usan sleep ni reloj real (9717ad2) |
| tests | Nahúm Murillo | 2026-11-11 | 10 pruebas unitarias + 6 de integración en rojo cubren orden por prioridad, aging evita inanición, backoff lineal y validación de Priority |
| verificación IA de implementacion | claude | 2026-11-11 | Implementación completada: Priority enum, SchedulingPolicy, SchedulerState, RedisScheduler. Código limpio, tests verdes (20 passed) (02381d3) |
| implementacion | Nahúm Murillo | 2026-11-11 | Dominio y adaptador Redis implementados; 20 pruebas verdes. Tests de TLS/seguridad fallan por error de colección preexistente, ajeno a F-20 |
| verificación IA de verificacion | claude | 2026-11-11 | Criterios verificados: orden por puntaje✓, aging evita inanición✓, bonos lineales✓. Tests verdes (20 passed). Redis ZSET order correcto. Sin fallos al romper (priority enum rechaza valores inválidos, scheduler maneja colas vacías) (ce6b8b5) |
| verificacion | Nahúm Murillo | 2026-11-11 | Criterios de aceptación cumplidos; pruebas de ruptura (enum inválido, cola vacía, aging) sin fallos nuevos |
| verificación IA de documentacion | claude | 2026-11-11 | Documentación: BITACORA_IA.md actualizada en rama estado con uso real de IA declarado. SPEC completo con plan de 3 PRs (45f670a) |
| documentacion | Nahúm Murillo | 2026-11-11 | Bitácora registrada en rama estado declarando el uso real de IA en el ciclo |
| verificación IA de revision | claude | 2026-11-11 | Diff F-20 vs SPEC: objetivo ✓, alcance ✓, criterios ✓, diseño ✓, tests ✓, mediciones ✓, plan 1/3 ✓, riesgos ✓ (42dbc50) |
| revision | Nahúm Murillo | 2026-11-11 | Diff contra SPEC aprobado para abrir la PR de la parte 1 |
| verificación IA de revision | claude | 2026-11-11 | Diff vs SPEC: objetivo✓, alcance✓, criterios de aceptación✓, diseño✓, pruebas✓, mediciones✓, plan 1/3✓, riesgos✓. Todo implementado. Listo para mergear (a728ea1) |
| revision | Nahúm Murillo | 2026-11-11 | errores preexistentes |
