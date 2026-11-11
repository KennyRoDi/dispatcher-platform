# SPEC F-22: Chunks verificados

**Fase:** revision
**Base:** feat/F-22-1-chunks-verificados
**Verificación IA:** revision a7c8e59
**Historia:** US-22 · **Requisitos:** RF-31, RF-22, RNF-11 (parte de throughput), QA-04; AD-10, SUP-13, SUP-17; [B.5 M3] · **Responsable:** V

## Objetivo

[B.5 M3] exige «transferencia de archivos grandes en bloques (chunks) de tamaño justificado, con reensamblado verificado por hash» (RF-31), y el dataset incluye al menos cinco casos con archivos ≥ 200 MB (RF-22). Hoy el coordinador solo recibe casos como JSON con rutas (`POST /cases`) y los workers leen de MinIO: no existe forma de subir un archivo grande al sistema, ni de detectar que llegó corrupto. F-22 entrega el protocolo propio por chunks de AD-10: el cliente declara el archivo (SHA-256 y tamaño), envía cada chunk con su propio SHA-256, el coordinador rechaza un chunk alterado, reensambla en orden sin cargar el archivo completo en memoria y solo entrega al almacén un objeto cuyo SHA-256 coincide con el declarado. Es la base de F-25 (recepción no bloqueante), la entrada de F-23 (almacén por contenido) y el instrumento de la medición de throughput de la ficha M3 (RNF-11, QA-04).

## Alcance

**Incluye:**

- Lógica pura de dominio: manifiesto de subida (SHA-256 total, tamaño, tamaño de chunk y número de chunks derivado), verificación del SHA-256 de cada chunk, validación de índice y tamaño, control de chunks recibidos y faltantes, y orden de reensamblado por índice.
- Caso de uso de aplicación: iniciar subida, recibir chunk, completar subida. Al completar, recorre los chunks en orden, calcula el SHA-256 de forma incremental y, si coincide, entrega el contenido por flujo al puerto `ObjectStore` (`put(sha256, content, size)`).
- Puerto nuevo `ChunkStaging` para el almacenamiento temporal de chunks y su adaptador en disco local, con un archivo por chunk, para no retener el archivo en RAM.
- Rutas HTTP en `src/coordinator/rutas_archivos.py` y su `include_router` en `main.py`.
- Cliente `scripts/subir_por_chunks.py` que lee el archivo por partes, calcula los hashes y lo sube, con tamaño de chunk configurable. Lo usan la prueba de integración y, después, la medición.
- Tamaño de chunk configurable, con valor provisional de 4 MiB (AD-10) y un máximo aceptado por el servidor para acotar la memoria por petición.
- Script de medición `scripts/measure/m3_chunks.py` y ficha M3 con MB/s para 256 KiB, 1 MiB, 4 MiB y 16 MiB.

**No incluye:**

- Deduplicación y adaptador real de MinIO (`minio_object_store.py`): es F-23. F-22 programa contra `ObjectStore` y prueba con `FakeObjectStore`.
- Recepción `async` con escritura en hilo: es F-25. En F-22 los handlers son síncronos; FastAPI ya los ejecuta en su pool de hilos.
- Backpressure y respuesta 503: F-24.
- Cifrado AES-GCM del objeto: F-28 (Kenni envuelve `ObjectStore`).
- Entrada de custodia del ingreso: F-29 (Kenni). F-22 no llama a `CustodyLog`.
- Autenticación y TLS de las rutas: F-26 y F-27, que se aplican en `main.py` sin tocar estas rutas.
- Asociar el objeto subido a un caso y crear sus sub-tareas: F-05.
- Limpieza automática de subidas abandonadas: queda como pregunta abierta.
- Reanudar una subida desde otro coordinador: el sistema tiene un solo coordinador en el Nodo A.

## Criterios de aceptación

Copiados de `docs/backlog/m3-es-almacenamiento.md`, US-22:

- **Dado** un archivo ≥ 200 MB dividido en chunks
- **Cuando** se envía y reensambla
- **Entonces** el SHA-256 coincide; un chunk alterado se rechaza

