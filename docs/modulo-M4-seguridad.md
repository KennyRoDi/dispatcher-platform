# Módulo M4: seguridad

**Responsable:** Kenni Rodriguez (`KennyRoDi`).

Estado: evidencia parcial de F-26 a F-30. Existen ejecuciones reales locales de roles, cifrado en reposo, custodia, TLS de servidores y worker sin privilegios (sección 4). No acreditan captura de tráfico entre nodos ni todos los controles del despliegue. La regla de Parte I §5 aplica a módulos sin ficha con datos medidos; los datos locales existentes no equivalen a cumplimiento completo de M4.

## 1. Qué se implementó

### F-30 Workers sin privilegios

Configuración (AD-36, SUP-32): `user: "10001:10001"`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, volumen `scratch` propio por worker en `/scratch` y `tmpfs` en `/tmp` de 64 MB. Está en `Dockerfile.worker`, `deploy/docker-compose.worker.yml` y `deploy/docker-compose.local.yml`.

### F-26 Autenticación y roles

Decisión AD-33 (provisional; SUP-28 y SUP-29). Fuente de la matriz: `src/domain/rbac.py` (`PERMISOS`).

| Rol | crear_caso | consultar_caso | cancelar_caso | ver_monitoreo | reportar_subtarea |
|---|---|---|---|---|---|
| analista | sí | sí | no | no | no |
| supervisor | no | sí | sí | sí | no |
| administrador | sí | sí | sí | sí | no |
| servicio | no | no | no | no | sí |

El rol `servicio` es para los workers (`POST /subtasks/report`).

**Token.**

