# SPEC F-13: Reporte consolidado

**Fase:** verificacion
**Base:** feat/F-13-1-reporte-consolidado
**Verificación IA:** implementacion 1ad0b7f
**Historia:** US-13 · **Requisitos:** RF-13, RF-14 (B.4 Reporte consolidado, SUP-09, SUP-18) · **Responsable:** K

## Objetivo

Que el analista consulte, para un caso, un reporte JSON con hallazgos, categorías detectadas, línea temporal e incidencias, donde cada fragmento de evidencia (mensaje, imagen o segmento de audio) resuelve a su objeto de origen y a su posición o timestamp [B.4 Reporte consolidado; RF-13, RF-14]. Hoy `GET /cases/{id}/report` (I Proyecto) solo resume operación y tiempos por sub-tarea; no usa `Finding`. El reporte nuevo se calcula al consultarlo a partir de los hallazgos que ya producen F-07 a F-09, sin tocar a los analizadores.

## Alcance

**Incluye:**
- Dominio puro: lectura de las posiciones de `EvidenceRef.position` que ya emiten los analizadores (`mensajes 3,7`, `mensajes 0-49`, `segmento 2 t=1.00-4.50s`, `segmentos 1,4 t=...`, `caja x1,y1,x2,y2`), con la marca de tiempo UTC que traen `Finding.detail` de texto (`indice ISO-8601 source_ref`) y el tramo en segundos del audio; modelo del reporte; categorías agregadas, línea temporal ordenada e incidencias.
- Caso de uso `build_report(case_id, findings, catalogo, almacen, reloj)` en `src/application/build_report.py`, que implementa el contrato `FindingStore` (lectura) y añade el puerto `CaseCatalog` (lectura del caso y de sus fuentes).
- Adaptadores Redis de `FindingStore` (escritura y lectura; lo prometido en `docs/CONTRATOS.md` a Kenni) y de `CaseCatalog` (solo lectura de los hashes del coordinador).
- Ruta `GET /cases/{case_id}/consolidated-report` en un archivo nuevo, con una línea `include_router` en `main.py`.
- Serialización a JSON separada del dominio (refactor de IMPLEMENTACION §4).
- JSON de ejemplo sintético en `docs/evidencia/` como evidencia de la prueba A.

**No incluye:**
- Cablear a los workers para que escriban hallazgos en el `FindingStore` (código de José, `src/workers/`); queda como contacto declarado, ver preguntas.
- Cablear `source_sha256` en el hash de cada sub-tarea (código de Nahúm); el adaptador lo lee si existe.
- El contenido textual de cada mensaje y recortes de imagen o audio: el fragmento es una referencia (objeto, posición, marca); para el audio se incluye el texto transcrito porque ya viaja en `detail`.
- Alertas (F-14), dashboard (F-15), estados y cierre del caso (F-10), cifrado (F-28), cadena de custodia (F-29).
- Cambiar `GET /cases/{id}/report` ni los dos archivos de Nahúm que lo definen.
- Datos reales: todo caso de prueba y el ejemplo son sintéticos.

## Criterios de aceptación

Copiados de `docs/backlog/estados-reporte-dashboard.md` (US-13):

- **Dado** un caso finalizado
- **Cuando** se consulta el reporte
- **Entonces** contiene hallazgos, categorías, línea temporal e incidencias, y cada fragmento resuelve a su fuente y timestamp

Pruebas: U secciones y resolución de enlaces. I caso completo. A reporte de un caso heterogéneo. Evidencia: JSON de ejemplo en el informe.

Interpretación (SUP-34): «resuelve a su fuente» es que el fragmento nombra el objeto (`sha256`, `file_path`, tipo) que existe en el almacén; «timestamp» es la hora UTC del mensaje (texto) o el tramo en segundos dentro del archivo (audio). Una imagen no tiene marca temporal propia: lleva la caja y `timestamp_utc: null`.

## Diseño

**Contratos** (`docs/CONTRATOS.md`). Usa sin cambiar `Finding`, `EvidenceRef`, `Severity`, `ObjectStore.exists` y `Clock`. Implementa `FindingStore` (Kenni, F-13). Agrega un puerto nuevo, `CaseCatalog` (Kenni), sin modificar ninguno existente; la fila nueva de la tabla de contratos avisa a Nahúm y José, que no cambian código. `tests/dobles.py` gana `FakeCaseCatalog` y `tests/contratos.py` gana `comprobar_case_catalog`, que pasan el doble y el adaptador.

