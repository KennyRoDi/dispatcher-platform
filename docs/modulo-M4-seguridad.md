# Módulo M4: seguridad

Estado: borrador de F-30 y de F-28 (parte 1). **Mediciones pendientes**: no hay salidas reales en este documento. Sin datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].

## 1. Qué se implementó

### F-30 Workers sin privilegios

Configuración (AD-36, SUP-32): `user: "10001:10001"`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, volumen `scratch` propio por worker en `/scratch` y `tmpfs` en `/tmp` de 64 MB. Está en `Dockerfile.worker`, `deploy/docker-compose.worker.yml` y `deploy/docker-compose.local.yml`.

### F-28 Cifrado en reposo

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

**Proveedor de la KEK (F-28 parte 2).**

Implementado en el proveedor de archivo (`FileKeyProvider`):

- `KEK_FILE`: ruta a un archivo regular de 32 bytes binarios, con modo exactamente 0400 o 0600, fuera del repositorio. Generación: `openssl rand -out <ruta> 32` y luego `chmod 0400 <ruta>`.
- `KEK`: base64 de 32 bytes, solo para desarrollo.
- `KEK_FILE` gana sobre `KEK`. Un valor vacío cuenta como no definido.
- Falla cerrado: sin KEK válida lanza `KeyUnavailable`. Un modo distinto de 0400/0600 o un archivo no regular también la lanza.
- Relee la fuente en cada llamada; no hay caché.
- `.gitignore` excluye `*.kek` y `kek*`.

## 2. Concepto de Sistemas Operativos

### F-30 Workers sin privilegios

Conceptos que respalda la configuración:

- **Usuarios y UID:** el proceso del worker corre con UID/GID `10001`, distinto de 0, de modo que una vulnerabilidad en FFmpeg o en un modelo no obtiene los privilegios de `root` dentro del contenedor [B.5 M4].
- **Capacidades de Linux:** `cap_drop: [ALL]` retira todas las capacidades del proceso y `no-new-privileges:true` impide recuperarlas con binarios setuid.
- **Namespaces:** el contenedor ve su propio árbol de procesos, montajes y usuarios; la raíz de solo lectura (`read_only: true`) impide modificar el sistema de archivos de la imagen.
- **cgroups:** el volumen `scratch` en `/scratch` cuenta contra el cgroup del contenedor, a diferencia de `tmpfs`, por eso el video grande va a `/scratch` y no a memoria.

### F-28 Cifrado en reposo

Conceptos que respalda el diseño, sin datos medidos:

- **Cifrado de sobre:** cada objeto tiene su propia llave de datos (DEK, 32 bytes de `os.urandom`) envuelta con la llave maestra del nodo (KEK); la KEK no se escribe en el repositorio ni en el historial [B.5 M4].
- **Memoria:** el objeto se procesa por chunks, de modo que la memoria usada queda acotada a un chunk (4 MiB por defecto, tope de 64 MiB) y no al tamaño del archivo.
- **Integridad:** AES-256-GCM autentica cada chunk; reordenar, duplicar o truncar chunks hace fallar el descifrado.
- **Permisos de archivo:** el proveedor `FileKeyProvider` exige que el archivo de la KEK sea regular y de modo 0400 o 0600, para que otros usuarios del sistema no puedan leerlo.

## 3. Método de medición

### F-30 Workers sin privilegios

```bash
python -m scripts.verificar_workers
```

Salida: pendiente: se mide en los tres nodos reales. El código de salida 0 indica sin incumplimientos.

Sustituye `<worker>` por el nombre del contenedor.

```bash
docker exec <worker> id -u
docker exec <worker> touch /x
docker inspect --format '{{.Config.User}}' <worker>
docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' <worker>
docker inspect --format '{{.HostConfig.CapDrop}}' <worker>
docker inspect --format '{{.HostConfig.SecurityOpt}}' <worker>
```

### F-28 Cifrado en reposo

Pendiente: costo de CPU y tamaño de chunk óptimo se miden con los comandos de `docs/IMPLEMENTACION.md` §5 (busca `F-28`); este documento no los reproduce y no contiene salidas medidas.

Búsqueda de llaves en el historial (la automatiza `test_historial_sin_llaves`):

```bash
git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'
```

## 4. Resultados

### F-30 Workers sin privilegios

Pendiente: sin evidencia medida en tres nodos reales. Las salidas esperadas y su estado:

| Comando | Esperado | Salida medida |
|---|---|---|
| `id -u` | distinto de 0 | pendiente: se mide en los tres nodos reales |
| `touch /x` | falla (sistema de archivos de solo lectura) | pendiente: se mide en los tres nodos reales |
| `.Config.User` | `10001:10001` | pendiente: se mide en los tres nodos reales |
| `ReadonlyRootfs` | `true` | pendiente: se mide en los tres nodos reales |
| `CapDrop` | contiene `ALL` | pendiente: se mide en los tres nodos reales |
| `SecurityOpt` | contiene `no-new-privileges:true` | pendiente: se mide en los tres nodos reales |

Nodos: José, Nahúm y Melany; cada uno captura sus salidas.

### F-28 Cifrado en reposo

Pendiente: sin datos medidos de costo de CPU, de tamaño de chunk ni de costo de leer la KEK en cada llamada.

## 5. Interpretación

### F-30 Workers sin privilegios

Pendiente. Las pruebas unitarias y `python -m scripts.verificar_workers` respaldan que la configuración está escrita, no que el kernel la aplique en los nodos. Sin evidencia medida en los tres nodos reales, el módulo M4 tiene máximo 2 [Parte I §5].

### F-28 Cifrado en reposo

Pendiente. Las pruebas unitarias respaldan el formato y la detección de alteraciones, no el costo de CPU en los nodos. Sin ficha con datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].
