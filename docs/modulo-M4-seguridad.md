# Módulo M4: seguridad

**Responsable:** Kenni Rodriguez. **Corte:** borrador de F-28 parte 1. **Mediciones de SO: pendientes.** Esta ficha no acredita el módulo.

## Cifrado en reposo (F-28)

Implementado en `src/adapters/envelope_cipher.py` (decisión AD-34, SUP-30 en `docs/ARQUITECTURA.md` y `docs/REQUERIMIENTOS.md`).

**Biblioteca de terceros:** `cryptography==50.0.2` (Apache-2.0 o BSD-3-Clause), https://github.com/pyca/cryptography; se usa `AESGCM`. Fuente de la construcción: NIST SP 800-38D.

**Formato de cable** (big-endian):

| Campo | Bytes |
|---|---|
| Magia `EVC1` | 4 |
| Versión (1) | 1 |
| Tamaño de chunk | 4 |
| Prefijo de nonce aleatorio | 4 |
| Nonce de envoltura | 12 |
| DEK envuelta por la KEK | 32 |
| Etiqueta GCM de la DEK | 16 |
| Chunks: texto cifrado + etiqueta | tamaño de chunk + 16 cada uno |

Nonce de chunk: prefijo de 4 B más contador de 8 B. AAD de chunk: cabecera fija, SHA-256 del claro, índice y marca de último. Tope de chunk: 64 MiB.

**Límites:** cifrar no oculta el tamaño del objeto; `decrypt` entrega los chunks ya autenticados antes de fallar en uno alterado. Detalle en `docs/specs/F-28/SPEC.md`.

**Mediciones:** costo de CPU y tamaño de chunk óptimo: pendiente, sin datos medidos.

### Proveedor de la KEK (F-28 parte 2)

Implementado en el proveedor de archivo (`FileKeyProvider`).

- `KEK_FILE`: ruta a un archivo regular de 32 bytes binarios, con modo exactamente 0400 o 0600, fuera del repositorio. Generación: `openssl rand -out <ruta> 32` y luego `chmod 0400 <ruta>`.
- `KEK`: base64 de 32 bytes, solo para desarrollo.
- `KEK_FILE` gana sobre `KEK`. Un valor vacío cuenta como no definido.
- Falla cerrado: sin KEK válida lanza `KeyUnavailable`. Un modo distinto de 0400/0600 o un archivo no regular también la lanza.
- Relee la fuente en cada llamada; no hay caché.
- `.gitignore` excluye `*.kek` y `kek*`.
- Búsqueda de llaves en el historial: `git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'` (la automatiza `test_historial_sin_llaves`).

**Mediciones:** costo de leer la KEK en cada llamada: pendiente, sin datos medidos.

### Decorador de almacén cifrado (F-28 parte 3)

Implementado en `src/adapters/encrypted_object_store.py` (`EncryptedObjectStore`), decorador de `ObjectStore`.

- `put` cifra el flujo con `EnvelopeCipher` antes de entregarlo al almacén interno; `open` descifra al leer. La clave sigue siendo el SHA-256 del claro (AD-11), por eso `exists` se delega sin cambios.
- Cifra el contenido del objeto (cabecera, DEK envuelta y chunks con etiqueta). No cifra la clave ni oculta el tamaño.
- Al almacén interno se le informa el tamaño del objeto cifrado: cabecera + claro + una etiqueta por chunk.
- `open` descifra el primer chunk al abrir: un objeto corrupto o una KEK errónea fallan en `open`, no en la primera lectura.
- **El cableado al adaptador MinIO no está hecho.** Ese adaptador es de F-23 (Melany); hoy `src/workers/storage.py` usa el cliente directo. Este decorador aún no se usa en el flujo real.

**Justificación (AD-16, AD-34):** AES-256-GCM en la aplicación protege también contra quien lee MinIO, lo que SSE del lado del servidor no cubre. Una DEK por objeto envuelta por una KEK de archivo `0400` evita reutilizar nonces. Se eligió sobre MinIO SSE, LUKS y Vault por costo operativo con el tiempo disponible. Detalle en `docs/ARQUITECTURA.md` §8.

#### Prueba I contra MinIO real

Archivo: `tests/integration/test_encrypted_object_store_minio.py`. Usa un adaptador mínimo solo de prueba. Sin las variables, se salta.

```bash
export MINIO_ENDPOINT=<host:puerto> MINIO_ACCESS_KEY=<usuario> MINIO_SECRET_KEY=<clave>
pytest -q -m integration tests/integration/test_encrypted_object_store_minio.py
```

**Salida:** pendiente: la prueba I no se ha ejecutado contra MinIO real. Sin datos.

#### Búsqueda de llaves en el historial

Automatizada en `tests/unit/test_historial_sin_llaves.py`. Comando manual: `git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'`.

**Salida:** pendiente: la prueba I no se ha ejecutado contra MinIO real; la búsqueda manual tampoco se ha registrado aquí.

**Mediciones:** costo de CPU del decorador: pendiente, sin datos medidos.
