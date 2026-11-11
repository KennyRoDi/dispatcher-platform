# Módulo M4: seguridad

Estado: borrador de F-30, F-28 (partes 1 a 3) y F-27 (parte 1). **Mediciones pendientes**: no hay salidas reales en este documento. Sin datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].

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

**Decorador de almacén cifrado (F-28 parte 3).**

Implementado en `src/adapters/encrypted_object_store.py` (`EncryptedObjectStore`), decorador de `ObjectStore`.

- `put` cifra el flujo con `EnvelopeCipher` antes de entregarlo al almacén interno; `open` descifra al leer. La clave sigue siendo el SHA-256 del claro (AD-11), por eso `exists` se delega sin cambios.
- Cifra el contenido del objeto (cabecera, DEK envuelta y chunks con etiqueta). No cifra la clave ni oculta el tamaño.
- Al almacén interno se le informa el tamaño del objeto cifrado: cabecera + claro + una etiqueta por chunk.
- `open` descifra el primer chunk al abrir: un objeto corrupto o una KEK errónea fallan en `open`, no en la primera lectura.
- **El cableado al adaptador MinIO no está hecho.** Ese adaptador es de F-23 (Melany); hoy `src/workers/storage.py` usa el cliente directo. Este decorador aún no se usa en el flujo real.

**Justificación (AD-16, AD-34):** AES-256-GCM en la aplicación protege también contra quien lee MinIO, lo que SSE del lado del servidor no cubre. Una DEK por objeto envuelta por una KEK de archivo `0400` evita reutilizar nonces. Se eligió sobre MinIO SSE, LUKS y Vault por costo operativo con el tiempo disponible. Detalle en `docs/ARQUITECTURA.md` §8.

### F-27 TLS entre nodos

**Responsable:** Kenni Rodriguez. Decisión: AD-37 y SUP-33 en [ARQUITECTURA](ARQUITECTURA.md) §8 y [REQUERIMIENTOS](REQUERIMIENTOS.md). Diseño: `docs/specs/F-27/SPEC.md`.

Parte 1:

- `src/infrastructure/tls.py`: `TlsSettings.from_env` (`TLS_ENABLED`, `TLS_CA_FILE`; falla cerrado si falta la CA o no es legible), `client_context` (TLS 1.3 mínimo, `CERT_REQUIRED`, verificación de hostname), `exigir_cifrado` (rechaza `http://`, `redis://` y `MINIO_SECURE=false` con TLS activo) y constructores `redis_kwargs`, `requests_session` y `minio_http_client`.
- `requests_session` usa `trust_env=False` y `verify` fijo a la CA del equipo, de modo que `REQUESTS_CA_BUNDLE`, proxies y `.netrc` no lo alteran, y rechaza redirecciones de https a un esquema en claro.
- Pruebas unitarias y de integración con sockets locales y certificados efímeros de `trustme`, generados dentro de la prueba y sin versionar ninguno.
- Todavía no hay cableado en workers, coordinador ni scripts (parte 2), ni servidores con TLS ni `generar_certs.sh` (parte 3).

**Fuentes y dependencias de terceros:**

- Módulo `ssl` de Python, `openssl`, `redis-py`, `minio-py` y `requests`.
- `trustme` 1.2.1, solo desarrollo (`requirements-dev.txt`): licencia MIT o Apache-2.0 según `pip show trustme`; https://github.com/python-trio/trustme.
- RFC 8446 (TLS 1.3); RFC 6125 y RFC 9525 (verificación de identidad del servidor).

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

### F-27 TLS entre nodos

TLS protege el canal entre procesos de distintos nodos: cifra, comprueba la integridad y autentica al servidor con una cadena de confianza. El módulo `ssl` de Python delega en OpenSSL; el cliente decide con qué CA confía y qué versión mínima acepta. JWT (F-26) identifica a quien llama; no protege el canal. Tailscale tampoco sustituye a TLS: la captura debe mostrar el handshake (`docs/ARQUITECTURA.md` §6).

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

Prueba I contra MinIO real.

Archivo: `tests/integration/test_encrypted_object_store_minio.py`. Usa un adaptador mínimo solo de prueba. Sin las variables, se salta.

```bash
export MINIO_ENDPOINT=<host:puerto> MINIO_ACCESS_KEY=<usuario> MINIO_SECRET_KEY=<clave>
pytest -q -m integration tests/integration/test_encrypted_object_store_minio.py
```

Búsqueda de llaves en el historial (la automatiza `tests/unit/test_historial_sin_llaves.py`):

```bash
git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'
```

### F-27 TLS entre nodos

Comandos exactos de `docs/IMPLEMENTACION.md` §5; los ejecuta la persona en el Nodo A con `sudo`, con la IP real de Tailscale:

```bash
sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'
tshark -r m4.pcap -Y tls.handshake.type==1
strings m4.pcap | grep -c <marcador_sintetico>
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

Pendiente: sin datos medidos de costo de CPU, de tamaño de chunk, de costo de leer la KEK en cada llamada ni de costo de CPU del decorador.

**Salida de la prueba I:** ejecutada una vez, de forma local (una máquina, MinIO efímero en Docker, sin TLS ni red entre nodos): 2 pruebas pasadas; el objeto crudo en MinIO no contiene el marcador en claro y un bit alterado lanza `DecryptionError`. Salida completa en [docs/evidencia/F-28_prueba_I_minio_local_2026-11-11.md](evidencia/F-28_prueba_I_minio_local_2026-11-11.md). No es evidencia en los tres nodos ni mide costo de CPU.

**Salida de la búsqueda en el historial:** pendiente: la búsqueda manual en el historial no se ha registrado aquí. La prueba automática `tests/unit/test_historial_sin_llaves.py` sí corre en la suite y pasa.

### F-27 TLS entre nodos

| Medición | Resultado |
|---|---|
| Handshakes TLS en la captura (`tshark`) | pendiente |
| Coincidencias del marcador (`strings ... \| grep -c`) | pendiente |
| Cliente sin la CA rechazado en los servicios reales | pendiente |
| Costo de TLS sobre el throughput de M3 | pendiente |

## 5. Interpretación

### F-30 Workers sin privilegios

Pendiente. Las pruebas unitarias y `python -m scripts.verificar_workers` respaldan que la configuración está escrita, no que el kernel la aplique en los nodos. Sin evidencia medida en los tres nodos reales, el módulo M4 tiene máximo 2 [Parte I §5].

### F-28 Cifrado en reposo

Pendiente. Las pruebas unitarias respaldan el formato y la detección de alteraciones, no el costo de CPU en los nodos. Sin ficha con datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].

### F-27 TLS entre nodos

Pendiente. Sin captura real no hay resultado de TLS y el módulo no pasa de 2 [Parte I §5]. `m4.pcap` queda fuera del repo; solo se versiona el resumen de `tshark`.
