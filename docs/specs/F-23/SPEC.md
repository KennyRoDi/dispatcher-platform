# SPEC F-23: Almacenamiento por contenido

**Fase:** tests
**Base:** feat/F-23-4-deduplicar-subidas-antes-de-transferir
**Verificación IA:** tests eb396b8c
**Historia:** US-23 · **Requisitos:** RF-32, [B.5 M3] · **Responsable:** V

## Objetivo

El enunciado pide «manejo eficiente de archivos grandes» [B.5 M3] y RF-32 exige almacenamiento direccionado por contenido con deduplicación. Hoy no hay adaptador de producción de `ObjectStore`: las rutas de subida de F-22 responden 503 y F-28 prueba el cifrado con un adaptador mínimo solo de prueba. F-23 entrega `MinioObjectStore`, que guarda cada objeto con su SHA-256 como clave y no vuelve a guardar un contenido que ya existe. Además, la subida por chunks pregunta antes de transferir: si el contenido ya está, no se envía ni un byte. El operador ahorra espacio y red, y la ficha M3 reporta la tasa de deduplicación medida.

## Alcance

**Incluye:**
- Regla del contrato `ObjectStore` pendiente de F-22 (riesgo 8): `put` no confirma el objeto si la lectura de `content` lanza una excepción, y `open` de una clave inexistente lanza `KeyError`.
- Adaptador `MinioObjectStore` sobre el cliente `minio` ya usado en el I Proyecto, con validación de clave segura y deduplicación en `put`.
- Deduplicación antes de transferir en `POST /uploads` y en el cliente `scripts/subir_por_chunks.py`.
- Composición en el coordinador desde variables de entorno, con TLS según `src/infrastructure/tls.py`, para que las rutas de subida dejen de responder 503.
- Script de medición de la tasa de deduplicación y su sección en la ficha M3.

**No incluye:** deduplicación por bloques o chunks (AD-11 la descarta); recolección de objetos sin referencias; cambios al diseño del cifrado (F-28, Kenni); el catálogo de casos, que ya referencia fuentes por SHA-256 (`CaseSource.sha256`). Incluye el cableado de variables y volumen `STAGING_DIR` en `deploy/docker-compose.local.yml`, solicitado por Melany para el coordinador.

## Criterios de aceptación

De `docs/backlog/m3-es-almacenamiento.md` (US-23):

- **Dado** dos fuentes con el mismo contenido
- **Cuando** se almacenan
- **Entonces** existe un solo objeto, con clave SHA-256, referenciado por ambas

Criterios adicionales derivados de los requisitos:

- RF-32: la clave de cada objeto es el SHA-256 en minúsculas de su contenido en claro (AD-11). El adaptador rechaza con `ValueError`, sin tocar MinIO, solo las claves inseguras: vacías, con `/` o iguales a `.` o `..`. La forma de 64 hexadecimales la garantiza quien llama (`normalizar_sha256` en F-22), porque `comprobar_object_store` usa claves cortas como `"abc"`; exigirla en el adaptador rompería el contrato. Decisión aprobada por Melany Vindas en la fase tests de la parte 2.
- RF-32: con MinIO real, varias subidas concurrentes del mismo contenido dejan un solo objeto y su contenido es el original.
- Contrato: si la lectura de `content` falla a mitad de `put`, el objeto no existe después; `open` de una clave inexistente lanza `KeyError`. Lo cumplen el doble, `MinioObjectStore` y `EncryptedObjectStore`.
- [B.5 M3]: `POST /uploads` de un contenido ya guardado responde 200 `{"stored": true, "sha256", "size"}` sin crear subida en staging, y el cliente no envía chunks.
- [B.5 M3]: `open` entrega un flujo que libera la conexión HTTP al cerrarse; `put` no carga el objeto completo en memoria.

## Diseño

**Contratos.** Implementa `ObjectStore` (`exists`, `put`, `open`), del que Melany es dueña (`docs/CONTRATOS.md`). Lo consumen el coordinador, los workers y `EncryptedObjectStore` (F-28), que lo envuelve. El cambio de contrato es aditivo: dos comprobaciones nuevas en `comprobar_object_store`.