- JWT firmado con HS256 (decisión AD-33), con PyJWT (licencia MIT, https://github.com/jpadilla/pyjwt).
- Claims usados: `sub`, rol, `iat`, `exp`. El coordinador rechaza `sub` vacío y fechas no finitas.
- Se envía como `Authorization: Bearer <token>`.

**Secreto.** El secreto nunca va en el repositorio. Generarlo fuera de él:

```bash
openssl rand -hex 32 > ~/jwt.secret
chmod 600 ~/jwt.secret
export JWT_SECRET_FILE=~/jwt.secret
```

`JWT_SECRET` (variable directa) se admite, pero se prefiere el archivo. `.gitignore` cubre `jwt.secret`, `*.key` y `.env`.

**AUTH_ENABLED.** Activa por defecto. Solo `0`, `false`, `no` u `off` la desactivan (`src/coordinator/main.py`). Desactivarla es solo para pruebas locales.

**Emitir un token.**

```bash
PYTHONPATH=. python scripts/emitir_token.py --rol supervisor --sub demo-supervisor --minutos 30
```

Roles: `analista`, `supervisor`, `administrador`, `servicio`.

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

**Parte 1.**

- `src/infrastructure/tls.py`: `TlsSettings.from_env` (`TLS_ENABLED`, `TLS_CA_FILE`; falla cerrado si falta la CA o no es legible), `client_context` (TLS 1.3 mínimo, `CERT_REQUIRED`, verificación de hostname), `exigir_cifrado` (rechaza `http://`, `redis://` y `MINIO_SECURE=false` con TLS activo) y constructores `redis_kwargs`, `requests_session` y `minio_http_client`.
- `requests_session` usa `trust_env=False` y `verify` fijo a la CA del equipo, de modo que `REQUESTS_CA_BUNDLE`, proxies y `.netrc` no lo alteran, y rechaza redirecciones de https a un esquema en claro.
- Pruebas unitarias y de integración con sockets locales y certificados efímeros de `trustme`, generados dentro de la prueba y sin versionar ninguno.
- Todavía no hay cableado en workers, coordinador ni scripts (parte 2), ni servidores con TLS ni `generar_certs.sh` (parte 3).

**Fuentes y dependencias de terceros:**

- Módulo `ssl` de Python, `openssl`, `redis-py`, `minio-py` y `requests`.
- `trustme` 1.2.1, solo desarrollo (`requirements-dev.txt`): licencia MIT o Apache-2.0 según `pip show trustme`; https://github.com/python-trio/trustme.
- RFC 8446 (TLS 1.3); RFC 6125 y RFC 9525 (verificación de identidad del servidor).

**Parte 2: cómo se activa.**

- `TLS_ENABLED=true` y `TLS_CA_FILE=<ruta a ca.pem>`; sin CA legible el arranque falla.
- Coordinador y scripts: URLs `https://`. Redis: `rediss://`. MinIO: `MINIO_SECURE=true`.
- Con TLS activo, una URL `http://` o `redis://`, o `MINIO_SECURE=false`, se rechaza al arrancar, sin degradar a texto claro.
- Salidas reales de un arranque con TLS y de un rechazo: pendiente (sin captura ni ejecución medida).

**Parte 3: certificados y Compose.**

- `deploy/tls/generar_certs.sh` crea la CA (EC P-256, `pathlen:0`, 365 días) y el certificado del Nodo A (90 días) en `CERTS_DIR`, fuera del repo. Si a la CA le quedan 91 días o menos, se regenera y hay que redistribuir `ca.pem` a los workers.
- Coordinador `8443` y Redis `6380` con TLS; MinIO con su certificado. Pasos en `docs/DEPLOY_WORKERS.md`.

**Límites declarados.**

- Redis, MinIO y el coordinador con TLS se probaron solo en una máquina, con las imágenes reales ([evidencia local](evidencia/F-27_servidores_tls_local_2026-11-11.md)); no hay tres nodos reales, Tailscale ni captura de red.
- `coordinator`, `redis` y `minio` del Nodo A corren con `user: CERTS_UID:CERTS_GID` para leer `server.key` (0600). `redis-data-init` ajusta la propiedad del volumen de Redis a ese UID. Solo se probó con UID 1000, que coincide con el de `appuser` del coordinador; un `CERTS_UID` distinto y el dueño `65532` de `/data/.minio.sys` de MinIO no se probaron ni se investigaron.
- El healthcheck de MinIO usa `MC_HOST_local=https://localhost:9000 mc --config-dir /tmp/.mc ready local --insecure`, porque con `user:` propio `mc` no puede escribir `/.mc` y su alias apunta a `http`.
- uvicorn no fija un mínimo de TLS 1.3: con TLS 1.2 el coordinador respondió 200 en la prueba local (AD-37). Redis sí rechazó TLS 1.2.
- Con `TLS_ENABLED=false` el worker ya no exige `TLS_CA_FILE`; con TLS activo y sin CA se detiene.
- Pendientes de otros dueños: `dashboard/app.py` y `scripts/generate_dataset.py` siguen apuntando a `http://localhost:8000`; hay que fijar la URL `https://<IP_TAILSCALE_NODO_A>:8443` y, en el dashboard, `REQUESTS_CA_BUNDLE`.
- Sin evidencia medida, M4 máximo 2.

**Parte 4: prueba de aceptación de la captura.** `tests/acceptance/test_tls_entre_nodos.py` levanta la captura, procesa un caso con marcador sintético y revisa con `tshark` y `strings`. Solo se verificó su omisión (skip); no hay ejecución real.

### F-29 Cadena de custodia

Parte 1: `CustodyChain` en `src/domain/custody_chain.py` (dominio puro, solo `hmac`, `hashlib` y `json`). Sella cada eslabón con `entry_hash = HMAC-SHA256(llave, prev_hash ‖ JSON canónico)` y `verify_chain` reporta la posición (línea, base 1) de la primera alteración; el ancla del último eslabón (`seq`, `entry_hash`, `mac`) delata el truncamiento (AD-35, SUP-31). La llave es de 32 bytes, fuera del repositorio. Parte 2: `JsonlCustodyLog` en `src/adapters/jsonl_custody_log.py`, log JSONL de solo-anexión (`O_APPEND`, `fsync`, `flock`, modo 0600) que implementa `CustodyLog.record`, escribe el ancla de forma atómica y un ancla génesis al crear el log; `record` verifica solo las últimas 2 líneas y el ancla, y el verificador completo detecta una línea intermedia manipulada. La llave entra como bytes. Parte 3: `verify_custody` (cadena, ancla, evidencia y linaje) y la CLI `scripts/verify_custody.py`, que lee la llave de `CUSTODY_KEY_FILE` con `FileKeyProvider` (F-28); sale con 0 sin violaciones, 1 con violaciones y 2 si no pudo verificar.

## 2. Concepto de Sistemas Operativos

### F-30 Workers sin privilegios

Conceptos que respalda la configuración:

- **Usuarios y UID:** el proceso del worker corre con UID/GID `10001`, distinto de 0, de modo que una vulnerabilidad en FFmpeg o en un modelo no obtiene los privilegios de `root` dentro del contenedor [B.5 M4].
- **Capacidades de Linux:** `cap_drop: [ALL]` retira todas las capacidades del proceso y `no-new-privileges:true` impide recuperarlas con binarios setuid.
- **Namespaces:** el contenedor ve su propio árbol de procesos, montajes y usuarios; la raíz de solo lectura (`read_only: true`) impide modificar el sistema de archivos de la imagen.
- **cgroups:** el volumen `scratch` en `/scratch` cuenta contra el cgroup del contenedor, a diferencia de `tmpfs`, por eso el video grande va a `/scratch` y no a memoria.

### F-26 Autenticación y roles

Conceptos que respalda la configuración (no medidos):

- **Control de acceso por rol (RBAC) y mínimo privilegio:** cada identidad recibe solo las acciones de su rol; el rol técnico `servicio` de los workers solo puede reportar sub-tareas. Es la misma idea que los UID y permisos del sistema operativo, aplicada en la capa de aplicación.
- **Permisos de archivo:** el secreto de firma vive en un archivo fuera del repositorio con modo `600`, de modo que solo su dueño puede leerlo [B.5 M4].
- **Secretos fuera del código:** el repositorio es público; la llave nunca se versiona.

### F-28 Cifrado en reposo

Conceptos que respalda el diseño, sin datos medidos:

- **Cifrado de sobre:** cada objeto tiene su propia llave de datos (DEK, 32 bytes de `os.urandom`) envuelta con la llave maestra del nodo (KEK); la KEK no se escribe en el repositorio ni en el historial [B.5 M4].
- **Memoria:** el objeto se procesa por chunks, de modo que la memoria usada queda acotada a un chunk (4 MiB por defecto, tope de 64 MiB) y no al tamaño del archivo.
- **Integridad:** AES-256-GCM autentica cada chunk; reordenar, duplicar o truncar chunks hace fallar el descifrado.
- **Permisos de archivo:** el proveedor `FileKeyProvider` exige que el archivo de la KEK sea regular y de modo 0400 o 0600, para que otros usuarios del sistema no puedan leerlo.

### F-27 TLS entre nodos

TLS protege el canal entre procesos de distintos nodos: cifra, comprueba la integridad y autentica al servidor con una cadena de confianza. El módulo `ssl` de Python delega en OpenSSL; el cliente decide con qué CA confía y qué versión mínima acepta. JWT (F-26) identifica a quien llama; no protege el canal. Tailscale tampoco sustituye a TLS: la captura debe mostrar el handshake (`docs/ARQUITECTURA.md` §6).

### F-29 Cadena de custodia

Conceptos que respalda el diseño, sin datos medidos:

- **Integridad con hash encadenado:** cada eslabón sella la evidencia y el hash del eslabón previo; alterar, borrar, insertar o reordenar una entrada rompe el enlace en esa posición.
- **HMAC en vez de SHA-256 solo:** sin llave, quien altera el log puede recalcular toda la cadena; con HMAC-SHA-256 necesita la llave, que vive fuera del repositorio [B.5 M4].
- **Ancla del último eslabón:** el archivo de ancla delata el truncamiento, que el encadenamiento por sí solo no ve.

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

### F-26 Autenticación y roles

```bash
TOKEN=$(PYTHONPATH=. python scripts/emitir_token.py --rol analista --sub demo-analista)
curl -i -X POST http://localhost:8000/cases -H "Authorization: Bearer $TOKEN" ...   # crear
curl -i http://localhost:8000/cases -H "Authorization: Bearer $TOKEN"              # consultar
curl -i http://localhost:8000/stats -H "Authorization: Bearer $TOKEN"              # monitoreo
curl -i http://localhost:8000/cases                                                # sin token
```

El cuerpo de `POST /cases` se omite; ver `docs/DEMO.md`.

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

La ejecuta la persona en el Nodo A, con `sudo` y la IP real de Tailscale. Comandos exactos de `docs/IMPLEMENTACION.md` §5, una captura por intento:

```bash
sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'
tshark -r m4.pcap -Y tls.handshake.type==1
strings m4.pcap | grep -c <marcador_sintetico>
```

Producto esperado: handshakes TLS y 0 coincidencias del marcador. `m4.pcap` queda fuera del repo; solo se versiona el resumen de `tshark`.

Prueba de aceptación (se omite si falta algo de lo siguiente):

```bash
F27_CAPTURA=1 COORDINATOR_URL=https://<ip>:8443 TLS_CA_FILE=<ca.pem> pytest tests/acceptance/test_tls_entre_nodos.py -q
```

- `F27_CAPTURA=1`: obligatoria; sin ella se omite.
- `COORDINATOR_URL` y `TLS_CA_FILE`: obligatorias.
- `F27_INTERFAZ`: interfaz de captura; por defecto `any`.
- `F27_LEVANTAR_NODO=1`: ejecuta `docker compose up -d --wait` y lo baja al terminar.
- Requiere `tcpdump`, `tshark`, `strings` y `sudo` sin contraseña (`sudo -v` antes).

Comandos de la prueba local de los servidores: en la [evidencia local](evidencia/F-27_servidores_tls_local_2026-11-11.md) (`generar_certs.sh`, `docker compose up`, `redis-cli --tls`, `openssl s_client`, `curl --cacert`).

### F-29 Cadena de custodia

No aplica como medición de SO M1 a M5: F-29 aporta evidencia de ejecución. El comando previsto, que se ejecuta en la demo con un log y una evidencia sintéticos, antes y después de manipularlos, es `PYTHONPATH=. python -m scripts.verify_custody --log <log.jsonl> --anchor <log.jsonl.head> [--store <dir>]`, con la llave en `CUSTODY_KEY_FILE` (32 bytes aleatorios, fuera del repositorio, distinta de la KEK de F-28). Entorno de la ejecución local sintética: una sola máquina, log y objetos generados para la ocasión, llave aleatoria de 32 bytes con permisos 0600. Códigos de salida: 0 íntegro, 1 con violaciones, 2 no se pudo verificar.

## 4. Resultados

### F-30 Workers sin privilegios

Medido en **una sola máquina**, no en tres nodos reales: la demo local de `deploy/docker-compose.demo.yml` sobre Docker Desktop 29.9.3 (Windows 10, WSL2, `linux/amd64`), el 2026-11-11 a las 20:57 UTC, contra el contenedor `deploy-worker-1-1`. La columna de nodos reales sigue pendiente y esta salida no la sustituye.

| Comando | Esperado | Salida medida (demo local) | Nodos reales |
|---|---|---|---|
| `id -u` | distinto de 0 | `10001` | pendiente |
| `touch /x` | falla (sistema de archivos de solo lectura) | `touch: cannot touch '/x': Read-only file system`, código de salida 1 | pendiente |
| `.Config.User` | `10001:10001` | `10001:10001` | pendiente |
| `ReadonlyRootfs` | `true` | `true` | pendiente |
| `CapDrop` | contiene `ALL` | `[ALL]` | pendiente |
| `SecurityOpt` | contiene `no-new-privileges:true` | `[no-new-privileges:true]` | pendiente |

Las cuatro pruebas de `tests/integration/test_workers_sin_privilegios_docker.py` también pasaron contra ese contenedor (`WORKER_CONTAINER=deploy-worker-1-1`, 4 passed). Hecho en Git Bash sobre Windows: `docker exec ... touch /x` necesita `MSYS_NO_PATHCONV=1`, porque Git Bash convierte `/x` en una ruta de Windows y el mensaje de error sale distinto.

Nodos: José, Nahúm y Melany; cada uno captura sus salidas.

### F-26 Autenticación y roles

Medido el 2026-11-11 (20:57 UTC) en la demo local, **una sola máquina**, contra el coordinador de `deploy/docker-compose.demo.yml` en `http://localhost:8000` con TLS desactivado. La demo usó los cambios de la PR #112 (`WORKER_TOKEN`, `JWT_SECRET` en el Compose y `scripts/generar_credenciales.py`): sin ellos la demo no autentica, el coordinador rechaza todo con 401. El secreto y los tokens se generaron para la prueba, con vigencia de 30 minutos, y no se guardan. Cada celda es el código HTTP de una petición.

Tokens ausentes o inválidos (la columna `GET /health` es ruta pública):

| Token | GET /health | GET /cases | POST /cases | GET /cases/{id} | POST /cases/{id}/cancel | GET /stats | GET /workers | POST /subtasks/report |
|---|---|---|---|---|---|---|---|---|
| sin token | 200 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| basura (`abc`) | 200 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| firma alterada | 200 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| vencido (emitido hace 2 h con 1 minuto de vigencia) | 200 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| `alg: none` | 200 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |

Roles válidos:

| Rol | GET /health | GET /cases | POST /cases | GET /cases/{id} | POST /cases/{id}/cancel | GET /stats | GET /workers | POST /subtasks/report |
|---|---|---|---|---|---|---|---|---|
| analista | 200 | 200 | 201 | 200 | 403 | 403 | 403 | 403 |
| supervisor | 200 | 200 | 403 | 200 | 409 | 200 | 200 | 403 |
| administrador | 200 | 200 | 201 | 200 | 409 | 200 | 200 | 403 |
| servicio | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 200 |

Todos los códigos coinciden con la matriz de la sección F-26. Las dos celdas `409` son de un rol con permiso para cancelar: la autorización pasó y el caso ya no admitía la cancelación. El caso de la prueba se creó con un archivo inexistente (`medicion/prueba.mp4`) y, al pedir la cancelación, ya estaba en estado terminal: en una repetición con otro caso, la respuesta fue `409` con el texto «ya está en estado terminal: 'failed'», tanto de inmediato como 8 segundos después. No se averiguó qué componente lo marcó `failed`. `POST /subtasks/report` con el rol `servicio` devolvió 200 con un informe `failed` sobre una sub-tarea de la prueba.

Límites: es una sola máquina, sin TLS, con datos sintéticos, y cada petición se hizo una vez. No se midió el cuerpo de las respuestas ni la cabecera `WWW-Authenticate`; los 429 y la expiración por reloj del servidor no se probaron.

### F-28 Cifrado en reposo

Pendiente: sin datos medidos de costo de CPU, de tamaño de chunk, de costo de leer la KEK en cada llamada ni de costo de CPU del decorador.

**Salida de la prueba I:** ejecutada una vez, de forma local (una máquina, MinIO efímero en Docker, sin TLS ni red entre nodos): 2 pruebas pasadas; el objeto crudo en MinIO no contiene el marcador en claro y un bit alterado lanza `DecryptionError`. Salida completa en [docs/evidencia/F-28_prueba_I_minio_local_2026-11-11.md](evidencia/F-28_prueba_I_minio_local_2026-11-11.md). No es evidencia en los tres nodos ni mide costo de CPU.

**Salida de la búsqueda en el historial:** pendiente: la búsqueda manual en el historial no se ha registrado aquí. La prueba automática `tests/unit/test_historial_sin_llaves.py` sí corre en la suite y pasa.

### F-27 TLS entre nodos

| Medición | Resultado |
|---|---|
| Handshakes TLS en la captura (`tshark`) | pendiente |
| Coincidencias del marcador (`strings ... \| grep -c`) | pendiente |
| Cliente sin la CA rechazado en los servicios reales | pendiente (solo prueba local, abajo) |
| Costo de TLS sobre el throughput de M3 | pendiente |

**Prueba local de servidores TLS (una sola máquina, sin captura de red; no acredita M4).** Con `redis:7-alpine`, MinIO de Chainguard y el coordinador construido con `Dockerfile.worker`, todo en `127.0.0.1`: los tres servicios quedaron `healthy` con `user:` propio; `redis-cli --tls` y `openssl s_client` verificaron la CA y el hostname con TLS 1.3, Redis rechazó TLS 1.2, el puerto 6379 quedó cerrado, y el coordinador atendió `https://localhost:8443/health` con la CA y rechazó la petición sin ella o en claro. La prueba encontró dos fallos del Compose original (Redis sin permiso de escritura en `redis-data` y healthcheck de MinIO que no pasaba), ya corregidos. Detalle y salidas en [la evidencia](evidencia/F-27_servidores_tls_local_2026-11-11.md).

### F-29 Cadena de custodia

Salida real de una ejecución local sintética (una sola máquina, datos sintéticos) en [`docs/evidencia/F-29_prueba_A_local_sintetica_2026-11-11.md`](evidencia/F-29_prueba_A_local_sintetica_2026-11-11.md): cadena íntegra exit 0; alteración, borrado, reordenamiento, truncado, ancla borrada, cadena recalculada sin llave, evidencia alterada y evidencia borrada exit 1 con la posición; llave con permisos 0644, de 16 bytes o ausente exit 2. No acredita la prueba A en la demo ni en nodos: la columna de la tabla sigue pendiente para ellos.

| Prueba | Esperado | Salida medida |
|---|---|---|
| Verificador sobre cadena íntegra | sin violaciones, código de salida 0 | pendiente |
| Verificador tras alterar una entrada | falla e indica la posición | pendiente |
| Verificador tras truncar el log | falla por ancla | pendiente |
| Verificador tras alterar una evidencia | falla e indica la entrada | pendiente |

## 5. Interpretación

### F-30 Workers sin privilegios

La demo local registró UID 10001, raíz de solo lectura y restricciones efectivas (sección 4). Falta repetir en los workers desplegados; la configuración escrita y las unitarias no prueban esa ejecución remota.

### F-26 Autenticación y roles

La tabla local registra 401 para tokens inválidos y 403 para roles sin permiso. Los 409 de cancelación corresponden a autorización aceptada y estado del caso incompatible; no son denegaciones por rol. Una petición por celda, sin TLS, no demuestra el despliegue ni todos los cuerpos/cabeceras. Límites conocidos: `docs/specs/F-26/SPEC.md`.

### F-28 Cifrado en reposo

Pendiente. Las pruebas unitarias respaldan el formato y la detección de alteraciones, no el costo de CPU en los nodos. La prueba local con MinIO acredita cifrado y detección de alteración en ese entorno; no mide esos costos.

### F-27 TLS entre nodos

Pendiente. La prueba local respalda que los servidores arrancan con TLS y UID propio y que el cliente verifica la CA, no que el tráfico entre nodos reales vaya cifrado: falta la captura con `tshark` y `strings`. Sin captura real entre nodos no se acredita ese producto RNF-12, aunque el arranque TLS local sí tiene resultados.

**Repetir M3.** TLS puede alterar M1 a M3: hay que repetir al menos el throughput de M3 con TLS activo y reportar la diferencia (`docs/IMPLEMENTACION.md` §7). No se estima aquí.

### F-29 Cadena de custodia

Parcial. La ejecución local sintética muestra que el verificador detecta cada manipulación probada y que falla cerrado con llave inválida o ausente; no demuestra la prueba A en nodos reales. Las pruebas unitarias respaldan la lógica de sellado y detección. Límites declarados (SUP-31): el verificador carga todo el log en memoria; quien posea la llave puede forjar la cadena (HMAC simétrico) y un ancla antigua repuesta junto con un log truncado al mismo punto no se detecta mientras el ancla viva en el mismo disco.
