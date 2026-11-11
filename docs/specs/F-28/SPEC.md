# SPEC F-28: Cifrado en reposo

**Fase:** plan
**Base:** main
**Verificación IA:** pendiente
**Historia:** US-28 · **Requisitos:** RF-37, RNF-08 · **Responsable:** K

## Objetivo

Hoy quien lee MinIO ve las evidencias en claro, y las llaves de acceso tienen valores por defecto en archivos de despliegue. El enunciado exige «cifrado en reposo de las evidencias con gestión de llaves justificada» y que las llaves no estén en el código [B.5 M4]. Esta feature cifra cada objeto antes de que llegue a MinIO con AES-256-GCM, protege la llave de cada objeto con una KEK que vive fuera del repositorio, y falla cerrado si la KEK falta o si un byte del objeto cambió (RF-37, RNF-08). La llave se justifica en AD-16 y la decisión de formato en AD-34.

## Alcance

**Incluye:**
- `EnvelopeCipher`: cifrado de sobre por objeto, en flujo y por chunks, con detección de alteración, reordenamiento y truncamiento.
- Puerto `KeyProvider` y adaptador que lee la KEK de un archivo (`KEK_FILE`, permisos `0400`) o, solo para desarrollo, de la variable `KEK`.
- `EncryptedObjectStore`: decorador de `ObjectStore` que cifra en `put` y descifra en `open`, sin cambiar el puerto.
- Doble de `KeyProvider` y prueba de contrato.
- Prueba I contra MinIO real y búsqueda de llaves en el historial de Git, con sus comandos para la ficha M4.
- Registro de AD-34 y SUP-30.

**No incluye:**
- El adaptador MinIO de `ObjectStore` (F-23, Melany) ni el cableado en workers y coordinador: se declara el punto de composición y su dueño lo conecta.
- Rotación de la KEK, KMS o Vault (AD-16 los descarta), derivación de llave desde contraseña.
- Cifrado de Redis, de `/scratch` o de logs; TLS en tránsito (F-27); cadena de custodia (F-29).
- Cifrado de metadatos como el nombre de objeto (es el SHA-256 del claro, AD-11).

## Criterios de aceptación

Copiados de `docs/backlog/m4-seguridad.md`:

- **Dado** una evidencia almacenada con un marcador sintético
- **Cuando** se lee directo de MinIO, o se busca en el historial de Git
- **Entonces** no contiene el marcador, un byte alterado hace fallar el descifrado, falla sin KEK y no hay llaves en el historial

Concretado:
1. El objeto leído con el cliente de MinIO sin pasar por el decorador no contiene el marcador sintético.
2. Ida y vuelta: `open(put(x))` devuelve exactamente `x`, también para objetos vacíos, de un chunk y de varios chunks.
3. Alterar un byte en cualquier posición (cabecera, llave envuelta, cuerpo, etiqueta), quitar o reordenar chunks o truncar el final hace que la lectura lance `DecryptionError`; nunca devuelve datos parciales como válidos.
4. Sin KEK (archivo ausente, vacío, de longitud distinta de 32 bytes o legible por grupo u otros) el decorador no arranca la operación y lanza `KeyUnavailable`; nunca guarda en claro.
5. Dos nonces nunca se repiten bajo una misma llave: el nonce de cada chunk es único por construcción.
6. `git log -p --all` no contiene llaves privadas ni `MINIO_SECRET_KEY=` con valor; la KEK no está en el repositorio.

## Diseño

**Contratos.** Implementa el envoltorio de `ObjectStore` de `docs/CONTRATOS.md` (Kenni lo envuelve con cifrado, F-28). Usa `ObjectStore.exists/put/open` tal como están. `exists` se delega sin descifrar, porque la clave es el SHA-256 del claro (AD-11).

**Capas y archivos** (`tests/unit/test_arquitectura.py` hace cumplir las dependencias):

| Capa | Archivo | Contenido |
|---|---|---|
| Aplicación | `src/application/ports.py` | Puerto `KeyProvider.kek() -> bytes`; errores `KeyUnavailable` y `DecryptionError`. |
| Adaptador | `src/adapters/envelope_cipher.py` | `EnvelopeCipher.encrypt(stream, sha256) -> Iterator[bytes]` y `decrypt(stream, sha256) -> Iterator[bytes]`, con `cryptography` (AESGCM). |
| Adaptador | `src/adapters/file_key_provider.py` | `FileKeyProvider`: lee `KEK_FILE` (o `KEK` en base64 solo en desarrollo), exige 32 bytes y que el modo no dé permisos a grupo ni otros. |
| Adaptador | `src/adapters/encrypted_object_store.py` | `EncryptedObjectStore(inner, cipher)`: implementa `ObjectStore`. |
| Pruebas | `tests/dobles.py`, `tests/contratos.py` | `FakeKeyProvider`; contrato `KeyProvider` para doble y `FileKeyProvider`. |

