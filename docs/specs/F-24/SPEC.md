# SPEC F-24: Backpressure

**Fase:** verificacion
**Base:** main
**Verificación IA:** verificacion 15e0f8a2
**Historia:** US-24 · **Requisitos:** RF-33, [B.5 M3], QA-05 · **Responsable:** V

## Objetivo

El enunciado pide para M3 «colas acotadas y backpressure» [B.5 M3], y RF-33 exige que, con la cola llena, el productor reciba rechazo o bloqueo y la profundidad no supere el límite. Hoy `POST /cases` hace `RPUSH` en `queue:{op}` y `queue:{op}:high` sin límite: una ráfaga de productores más rápidos que los workers hace crecer Redis sin control. F-24 acota cada cola según AD-12. La API rechaza con `503` y `Retry-After` antes de pasar el límite, y queda una primitiva atómica para que el scheduler (F-20) y la cola de trabajo (F-06) muevan solo si hay espacio. Un parámetro desactiva el límite para el experimento con y sin límite de la ficha M3.

## Alcance

**Incluye:**
- Configuración del límite desde el entorno: `QUEUE_MAX_DEPTH` (profundidad máxima por cola; `0` desactiva) y `QUEUE_RETRY_AFTER` (segundos para `Retry-After`).
- Admisión acotada en `POST /cases`: la creación del caso y el encolado de sus subtareas son una sola transacción `WATCH/MULTI/EXEC` que se aborta si alguna cola destino quedaría por encima del límite.
- Primitiva Lua `mover_acotado` (comprobar `LLEN` y encolar en un solo paso) para el scheduler y la cola de trabajo, con su contrato.
- Script de carga y medición con y sin límite, y su sección en la ficha M3.

**No incluye:** el scheduler con prioridades (F-20, Nahúm) ni el adaptador `RedisWorkQueue` (F-06, Nahúm), que usarán la primitiva; bloquear al productor (AD-12 lo descarta); límites por tipo de operación distintos entre sí.

## Criterios de aceptación

De `docs/backlog/m3-es-almacenamiento.md` (US-24):

- **Dado** una cola en su límite
- **Cuando** llega más carga
- **Entonces** la API responde 503 con `Retry-After`, el scheduler no mueve más y la profundidad no supera el límite

Criterios adicionales derivados de los requisitos:

- RF-33: con N productores concurrentes contra Redis real, ninguna cola supera `QUEUE_MAX_DEPTH` en ningún momento muestreado, y cada caso rechazado no deja rastro: ni hash del caso, ni subtareas, ni entrada en `cases:registry`.
- RF-33: un caso se admite completo o no se admite; si sus subtareas van a varias colas, todas deben tener espacio.
- AD-12: con `QUEUE_MAX_DEPTH=0` no hay límite y el comportamiento es el de hoy.
- AD-12: `mover_acotado` con la cola llena no encola y lo informa; con espacio encola de forma atómica, aun con varios llamadores concurrentes.
- `Retry-After` es un entero de segundos tomado de `QUEUE_RETRY_AFTER`.

## Diseño

**Contratos.** `WorkQueue` (Nahúm, F-06) ya declara `has_capacity` y `QueueFull`, y `comprobar_work_queue` ya los exige; F-24 no lo cambia. `rutas_casos.py` es de Nahúm: el cambio se limita a envolver la transacción existente y se le avisa.

| Capa | Archivo | Cambio | Dueño |
|---|---|---|---|
| Dominio | `src/domain/backpressure.py` (nuevo) | `QueueLimit(max_depth, retry_after)`: `from_env`, `desactivado` cuando `max_depth == 0`, `admite(profundidad, entrantes) -> bool`. Lógica pura, sin Redis | Melany |
| Adaptador | `src/adapters/redis_backpressure.py` (nuevo) | `transaccion_acotada(redis, demanda: dict[cola, n], limite, preparar)`: `WATCH` de las colas, `LLEN`, rechazo con `QueueFull` si alguna no admite, `MULTI` con los comandos que arma `preparar(pipe)`, `EXEC`; reintenta ante `WatchError` hasta 5 veces y luego rechaza. `mover_acotado(redis, cola, payload, limite) -> bool` con un script Lua (`LLEN` y `RPUSH` atómicos) | Melany |
| Coordinador | `src/coordinator/rutas_casos.py` | `create_case` calcula la demanda por cola, construye los comandos actuales dentro de `transaccion_acotada` y, ante `QueueFull`, responde `503` con `Retry-After` | Nahúm (avisar) |
| Medición | `scripts/measure/m3_backpressure.py` (nuevo), `docs/modulo-M3-es-almacenamiento.md` | Ráfaga de `POST /cases` con y sin límite; muestreo de `LLEN` y de códigos y latencias | Melany |