| Capa | Archivo | Cambio | Dueño |
|---|---|---|---|
| Pruebas de contrato | `tests/contratos.py`, `docs/CONTRATOS.md` | `comprobar_object_store`: `put` fallido no confirma; `open` inexistente lanza `KeyError` | Melany (avisar a Kenni) |
| Adaptador | `src/adapters/minio_object_store.py` (nuevo) | `MinioObjectStore(client, bucket)`. `exists`: `stat_object`; `NoSuchKey` da `False` y cualquier otro error se propaga. `put`: si ya existe, no escribe (dedup); si no, `put_object(..., length=size)` por flujo. `open`: `get_object` envuelto en un lector que hace `close` y `release_conn`; `NoSuchKey` da `KeyError` | Melany |
| Aplicación | `src/application/chunked_upload.py` | `start` consulta `ObjectStore.exists(sha256)`: si ya existe, devuelve que está guardado y no crea manifiesto | Melany |
| Coordinador | `src/coordinator/rutas_archivos.py` | `POST /uploads` responde 200 `{"stored": true, ...}` cuando ya existe | Melany |
| Cliente | `scripts/subir_por_chunks.py` | Si recibe `stored`, termina sin enviar chunks | Melany |
| Infraestructura | `src/infrastructure/almacen.py` (nuevo), una línea en `src/coordinator/main.py` | Arma `ChunkedUpload(DiskChunkStaging(STAGING_DIR), MinioObjectStore(...))` desde `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`, `OBJECTS_BUCKET`; exige TLS con `exigir_cifrado` y `minio_http_client`, como `src/workers/storage.py`. Sin variables, las rutas siguen en 503 | Melany |
| Medición | `scripts/measure/m3_dedup.py` (nuevo), `docs/modulo-M3-es-almacenamiento.md` | Tasa de deduplicación | Melany |

**Por qué la deduplicación vive en `put` y en `start`, y no en una clase `ContentStore`.** `docs/IMPLEMENTACION.md` §4 propone un `ContentStore` sobre el puerto. Con la clave ya calculada y verificada por F-22, una clase intermedia solo repetiría `exists` antes de `put`. El adaptador deduplica en `put` para cualquier llamador, y `start` deduplica antes de transferir, que es lo que ahorra red. Se conservan los nombres de prueba de §4.

**Atomicidad de `put`.** minio-py 7.2 lee la parte completa antes de enviarla y aborta el *multipart* si la lectura lanza una excepción. Por eso un `IntegrityMismatch` de F-22 o un fallo del cifrado de F-28 no deja objeto. La prueba de integración lo comprueba con MinIO real, con un objeto menor y otro mayor que el tamaño mínimo de parte (5 MiB).

**Concurrencia.** Dos `put` simultáneos del mismo contenido pueden pasar ambos el `exists` y escribir dos veces la misma clave. MinIO reemplaza el objeto de forma atómica y el contenido en claro es idéntico, así que sigue habiendo un solo objeto. Con F-28 el texto cifrado cambia, pero descifra al mismo contenido.

**Decisiones.** Aplica AD-10, AD-11 y AD-34. La deduplicación antes de transferir se registra como AD-44 en `docs/ARQUITECTURA.md` §8; AD-43 corresponde a la tabla de transiciones de F-10.

**Código del I Proyecto que reutiliza.** La conexión de `src/workers/storage.py` (cliente `minio`, `exigir_cifrado`, `minio_http_client`) y el arnés de MinIO efímero de `tests/integration/test_encrypted_object_store_minio.py`.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `comprobar_object_store` ampliado sobre `FakeObjectStore` y `EncryptedObjectStore` | El contrato nuevo se cumple sin MinIO |
| Unitaria | `test_mismo_contenido_guarda_un_objeto`, `test_clave_es_sha256_del_contenido`, clave inválida, `NoSuchKey`, error de red propagado, `open` libera la conexión; con un cliente `minio` simulado | Lógica del adaptador sin red |
| Unitaria | `start` de contenido existente; ruta 200 `stored`; el cliente no envía chunks | Dedup antes de transferir |
| Unitaria | Composición: sin variables, 503; con `MINIO_SECURE=false` y TLS exigido, falla cerrado | Configuración segura |
| Integración | `tests/integration/test_minio_object_store.py`: `comprobar_object_store` con MinIO real; 8 subidas concurrentes del mismo contenido dejan un objeto; `put` que falla a mitad, de 1 MiB y de 12 MiB, no deja objeto. Usa `MINIO_ENDPOINT` o Docker, si no hay ninguno se omite | Criterio de US-23 con MinIO real |