**Dominio** (puro, sin E/S):
- `src/domain/evidence_position.py`: `parse_position(finding) -> tuple[Locator, ...]`. `Locator` es `MessageLocator(index, timestamp_utc | None, source_ref | None)`, `SegmentLocator(index, start_s, end_s)` o `BoxLocator(x1, y1, x2, y2)`. Un rango de lote (`mensajes 0-49`) es posición de resumen, no de evidencia, y devuelve `()`. Una posición que no se entiende devuelve `UnknownLocator(raw)` en vez de lanzar, para que una categoría futura no rompa el reporte; el reporte la lista como incidencia.
- `src/domain/consolidated_report.py`: `CaseSource(sha256, file_path, kind, status, error_type)`, `CaseInfo(case_id, status, created_at, finished_at, sources)`, `Fragment`, `ReportedFinding`, `Incident`, `ConsolidatedReport`; funciones `category_summary` (cantidad y severidad máxima por categoría), `build_timeline` y `find_incidents`.
- Línea temporal: eventos con `timestamp_utc` ordenados por marca y, a igualdad, por `(sha256, posición)`, de modo que el orden sea determinista. Los eventos sin hora absoluta (audio, imagen) van aparte en `sin_marca_absoluta`, ordenados por `(file_path, inicio_s)`; no se inventa una hora (RF-14 y regla de evidencia).
- Incidencias (SUP-34): hallazgo de severidad `ALTA`; sub-tarea con estado `failed` (con su `error_type`); evidencia cuyo objeto no está en el catálogo o no existe en el almacén; posición no reconocida.

**Aplicación**: `src/application/build_report.py` orquesta `FindingStore.list`, `CaseCatalog.case` y `ObjectStore.exists`; sin conocer Redis ni FastAPI. Caso inexistente lanza `CaseNotFound`. `src/application/report_json.py` convierte el reporte a `dict` con claves en español en este orden: `case_id`, `status`, `finalizado`, `generado_en`, `hallazgos`, `categorias`, `linea_temporal`, `sin_marca_absoluta`, `incidencias`. Cada hallazgo lleva `evidencia`: lista de fragmentos `{fuente: {sha256, file_path, tipo}, localizador, timestamp_utc, tramo_s, extracto}`. El puerto `CaseCatalog.case(case_id) -> CaseInfo | None` se declara en `src/application/ports.py` (archivo compartido: solo se agrega el puerto).

**Adaptadores** (`src/adapters/`, archivos de Kenni):
- `redis_finding_store.py`: lista `case:{id}:findings` con un JSON por hallazgo (`category`, `severity`, `confidence`, `sha256`, `position`, `detail`); `add` usa un `RPUSH` por lote en un `pipeline`; `list` conserva el orden de inserción. Lo escriben los workers y lo lee el reporte (escritor múltiple, lectura al consultar). Sin transacciones nuevas.
- `redis_case_catalog.py`: lee `case:{id}` y los hashes `subtask:{id}` listados en `case:{id}:subtasks` (mismos nombres que usan `apoyo.fetch_subtasks`, sin importarlos de `src/coordinator`). Une cada hallazgo con su sub-tarea por `source_sha256` y, si falta, por `file_path` igual al `sha256` (clave de objeto direccionada por contenido, F-23). Hoy el hash de la sub-tarea no trae `source_sha256` (ver preguntas); si no hay coincidencia el fragmento queda sin fuente y sale como incidencia.

**Coordinador**: `src/coordinator/rutas_reporte.py` (nuevo) con `GET /cases/{case_id}/consolidated-report` (`404` caso inexistente); construye el caso de uso desde `conexion.redis_client` y el almacén vigente; añade `app.include_router(rutas_reporte.router)` en `main.py`. Un caso que aún no terminó se devuelve con `finalizado: false` (no es error). Cuando F-26 fusione su matriz, la ruta se registra como lectura del analista y del supervisor (F-26 es de Kenni, mismo responsable).

