# Reutilización y correcciones

Cumple [B.2]: qué se reutiliza del I Proyecto, qué se modificó y qué es nuevo, y cómo se corrigieron sus deficiencias. Los estados salen de `git`, no de memoria del equipo.

## 1. Origen y método de comprobación

Origen: repositorio `nahum0804/distributed-processing-platform`, commit `bc6bab6` (último del I Proyecto, 2026-10-03), ancestro de `main`. Es el commit que cita `docs/ARQUITECTURA.md` §1. No se debe reescribir el historial (`rebase`, squash) para que la comprobación siga posible.

Se clasifica solo el producto (`src/`, `scripts/`, `dashboard/`, `deploy/`, `benchmarks/` y la raíz). Las pruebas heredadas se resumen en una fila. Reglas:

- `reutilizado`: sin diferencia entre `bc6bab6` y `main`.
- `modificado`: con diferencia; se indica la feature y el commit que lo tocó.
- `nuevo`: ausente en `bc6bab6`.

Para repetirlo:

```bash
git diff --name-status bc6bab6 origin/main -- src scripts dashboard deploy benchmarks
git log --no-merges --format='%h %s' bc6bab6..origin/main -- <ruta>
git ls-tree -r --name-only bc6bab6 -- <ruta>
```

Estados de las deficiencias (sección 4): `corregida` (existe corrección y prueba o evidencia), `parcial` (existe pero no cubre todo el camino), `pendiente` (sin corrección) y `no aplica` (decisión declarada, no se corrige). Lista de deficiencias: tabla de `docs/ARQUITECTURA.md` §1 y «Limitaciones conocidas» de `docs/DECISIONES_DISENO.md` (SUP-19: no se halló la retroalimentación de la evaluación del I Proyecto).

## 2. Componentes del I Proyecto

### Reutilizado (sin diferencia)

| Estado | Ruta | Nota |
|---|---|---|
| reutilizado | `src/coordinator/router.py`, `src/coordinator/__init__.py` | Resolución del tipo de tarea |
| reutilizado | `src/workers/recovery.py`, `scripts/reaper.py` | Heartbeat y reaper: reencolado de sub-tareas de workers caídos (`Heartbeat y reaper` en la sección 4) |
| reutilizado | `scripts/build_dataset.py`, `scripts/seed_minio.py`, `seed_tasks.py`, `server.py`, `worker.py`, `build_manual_pdf.py` | Utilidades y puntos de entrada |
| reutilizado | `dashboard/app.py`, `dashboard/views/casos.py`, `dashboard/views/conexion.py`, `dashboard/views/resumen.py`, `dashboard/views/tareas.py`, `dashboard/views/workers.py` | Dashboard Streamlit |
| reutilizado | `benchmarks/benchmark_transcode.py` | Benchmark de transcodificación |
| reutilizado | `requirements-dashboard.txt`, `.dockerignore`, `.gitattributes`, `documentacion/` | Configuración y manual |

### Modificado

