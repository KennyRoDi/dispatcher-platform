# SPEC F-14: Alertas

**Fase:** implementacion
**Base:** feat/F-14-2-alertas
**Verificación IA:** implementacion 7bea224
**Historia:** US-14 · **Requisitos:** RF-15, RF-16 (B.4 Alertas, SUP-35) · **Responsable:** K

## Objetivo

Que el supervisor reciba, sin consultar el reporte, una alerta cuando un caso finaliza y otra por cada incidencia de severidad alta que se detecta, y que un fallo del consumidor o del canal de alertas no detenga el pipeline [B.4 Alertas; RF-15, RF-16]. Hoy no existe nada de esto: `AlertPublisher` está declarado en `src/application/ports.py` y tiene su doble `FakeAlertPublisher`, pero nadie lo implementa ni lo invoca, y el coordinador cierra el caso en `rutas_subtareas.report_subtask` sin avisar a nadie.

## Alcance

**Incluye:**
- Dominio puro (`src/domain/alert_policy.py`): `Alert`, las dos clases de alerta (`incidencia_alta`, `caso_finalizado`), la regla que decide qué hallazgos son incidencia (`Finding.severity == Severity.ALTA`, sin recalcular reglas) y la construcción del `detail` de cada alerta, sin texto de mensajes.
- Aplicación (`src/application/alerting.py`): `SafeAlertPublisher`, que envuelve a cualquier `AlertPublisher` y absorbe y registra sus errores; `AlertingFindingStore`, decorador de cualquier `FindingStore` que publica una alerta por cada hallazgo alto que se agrega, sin alterar lo guardado; `notify_case_closed(publisher, case_id, status)`.
- Puerto nuevo `AlertReader` (lectura de las alertas recientes) con su doble y su prueba de contrato, para el consumidor.
- Adaptadores Redis (`src/adapters/redis_alert_stream.py`): publicador con `XADD` a un Stream acotado y lector con `XREVRANGE`; la marca de tiempo de emisión sale de `Clock`.
- Ruta `GET /alerts` en un archivo nuevo del coordinador (`src/coordinator/rutas_alertas.py`), con una línea `include_router` en `main.py`: es lo que consume el dashboard.
- Cableado mínimo del cierre: una llamada protegida tras el `hset` que marca el caso terminal en `rutas_subtareas.report_subtask` (archivo de Nahúm; se avisa, ver preguntas).
- Prueba A y evidencia: marcas de tiempo de alerta y de cierre de un caso sintético.

**No incluye:**
- Cablear a los workers para que usen `AlertingFindingStore` sobre el `FindingStore` Redis (código de José en `src/workers/`; el adaptador Redis de `FindingStore` es de F-13). Queda como contacto declarado: sin ese cableado no hay alertas de incidencia en operación real.
- La vista de alertas en el dashboard Streamlit (`dashboard/`, de Melany, F-15). F-14 entrega el endpoint que la alimenta; no se afirma «visible en el dashboard» hasta que ella lo cablee.
- Notificación externa (correo, webhook, Telegram) y reintentos o cola de salida de alertas: el enunciado pide notificación asíncrona, no entrega garantizada.
- Cambiar severidades, reglas (`src/domain/severity.py`, de José) o el formato de `Finding`.
- Autenticación de la ruta (F-26) y cifrado, TLS o MinIO (F-28, F-27, F-23): `/alerts` solo se clasifica en la matriz cuando F-26 se fusione.
- Datos reales: todo caso de prueba y el ejemplo son sintéticos.

## Criterios de aceptación

Copiados de `docs/backlog/estados-reporte-dashboard.md` (US-14):

- **Dado** un caso con una incidencia alta
- **Cuando** se detecta y cuando el caso finaliza
- **Entonces** se publica una alerta por cada evento; si el consumidor falla, el pipeline continúa

Pruebas: U publicación y aislamiento de fallo. I Stream con consumidor. A alerta visible en el dashboard. Demuestra: prueba A. Evidencia: marcas de tiempo de alerta y de cierre.