- **Pruebas:** U reensamblado, alteración y orden. I subida real entre nodos.
- **Demuestra:** prueba I. **Evidencia:** ficha M3: MB/s para ≥ 3 tamaños.

Criterios adicionales derivados de los requisitos:

- RF-31: un chunk cuyo SHA-256 no coincide con el declarado se rechaza con 422 y no se guarda; reenviarlo correcto se acepta.
- RF-31: los chunks pueden llegar en cualquier orden; el objeto se reensambla por índice.
- RF-31: completar con chunks faltantes responde 409 y lista los índices que faltan.
- RF-31: si el SHA-256 del archivo reensamblado no coincide con el declarado, no se entrega nada al `ObjectStore` y se responde 422.
- [B.5 M3] «archivos grandes»: el servidor nunca mantiene en memoria más de un chunk por petición; el reensamblado es por flujo.
- AD-10: el tamaño de chunk es un parámetro, no una constante, para poder medir 256 KiB, 1 MiB, 4 MiB y 16 MiB.

## Diseño

### Contratos

| Contrato | Rol de F-22 | Fuente |
|---|---|---|
| `ObjectStore.put(sha256, content, size)` | Lo usa al completar la subida. En pruebas, `FakeObjectStore` | `src/application/ports.py`; adaptador real en F-23 |
| `ChunkStaging` (nuevo) | Lo define e implementa | `src/application/ports.py`, `src/adapters/disk_chunk_staging.py` |

`ChunkStaging` se agrega a `ports.py`, sin modificar los puertos existentes:

```python
class ChunkStaging(Protocol):
    def save_manifest(self, upload_id: str, manifest: dict) -> None: ...
    def load_manifest(self, upload_id: str) -> dict: ...
    def put_chunk(self, upload_id: str, index: int, data: bytes) -> None: ...
    def received(self, upload_id: str) -> set[int]: ...
    def open_chunk(self, upload_id: str, index: int) -> BinaryIO: ...
    def discard(self, upload_id: str) -> None: ...
```

Se agrega su doble `FakeChunkStaging` a `tests/dobles.py` y `comprobar_chunk_staging` a `tests/contratos.py`, que valida al doble y al adaptador en disco. Es un agregado: se avisa al equipo porque toca archivos compartidos.

### Protocolo HTTP

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /uploads` | JSON `{sha256, size, chunk_size}` | 201 `{upload_id, chunk_count}`; 422 si `chunk_size` excede 64 MiB, si la subida tendría más de 100 000 chunks o si los datos no son válidos |
| `PUT /uploads/{id}/chunks/{index}` | Bytes del chunk; cabecera `X-Chunk-SHA256` | 204; 413 si el cuerpo supera el tamaño esperado del chunk, sin leerlo completo; 422 si el hash no coincide, el chunk es más corto o el índice está fuera de rango; 404 si la subida no existe, sin leer el cuerpo |
| `GET /uploads/{id}` | — | 200 `{received, missing}`, para que el cliente reenvíe; 404 si no existe o ya se completó |
| `POST /uploads/{id}/complete` | — | 201 `{sha256, size}`; 409 con `missing`; 422 si el SHA-256 total no coincide; 404 si no existe o la completó otra petición concurrente |

Reenviar un chunk ya recibido con el mismo hash es idempotente. Mientras no haya `ObjectStore` configurado (F-23), todas las rutas responden 503.

El PUT reserva un único buffer del tamaño esperado y lo llena por partes, sin copia final: nunca hay más de un chunk en memoria por petición [B.5 M3]. El tope de 100 000 chunks acota los índices que `status` y `complete` materializan; con chunks de 4 MiB equivale a unos 390 GiB.

### Flujo

```
cliente: sha_total = sha256(archivo); POST /uploads
por cada índice i (en cualquier orden):
  dato = leer(archivo, i * chunk_size, chunk_size)
  PUT /uploads/{id}/chunks/{i}  X-Chunk-SHA256: sha256(dato)
    dominio: validar índice y tamaño; verificar hash → ChunkRejected
    staging.put_chunk(id, i, dato)
POST /uploads/{id}/complete
  dominio: faltantes(recibidos) → MissingChunks
  object_store.put(sha_total, flujo_verificado, size)
    flujo_verificado: por i en orden, lee cada chunk del staging una sola vez
    y calcula el sha256 sobre los mismos bytes que entrega a put
    si hash != sha_total → IntegrityMismatch antes del último byte (put aborta)
  staging.discard(id)