**Decisiones.** AD-38 (propuesta): el reporte se calcula bajo demanda desde `FindingStore` y `CaseCatalog`, no se materializa al cerrar el caso. Alternativas: materializarlo al cerrar (exige un gancho en el barrier de Nahúm y queda desactualizado si un hallazgo llega tarde); guardarlo en el almacén de objetos (copia mutable de la evidencia, fuera de F-29). Criterio: la evidencia sigue siendo la referencia al objeto original y el reporte es una vista reproducible; costo: se recalcula en cada consulta (se mide solo si el reporte lo exige; no hay medición de SO). Se registra en `docs/ARQUITECTURA.md` §8 en la fase de documentación. SUP-34 (propuesta): significado de «incidencia», «resuelve a fuente y timestamp» y «sin marca absoluta», arriba. Capas: dominio y aplicación sin `redis`, `fastapi` ni adaptadores; `tests/unit/test_arquitectura.py` en verde. No reutiliza código del I Proyecto salvo los nombres de claves Redis y la lista de estados terminales (`TERMINAL_CASE_STATUSES`, `src/coordinator/apoyo.py`), que se repite como constante del dominio con comentario de origen para no crear una dependencia hacia el coordinador.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_parse_position_mensajes_con_marca_utc`, `test_parse_position_segmento_con_tramo`, `test_parse_position_caja_de_imagen`, `test_parse_position_rango_de_lote_no_es_evidencia`, `test_parse_position_desconocida_no_lanza` | Cada formato real de posición se lee y uno nuevo no rompe el reporte |
| Unitaria | `test_reporte_tiene_cuatro_secciones` | Hallazgos, categorías, línea temporal e incidencias siempre presentes, aun vacías |
| Unitaria | `test_evidencia_resuelve_a_fuente` | Cada fragmento lleva sha256, `file_path`, tipo y posición o marca; sin fuente sale como incidencia |
| Unitaria | `test_linea_temporal_ordenada`, `test_eventos_sin_hora_absoluta_van_aparte_y_ordenados` | Orden determinista, sin inventar horas |
| Unitaria | `test_categorias_cuentan_y_toman_severidad_maxima`, `test_incidencias_incluyen_alta_fallo_y_evidencia_sin_objeto` | Agregación e incidencias (SUP-34) |
| Unitaria | `test_caso_inexistente_lanza_case_not_found`, `test_caso_no_finalizado_marca_finalizado_falso`, `test_reporte_serializa_a_json_con_claves_acordadas` | Casos borde y serialización |
| Contrato | `comprobar_finding_store` y `comprobar_case_catalog` sobre `FakeFindingStore`, `FakeCaseCatalog` y los adaptadores | Doble y real cumplen lo mismo |
| Integración | `test_caso_completo_texto_imagen_audio` (hallazgos de `analyze_conversation`, `analyze_audio` y `sensitive_findings` con dobles, sin Redis) | El reporte se arma con las posiciones reales de los analizadores |
| Integración | `test_redis_finding_store_conserva_orden`, `test_redis_case_catalog_lee_caso_y_subtareas` (marca `integration`, Redis real de Compose) | Los adaptadores leen y escriben las claves reales |
| Aceptación | `test_reporte_de_caso_heterogeneo_sintetico` (marca `acceptance`; `TestClient` con dobles inyectados) | Un caso sintético con texto, imagen y audio devuelve las cuatro secciones y fragmentos resueltos; escribe el JSON de ejemplo |

## Mediciones

No aplica. F-13 no es un módulo M1 a M5; no se registran cifras de SO ni se inventan.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimación de `src/` por parte entre paréntesis.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-13): modelo de reporte y lectura de posiciones de evidencia` | `src/domain/evidence_position.py`, `src/domain/consolidated_report.py`; pruebas unitarias de dominio (~180 líneas) |
| 2 | `feat(F-13): caso de uso build_report y puerto CaseCatalog` | `src/application/build_report.py`, `report_json.py`, puerto en `ports.py`, doble y prueba de contrato; prueba de integración sin Redis (~140 líneas); fila nueva en `docs/CONTRATOS.md` |
| 3 | `feat(F-13): adaptadores Redis y ruta del reporte consolidado` | `redis_finding_store.py`, `redis_case_catalog.py`, `rutas_reporte.py`, línea en `main.py`; pruebas de integración y aceptación; JSON de ejemplo, ficha en `docs/`, AD-38 y SUP-34 en los documentos, bitácora (~170 líneas) |

Las partes 2 y 3 se apilan sobre la anterior porque usan sus tipos; la parte 1 sale de `main`.

## Riesgos y preguntas abiertas

Cada una con decisión provisional del arquitecto; se aplica salvo que la persona indique otra cosa.