**Por qué `WATCH` en la API y Lua en el scheduler.** AD-12 pide Lua para el scheduler, que mueve un elemento por vez. La API, en cambio, debe crear el caso, sus subtareas y los encolados como una unidad: un script Lua obligaría a reescribir toda la creación de casos de Nahúm. `WATCH/MULTI/EXEC` mantiene sus comandos tal como están y aborta si otra petición o un worker cambia una cola vigilada entre la lectura de `LLEN` y el `EXEC`, así que el límite nunca se supera. Ambos mecanismos usan el mismo `QueueLimit`.

**Pruebas sin Lua nativo.** `fakeredis` necesita `lupa` para Lua: se agrega `fakeredis[lua]` a `requirements-dev.txt`, como prevé `docs/IMPLEMENTACION.md` §4.

**Decisiones.** Aplica AD-12 sin cambiarla y la completa con el mecanismo `WATCH` para la API. Si el revisor lo pide, se registra como AD-45. Sin supuestos nuevos.

**Código del I Proyecto que reutiliza.** La creación atómica de casos de `rutas_casos.py` (pipeline transaccional) y los nombres de cola de `router.queue_key`.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_limite_desactivable`, `admite` en el borde exacto (`profundidad + entrantes == límite`), configuración inválida (negativo, no numérico) | Lógica del dominio |
| Unitaria | `test_cola_llena_rechaza_productor`: `POST /cases` con la cola en el límite responde 503 con `Retry-After` y no deja hash, subtareas ni registro; caso con subtareas en dos colas, una llena; con espacio, 201 como hoy | Admisión en la API con `fakeredis` |
| Unitaria | `transaccion_acotada` reintenta ante `WatchError` y rechaza tras 5 intentos | Concurrencia sin Redis real |
| Unitaria | `test_scheduler_no_mueve_si_cola_llena`: `mover_acotado` con la cola llena devuelve `False` y no encola; con espacio encola; desactivado siempre encola (`fakeredis[lua]`) | Primitiva del scheduler |
| Integración | Redis real: 20 productores concurrentes contra la API con `QUEUE_MAX_DEPTH=50` mientras un hilo muestrea `LLEN`; ningún muestreo supera 50 y los rechazos son 503. Igual con `mover_acotado` | Criterio de US-24 con Redis real |

## Mediciones

M3, backpressure (QA-05):

```bash
python scripts/measure/m3_backpressure.py --url <coordinador> --redis <url> --limite 200 --productores 20 --duracion 60 --out m3_backpressure_con.csv
python scripts/measure/m3_backpressure.py --url <coordinador> --redis <url> --limite 0 --productores 20 --duracion 60 --out m3_backpressure_sin.csv
```

Cada corrida muestrea `LLEN` de cada cola cada 250 ms y registra código y latencia de cada `POST /cases`. Tres repeticiones por condición, sin workers o con workers detenidos para forzar la saturación. Ficha de destino: `docs/modulo-M3-es-almacenamiento.md`, sección de backpressure, con el gráfico de profundidad en el tiempo y la distribución de respuestas. Basta un coordinador y un Redis; no requiere tres nodos.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-24): frenar productores con colas acotadas` | `QueueLimit`, `transaccion_acotada` y el cambio en `create_case`; pruebas unitarias e integración de la API. Estimado: ~120 líneas |
| 2 | `feat(F-24): mover al scheduler solo con espacio en la cola` | `mover_acotado` con Lua, `fakeredis[lua]` y su integración. Estimado: ~60 líneas |
| 3 | `docs(F-24): medir backpressure con y sin limite` | Script de medición y sección de la ficha M3 con datos medidos |

