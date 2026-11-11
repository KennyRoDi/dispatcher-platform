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