1. **Los workers no escriben hallazgos en un `FindingStore`.** Hoy F-07 a F-09 devuelven `Finding` pero el worker (código de José) no los persiste ni los envía. Sin esa escritura, el reporte real sale vacío en hallazgos. Provisional: F-13 entrega el adaptador y la prueba de contrato; el cableado en `src/workers/` queda a José y se declara como pendiente en el PR y la bitácora. No se inventan hallazgos.
2. **El hash de la sub-tarea no trae `source_sha256`.** Sin él, no se puede unir un `Finding` con su archivo. Provisional: el adaptador lo lee si Nahúm lo agrega y, si no, compara `file_path` con el sha256; sin coincidencia, incidencia «evidencia sin fuente». Pedir a Nahúm el campo.
3. **Texto sin hora para mensajes marcados solo por rango.** La marca UTC solo viaja en `detail` de `amenaza` y `ofensivo`; `palabras_clave`, `tema` y `sentimiento` solo traen el rango. Provisional: esos hallazgos son categorías, no fragmentos de evidencia. Alternativa: que el reporte lea la conversación original con `ConversationParser` (F-02, aún sin adaptador) para dar hora a todo rango. No se hace ahora.
4. **Imágenes sin marca temporal.** Provisional: `timestamp_utc: null` y la caja como posición; no se usa la hora de procesamiento como si fuera del hecho. Alternativa: usar `finished_at` de la sub-tarea con una etiqueta explícita.
5. **Contenido del mensaje.** Provisional: el fragmento es referencia, sin el texto del mensaje (privacidad y mínimo alcance); solo la transcripción trae su texto. Alternativa: incluir un extracto leyendo el objeto por `ObjectStore.open`.
6. **Caso no finalizado.** Provisional: `200` con `finalizado: false`. Alternativa: `409`.
7. **Ruta nueva `/cases/{id}/consolidated-report`** para no pisar `/report` del I Proyecto. ¿Se prefiere ampliar `/report` (archivo de Nahúm)? Provisional: ruta nueva; el dashboard (Melany) la usa si quiere el reporte con evidencias.
8. **Definición de «incidencia» (SUP-34).** El enunciado no la define. Provisional: hallazgo `ALTA`, sub-tarea fallida, evidencia sin fuente, posición no reconocida. Confirmar con F-14, que reutiliza la severidad.
9. **Formato de posición como cadena.** El lector acopla el reporte al texto que emiten `analyze_text`, `analyze_audio` e `analyze_image` (archivos de José). Un cambio de formato rompería la lectura; la prueba del caso completo usa los analizadores reales para detectarlo. Alternativa: que `EvidenceRef` sea estructurada (cambio de contrato, no ahora).
10. **Sin medición:** el costo de recalcular el reporte por consulta no está medido; no se afirma rendimiento. Si un caso grande lo exige, se mide en una parte aparte.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | orquestador | 2026-11-11 | SPEC F-13 completo (grep … = 0), diff contra main solo el SPEC, Base main; AD-38 y SUP-34 libres segun arquitecto; pila de 3 partes; 10 preguntas abiertas con decision provisional: aceptar (811c1a5) |
| plan | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | orquestador | 2026-11-11 | Diff solo tests (2 archivos nuevos), src intacto; ambos modulos fallan en coleccion con ModuleNotFoundError src.domain.evidence_position (rojo); API asumida fijada por las pruebas (f18bbd6) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | pytest + revision | 2026-11-11 | Dominio implementado (281 lineas src, sin ediciones a pruebas); suite completa verde (83ab577) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: 5 hallazgos medios (ValueError/OverflowError en marcas, TypeError con timestamp sin zona, empates no deterministas, marca sobrescrita) y 6 bajos |
| verificación IA de implementacion | orquestador | 2026-11-11 | 14 hallazgos QA corregidos en db69f86; suite verde; solo se quitaron decoradores xfail (db69f86) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de verificacion | orquestador | 2026-11-11 | QA 14 defectos reproducidos como xfail, corregidos y en verde; sin segundo QA (3b22114) |
| verificacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de documentacion | orquestador | 2026-11-11 | AD-38 y SUP-34 añadidos (provisionales), limites en AD-38, bitacora en estado; sin cambios de codigo (b1adfc1) |
| documentacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de revision | revisor + orquestador | 2026-11-11 | Revisor APROBADO parte 1: dominio 329 lineas src, capas puras, SPEC cumplido, AD-38 y SUP-34 presentes; menores no bloqueantes (f-strings largas, tipos de retorno) (131a892) |
| revision | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | orquestador | 2026-11-11 | Diff solo tests y dobles (51cfecb); src intacto; test_build_report.py falla en coleccion con ModuleNotFoundError src.application.build_report (rojo); API asumida declarada (51cfecb) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | pytest + revision | 2026-11-11 | Aplicacion implementada (7a18d66, ~135 lineas src, sin ediciones a pruebas); suite verde (7a18d66) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: exists que lanza tumba el reporte, extracto de audio erroneo, sin tope, sin UTC, sha vacio enlaza, surrogate, N+1 exists |
| verificación IA de implementacion | orquestador | 2026-11-11 | 7 hallazgos QA corregidos en 1ad0b7f; suite verde; solo se quitaron decoradores xfail; limite: almacen caido sale como objeto_inexistente (1ad0b7f) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