Interpretación (SUP-35): «incidencia alta» es un `Finding` de severidad `ALTA` (la que ya asignan F-07 a F-09); «una alerta por cada evento» es una alerta por hallazgo alto que se agrega al almacén y una por el cierre del caso; «consumidor» es quien lee el Stream (dashboard); «el pipeline continúa» incluye que falle el propio canal (Redis de alertas caído), no solo el lector; «visible en el dashboard» se acredita por el endpoint `GET /alerts` mientras la vista de Melany no exista.

## Diseño

**Contratos** (`docs/CONTRATOS.md`). Implementa `AlertPublisher` (Kenni, F-14; usuarios: coordinador y workers) sin cambiarlo: `publish(kind, case_id, detail) -> None`. Usa sin cambiar `Finding`, `EvidenceRef`, `Severity`, `FindingStore` y `Clock`. Agrega un puerto nuevo, `AlertReader` (Kenni; consumidor: dashboard de Melany), sin modificar ninguno existente: solo se añade a `src/application/ports.py` y una fila a la tabla de contratos. `tests/dobles.py` gana `FakeAlertReader` y `tests/contratos.py` gana `comprobar_alert_publisher` y `comprobar_alert_reader`, que pasan el doble y el adaptador. No usa `ObjectStore`, `WorkQueue` ni MinIO.

**Dominio** (puro, sin E/S): `src/domain/alert_policy.py`.
- `HIGH_INCIDENT = "incidencia_alta"` y `CASE_CLOSED = "caso_finalizado"`.
- `Alert(kind, case_id, detail)` y `StoredAlert(alert_id, kind, case_id, detail, emitted_at)` con la marca UTC.
- `high_incident_alerts(case_id, findings) -> list[Alert]`: un `Alert` por hallazgo con `severity is Severity.ALTA`, en el orden recibido. El `detail` lleva `categoria`, `confianza`, `sha256` y `posicion`; no copia `Finding.detail`, que puede traer texto o marcas de mensajes.
- `case_closed_alert(case_id, status) -> Alert`; rechaza con `ValueError` un estado no terminal (`completed`, `partially_completed`, `failed`) y `cancelled` (SUP-35).
- Reutiliza la severidad ya calculada (`Finding.severity`); no importa `severity.py` ni duplica umbrales: el refactor «reutilizar reglas de severidad» de `docs/IMPLEMENTACION.md` §4 se cumple apoyándose en ese campo.

**Aplicación**: `src/application/alerting.py`.
- `SafeAlertPublisher(inner, log)`: llama a `inner.publish` y absorbe y registra `Exception` (no `BaseException`); nunca relanza. Es lo único que ven el decorador y el cierre, así el aislamiento está en un solo sitio.
- `AlertingFindingStore(inner: FindingStore, publisher)`: `add` primero delega en `inner.add` (si falla, propaga y no alerta: no se alerta por lo que no se guardó) y después publica las alertas de `high_incident_alerts`; `list` delega. Decorador, para que el worker no conozca las alertas.
- `notify_case_closed(publisher, case_id, status)`: publica `case_closed_alert`.
- Sin `redis`, `fastapi` ni adaptadores.

**Adaptadores** (`src/adapters/redis_alert_stream.py`, de Kenni). `RedisAlertStream(client, clock, key="alerts", maxlen=1000)` implementa `AlertPublisher` y `AlertReader`. `publish` hace `XADD` con los campos `kind`, `case_id`, `detail` y `emitted_at` (ISO-8601 UTC desde `Clock`) y `MAXLEN ~` para acotar la memoria; `recent(limit)` hace `XREVRANGE` y devuelve las más recientes primero. El Stream desacopla al productor del consumidor: el pipeline solo espera un `XADD`, nunca a quien lee. Sin transacciones ni grupos de consumidores.

**Coordinador**: `src/coordinator/rutas_alertas.py` (nuevo) con `GET /alerts?limit=` (1 a 200, 50 por defecto; `422` fuera de rango; `503` si Redis no responde, solo para esta ruta), más la función que arma `SafeAlertPublisher(RedisAlertStream(...))` desde `conexion.redis_client`; `main.py` gana un `include_router`. En `rutas_subtareas.report_subtask`, tras marcar el caso terminal, una llamada a `notify_case_closed` dentro de `try/except Exception` que registra y sigue; no cambia la respuesta ni los contadores. Cuando F-26 se fusione, `/alerts` se registra como lectura del supervisor (mismo responsable).