| Estado | Ruta | Feature y commit |
|---|---|---|
| modificado | `src/coordinator/main.py` | Pasó de 802 a 104 líneas: `5a11a66` (PR #16, `refactor`) lo repartió en `src/coordinator/rutas_casos.py`, `src/coordinator/rutas_subtareas.py`, `src/coordinator/rutas_monitoreo.py` y `src/coordinator/apoyo.py`. Después: F-26 `f792c68`, F-13 `13afce3`, F-14 `b0b8803`, F-22 `94a26b0`, F-23 `679ee79`, F-24 `9d2249d` |
| modificado | `src/workers/worker_node.py` | F-12 `8c85862`, F-15 `b12cb67`, F-17 `d0c909a`, F-18 `a6484aa`, F-36 `d80b225` |
| modificado | `src/workers/multimedia_processor.py` | F-18 `a6484aa`, F-36 `d80b225` |
| modificado | `src/workers/heartbeat.py` | F-15 `b12cb67`, F-38 `9517e4d` |
| modificado | `src/workers/config.py` | F-17 `d0c909a`, F-26 `b366e3e`, F-27 `5be25e1`, F-38 `9517e4d` |
| modificado | `src/workers/reporter.py` | F-26 `b366e3e`, F-27 `5be25e1` |
| modificado | `src/workers/storage.py` | F-27 `5be25e1` |
| modificado | `scripts/submit_case.py`, `scripts/run_load.py` | F-26 `c5dbcc8`, F-27 `98aa38f` y `5be25e1` |
| modificado | `scripts/check_connectivity.py` | F-27 `98aa38f` y `5be25e1` |
| modificado | `scripts/demo_feeder.py`, `scripts/fetch_results.py`, `scripts/generate_dataset.py` | F-27 `98aa38f` |
| modificado | `dashboard/ui.py` | F-26 `b366e3e` |
| modificado | `dashboard/views/monitor.py` | F-15 `b12cb67` |
| modificado | `Dockerfile.worker` | F-30 `82f685d`, F-38 `3d925e9` y `e3ab57f` |
| modificado | `docker-compose.yml` | F-26 `b366e3e`, F-27 `c54de78`, F-38 `d5b5bff` |
| modificado | `deploy/docker-compose.worker.yml` | F-16 `7fef365`, F-27 `c54de78`, F-30 `82f685d`, F-38 `df22ac9` |
| modificado | `deploy/docker-compose.local.yml`, `deploy/docker-compose.demo.yml`, `deploy/docker-compose.worker-gpu.yml` | Diferencia respecto de `bc6bab6` (`git log` por ruta) |
| modificado | `.env.example`, `.env.demo`, `.gitignore`, `README.md`, `pytest.ini`, `requirements.txt`, `requirements-dev.txt` | Diferencia respecto de `bc6bab6` (`git log` por ruta) |
| modificado | `tests/test_config.py`, `tests/test_contract.py`, `tests/test_coordinator.py`, `tests/test_dashboard.py`, `tests/test_heartbeat.py`, `tests/test_reporter.py`, `tests/test_scripts.py`, `tests/test_worker_node.py` | De los 18 `tests/test_*.py` heredados, estos 8 cambiaron; los otros 10 y `tests/fakes.py` se conservan |

### Elementos de `docs/ARQUITECTURA.md` §1 marcados «Reutilizar»

| Estado | Elemento de §1 | Ruta |
|---|---|---|
| modificado | Coordinador FastAPI sin estado propio | `src/coordinator/main.py`, `src/coordinator/router.py` (este sin cambios) |
| modificado | Barrier/join idempotente (`SADD`) | La lógica se movió de `src/coordinator/main.py` a `src/coordinator/rutas_subtareas.py` (`5a11a66`); después la tocaron F-10 `0af6c06` y F-14 `7bea224`, `8ee78c6` |
| modificado | Heartbeat y reaper | `src/workers/recovery.py` y `scripts/reaper.py` sin cambios; `src/workers/heartbeat.py` modificado |
| modificado | Dashboard Streamlit | `dashboard/app.py` y las vistas sin cambios; `dashboard/ui.py` y `dashboard/views/monitor.py` modificados |

### Nuevo dentro de directorios heredados

| Estado | Ruta | Feature |
|---|---|---|
| nuevo | `src/coordinator/seguridad.py` | F-26 |
| nuevo | `src/coordinator/rutas_alertas.py`, `src/coordinator/rutas_reporte.py` | F-14, F-13 |
| nuevo | `src/coordinator/rutas_archivos.py` | F-22 |
| nuevo | `src/coordinator/apoyo.py`, `src/coordinator/conexion.py`, `src/coordinator/modelos.py`, `src/coordinator/rutas_casos.py`, `src/coordinator/rutas_monitoreo.py`, `src/coordinator/rutas_subtareas.py` | `5a11a66`: división de `main.py` |
| nuevo | `src/workers/cancelacion.py` | F-12 |
| nuevo | `dashboard/nodos.py` | F-15 |
| nuevo | `scripts/measure/` | F-19, F-21, F-22, F-23, F-24, F-25, F-31 |
| nuevo | `scripts/preflight.py`, `scripts/start_worker.py` | F-16 |
| nuevo | `scripts/emitir_token.py`, `scripts/generar_credenciales.py` | F-26 |
| nuevo | `scripts/verificar_workers.py` | F-30 |
| nuevo | `scripts/verify_custody.py` | F-29 |
| nuevo | `scripts/subir_por_chunks.py` | F-22 |
| nuevo | `scripts/dataset_sintetico.py`, `scripts/dataset_verdad.py` | F-03, F-04 |
| nuevo | `scripts/aciertos_imagen.py`, `scripts/aciertos_texto.py`, `scripts/comparar_transcripcion.py` | F-08, F-07, F-09 |
| nuevo | `scripts/flujo.py`, `scripts/conformidad.py` | Ciclo de trabajo y conformidad con el enunciado |
| nuevo | `deploy/tls/` | F-27 |
| nuevo | `tests/unit/`, `tests/integration/`, `tests/acceptance/`, `tests/dobles.py`, `tests/contratos.py` | Pruebas por capa, dobles y contratos |

## 3. Componentes nuevos por capa

Ninguna de estas capas existía en `bc6bab6`; las define `docs/ARQUITECTURA.md` §4.

| Capa | Ruta | Features |
|---|---|---|
| Dominio | `src/domain/` | F-03, F-04, F-05, F-07, F-08, F-09, F-10, F-13, F-14, F-16, F-17, F-18, F-19, F-20, F-22, F-24, F-26, F-29, F-31, F-32; prioridad en `src/domain/priority.py`, planificación en `src/domain/scheduling.py` |
| Aplicación | `src/application/` | Puertos en `src/application/ports.py`; casos de uso de F-01, F-05, F-07, F-08, F-09, F-10, F-12, F-13, F-14, F-22, F-29 |
| Adaptadores | `src/adapters/` | Redis: `src/adapters/redis_type_queue.py` (F-06), `src/adapters/redis_scheduler.py` (F-20), `src/adapters/redis_backpressure.py` (F-24), `src/adapters/redis_case_state.py` (F-10), `src/adapters/redis_case_catalog.py` y `src/adapters/redis_finding_store.py` (F-13), `src/adapters/redis_alert_stream.py` (F-14). Almacén y llaves: `src/adapters/minio_object_store.py` (F-23), `src/adapters/encrypted_object_store.py`, `src/adapters/envelope_cipher.py` y `src/adapters/file_key_provider.py` (F-28), `src/adapters/jsonl_custody_log.py` (F-29). Analizadores: F-07, F-08, F-09. Generadores de dataset: F-03. Seguridad y procesos: `src/adapters/jwt_tokens.py` (F-26), `src/adapters/posix_process_runner.py` (F-12) |
| Infraestructura | `src/infrastructure/` | `src/infrastructure/cgroup_resources.py` (F-16), `src/infrastructure/tls.py` (F-27), `src/infrastructure/model_loader.py` y `src/infrastructure/fork_runtime.py` (F-19), `src/infrastructure/object_store.py` (F-23), `src/infrastructure/clock.py` (F-36) |
| Configuración y escenarios | `config/`, `scenarios/` | Routing y analizadores (F-07, F-08, F-09, F-32); `scenarios/cancel_heavy.py` (F-36), `scenarios/memory_saturation.py` (F-37) |

## 4. Deficiencias del I Proyecto y su corrección

| Deficiencia (fuente) | Corrección enlazada | Estado | Detalle |
|---|---|---|---|
| Consumo `BLPOP` + `WATCH/MULTI`: ventana de pérdida entre el `BLPOP` y el reclamo (§1; Limitaciones conocidas) | AD-03, F-06, PR #131; `src/adapters/redis_type_queue.py`; `tests/unit/test_redis_type_queue.py`, `tests/integration/test_redis_type_queue_reaper.py` | parcial | Solo el camino nuevo de F-05/F-01 usa `BLMOVE`. `src/workers/worker_node.py` (`poll_once`) sigue con `blpop` y `scripts/reaper.py` con la ventana; declarado en AD-03 y pendiente para F-34 |
| Prioridad estricta `:high` con inanición (§1; Limitaciones conocidas) | AD-04, F-20, PR #126; `src/domain/scheduling.py`, `src/domain/priority.py`, `src/adapters/redis_scheduler.py`; `tests/unit/test_scheduling.py`; comparación F-21, PR #129, `docs/evidencia/F-21_comparacion_politicas_2026-11-11.csv` | parcial | `RedisScheduler` no tiene consumidor en `src/` fuera de su módulo y `Settings.queue_keys` (`src/workers/config.py`) sigue poniendo las colas `:high` primero (`git grep`) |
| Cancelación que no detiene FFmpeg en curso (§1; Limitaciones conocidas) | AD-08, AD-09, AD-31, F-12, F-36 (PR #95); `src/workers/cancelacion.py`, `src/adapters/posix_process_runner.py`, `src/application/process_supervisor.py`; `tests/unit/test_cancelacion_en_curso.py`, `tests/test_worker_cancelacion.py`; `docs/evidencia/F-12_cancelacion_2026-11-10.md`, `docs/evidencia/F-36_cancelacion_en_curso.md` | corregida | Con prueba y evidencia |
| Límites de memoria: no existen (§1) | AD-05, AD-06, AD-29, AD-30; F-16 `deploy/docker-compose.worker.yml`, `scripts/preflight.py`; F-17 `src/domain/admission.py`; F-18 `src/domain/oom_policy.py`; `tests/unit/test_admission.py`, `tests/unit/test_f16_compose_memory.py`, `tests/unit/test_oom_policy.py`; `docs/evidencia/mediciones-f18` | corregida | Corregida en código y pruebas; la ficha M1 con datos medidos va en F-41, sin ella M1 queda con máximo 2 |
| TLS, autenticación: no existen (§1) | AD-14, AD-33, F-26 (`src/coordinator/seguridad.py`, `src/adapters/jwt_tokens.py`, `src/domain/rbac.py`); AD-15, AD-37, F-27 (`src/infrastructure/tls.py`, `deploy/tls/generar_certs.sh`); `tests/unit/test_seguridad_rutas.py`, `tests/unit/test_tls.py`; `docs/evidencia/F-27_servidores_tls_local_2026-11-11.md` | parcial | Probado en una máquina; la captura en tres nodos reales depende de F-38 |
| TLS, autenticación: MinIO con credencial por defecto (§1) | F-26 emite `JWT_SECRET`, `WORKER_TOKEN` y `API_TOKEN` (`scripts/generar_credenciales.py`) pero no la de MinIO | pendiente | `minioadmin` sigue como valor por defecto en `docker-compose.yml:48-49`, `docker-compose.yml:80-81`, `.env.example:23-24`, `.env.demo:8-9`, `deploy/docker-compose.local.yml:28,68,100`, `deploy/docker-compose.demo.yml:19` y `src/workers/config.py:106-107` (`git grep minioadmin`). Sin corrección enlazable; propuesta en la pregunta 1 del SPEC de F-39 |
| Workers: solo FFmpeg, sin modelos ni texto (§1) | F-07, F-08, F-09, AD-26, AD-27, AD-28; F-32, AD-32; `src/adapters/text_analyzer.py`, `src/adapters/image_analyzer.py`, `src/adapters/audio_analyzer.py`, `src/domain/routing.py` | no aplica | Es capacidad nueva que exige [B.1], no una corrección. Los analizadores y la aplicación existen; `src/workers/` no los invoca (`git grep`): cableado de producción pendiente de confirmar por el dueño de F-07 a F-09 |
| Evidencia en 3 máquinas: una sola máquina; prueba de carga sin GPU (§1; Limitaciones conocidas) | F-38, AD-23, AD-24; `docs/evidencia/F-38_tres_nodos_simulacion_local_2026-11-11.md` | pendiente | Esa evidencia se declara «simulación local, no acredita B.2»; faltan tres nodos reales |
| Redis, MinIO, coordinador y reaper en una sola máquina, sin alta disponibilidad (Limitaciones conocidas) | AD-02, AD-21 | no aplica | Decisión declarada: Nodo A único, no se corrige |
| Heartbeat y reaper: reencola en ~25 s, declarado sin logs en `docs/evidencia/` (§1) | F-34, F-35 | pendiente | Sin logs de las pruebas de caos; F-34 y F-35 aún `pendiente` |
| Sin soporte de NPU (Limitaciones conocidas) | `docs/DECISIONES_DISENO.md` §3 la descarta por hardware; clasificación en F-39, SUP-19 | no aplica | Ninguna feature la añade |

## 5. Terceros por feature

| Feature | Componente | Fuente | Licencia | Cambio |
|---|---|---|---|---|
| F-12 | Sin terceros en F-12 | F-12 usa solo biblioteca estándar (`signal`, `shutil`, `threading`, `logging`) | — | — |
| F-36 | Sin terceros en F-36 | F-36 usa solo biblioteca estándar de Python | — | — |
| F-06 | Sin terceros en F-06 | F-06 usa Redis (ya dependencia) vía `redis-py`; la corrección de la ventana de pérdida se documenta en AD-03, `docs/ARQUITECTURA.md` | — | — |
| F-39 | Código del I Proyecto | repositorio `nahum0804/distributed-processing-platform`, commit `bc6bab6` | por confirmar | ver sección 2 |