**Formato del objeto (AD-34, provisional).** Cabecera: magia de 4 bytes, versión de 1 byte, tamaño de chunk de 4 bytes, prefijo de nonce aleatorio de 4 bytes, DEK envuelta por la KEK. Luego chunks, cada uno AES-256-GCM.
- **DEK por objeto**, 32 bytes aleatorios de `os.urandom`, envuelta con AES-256-GCM bajo la KEK con un nonce aleatorio propio y el SHA-256 del claro como dato asociado (AAD). Así un objeto no se puede copiar bajo otra clave de MinIO sin que falle.
- **Nonce por chunk** de 12 bytes: prefijo aleatorio de 4 bytes más contador de 8 bytes por chunk. Con una DEK por objeto, el contador garantiza unicidad sin depender del azar; la cota de NIST para nonces aleatorios (2^32 invocaciones por llave) no se alcanza nunca [R9, NIST SP 800-38D §8.3].
- **AAD de cada chunk:** SHA-256 del claro, índice del chunk y una marca de «último chunk». Esto detecta reordenar, duplicar o truncar chunks, algo que GCM por sí solo no detecta.
- **Tamaño de chunk:** 4 MiB, igual al protocolo de AD-10; el objeto se procesa en flujo con memoria acotada a un chunk. Provisional: **Medición pendiente**, el costo de CPU y el sobrecosto de almacenamiento (28 bytes por chunk más la cabecera) se miden en la ficha M3/M4 si se necesita.
- **Alternativas de nonce:** (a) 96 bits aleatorios por chunk: más simple, pero la unicidad es probabilística; (b) contador determinista con DEK por objeto (elegida): unicidad exacta; (c) SIV (AES-GCM-SIV): resistente a repetición pero no está en la librería estándar de `cryptography` en todas las versiones y añade complejidad sin necesidad con DEK por objeto.
- **Biblioteca:** `cryptography` (Apache-2.0/BSD), citada en el código y en `docs/modulo-M4-seguridad.md` [Parte I §9]. La versión exacta se fija en la parte 1 tras comprobarla con `pip`; no se afirma aquí.

**KEK (AD-16 aplicada).** `KEK_FILE` apunta a un archivo fuera del repositorio con 32 bytes aleatorios (generado con `openssl rand -out ... 32` y `chmod 0400`), montado en el nodo como secreto. La variable `KEK` (base64) existe solo para desarrollo y pruebas. Nunca se registra su valor ni se deriva de otra cosa. Sin KEK, `put` y `open` lanzan `KeyUnavailable` y no tocan MinIO. Se añaden al `.gitignore` los patrones `*.kek` y `kek*` si faltan.

**Composición.** El decorador se instancia donde se arma el almacén (coordinador y workers) como `EncryptedObjectStore(MinioObjectStore(...), EnvelopeCipher(FileKeyProvider.from_env()))`. Esa línea pertenece a quien cablea el adaptador MinIO (F-23); esta feature entrega el decorador listo y lo documenta.

**Puertos y dobles.** El decorador se prueba con `FakeObjectStore` y `FakeKeyProvider`, sin red. La parte de MinIO real usa un adaptador mínimo solo de prueba sobre el cliente `minio`, no un entregable.

**Reutilización.** Del I Proyecto no se reutiliza nada. `minio` ya está en `requirements.txt`.