## Riesgos y preguntas abiertas

1. **Archivo de Nahúm.** `create_case` es de Nahúm. El cambio solo envuelve su transacción; hay que avisarle antes de la parte 1 y verificar que nadie más lo esté cambiando.
2. **Valores por defecto.** Propuesta: `QUEUE_MAX_DEPTH=1000` y `QUEUE_RETRY_AFTER=5`. Se ajustan con la medición; Kenni los agrega a `deploy/` y `.env.example`.
3. **Contención de `WATCH`.** Con muchos productores y workers vaciando la misma cola, `EXEC` puede fallar seguido. Tras 5 reintentos se responde 503, que es seguro. La medición reporta cuántos 503 fueron por contención.
4. **Integración con F-20 y F-06.** `mover_acotado` queda listo, pero el scheduler y `RedisWorkQueue` no existen todavía. Cuando Nahúm los implemente, deben usarlo; hasta entonces el criterio del scheduler se demuestra sobre la primitiva.
5. **Workers con `BLPOP`.** El worker actual consume con `BLPOP` (AD-03 prevé `BLMOVE`, F-06). No afecta al límite: consumir solo reduce la profundidad.
6. **Medición.** Necesita un coordinador y un Redis con los workers detenidos. La puede correr cualquier integrante; los números se miden, nunca se estiman.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude (Opus 5.5) | 2026-11-11 | Sin subagente: el orquestador escribio el SPEC, verificacion no independiente. Sigue AD-12. Comprobado en codigo: WorkQueue ya declara has_capacity y QueueFull; create_case usa pipeline transaccional; queue_key en router.py; F-06 y F-20 pendientes (de Nahum); AD-45 libre. Sin campos pendientes; conformidad 0. Pila: limite en la API, primitiva Lua del scheduler, medicion. (c7509b60) |
| plan | Melany Vindas | 2026-11-11 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. 21 unitarias (QueueLimit desde entorno, borde exacto, desactivable, WATCH con reintentos, API 503 con Retry-After sin rastro, caso que no cabe entero, dos colas) y 1 de integracion con Redis real (20 productores, limite 50, la cola nunca lo supera). Rojo: modulos inexistentes y la integracion admite 200 de 200. Contra borrador: 21/21 y 3/3 con Redis real; suite 3773 verde en Linux. (930745a7) |
| tests | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude; en Windows falla test_generar_certs, ajena a F-24. |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. QueueLimit (dominio), transaccion_acotada con WATCH/MULTI/EXEC y 5 reintentos (adaptador), create_case envuelto sin cambiar sus comandos y 503 con Retry-After. Sin limite no hay WATCH. Unitarias 21/21, integracion con Redis real 3/3, test_coordinator 40/40, suite 3773 verde en Linux, conformidad 0. (9593443d) |
| implementacion | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude; en Windows falla test_generar_certs, ajena a F-24. |
| devuelta de verificacion | Melany Vindas | 2026-11-11 | QA: H1 WATCH daba 503 por contencion con la cola lejos del limite; H2 config invalida daba 500; H3 caso mas grande que el limite recibia 503 |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Arreglo de devuelta QA: admision con script Lua atomico en vez de WATCH (0 % de 503 lejos del limite, antes 7-25 %), QueueLimit validado al arrancar, CaseTooLarge da 422. Suite 3778 verde en Linux, integracion 5/5. (9d2249d2) |
| implementacion | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude (3778 verde); en Windows falla test_generar_certs, ajena a F-24. |
| verificación IA de verificacion | Claude (Opus 5.5) | 2026-11-11 | QA independiente (subagente) APROBADO contra Redis 7 real: cero 503 lejos del limite con workers, limite nunca superado, rechazos sin rastro, H2 y H3 cerrados, estado Lua identico al pipeline, 6/7 mutantes (el restante es equivalente). Hallazgos bajos H4, H5 y H6. Suite 3778 verde en Linux. (15e0f8a2) |