```

### Capas y archivos

| Capa | Archivo | Contenido | Dueño |
|---|---|---|---|
| Dominio | `src/domain/chunks.py` | `UploadManifest` (inmutable, `chunk_count` y `expected_size(i)`), `verify_chunk`, `missing_chunks`, excepciones `ChunkRejected`, `MissingChunks`, `IntegrityMismatch`. Solo `hashlib` de la biblioteca estándar | Melany |
| Aplicación | `src/application/ports.py` | `ChunkStaging` (agregado) | Compartido |
| Aplicación | `src/application/chunked_upload.py` (nuevo) | Caso de uso `ChunkedUpload(staging, object_store, max_chunk_size)`: `start`, `receive`, `status`, `complete` | Melany (archivo nuevo; ver preguntas) |
| Adaptador | `src/adapters/disk_chunk_staging.py` (nuevo) | Un directorio por subida, un archivo por chunk escrito a temporal y renombrado de forma atómica; manifiesto en JSON | Melany (archivo nuevo) |
| Coordinador | `src/coordinator/rutas_archivos.py` (nuevo) | Rutas de la tabla; traduce excepciones de dominio a 404, 409 y 422 | Melany |
| Coordinador | `src/coordinator/main.py` | Un `include_router` | Compartido, una línea |
| Scripts | `scripts/subir_por_chunks.py`, `scripts/measure/m3_chunks.py` | Cliente y medición | Melany |

Decisiones que aplica: AD-10 (protocolo propio, chunk provisional de 4 MiB), SUP-13 (el chunk es solo unidad de transferencia; la dedup es por archivo, F-23), SUP-17 (el tamaño se calibra midiendo). Decisión nueva propuesta, que se registra en `docs/ARQUITECTURA.md` §8 al aprobar este plan:

- **AD-28 (provisional).** Staging de chunks en disco del Nodo A, un archivo por chunk, con reensamblado por flujo hacia `ObjectStore`. Alternativas: retener los chunks en memoria; *multipart upload* de MinIO. Criterio: acota la RAM a un chunk por petición [B.5 M3] y deja el control del hash en la aplicación; *multipart* ataría F-22 al adaptador de F-23 y su ETag no es SHA-256. Costo: el archivo se escribe dos veces en disco. **Medición pendiente:** ficha M3.

Código del I Proyecto que reutiliza: la aplicación FastAPI y el patrón de routers de `src/coordinator/`. `src/workers/storage.py` no se toca.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_reensamblado_coincide_con_sha256` | Un archivo en N chunks reensamblado produce el SHA-256 declarado y llega a `ObjectStore` |
| Unitaria | `test_chunk_alterado_se_rechaza` | Un chunk con un byte cambiado lanza `ChunkRejected` y no queda en staging |
| Unitaria | `test_chunk_fuera_de_orden_se_ordena` | Chunks recibidos en orden inverso se reensamblan por índice |
| Unitaria | `test_completar_con_faltantes_lista_indices` | `MissingChunks` con los índices exactos |
| Unitaria | `test_hash_total_distinto_no_guarda_objeto` | `IntegrityMismatch` y `ObjectStore` vacío |
| Unitaria | `test_tamano_de_chunk_invalido_se_rechaza` | Índice fuera de rango, tamaño distinto al esperado y `chunk_size` sobre el máximo |
| Unitaria | `test_reenvio_del_mismo_chunk_es_idempotente` | Reenviar no duplica ni falla |
| Unitaria | `comprobar_chunk_staging(FakeChunkStaging())` y sobre `DiskChunkStaging(tmp_path)` | El doble y el adaptador cumplen el mismo contrato |
| Unitaria | Rutas con `TestClient` y dobles: 201, 204, 409, 422, 404 | Traducción de errores de dominio a HTTP |
| Integración | `tests/integration/test_subida_por_chunks.py`: uvicorn real y `scripts/subir_por_chunks.py` con un archivo sintético de 200 MiB | El SHA-256 del objeto coincide; un chunk alterado en tránsito recibe 422 |
| Aceptación | Subida real de un archivo ≥ 200 MB desde un nodo worker al coordinador del Nodo A por Tailscale | Criterio «subida real entre nodos» de US-22 |

