# SPEC F-39: Reutilización y correcciones

**Fase:** implementacion
**Base:** main
**Verificación IA:** implementacion 87c887a
**Historia:** US-39 · **Requisitos:** RNF-02, RNF-03, RNF-24 · **Responsable:** N

## Objetivo

Un evaluador debe poder distinguir, sin leer el código, qué se heredó del I Proyecto, qué se cambió y qué es nuevo, y comprobar que las deficiencias del I Proyecto se corrigieron. El enunciado lo exige en [B.2]: «El equipo debe entregar docs/reutilizacion.md indicando con precisión qué se reutiliza, qué se modifica y qué es nuevo» y «Si la infraestructura del I Proyecto presentó deficiencias señaladas en su evaluación, el equipo debe corregirlas como parte de este proyecto». La evaluación técnica se concentra en lo nuevo, por lo que el documento también debe señalar dónde está.

Hoy `docs/reutilizacion.md` solo tiene tres filas de terceros (F-12, F-36, F-06). Esta feature lo reorganiza en cinco secciones sin perder esas filas y se apoya únicamente en hechos verificables en el repositorio: `bc6bab6` (último commit del I Proyecto, 2026-10-03, el que cita `docs/ARQUITECTURA.md` §1) es ancestro de `main`, así que cada clasificación se comprueba con `git diff --name-status bc6bab6 origin/main -- <ruta>`.

## Alcance

**Incluye:**

- Reescribir `docs/reutilizacion.md` con cinco secciones: (1) origen y método de comprobación; (2) componentes del I Proyecto, cada archivo o directorio con estado `reutilizado`, `modificado` o `nuevo`, ruta, feature y commit o PR que lo cambió; (3) componentes nuevos por capa; (4) deficiencias del I Proyecto, cada una con su corrección enlazada (AD-XX, F-XX, PR, prueba o evidencia) y su estado real (`corregida`, `parcial`, `pendiente`, `no aplica`); (5) «Terceros por feature», con las tres filas actuales intactas y el mismo formato de tabla para que otras features sigan añadiendo filas.
- Una fila por cada «Elemento» de la tabla de `docs/ARQUITECTURA.md` §1 y por cada viñeta de «Limitaciones conocidas» de `docs/DECISIONES_DISENO.md`.
- Una prueba unitaria que valide el documento (ver Pruebas).
- Declarar sin maquillar lo que está solo parcialmente corregido (ver Diseño).

**No incluye:** cambios en `src/`, `scripts/`, `deploy/` ni `dashboard/`; corregir en esta feature las deficiencias que hoy están `parcial` o `pendiente` (cableado de `RedisScheduler`, cierre de la ventana `BLPOP` del camino heredado, credencial `minioadmin`, evidencia en tres máquinas reales, pruebas de caos); modificar la tabla de `docs/ARQUITECTURA.md` §1 ni crear decisiones `AD-XX`; auditar licencias de `requirements*.txt` (ver pregunta 4); mediciones de SO; evaluar a las personas del equipo (la columna de responsable no se incluye).

## Criterios de aceptación

Copiados de `docs/backlog/entrega.md` (US-39):

- **Dado** el repositorio del I Proyecto
- **Cuando** se revisa `docs/reutilizacion.md`
- **Entonces** cada componente aparece como reutilizado, modificado o nuevo, con ruta, y cada deficiencia tiene corrección enlazada

Criterios de RNF-02, RNF-03 y RNF-24 (`docs/REQUERIMIENTOS.md`): cada componente del I Proyecto aparece en una de las tres categorías con ruta; cada deficiencia señalada tiene su corrección enlazada; cada dependencia copiada o adaptada tiene su fuente citada en el código y en la documentación.

## Diseño

**Contratos:** ninguno de `docs/CONTRATOS.md`; no hay código de producción. **Capas:** ninguna. **Decisiones:** aplica AD-01 (reutilizar donde sirva) y SUP-19 (las deficiencias se toman de `docs/DECISIONES_DISENO.md` porque no se halló la retroalimentación de la evaluación). No propone decisión nueva.

**Archivos:** `docs/reutilizacion.md` (reescrito) y `tests/unit/test_reutilizacion_doc.py` (nuevo). `scripts/conformidad.py` ya exige `docs/reutilizacion.md` para F-39.