**Decisiones.** AD-39 (propuesta): las alertas se publican en un Redis Stream acotado y se leen sin grupo de consumidores; el aislamiento de fallo vive en un decorador de publicador (`SafeAlertPublisher`) y la incidencia alta se detecta al agregar hallazgos mediante un decorador de `FindingStore`. Alternativas: Pub/Sub de Redis (sin retención: una alerta emitida sin lector se pierde y el dashboard no vería el historial); lista Redis con `LPUSH` y `LTRIM` (sin identificadores ni orden estable por tiempo); llamar al publicador desde cada worker y desde el coordinador (duplica la regla y acopla a José y Nahúm); tarea en segundo plano que sondea casos cerrados (más piezas y retraso). Criterio: la arquitectura ya fija «Alertas → Stream → Redis» (`docs/ARQUITECTURA.md` §5) y el enunciado pide notificación asíncrona; el Stream retiene las últimas alertas para quien se conecte tarde y no bloquea al productor. Costo: entrega «a lo sumo una vez» (si Redis falla, la alerta se pierde y queda en el log) y retención acotada. Medición pendiente: ninguna; no se afirman cifras de rendimiento. SUP-35 (propuesta): interpretación del criterio, arriba. Ambas se registran en `docs/ARQUITECTURA.md` §8 y en los requisitos en la fase de documentación. Capas: dominio y aplicación sin `redis` ni `fastapi`; `tests/unit/test_arquitectura.py` en verde. No reutiliza código del I Proyecto salvo las claves y los estados terminales de caso de `src/coordinator/apoyo.py` y `rutas_subtareas.py`, que el dominio repite como constante con comentario de origen para no depender del coordinador.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_incidencia_alta_publica_alerta` | `AlertingFindingStore.add` con un hallazgo `ALTA` publica una alerta `incidencia_alta` con categoría, confianza, `sha256` y posición |
| Unitaria | `test_hallazgos_baja_y_media_no_publican`, `test_una_alerta_por_hallazgo_alto_en_orden` | Solo la severidad alta alerta y hay una alerta por hallazgo |
| Unitaria | `test_fallo_de_alerta_no_afecta_pipeline` | Si el publicador lanza, `add` guarda los hallazgos, no propaga y registra el error |
| Unitaria | `test_fallo_al_guardar_no_publica_alerta` | Si el almacén interno falla, el error se propaga y no se alerta |
| Unitaria | `test_alerta_no_copia_el_detalle_del_hallazgo` | El `detail` de la alerta no incluye texto de mensajes |
| Unitaria | `test_cierre_publica_una_alerta_con_el_estado`, `test_estado_no_terminal_o_cancelado_se_rechaza`, `test_fallo_de_alerta_en_cierre_no_propaga` | RF-15 y su aislamiento |
| Contrato | `comprobar_alert_publisher` y `comprobar_alert_reader` sobre `FakeAlertPublisher`, `FakeAlertReader` y `RedisAlertStream` con Redis simulado | Doble y adaptador cumplen lo mismo |
| Integración | `test_stream_publica_y_lector_ve_alertas_recientes_primero`, `test_stream_se_acota_por_maxlen`, `test_publicar_sin_consumidor_no_espera` (marca `integration`, Redis real de Compose) | El Stream retiene y acota alertas y publicar no depende de un lector |
| Integración | `test_redis_caido_no_detiene_el_cierre_del_caso` (`TestClient` con publicador que falla) | Un canal de alertas caído no cambia la respuesta de `/subtasks/report` |
| Aceptación | `test_alerta_de_incidencia_y_de_cierre_visible_en_alerts` (marca `acceptance`; `TestClient` con dobles inyectados y `FakeClock`) | Un caso sintético con una incidencia alta produce alerta antes del cierre y otra al cerrar, ambas en `GET /alerts`; escribe las marcas de tiempo de ejemplo |

## Mediciones

No aplica. F-14 no es un módulo M1 a M5; no se registran cifras de SO ni se inventan. La evidencia de la prueba A son las marcas de tiempo de alerta y de cierre de la ejecución sintética, no una medición de rendimiento.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimación de `src/` por parte entre paréntesis.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-14): política de alertas y decoradores de publicación` | `src/domain/alert_policy.py`, `src/application/alerting.py`; pruebas unitarias con `FakeAlertPublisher` y `FakeFindingStore` (~140 líneas) |
| 2 | `feat(F-14): Stream de alertas en Redis y ruta GET /alerts` | puerto `AlertReader` en `ports.py`, `redis_alert_stream.py`, `rutas_alertas.py`, línea en `main.py`, `FakeAlertReader` y pruebas de contrato; integración con Redis; fila nueva en `docs/CONTRATOS.md` (~150 líneas) |
| 3 | `feat(F-14): alerta al cerrar el caso y evidencia de la prueba A` | llamada protegida en `rutas_subtareas.report_subtask`, prueba de integración y de aceptación, marcas de tiempo de ejemplo en `docs/ejemplos/`, AD-39 y SUP-35 en los documentos, bitácora (~25 líneas) |