Las unitarias no usan red, `sleep` ni reloj real; los archivos grandes solo aparecen en integración y aceptación.

## Mediciones

Throughput de M3, ficha `docs/modulo-M3-es-almacenamiento.md`, datos crudos en `docs/evidencia/`:

```bash
python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a
```

- Archivo ≥ 200 MB del dataset sintético (RF-22), desde un nodo worker al Nodo A.
- 5 repeticiones por tamaño; se reporta media, desviación y el CSV crudo con tiempo total y bytes.
- MB/s = bytes / tiempo total desde `POST /uploads` hasta la respuesta de `complete`, y por separado el tiempo de `complete` (reensamblado y hash).
- Se repite cuando entre TLS (F-27), según `docs/IMPLEMENTACION.md` §5.
- El tamaño elegido con estos datos reemplaza el provisional de AD-10.

Requiere los nodos reales: la hace Melany; la IA no estima ningún dato.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-22): reensamblar chunks verificados por sha-256` | `src/domain/chunks.py`, puerto `ChunkStaging`, `src/application/chunked_upload.py`, `src/adapters/disk_chunk_staging.py`, doble y conformidad. Estimado: ~280 líneas |
| 2 | `feat(F-22): recibir archivos por chunks en la api` | `src/coordinator/rutas_archivos.py`, `include_router`, `scripts/subir_por_chunks.py`, prueba de integración. Estimado: ~220 líneas |
| 3 | `docs(F-22): medir throughput por tamano de chunk` | `scripts/measure/m3_chunks.py`, ficha M3 con datos medidos entre nodos, AD-10 actualizado |

## Riesgos y preguntas abiertas

1. **Archivos nuevos fuera de la tabla de dueños.** `docs/CONTRATOS.md` asigna a Melany `rutas_archivos.py`, `chunks.py` y `minio_object_store.py`. Este plan agrega `src/application/chunked_upload.py` y `src/adapters/disk_chunk_staging.py`. ¿Se aprueban y se agregan a la tabla?
2. **Puerto compartido.** Agregar `ChunkStaging` a `ports.py` y su doble obliga a avisar al equipo. ¿Se hace en esta misma PR (parte 1) o en una PR aparte solo con el contrato, como sugiere `CONTRATOS.md`?
3. **Tamaño máximo de chunk aceptado.** Propuesta: 64 MiB, para acotar la memoria por petición y permitir medir 16 MiB con margen.
4. **Subidas abandonadas.** Quedan en disco hasta un `DELETE` o reinicio manual. ¿Se acepta para el alcance, o se agrega una expiración (por ejemplo 24 h) en una parte posterior?
5. **Ubicación del staging.** Un volumen del Compose del Nodo A (`deploy/` es de Kenni). Hay que coordinar con él la línea del volumen.
6. **Doble escritura en disco** (staging y luego MinIO): puede bajar el throughput medido. Se reporta en la ficha; si pesa demasiado, se revisa AD-28.
7. **Prueba entre nodos** depende de que F-38 (despliegue en tres nodos) esté disponible.
8. **`put` aborta por excepción (desviación aceptada en verificación).** QA encontró que leer el staging dos veces, una para el hash y otra para el `put`, permitía que un chunk cambiado entre ambas pasadas llegara a `ObjectStore` bajo un SHA-256 ajeno (H1). Ahora el hash se calcula sobre el mismo flujo que lee `put`, y si no coincide la lectura lanza `IntegrityMismatch` antes del último byte. Por eso `put` sí se llama, pero termina en excepción. **Requisito para F-23 (MinIO) y F-28 (cifrado):** el adaptador de `ObjectStore` no debe confirmar el objeto si la lectura de `content` lanza una excepción. Falta llevarlo al contrato en `docs/CONTRATOS.md` y a `comprobar_object_store`, en una PR aparte según «Cambiar un contrato». Aprobado por Melany Vindas.
9. **Carrera entre `receive` y `discard` (H2, baja). Resuelta en la parte 2.** `put_chunk` exige el manifiesto y ya no crea la carpeta; `discard` renombra la carpeta de forma atómica antes de borrarla, para que un `put_chunk` concurrente no deje restos. Lo cubre una prueba de estrés de 200 rondas. La pregunta 4 (subidas abandonadas) sigue abierta: no hay `DELETE` ni expiración.
10. **El servidor drena el cuerpo tras un error (H7, informativa).** Después de responder 413, 404 o 422, uvicorn sigue leyendo y descartando el resto del cuerpo para conservar la conexión *keep-alive*. No ocupa memoria, solo red y CPU.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude (Opus 5.5) | 2026-11-10 | Plan revisado contra main: AD-27 ya usado por F-08, se renumera a AD-28. Verificacion no independiente. (082b106) |
| plan | Melany Vindas | 2026-11-10 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-10 | Diff contra main solo toca tests y SPEC; test_chunks en rojo por modulos faltantes de src; FakeChunkStaging cumple comprobar_chunk_staging. Verificacion no independiente. (47b06f4) |
| tests | Melany Vindas | 2026-11-10 |  |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-10 | 1069 pruebas en verde con test_chunks 27/27 y capas; 254 lineas; commits validos. Desviacion: el staging no se borra si el sha256 total no coincide. Verificacion no independiente. (316b0de) |
| implementacion | Melany Vindas | 2026-11-10 |  |
| devuelta de verificacion | Melany Vindas | 2026-11-10 | QA: H1, complete relee el staging y un chunk cambiado entre pasadas llega a ObjectStore con sha256 ajeno (test e7273fe en rojo) |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-10 | Devuelta por H1 de QA. Developer (subagente) cambio complete a una sola pasada que verifica el sha256 sobre el flujo entregado a ObjectStore. pytest: test_chunks 32/32, suite 1074 verde; mutante sin verificacion detectado; tests sin debilitar; 268 lineas. Desviacion: put se llama y aborta por excepcion si el hash no coincide; requiere que ObjectStore no confirme ante excepcion (F-23/F-28). H2 abierto para parte 2. Verificacion independiente. (9e5b2b4) |
| implementacion | Melany Vindas | 2026-11-10 |  |
| verificación IA de verificacion | Claude (Opus 5.5) | 2026-11-10 | QA (subagente) re-verifico parte 1 tras arreglo de H1: APROBADO. Ataque con 14 lectores, chunks alterados en disco y concurrencia con hilos: ningun objeto con contenido distinto a su clave. 12 pruebas nuevas en verde que matan 3 mutantes. Orquestador: test_chunks 44/44, suite 1086 verde, mutante >= por == detectado, solo tests tocados. Sin mediciones en esta parte (M3 en parte 3). Riesgo 8 y H2 aceptados. Verificacion independiente. (c121d8e) |
| verificacion | Melany Vindas | 2026-11-10 |  |
| verificación IA de documentacion | Claude (Opus 5.5) | 2026-11-10 | Documentador (subagente): AD-28 provisional en ARQUITECTURA §8 con arreglo H1 y regla del put, capas en §4, ChunkStaging y archivos nuevos en CONTRATOS. Orquestador: diff solo en esos 2 docs, 64 MiB coincide con chunked_upload.py, conformidad 0 problemas. Ficha M3 y reutilizacion no existen todavia (parte 3 y F-39). Bitacora con 4 errores reales de la IA. Verificacion independiente. (cabfc4b) |
| documentacion | Melany Vindas | 2026-11-10 |  |
| verificación IA de revision | Claude (Opus 5.5) | 2026-11-10 | Revisor (subagente, contexto nuevo): APROBADO. Diff de la parte 1 cumple el SPEC; sin errores de logica en src; capas y sin llaves. Orquestador: 268 lineas, suite 1086 verde, conformidad 0, bitacora publicada. Autoria: 6 commits aplicados con git am pasaron a Melany Vindas conservando fechas y contenido (rebase con --exec); los hashes anteriores en la tabla de aprobaciones quedan como referencia historica. Pendientes para la parte 2: ResourceWarning en tests/contratos.py:71 y mapeo de ValueError/UploadNotFound. Verificacion independiente. (2f2f6c0) |
| revision | Melany Vindas | 2026-11-10 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente: orquestador escribio las pruebas, verificacion no independiente. Diff solo en tests/ (444 lineas). Rojo por falta de funcionalidad: rutas_archivos y subir_por_chunks no existen; 4 de test_chunks fallan con DID NOT RAISE (H2). Resto de la suite en verde. Contra un borrador no confirmado: rutas y cliente 41/41, integracion 200 MiB 2/2 con uvicorn real, suite 1129 verde. ResourceWarning corregido. Conformidad 0. (427f2c7) |
| tests | Melany Vindas | 2026-11-11 |  |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Sin subagente: orquestador implemento y verifico, verificacion no independiente. Rutas /uploads (201/204/409/422/404, 503 sin almacen), cliente scripts/subir_por_chunks.py y H2: put_chunk exige manifiesto y no recrea la carpeta. Error de IA detectado: el primer arreglo de H2 dejaba 88/200 carpetas huerfanas con put y discard concurrentes; discard ahora renombra atomico antes de borrar y una prueba de estres lo cubre (falla sin el arreglo, 8/8 verde con el). Suite 1129 verde sin ResourceWarning; integracion 3/3 con subida real de 200 MiB. Riesgo: el chunk se lee completo en memoria antes de validar tamano. Conformidad: solo falta docs/dataset.md de F-04, ajeno a esta rama. (844fe4e) |
| implementacion | Melany Vindas | 2026-11-11 |  |
| devuelta de verificacion | Melany Vindas | 2026-11-11 | QA: H3 PUT lee el cuerpo entero en RAM (B.5 M3), H4 size sin tope agota memoria, H5 complete concurrente da 500 |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Arreglo de devuelta QA, sin subagente (no independiente). H3: PUT consulta el tamano esperado y lee el cuerpo por partes, corta con 413 al excederlo (B.5 M3). H4: start rechaza mas de 100000 chunks con 422. H5: complete traduce la carrera con otro complete a UploadNotFound. Pruebas de QA en verde, suite 1133 verde sin ResourceWarning, integracion 4/4 en 5 corridas incluida subida de 200 MiB y complete concurrente. 28 lineas. (06ceb32) |
| implementacion | Melany Vindas | 2026-11-11 |  |
| verificación IA de verificacion | Claude (Opus 5.5) | 2026-11-11 | QA independiente (subagente) re-verifico: H3, H4 y H5 cerrados con sondas en uvicorn real (1 GiB sin Content-Length o mentiroso: 413, RAM +6 MiB; 100000 chunks 201, 100001 422; 50 rondas de complete y PUT concurrentes sin 500). Hallazgo H6: copia final dejaba 2 chunks en RAM; arreglado con un buffer reservado sin copia (B.5 M3). 8 pruebas de QA matan 4 mutantes vivos. Suite 1141 verde, integracion 4/4 en 3 corridas. (3810af4) |
| verificacion | Melany Vindas | 2026-11-11 |  |
| verificación IA de documentacion | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. Diff solo en docs/specs/F-22/SPEC.md (protocolo con 413, tope 100000 chunks, 404 concurrente, 503; H2 resuelto, H7 informativa) y AD-28 en ARQUITECTURA. Sin ficha M3: no hay datos medidos (parte 3). README sin cambios: el despliegue no cambio. Bitacora con 4 errores reales de la IA. (5df88a5) |
| documentacion | Melany Vindas | 2026-11-11 |  |
| verificación IA de revision | Claude (Opus 5.5) | 2026-11-11 | Revisor independiente (subagente) devolvio dos veces y aprobo los arreglos 1, 2 y 5: receive en run_in_threadpool (no bloquea el event loop, B.5 M3 intacto), KeyError del ObjectStore ya no se disfraza de 404, separador eliminado. Su segunda revision hallo una carrera previa en received() (is_dir y luego iterdir) que daba 500 en 4/25; arreglada por el orquestador con prueba determinista, 0/25 fallos (verificacion no independiente de ese punto). Anotado: discard borra sin renombrar si rename falla con OSError. Diff 226 lineas en src y scripts. Suite 1144 verde. (a7c8e59) |