**Método.** Estado por archivo según `git diff bc6bab6 origin/main`: sin diferencia = `reutilizado`; con diferencia = `modificado`, con el commit y la feature que lo tocó (`git log bc6bab6..origin/main -- <ruta>`); ausente en `bc6bab6` = `nuevo`. El documento declara el comando para repetirlo. Solo se clasifica el producto (`src/`, `scripts/`, `dashboard/`, `deploy/`, `benchmarks/`, raíz, `documentacion/`); las pruebas heredadas se resumen en una fila.

**Clasificación verificada (`bc6bab6` contra `origin/main`).**

| Estado | Rutas |
|---|---|
| Reutilizado (sin diferencia) | `src/coordinator/router.py`, `src/coordinator/__init__.py`, `src/workers/recovery.py`, `scripts/reaper.py`, `scripts/build_dataset.py`, `scripts/seed_minio.py`, `dashboard/app.py`, `dashboard/views/casos.py`, `dashboard/views/conexion.py`, `dashboard/views/resumen.py`, `dashboard/views/tareas.py`, `dashboard/views/workers.py`, `benchmarks/benchmark_transcode.py`, `server.py`, `worker.py`, `seed_tasks.py`, `build_manual_pdf.py`, `requirements-dashboard.txt`, `documentacion/` |
| Modificado: coordinador | `src/coordinator/main.py` pasó de 802 a 104 líneas: `refactor: dividir el coordinador en modulos por responsabilidad` (`5a11a66`, PR #16) lo repartió en `rutas_casos.py`, `rutas_subtareas.py`, `rutas_monitoreo.py` y `apoyo.py`; después se tocó con F-26 (`f792c68`, `seguridad.py`), F-13 (`13afce3`, `rutas_reporte.py`), F-14 (`b0b8803`, `rutas_alertas.py`), F-22 (`94a26b0`, `rutas_archivos.py`), F-23 (`679ee79`), F-24 (`9d2249d`) y F-01 (`a0ac95a`) |
| Modificado: workers | `src/workers/worker_node.py` (F-12 `8c85862`, F-15 `b12cb67`, F-17 `d0c909a`, F-18 `a6484aa`, F-36 `d80b225`), `multimedia_processor.py` (F-18, F-36), `heartbeat.py` (F-15, F-38 `9517e4d`), `config.py` (F-17, F-26 `b366e3e`, F-27 `5be25e1`, F-38), `reporter.py` (F-26, F-27), `storage.py` (F-27) |
| Modificado: scripts, dashboard, despliegue | `scripts/{submit_case,run_load}.py` (F-26 `c5dbcc8`, F-27), `scripts/{check_connectivity,demo_feeder,fetch_results,generate_dataset}.py` (F-27 `98aa38f`), `dashboard/ui.py` (F-26), `dashboard/views/monitor.py` (F-15), `Dockerfile.worker` (F-30 `82f685d`, F-38 `3d925e9`), `docker-compose.yml` (F-26, F-27, F-38), `deploy/docker-compose.worker.yml` (F-16 `7fef365`, F-27, F-30, F-38 `df22ac9`), `deploy/docker-compose.{local,demo,worker-gpu}.yml`, `.env.example`, `.env.demo`, `.gitignore`, `README.md`, `pytest.ini`, `requirements.txt`, `requirements-dev.txt` |
| Modificado: pruebas heredadas | De los 18 archivos `tests/test_*.py` heredados, 8 cambiaron (`test_config`, `test_contract`, `test_coordinator`, `test_dashboard`, `test_heartbeat`, `test_reporter`, `test_scripts`, `test_worker_node`); los demás se conservan |
| Nuevo | `src/domain/`, `src/application/`, `src/adapters/`, `src/infrastructure/` (las cuatro capas de `docs/ARQUITECTURA.md` §4; no existían), `src/coordinator/{rutas_*,seguridad,conexion,apoyo,modelos}.py` salvo lo heredado, `src/workers/cancelacion.py`, `config/*.toml`, `scenarios/`, `scripts/measure/`, `deploy/tls/`, `scripts/{preflight,emitir_token,generar_credenciales,verify_custody,conformidad,dataset_sintetico,dataset_verdad,subir_por_chunks,comparar_transcripcion,aciertos_*,verificar_workers,start_worker}.py`, `tests/unit/`, `tests/integration/`, `tests/acceptance/`, `tests/dobles.py`, `tests/contratos.py` |

**Fila por fila de `docs/ARQUITECTURA.md` §1 y deficiencias.** El documento reproduce el «Elemento» de §1 tal cual (la prueba lo exige) y añade el enlace.

| Deficiencia (fuente) | Corrección enlazada | Estado propuesto |
|---|---|---|
| Ventana de pérdida entre `BLPOP` y `WATCH/MULTI` (§1; Limitaciones conocidas) | AD-03, F-06, PR #131; `src/adapters/redis_type_queue.py`; `tests/unit/test_redis_type_queue.py`, `tests/integration/test_redis_type_queue_reaper.py` | `parcial`: solo el camino nuevo de F-05/F-01 usa `BLMOVE`; `src/workers/worker_node.py` (`poll_once`, `blpop`) y `scripts/reaper.py` siguen con la ventana, declarado en AD-03 y pendiente para F-34 |
| Prioridad estricta `:high` con inanición (§1; Limitaciones conocidas) | AD-04, F-20, PR #126; `src/domain/scheduling.py`, `src/domain/priority.py`, `src/adapters/redis_scheduler.py`; `tests/unit/test_scheduling.py`; comparación F-21, PR #129, `docs/evidencia/F-21_comparacion_politicas_2026-11-11.csv` | `parcial`: `RedisScheduler` no tiene consumidor en `src/` fuera de su módulo y `Settings.queue_keys` aún pone las colas `:high` primero (verificado con `git grep`) |
| Cancelación que no detiene FFmpeg (§1; Limitaciones conocidas) | AD-08, AD-09, AD-31, F-12, F-36 (PR #95); `src/workers/cancelacion.py`, `src/adapters/posix_process_runner.py`, `src/application/process_supervisor.py`; `tests/unit/test_cancelacion_en_curso.py`, `tests/test_worker_cancelacion.py`; `docs/evidencia/F-12_cancelacion_2026-11-10.md`, `docs/evidencia/F-36_cancelacion_en_curso.md` | `corregida` |
| Sin límites de memoria (§1) | AD-05, AD-06, AD-29, AD-30; F-16 `deploy/docker-compose.worker.yml`, `scripts/preflight.py`; F-17 `src/domain/admission.py`; F-18 `src/domain/oom_policy.py`; `tests/unit/test_admission.py`, `tests/unit/test_f16_compose_memory.py`, `tests/unit/test_oom_policy.py`; `docs/evidencia/mediciones-f18` | `corregida` en código; la ficha M1 con datos medidos va en F-41 |
| Sin TLS ni autenticación (§1) | AD-14/AD-33 y F-26 (`src/coordinator/seguridad.py`, `src/adapters/jwt_tokens.py`, `src/domain/rbac.py`); AD-15/AD-37 y F-27 (`src/infrastructure/tls.py`, `deploy/tls/`); `tests/unit/test_seguridad_rutas.py`, `tests/unit/test_tls.py`; `docs/evidencia/F-27_servidores_tls_local_2026-11-11.md` | `parcial`: probado en una máquina; la captura en tres nodos reales depende de F-38 |
| MinIO con credencial por defecto (§1) | F-26 emite `JWT_SECRET`, `WORKER_TOKEN` y `API_TOKEN` (`scripts/generar_credenciales.py`) pero no la de MinIO: `docker-compose.yml:48-49` y `.env.example:23-24` conservan `minioadmin` como valor por defecto (verificado con `git grep minioadmin`) | `pendiente`: sin corrección enlazable; propuesta en la pregunta 1 |
| Workers solo FFmpeg, sin modelos ni texto (§1) | F-07, F-08, F-09 y AD-26, AD-27, AD-28 (`src/adapters/text_analyzer.py`, `image_analyzer.py`, `audio_analyzer.py`); F-32/AD-32 (`src/domain/routing.py`) | `no aplica` como corrección: es capacidad nueva que exige [B.1]; se clasifica `nuevo`; el cableado al worker de producción no se verificó (pregunta 3) |
| Evidencia en una sola máquina; prueba de carga en una máquina sin GPU (§1; Limitaciones conocidas) | F-38, AD-23, AD-24; `docs/evidencia/F-38_tres_nodos_simulacion_local_2026-11-11.md`, que declara «simulación local, no acredita B.2» | `pendiente`: faltan tres nodos reales |
| Redis, MinIO, coordinador y reaper en una sola máquina, sin alta disponibilidad (Limitaciones conocidas) | AD-02 (Nodo A único, aceptado), AD-21 | `no aplica`: decisión declarada, no se corrige (pregunta 5) |
| Logs de las pruebas de caos no están en `docs/evidencia/` (§1: «declarado, sin logs»; DECISIONES_DISENO §8) | F-34 y F-35 (US-34, US-35), ambas `pendiente` en `docs/STATUS.md` | `pendiente` |
| Sin soporte de NPU (Limitaciones conocidas) | DECISIONES_DISENO §3 la descarta por hardware; ninguna feature la añade | `no aplica` |

**Terceros.** Sección «Terceros por feature» con la tabla actual y el mismo encabezado (`Feature | Componente | Fuente | Licencia | Cambio`). Se añade una fila inicial `F-39 | Código del I Proyecto | repositorio `nahum0804/distributed-processing-platform`, commit `bc6bab6` | por confirmar (pregunta 10) | ver sección 2`, para cumplir RNF-24 con el origen de lo reutilizado. **Reutiliza:** todo el código del I Proyecto de la sección 2; no escribe código nuevo.

**Hechos de autoría para no atribuir mal.** El I Proyecto lo escribió el equipo; Nahúm es autor de `src/coordinator/main.py` y `router.py` originales. En este proyecto es autor de F-01, F-06, F-20 y F-21 (adaptador `redis_type_queue.py`, `scheduling.py`, `redis_scheduler.py`, ficha M2). Según `git log --format=%an`, la mayoría de las modificaciones de archivos heredados las hicieron otros (K: F-26, F-27, F-30, F-38, F-13, F-14; J: F-12, F-17, F-18, F-23, F-36; V: F-15, F-22, F-24): el documento da los hechos sin columna de responsable.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_reutilizacion_doc.py`: (a) toda ruta entre comillas invertidas con prefijo `src/`, `scripts/`, `tests/`, `docs/`, `deploy/`, `dashboard/`, `config/`, `scenarios/` o `benchmarks/` existe en el árbol (se ignoran patrones con `*`, `<` o `{`); (b) cada fila de la sección 2 tiene estado en {`reutilizado`, `modificado`, `nuevo`} y ruta; (c) cada fila de la sección 4 tiene estado en {`corregida`, `parcial`, `pendiente`, `no aplica`} y al menos un enlace (`AD-\d+`, `F-\d+`, `#\d+`, ruta de prueba o de evidencia), y toda AD o F citada existe en `docs/ARQUITECTURA.md` §8 o en `docs/specs/`; (d) las filas F-12, F-36 y F-06 de «Terceros por feature» siguen y la tabla tiene sus cinco columnas; (e) una fila `corregida` cita al menos una ruta de código o de evidencia que existe | El documento es consistente y nadie puede romperlo con una ruta vieja ni con una corrección sin enlace; protege las filas que otras features añaden |
| Integración | Mismo archivo, `test_cubre_cada_archivo_del_i_proyecto`: si `git cat-file -e bc6bab6` funciona, cada archivo de `git ls-tree -r bc6bab6` bajo `src/`, `scripts/`, `dashboard/`, `deploy/`, `benchmarks/` y la raíz aparece en el documento por su ruta exacta o por su directorio; se omite (`skip`) si el commit no está disponible, por ejemplo en un clon superficial | Ningún componente heredado queda sin clasificar (RNF-02) |
| Aceptación | `test_cada_elemento_de_arquitectura_1_aparece`: cada «Elemento» de la tabla de `docs/ARQUITECTURA.md` §1 y cada viñeta de «Limitaciones conocidas» de `docs/DECISIONES_DISENO.md` aparece en el documento (texto exacto del elemento en la columna de origen); más la revisión manual del PR contra `ARQUITECTURA.md` §1, como pide el backlog | Ninguna deficiencia señalada queda sin corrección enlazada (RNF-03) |

## Mediciones

No aplica.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-39): documento de reutilizacion y correcciones` | `docs/reutilizacion.md` reescrito y `tests/unit/test_reutilizacion_doc.py`. 0 líneas de `src/`, muy por debajo de las 400 |

## Riesgos y preguntas abiertas

1. **Corrección de la credencial MinIO.** `minioadmin` sigue como valor por defecto (`docker-compose.yml:48-49`, `.env.example:23-24`) y §1 la declara como deficiencia. Propuesta: no cambiar código en F-39; marcarla `pendiente` en el documento y abrir un `fix/` aparte del responsable de M4 (K) que haga `MINIO_ACCESS_KEY` y `MINIO_SECRET_KEY` obligatorios con `${VAR:?...}` y los genere `scripts/generar_credenciales.py`. Decide la persona si entra antes de la entrega.
2. **«Parcial» frente a «corregida».** Dos correcciones (`BLMOVE` y aging) existen como adaptador con pruebas, pero el camino heredado del worker no las usa. Propuesta: declararlas `parcial` con el enlace y no inflar el estado, porque [Parte I §5] prohíbe presentar como logrado lo que no lo está. Si la persona prefiere cablearlas, es otra feature (F-34 y una nueva), no F-39.
3. **Cableado de analizadores y routing al worker.** `git grep` no halló que `worker_node.py` use `TextAnalyzer`, `ImageAnalyzer` ni `AudioAnalyzer`. No se afirma en el documento cómo se integran hasta que lo confirme José, dueño de F-07 a F-09. Propuesta: la fila dirá «adaptador y aplicación existen; cableado en producción: pendiente de confirmar por J».
4. **Alcance de RNF-24.** El requisito pide citar fuente de todo código o configuración copiado, y el documento solo lista los terceros que cada feature declaró. No se revisó `requirements*.txt` (p. ej. Ultralytics con AGPL-3.0, que AD-19 ya advierte). Propuesta: F-39 solo preserva las filas y añade la del I Proyecto; una revisión de licencias de dependencias es una feature aparte, a decisión de la persona.
5. **Deficiencias señaladas por el evaluador.** No se halló la retroalimentación de la evaluación del I Proyecto (SUP-19); la lista sale de `docs/DECISIONES_DISENO.md` y de §1. Si la persona tiene la rúbrica o los comentarios del profesor, hay que añadir esas filas. Propuesta: aceptar SUP-19 y marcar `no aplica` la alta disponibilidad (AD-02) y la NPU por ser decisiones declaradas.
6. **Verificabilidad de la base.** La clasificación depende de que `bc6bab6` siga en el historial; no se debe reescribir (`rebase`, squash del historial). Propuesta: el documento incluye el comando y, además, la ruta y el estado en texto plano, para no depender solo de git; la prueba de integración se omite si el commit no está.
7. **Estados de las features citadas.** `docs/STATUS.md` marca F-20 como `en-pr` aunque la PR #126 está fusionada, y F-11 y F-02 no han terminado. El documento cita la PR fusionada como evidencia y no cita F-11 ni F-02. Propuesta: no corregir STATUS aquí (se genera); revisarlo al cerrar F-20.
8. **Formato.** La fila inicial de terceros usa `F-39` como «Feature»; si el equipo prefiere que esa tabla solo tenga filas por cada feature con terceros, se mueve el origen del I Proyecto a la sección 1. Propuesta: dejarla en la tabla.
9. **Verificación de las clasificaciones.** Las referencias a commits (`5a11a66`, `f792c68`, etc.) se tomaron de `git log bc6bab6..origin/main`; no se contó con subagente independiente para repetirlas. Propuesta: la fase de verificación las repite con el comando del documento.
10. **Licencia del código del I Proyecto.** El repositorio actual tiene `LICENSE` MIT (`tests/unit/test_licencia_mit.py`), pero no se verificó la licencia con que se publicó el I Proyecto. Propuesta: la fila lo declara «por confirmar» y la persona indica la licencia real o confirma que es el mismo equipo y repositorio.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | claude | 2026-11-12 | SPEC sin campos pendientes (grep 0); bc6bab6 existe; minioadmin confirmado en docker-compose.yml:48-49 y .env.example:23-24; plan de 1 parte, 0 lineas de src (ce6e2d7) |
| plan | Kenni Rodriguez | 2026-11-12 |  |
| verificación IA de tests | claude | 2026-11-12 | Solo tests/unit/test_reutilizacion_doc.py (842ab69); pytest: 20 failed 2 passed, fallas por documento sin reescribir, sin errores de import (842ab69) |
| tests | Kenni Rodriguez | 2026-11-12 | aprobación delegada |
| verificación IA de implementacion | claude | 2026-11-12 | pytest test_reutilizacion_doc 22 passed tras merge de origin/main; subagente reporta tests/unit 3371 passed sin fallos; minioadmin confirmado en docker-compose.yml:48-49,80-81; solo cambia docs/reutilizacion.md (87c887a) |