## Mediciones

M3, tasa de deduplicación (`docs/IMPLEMENTACION.md` §5):

```bash
python scripts/measure/m3_dedup.py --dir <carpeta del dataset> --reps 3 --out m3_dedup.csv
```

El script sube cada archivo con `subir_por_chunks` a un coordinador con MinIO y reporta bytes lógicos, bytes guardados (suma de los objetos del bucket) y `1 − bytes_guardados / bytes_lógicos`. Tres repeticiones; la primera parte de un bucket vacío. Medición real 2026-11-11: 480 archivos sintéticos; 2,079,898,017 bytes lógicos; 687,678,832 bytes almacenados; 1,392,219,185 bytes ahorrados (66.936897%). Ficha y CSV: `docs/modulo-M3-es-almacenamiento.md` y `docs/evidencia/F-23_deduplicacion_2026-11-11.md`. No mide entre nodos, así que no depende de F-38.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `test(F-23): exigir que objectstore no confirme un put fallido` | Solo el contrato, según «Cambiar un contrato»: `tests/contratos.py`, `docs/CONTRATOS.md` y su aplicación al doble y a `EncryptedObjectStore`. Estimado: ~40 líneas |
| 2 | `feat(F-23): guardar objetos por contenido en minio` | `src/adapters/minio_object_store.py`, pruebas unitarias e integración con MinIO real. Estimado: ~120 líneas |
| 3 | `feat(F-23): deduplicar subidas antes de transferir` | `start`, ruta, cliente, composición MinIO y volumen de staging en Compose; registra AD-44. Va después de fusionar la parte 2 de F-23 |
| 4 | `docs(F-23): medir tasa de deduplicacion` | Ejecutar `scripts/measure/m3_dedup.py` con tres pasadas del dataset completo y registrar CSV y mediciones; evidencia añadida a esta entrega |

## Riesgos y preguntas abiertas

