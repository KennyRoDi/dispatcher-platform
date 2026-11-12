# SPEC F-15: Dashboard

**Fase:** plan
**Base:** main
**Verificación IA:** pendiente
**Historia:** US-15 · **Requisitos:** RF-17, [B.4 Dashboard] · **Responsable:** V

## Objetivo

El enunciado pide un dashboard en tiempo real [B.4], y RF-17 exige ver casos, sub-tareas, workers, colas y uso de recursos por nodo (CPU, memoria y GPU si existe). El dashboard del I Proyecto (`dashboard/`, Streamlit) ya muestra casos, sub-tareas, colas y CPU, RAM y GPU por worker, con refresco automático. Faltan dos cosas: la memoria del cgroup de cada worker (uso y límite reales, que son los que importan en M1) y la vista agrupada por nodo. F-15 agrega ambas para que el operador vea, durante una ráfaga, qué nodo se está saturando.

## Alcance

**Incluye:** campos `cgroup_memory_current` y `cgroup_memory_max` en el heartbeat del worker, leídos con el `ResourceReader` que el worker ya tiene (F-16); función pura de agregación por nodo; sección «Por nodo» en la vista Monitor; demo con captura y el comando de carga.

**No incluye:** métricas de GPU nuevas (se reutiliza `gpu` y `gpu_percent` del heartbeat); cambios en `ResourceReader` (José Andrés, F-16); alertas en el panel (F-14).

## Criterios de aceptación

De `docs/backlog/estados-reporte-dashboard.md` (US-15):

- **Dado** tres nodos activos y una ráfaga
- **Cuando** abro el dashboard
- **Entonces** veo casos, sub-tareas, workers, colas, y CPU, memoria y GPU si existe, para cada nodo, actualizándose

Criterios adicionales derivados de los requisitos:

- RF-17: el heartbeat publica `cgroup_memory_current` y `cgroup_memory_max` en bytes cuando el worker tiene `ResourceReader`; si la lectura falla o no hay lector, omite esos campos y el heartbeat sigue publicándose.
- RF-17: `GET /workers` devuelve esos campos tal como los publicó el heartbeat.
- RF-17: la agregación por nodo agrupa por `host`, cuenta workers vivos, promedia CPU y RAM, suma la memoria de cgroup (uso y límite), suma sub-tareas activas e informa la GPU si algún worker la tiene.

## Diseño

**Contratos.** Usa `ResourceReader` y `ResourceUsage` (José Andrés, F-16) sin cambiarlos.

| Capa | Archivo | Cambio | Dueño |
|---|---|---|---|
| Worker | `src/workers/heartbeat.py` | `Heartbeat(..., resource_reader=None)`; en `beat`, agrega los campos de cgroup si hay lector y la lectura no falla | Kenni (avisar) |
| Worker | `src/workers/worker_node.py` | Pasa `self.resource_reader` al `Heartbeat` | Kenni (avisar) |
| Dashboard | `dashboard/nodos.py` (nuevo) | `resumen_por_nodo(workers) -> list[dict]`, sin Streamlit, para probarla sola | Melany |
| Dashboard | `dashboard/views/monitor.py` | Sección «Por nodo» con la tabla de `resumen_por_nodo` y la memoria de cgroup como barra de uso | Melany |

**Decisiones.** Sin decisiones nuevas. La memoria de cgroup se publica en bytes y el panel la formatea.

**Código del I Proyecto que reutiliza.** El dashboard Streamlit, `GET /workers`, `GET /stats` y el heartbeat.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_heartbeat_incluye_memoria_de_cgroup`, sin lector no publica los campos, lector que falla no rompe el heartbeat | Heartbeat |
| Unitaria | `GET /workers` con un heartbeat que trae los campos de cgroup (fakeredis) | API |
| Unitaria | `resumen_por_nodo`: agrupa por `host`, ignora muertos en promedios, suma memoria de cgroup, GPU si existe, sin workers da lista vacía, valores faltantes o no numéricos no rompen | Formato separado de la vista |
| Aceptación | Demo: tres nodos, ráfaga con `scripts/submit_case.py`, captura del dashboard junto al comando | Criterio de US-15 |

## Mediciones

No aplica: F-15 no mide SO. La evidencia es la captura de la demo.

## Plan de pila

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-15): mostrar recursos por nodo en el dashboard` | Heartbeat con cgroup, `resumen_por_nodo` y la sección del Monitor. Estimado: ~80 líneas |
| 2 | `docs(F-15): demostrar el dashboard con tres nodos` | Captura y comando de carga |

## Riesgos y preguntas abiertas

1. **Archivos de workers.** `heartbeat.py` y `worker_node.py` son de Kenni; el cambio es aditivo (un parámetro opcional y dos campos). Hay que avisar.
2. **Demo.** Necesita los tres nodos levantados (F-38); la puede hacer cualquier integrante.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
