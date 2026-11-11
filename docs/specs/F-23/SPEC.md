# SPEC F-23: Almacenamiento por contenido

**Fase:** documentacion
**Base:** main
**Verificación IA:** verificacion b8ec62f
**Historia:** US-23 · **Requisitos:** RF-32, [B.5 M3] · **Responsable:** V

## Objetivo

El enunciado pide «manejo eficiente de archivos grandes» [B.5 M3] y RF-32 exige almacenamiento direccionado por contenido con deduplicación. Hoy no hay adaptador de producción de `ObjectStore`: las rutas de subida de F-22 responden 503 y F-28 prueba el cifrado con un adaptador mínimo solo de prueba. F-23 entrega `MinioObjectStore`, que guarda cada objeto con su SHA-256 como clave y no vuelve a guardar un contenido que ya existe. Además, la subida por chunks pregunta antes de transferir: si el contenido ya está, no se envía ni un byte. El operador ahorra espacio y red, y la ficha M3 reporta la tasa de deduplicación medida.

## Alcance

**Incluye:**
- Regla del contrato `ObjectStore` pendiente de F-22 (riesgo 8): `put` no confirma el objeto si la lectura de `content` lanza una excepción, y `open` de una clave inexistente lanza `KeyError`.
- Adaptador `MinioObjectStore` sobre el cliente `minio` ya usado en el I Proyecto, con validación de clave SHA-256 y deduplicación en `put`.
- Deduplicación antes de transferir en `POST /uploads` y en el cliente `scripts/subir_por_chunks.py`.
- Composición en el coordinador desde variables de entorno, con TLS según `src/infrastructure/tls.py`, para que las rutas de subida dejen de responder 503.
- Script de medición de la tasa de deduplicación y su sección en la ficha M3.

**No incluye:** deduplicación por bloques o chunks (AD-11 la descarta); recolección de objetos sin referencias; cifrado (F-28, Kenni); cambios en `deploy/` (Kenni); el catálogo de casos, que ya referencia fuentes por SHA-256 (`CaseSource.sha256`).

## Criterios de aceptación

De `docs/backlog/m3-es-almacenamiento.md` (US-23):

- **Dado** dos fuentes con el mismo contenido
- **Cuando** se almacenan
- **Entonces** existe un solo objeto, con clave SHA-256, referenciado por ambas

Criterios adicionales derivados de los requisitos:

- RF-32: la clave de cada objeto es el SHA-256 en minúsculas de su contenido en claro (AD-11); una clave que no sea de 64 hexadecimales se rechaza con `ValueError` sin tocar MinIO.
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

**Decisiones.** Aplica AD-10, AD-11 y AD-28. Propone AD-41: «Deduplicación antes de transferir en el protocolo de chunks», que se registra en `docs/ARQUITECTURA.md` §8 en la parte que la implemente.

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

El script sube cada archivo con `subir_por_chunks` a un coordinador con MinIO y reporta bytes lógicos, bytes guardados (suma de los objetos del bucket) y `1 − bytes_guardados / bytes_lógicos`. Tres repeticiones; la primera parte de un bucket vacío. Ficha de destino: `docs/modulo-M3-es-almacenamiento.md`, sección de deduplicación. No mide entre nodos, así que no depende de F-38.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `test(F-23): exigir que objectstore no confirme un put fallido` | Solo el contrato, según «Cambiar un contrato»: `tests/contratos.py`, `docs/CONTRATOS.md` y su aplicación al doble y a `EncryptedObjectStore`. Estimado: ~40 líneas |
| 2 | `feat(F-23): guardar objetos por contenido en minio` | `src/adapters/minio_object_store.py`, pruebas unitarias e integración con MinIO real. Estimado: ~120 líneas |
| 3 | `feat(F-23): deduplicar subidas antes de transferir` | `start`, ruta, cliente, `src/infrastructure/almacen.py` y la línea de `main.py`; AD-41. Va después de fusionar F-22 parte 2 (#98). Estimado: ~150 líneas |
| 4 | `docs(F-23): medir tasa de deduplicacion` | `scripts/measure/m3_dedup.py` y sección de la ficha M3 con datos medidos |

## Riesgos y preguntas abiertas

1. **Cambio de contrato.** La parte 1 va sola y hay que avisar a Kenni (F-28) y a quienes consumen `ObjectStore`. Es aditivo: el doble y `EncryptedObjectStore` ya lo cumplen hoy. ¿Se aprueba como primera PR?
2. **Cifrado en la composición.** ¿Quién envuelve `MinioObjectStore` con `EncryptedObjectStore`? Propuesta: la parte 3 lo hace si hay KEK configurada y, si no, guarda en claro, sin decidir por Kenni. Hay que confirmarlo con él.
3. **Cambio del protocolo de F-22.** `POST /uploads` pasa a responder 200 `stored` además de 201. El cliente de F-22 se actualiza en la misma parte; no hay otros consumidores.
4. **Variables de entorno y bucket.** Hay que coordinar con Kenni en `deploy/` las variables, el bucket `objetos` y el volumen de staging (riesgo 5 de F-22).
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