1. **Cambio de contrato.** La parte 1 va sola y hay que avisar a Kenni (F-28) y a quienes consumen `ObjectStore`. Es aditivo: el doble y `EncryptedObjectStore` ya lo cumplen hoy. ¿Se aprueba como primera PR?
2. **Cifrado en la composición.** La composición F-23 envuelve MinIO siempre con `EncryptedObjectStore`; F-28 exige fallar cerrado si falta o es inválida la KEK, nunca guardar en claro. El operador configura `KEK_FILE` como secreto fuera del repositorio.
3. **Cambio del protocolo de F-22.** `POST /uploads` pasa a responder 200 `stored` además de 201. El cliente de F-22 se actualiza en la misma parte; no hay otros consumidores.
4. **Variables de entorno y bucket.** La composición y `deploy/docker-compose.local.yml` configuran `MINIO_ENDPOINT`, credenciales, `MINIO_SECURE`, `OBJECTS_BUCKET` y el volumen persistente para `STAGING_DIR`. El despliegue multi-nodo debe montar el staging del Nodo A en el contenedor coordinador.
5. **MinIO real.** La prueba de integración necesita Docker o `MINIO_ENDPOINT`. Claude no puede levantarlo en su entorno: la ejecuta Melany o el equipo y se guarda la evidencia, como en F-28.
6. **Escritura doble concurrente.** Dos `put` del mismo contenido pueden escribir ambos. Se acepta: el resultado es un solo objeto con el mismo contenido.
7. **Medición.** Necesita los archivos del dataset y un coordinador con MinIO. La puede correr cualquier integrante con esos recursos; los números se miden, nunca se estiman.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude (Opus 5.5) | 2026-11-11 | Sin subagente: el orquestador escribio el SPEC, verificacion no independiente. Sin campos pendientes; conformidad 0. Comprobado en codigo: FakeObjectStore y EncryptedObjectStore ya cumplen el contrato nuevo (put fallido no confirma, open inexistente lanza KeyError); minio-py 7.2.20 aborta el multipart ante error de lectura; CaseSource ya referencia por sha256; AD-41 libre (ultima AD-40). Pila de 4 partes: contrato, adaptador MinIO, dedup antes de transferir, medicion. (f769b4c) |
| plan | Melany Vindas | 2026-11-11 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. Parte solo de contrato: comprobar_object_store exige KeyError en open inexistente y que un put cuya lectura falla no deje objeto; fila de ObjectStore en CONTRATOS.md. Pasan con FakeObjectStore y EncryptedObjectStore, como preveia el SPEC. Mutantes: almacen que confirma tras fallo y open sin KeyError, ambos detectados. Suite 3432 verde; 3 fallos preexistentes de main ajenos (process_supervisor, tls_cableado). (8b99f88) |
| tests | Melany Vindas | 2026-11-11 | Parte solo de contrato: las pruebas pasan porque el doble y EncryptedObjectStore ya cumplen; no hay codigo que implementar |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Parte solo de contrato, sin codigo de implementacion: el doble y EncryptedObjectStore ya cumplen. Sin cambios desde la fase tests. (1b40fed) |
| implementacion | Melany Vindas | 2026-11-11 | Parte solo de contrato: no hay codigo que implementar |
| verificación IA de verificacion | Claude (Opus 5.5) | 2026-11-11 | QA no independiente: contrato aplicado a FakeObjectStore y EncryptedObjectStore en verde; mutantes (almacen que confirma tras fallo de lectura, open sin KeyError) detectados. Sin mediciones en esta parte. (b8ec62f) |
| verificacion | Melany Vindas | 2026-11-11 | Suite verde en Linux (3432); en Windows 6 modulos de F-27/F-28/F-29 no cargan por fcntl y os.geteuid, ajenos a F-23. Pruebas del contrato en verde en Windows (41 passed). |
| verificación IA de documentacion | Claude (Opus 5.5) | 2026-11-11 | Documentacion: fila de ObjectStore en CONTRATOS.md con ambas reglas; sin ficha (no hay mediciones en esta parte); bitacora publicada con un error real de la IA. (df42621) |
| documentacion | Melany Vindas | 2026-11-11 |  |
| verificación IA de revision | Claude (Opus 5.5) | 2026-11-11 | Revision no independiente: diff de 30 lineas en tests/contratos.py y CONTRATOS.md, cumple el SPEC parte 1 sin agregados; cambio aditivo; sin llaves ni datos reales; commit en Conventional Commits. (872ab48) |
| revision | Melany Vindas | 2026-11-11 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. 14 unitarias de MinioObjectStore con cliente minio simulado y 4 de integracion con MinIO real (contrato, 8 subidas concurrentes dejan un objeto, put fallido de 1 y 12 MiB no deja objeto). Rojo: el modulo no existe. SPEC: el adaptador valida solo claves inseguras, aprobado por Melany. Contra un borrador: 14/14 y 4/4 contra moto (no MinIO real). (a3621ec) |
| tests | Melany Vindas | 2026-11-11 |  |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. MinioObjectStore: exists con stat_object (NoSuchKey falso, otros errores se propagan), put deduplica si ya existe y entrega el flujo con length sin leerlo antes, open envuelve la respuesta y libera la conexion al cerrar, claves inseguras con ValueError. Unitarias 14/14, suite 3446 verde en Linux (3 fallos preexistentes de main), integracion 4/4 contra moto; falta MinIO real (Kenni). Conformidad 0. (7657962) |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | QA independiente (subagente): APROBADO. Criterios de la parte 2 cumplidos; 7/7 mutantes detectados (M5 sobrevivia, ahora cubierto). Contrato sobre EncryptedObjectStore(MinioObjectStore) en verde; put que falla en la segunda parte de 15 MiB no deja objeto ni multipart. H3 (release_conn si close falla) arreglado con try/finally. Suite 3455 verde en Linux. Integracion solo contra moto, no MinIO real. (d401cf1) |
| verificación IA de implementacion | Codex, sin subagente independiente | 2026-11-11 | Se movio la prueba MinIO real a la ruta del SPEC, se renombro su homonima unitaria y se ajustaron imports QA. Verificado: pytest -q -m integration tests/integration/test_minio_object_store.py (4 passed); pytest -q tests/unit/test_minio_object_store_unit.py tests/unit/test_minio_object_store_qa.py (23 passed); diff --check limpio. La suite completa se ejecuto en Linux: 3387 passed, 29 failed y 11 errores por referencias .git del worktree Windows en el contenedor y pruebas historicas/artefactos ajenos a F-23; ejecucion Windows falla por fcntl/geteuid y colision ya corregida. (7dd2322) |
| implementacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó completar de forma autónoma las fases sin aprobación humana; verificación de IA registrada en 7dd2322. |
| verificación IA de verificacion | Codex | 2026-11-11 | F-23 parte 2: adaptador MinioObjectStore verificado; integración con MinIO real 4/4, unitarias y revisión IA independiente registradas antes; conformidad 0. Verificación de orquestación no independiente. (a4be525) |
| verificacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó completar autónomamente las fases con excepción; CI y MinIO real ya verificados y el control humano no está disponible. QA del orquestador no independiente. |
| verificación IA de documentacion | Codex | 2026-11-11 | Documentación de F-23 parte 2 revisada; bitácora publicada con resultados verificables de MinIO real y error real de IA; conformidad 0. Sin cambios posteriores a pruebas. (6d8793a) |
| documentacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó el avance autónomo. Documentación inspeccionada y bitácora oficial publicada. |
| verificación IA de revision | Codex | 2026-11-11 | Revisión contra SPEC F-23 parte 2: MinioObjectStore implementa exists/put/open, deduplica SHA-256, valida claves inseguras, libera conexión al cerrar y preserva el contrato de put fallido. Integración MinIO real 4/4, unitarias 23/23, sin secretos. QA del revisor no independiente. (3cbadc3) |
| revision | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó completar las fases de manera autónoma; revisión del diff contra SPEC y CI verde. |
| verificación IA de tests | Codex | 2026-11-11 | F-23 parte 3: staging del coordinador desde STAGING_DIR, MinIO cifrado obligatorio con KEK, TLS validado, dedup antes del staging, cliente evita chunks repetidos, volumen local persistente, script M3. Unitarias 115 passed, integración MinIO real 4 passed, conformidad 0. M3 medido pendiente por falta dataset/coordinador; verificación no independiente. (1ceae1e) |
| tests | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó completar autónomamente. Las pruebas se verifican en verde; el orden TDD de esta parte se completó en el stash previo y el test de composición añadido después. Se mantiene pendiente no estimada la medición de rendimiento. |
| verificación IA de implementacion | Codex | 2026-11-11 | Implementación F-23 parte 3 validada en el commit 1ceae1e: pruebas focalizadas 115 passed, MinIO real 4 passed, conformidad 0. Composición cifrada y staging persistente; sin dataset no hay medición de M3. QA no independiente. (673e304) |
| implementacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó autonomía; pruebas unitarias e integración real en verde, conformidad 0, CI pendiente. |
| verificación IA de verificacion | Codex | 2026-11-11 | QA F-23: dedup responde antes de staging; test prueba que no se crea manifiesto, cliente no envía chunks; composición minio cifrada siempre, TLS exige secure, volumen de staging montado. 115 unitarias, 4 MinIO real, conformidad 0. Medición M3 pendiente por ausencia de dataset/coordinador; verificación no independiente. (29a3d33) |
| verificacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó autonomía; funcionalidad probada. No se producen cifras de tasa sin dataset completo y entorno MinIO/coordinador con bucket limpio. |
| verificación IA de documentacion | Codex | 2026-11-11 | Documentación M3, variables, volumen y decisión AD-43 revisadas; bitácora F-23 publicada. Conformidad 0; faltan solo datos medidos del dataset real. (bf5e115) |
| documentacion | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó avance autónomo; documentación contrastada con código, SPEC y resultado de pruebas. |
| verificación IA de revision | Codex | 2026-11-11 | Corrección: crear OBJECTS_BUCKET al iniciar si falta, igual que otros adaptadores de almacenamiento. Prueba de composición lo verifica; 3 pruebas unitarias, conformidad 0. QA no independiente. (08e4f8e) |
| revision | José Andrés Loría Herrera | 2026-11-11 | José Andrés autorizó la ejecución autónoma; el requisito de crear bucket queda probado y la medición real sigue pendiente. |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente, no independiente. 14 pruebas: is_stored, POST 200 stored sin staging, cliente sin chunks, dos fuentes iguales un objeto (US-23), composicion desde entorno (sin MINIO_ENDPOINT None, bucket creado, STAGING_DIR obligatorio, TLS exige MinIO seguro, KEK envuelve con cifrado) y 503 si falla al arrancar. Rojo 13/14 por funcionalidad ausente. Contra borrador: 14/14, suite 3746 verde en Linux. (eb396b8c) |