**Decisiones nuevas** (se registran en `docs/ARQUITECTURA.md` §8 en la parte 1; los números se comprobaron libres en todas las ramas remotas: el mayor visto es AD-33 y SUP-29):
- **AD-34**, formato de objeto cifrado: DEK por objeto envuelta por la KEK con SHA-256 como AAD; nonce de chunk = prefijo aleatorio + contador; AAD por chunk con índice y marca de último. Alternativas: nonce aleatorio por chunk; AES-GCM-SIV; AES Key Wrap (RFC 3394) para la DEK. Criterio: unicidad exacta del nonce y detección de truncamiento y reordenamiento. Medición pendiente: tamaño de chunk y costo de CPU.
- **SUP-30**, la KEK es un secreto de 32 bytes por nodo; se admite que cada nodo tenga la misma KEK porque todos leen los mismos objetos, y se declara que la rotación queda fuera. El enunciado no fija el origen de la llave.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_ida_y_vuelta_aes_gcm` (vacío, 1 chunk, varios chunks, límite exacto de chunk) | El descifrado recupera el claro |
| Unitaria | `test_chunk_alterado_falla_autenticacion` parametrizada por posición (cabecera, DEK envuelta, cuerpo, etiqueta) | Un byte alterado lanza `DecryptionError` |
| Unitaria | `test_chunks_reordenados_o_truncados_fallan` | AAD con índice y marca de último |
| Unitaria | `test_nonce_no_se_repite` | Los nonces de todos los chunks de un objeto y de objetos distintos son distintos |
| Unitaria | `test_falla_si_falta_kek`, `test_kek_de_largo_invalido`, `test_kek_legible_por_otros_se_rechaza` | Falla cerrado y nunca guarda en claro |
| Unitaria | `test_objeto_copiado_bajo_otra_clave_falla` | El SHA-256 como AAD ata el objeto a su clave |
| Unitaria | `test_decorador_cumple_objectstore` con `FakeObjectStore` | `exists/put/open` conservan el contrato; el almacén interno solo ve bytes sin el marcador |
| Contrato | `KeyProvider` sobre doble y `FileKeyProvider` | Ambos cumplen el puerto |
| Integración (`integration`) | `test_objeto_real_en_minio_no_contiene_marcador` | Leer directo de MinIO no muestra el marcador y la ida y vuelta funciona |
| Integración (`integration`) | `test_byte_alterado_en_minio_falla` | Alterar el objeto guardado hace fallar el descifrado |
| Unitaria | `test_historial_sin_llaves` (llama al comando de §Mediciones sobre el repositorio) | RNF-08 |
| Aceptación | Ejecución de los comandos de `docs/IMPLEMENTACION.md` §5 para F-28 | Evidencia para la ficha M4 |

## Mediciones

No aplica. F-28 aporta a la ficha M4 evidencia de ejecución, no mediciones de SO M1–M5: la salida de la prueba I con MinIO real y la búsqueda de llaves en el historial (`git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'` y `gitleaks detect` si está disponible, según `docs/IMPLEMENTACION.md` §5). Se registran con el comando exacto en `docs/modulo-M4-seguridad.md`. Sin ejecutarlos no se escribe ningún resultado. El sobrecosto de CPU del cifrado, si se quiere reportar, es una medición aparte y queda pendiente.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-28): cifrado de sobre AES-256-GCM por chunks` | `EnvelopeCipher`, errores en `ports.py`, dependencia `cryptography` en `requirements.txt`, registro de AD-34 y SUP-30. Aprox. 150 líneas. |
| 2 | `feat(F-28): llaves de cifrado fuera del código` | Puerto `KeyProvider`, `FileKeyProvider` (archivo `0400`, 32 bytes, falla cerrado), `FakeKeyProvider`, contrato, `.gitignore`. Aprox. 80 líneas. |
| 3 | `feat(F-28): decorador de almacén cifrado` | `EncryptedObjectStore`, prueba I contra MinIO real, comando de búsqueda de llaves en el historial, borrador de la sección en `docs/modulo-M4-seguridad.md`. Aprox. 70 líneas. |

## Riesgos y preguntas abiertas

1. **Adaptador MinIO de `ObjectStore`.** No existe en `src/` (F-23, Melany; hoy `src/workers/storage.py` usa el cliente directo). ¿Se acepta probar con un adaptador mínimo de prueba y dejar el cableado a su dueña? Alternativa: esperar F-23.
2. **Origen de la KEK (SUP-30).** ¿Una KEK por nodo con el mismo valor, o por entorno? Cómo se distribuye a los tres nodos reales es una decisión operativa de F-38.
3. **Variable `KEK` para desarrollo.** ¿Se admite o solo archivo? Admitirla facilita pruebas y es un riesgo si se usa en producción.
4. **Tamaño de chunk 4 MiB.** Provisional, sin medición; confirmar que coincide con el de F-10 y AD-10.
5. **Costo de CPU.** El cifrado añade trabajo por petición; ¿se repiten M1 a M3 o se mide aparte?
6. **Versión de `cryptography`.** Se fija en la parte 1 tras comprobarla; no se afirma aquí.
7. **Credenciales de MinIO por defecto en `deploy/docker-compose.local.yml`** (`minioadmin`): son de desarrollo local y la búsqueda de RNF-08 podría marcarlas. ¿Se aceptan como valores de demo declarados o se retiran?
8. **Dedup (AD-11).** Cifrar con nonce y DEK distintos impide deduplicar sobre el cifrado; se mantiene la clave SHA-256 del claro, que revela objetos iguales. Riesgo ya aceptado en AD-11.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