Las partes 2 y 3 se apilan sobre la anterior porque usan sus tipos; la parte 1 sale de `main`. No depende de F-13 (solo usa el puerto `FindingStore` de `main`) ni de F-26.

## Riesgos y preguntas abiertas

Cada una con decisión provisional del arquitecto; se aplica salvo que la persona indique otra cosa.

1. **Los workers no persisten hallazgos.** Hoy F-07 a F-09 devuelven `Finding` pero el worker (José) no los envía a un `FindingStore`, y el adaptador Redis es de F-13 (PR abiertas). Sin ese cableado, la incidencia alta no genera alerta en operación real; la de cierre sí. Provisional: F-14 entrega el decorador y la prueba con dobles; el cableado a `AlertingFindingStore` queda a José y se declara en la PR y la bitácora. No se inventan alertas.
2. **Tocar `rutas_subtareas.py` (Nahúm).** El cierre ocurre ahí y no hay otro punto de enganche sin sondear. Provisional: una llamada protegida de pocas líneas, sin cambiar la respuesta, con aviso a Nahúm en la PR de la parte 3. Alternativa: que Nahúm la cablee (F-10 toca ese cierre) y F-14 entregue solo `notify_case_closed`.
3. **Una alerta por hallazgo alto.** Un caso con muchos hallazgos altos genera muchas alertas y puede inundar al supervisor. Provisional: una por hallazgo, sin agrupar ni tope, acotado solo por el `MAXLEN` del Stream. Alternativa: una alerta por categoría o por archivo.
4. **Vista en el dashboard (Melany).** El criterio habla de dashboard; el endpoint no lo es. Provisional: F-14 acredita la visibilidad con `GET /alerts` y declara la vista pendiente de Melany (F-15), que necesitará token de supervisor cuando F-26 active la autenticación.
5. **Estados que alertan al cerrar.** Provisional: `completed`, `partially_completed` y `failed`; `cancelled` no, porque el cierre por barrera no lo alcanza y cancelar es una acción del usuario. Alternativa: alertar también la cancelación.
6. **Contenido de la alerta.** Provisional: categoría, confianza, `sha256` y posición; sin texto de mensajes ni `Finding.detail`. Alternativa: incluir un extracto.
7. **Entrega a lo sumo una vez y retención de 1000.** Si el `XADD` falla, la alerta se pierde y solo queda en el log; no hay reintento ni cola de salida. `maxlen=1000` y la clave `alerts` son valores provisionales sin medición. Alternativa: «outbox» en el almacén de hallazgos.
8. **Lectura sin grupo de consumidores.** Cada lector ve las últimas alertas, sin acuse. Provisional: suficiente para un dashboard; un notificador externo con acuse exigiría `XGROUP`, fuera de alcance.
9. **Seguridad de la ruta.** `/alerts` queda pública hasta que F-26 se fusione; luego debe clasificarse como lectura del supervisor (la prueba «toda ruta clasificada» de F-26 lo obliga). El `detail` no lleva texto de mensajes para limitar la exposición.
10. **Identificadores.** AD-39 y SUP-35 estaban libres en todas las ramas remotas al 2026-11-11 (máximos AD-38 y SUP-34, de F-13); trabajo local sin publicar podría chocar. Verificar antes de fusionar.
11. **Sin medición.** No se mide el costo del `XADD` por hallazgo; no se afirma rendimiento. Si el volumen de hallazgos altos lo exige, se mide aparte.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | orquestador | 2026-11-11 | SPEC F-14 completo (grep … = 0), diff contra main solo el SPEC, Base main; AD-39 y SUP-35 libres segun arquitecto; pila de 3 partes; 11 preguntas abiertas con decision provisional: aceptar (la parte 3 toca rutas_subtareas.py de Nahum: avisar) (87a594b) |
| plan | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | orquestador | 2026-11-11 | Diff solo tests (2 archivos nuevos, be57e0f), src intacto; ambos fallan en coleccion con ModuleNotFoundError (rojo); API asumida declarada (be57e0f) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | pytest + revision | 2026-11-11 | Dominio y aplicacion implementados (171ca2b, ~90 lineas src, sin ediciones a pruebas); suite verde (171ca2b) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: generador agotado en add, publicador sin Safe propaga, estado no hashable da TypeError, case_id inyecta lineas en log, publicador async se pierde |
| verificación IA de implementacion | orquestador | 2026-11-11 | 5 hallazgos QA corregidos en 3337814; suite verde; solo se quitaron marcadores xfail (3337814) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de verificacion | orquestador | 2026-11-11 | QA 5 defectos reproducidos como xfail, corregidos y en verde; sin segundo QA (15f497e) |
| verificacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de documentacion | orquestador | 2026-11-11 | AD-39 y SUP-35 provisionales registrados con limites de la parte 1; bitacora en estado; sin cambios de codigo (492fceb) |
| documentacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de revision | revisor + orquestador | 2026-11-11 | Revisor APROBADO parte 1: 103 lineas src, dominio puro, AD-39 y SUP-35 coinciden con codigo; 2 menores no bloqueantes anotados en CLAUDE.md local (b2766af) |
| revision | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | orquestador | 2026-11-11 | Diff solo tests y dobles (3682776); src intacto; test_redis_alert_stream y test_rutas_alertas fallan en coleccion con ModuleNotFoundError (rojo); se modifico FakeAlertPublisher(reloj=None) en dobles.py (compatible); integracion validada con redis:7-alpine local por el developer con implementacion desechable (3682776) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | pytest + revision | 2026-11-11 | Adaptador RedisAlertStream, puerto AlertReader y GET /alerts implementados (b0b8803, ~88 lineas src); suite verde; integracion pasa con redis:7-alpine local (reportado por developer); 0 contenedores restantes (b0b8803) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: 503 filtra host y puerto, bytes no UTF-8 tiran la ruta, ResponseError da 500, emitted_at sin zona, recent(0) DataError, maxlen no positivo |
| verificación IA de implementacion | orquestador | 2026-11-11 | 6 hallazgos QA corregidos en c0fa551; suite verde; integracion pasa con redis:7-alpine; limite: relectura en crudo ante bytes no UTF-8 solo probada con fakeredis (c0fa551) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de verificacion | orquestador | 2026-11-11 | QA 6 defectos reproducidos como xfail, corregidos y en verde; sin segundo QA (2353fd7) |
| verificacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de documentacion | orquestador | 2026-11-11 | Limites de la parte 2 en AD-39, curl de GET /alerts en DEMO.md, bitacora en estado; sin cambios de codigo (c053c76) |
| documentacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de revision | revisor + orquestador | 2026-11-11 | Revisor APROBADO parte 2: ~108 lineas src, AlertReader con contrato y doble, 503 fijo, AD-39 coincide con codigo; 4 menores no bloqueantes anotados en CLAUDE.md local (fca1529) |
| revision | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | orquestador | 2026-11-11 | Diff solo tests y ayudas (b952465); src intacto; test_cierre_alertas: 11 fallan por asercion (no se publica alerta aun) y 5 de regresion pasan; aceptacion A con reloj sintetico, evidencia solo con F14_EJEMPLO_JSON (b952465) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | pytest + revision | 2026-11-11 | Llamada protegida de cierre en rutas_subtareas.py (7bea224, +12/-2); suite verde; sin ediciones a pruebas; toca archivo de Nahum (7bea224) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: log de alerta usa %s con case_id controlado por el cliente (inyeccion de lineas); previos de Nahum quedan como limites declarados |
