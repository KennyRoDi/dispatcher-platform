# Despliegue en cuatro máquinas: Nodo A y tres nodos worker

> **Estado:** nada de esta guía se ha ejecutado todavía sobre nodos reales. La Parte 2 de F-38 la recorre de principio a fin y corrige lo que falle. Los resultados no se escriben de antemano.

Bash en Linux, PowerShell en Windows. Los comandos se ejecutan desde la raíz del repositorio. Marcadores que debes sustituir: `<IP_TAILSCALE_NODO_A>`, `<AAAAMMDD_HHMMSS>`, `<case_id>`, `<worker_id>`.

**Reutilización.** Las operaciones multimedia de la corrida y `docker-compose.yml`, modificado, se reutilizan del I Proyecto. La declaración por componente corresponde a F-39.

## 1. Topología

| Máquina | Sistema | Corre | Compose |
|---|---|---|---|
| Nodo A | Linux | Coordinador, Redis, MinIO y reaper. Sin workers | `docker-compose.yml` |
| Nodos B, C y D | Windows 11, Docker Desktop sobre WSL2 | Un worker cada uno | `deploy/docker-compose.worker.yml` |

Las cuatro máquinas se comunican por **Tailscale**. El Nodo A publica estos puertos solo en su IP de Tailscale, así que `localhost` no responde, ni siquiera en el propio Nodo A:

| Puerto | Servicio |
|---|---|
| 8443 | Coordinador (HTTPS) (`/docs`, `/stats`, `/workers`) |
| 6380 | Redis (TLS, `rediss://`) |
| 9000, 9001 | MinIO: API y consola |

Coordinador y Redis van con TLS 1.3 (F-27); MinIO también, con su propio certificado. Tailscale no sustituye a TLS. Un cortafuegos como `ufw` no basta para limitarlos, porque las reglas de Docker para puertos publicados pueden saltárselo; por eso se publican solo en esa IP. Los workers solo abren conexiones salientes, de modo que los nodos Windows no necesitan reglas de entrada.

**Reparto.** Nadie asigna tareas a un nodo: cada worker toma trabajo (`BLPOP`) de las colas de `WORKER_QUEUES` cuando tiene capacidad (`WORKER_CONCURRENCY`), primero de las `queue:{op}:high` y luego de las `queue:{op}`. El nodo más rápido termina procesando más. `threads_per_job` es `cpu_count // WORKER_CONCURRENCY`. La justificación está en `docs/DECISIONES_DISENO.md`, decisiones 3 y 4.

**Un worker por nodo.** La concurrencia se ajusta con `WORKER_CONCURRENCY`. No uses `--scale`: Compose fija el `hostname`, así que las réplicas compartirían `worker_id`, heartbeat y lista `inflight`.

## 2. Prerrequisitos

Las cuatro máquinas deben estar en la misma red de Tailscale antes de levantar nada.

### Nodo A (bash)

Necesitas Docker con el plugin Compose, Tailscale, Git, curl y Python 3.13 o superior. Referencias: [Docker Engine](https://docs.docker.com/engine/install/) y [Tailscale](https://tailscale.com/download/linux).

**Requieren `sudo`: los ejecuta la persona, no un agente.** Los nombres de paquetes son de Debian o Ubuntu.

```bash
sudo apt-get update
sudo apt-get install -y git curl python3-venv
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"    # cierra sesión y vuelve a entrar
curl -fsSL https://tailscale.com/install.sh | sudo sh
sudo tailscale up
```

Se requiere Python 3.13 o superior, porque el código usa `os.process_cpu_count`. Si `python3 --version` da menos, instala 3.13 antes de crear el venv, según la [documentación oficial de Python](https://docs.python.org/3/using/unix.html).

Después, sin `sudo`. El venv hace falta porque `run_load` y `pytest` corren en nativo en este nodo:

```bash
git clone https://github.com/KennyRoDi/dispatcher-platform.git
cd dispatcher-platform
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
which docker tailscale
docker compose version
tailscale ip -4
```

### Nodos B, C y D (PowerShell)

En una ventana de administrador. Reinicia al terminar:

```powershell
wsl --install
winget install --id Docker.DockerDesktop -e
winget install --id Tailscale.Tailscale -e
winget install --id Git.Git -e
```

Abre Docker Desktop y comprueba que está activo *Use the WSL 2 based engine*. Abre Tailscale e inicia sesión en la misma red. Después, en una ventana normal:

```powershell
git clone https://github.com/KennyRoDi/dispatcher-platform.git
cd dispatcher-platform
wsl --status
docker version
docker compose version
tailscale ip -4
```

## 3. `.env` de cada máquina

Cada máquina tiene su propio `.env` en la raíz del repositorio. **Nunca se versiona:** el repositorio es público y `.env` está en `.gitignore`.

| Variable | Valor | ¿Igual en las cuatro? |
|---|---|---|
| `NODE_NAME` | Salida de `hostname` de esa máquina. Único entre nodos | No |
| `NODE_IP` | Salida de `tailscale ip -4` de esa máquina | No |
| `WORKER_MEM_LIMIT` | Límite de memoria medido para ese worker, en formato admitido por Compose | No |
| `ADMISSION_MARGIN_BYTES`, `FOOTPRINT_<OP>_BYTES` | **Obligatorias** (F-17), sin valor por defecto: medir según M1 §4.1; sin medir el worker no arranca. `<OP>` en mayúsculas: `TRANSCODE_VIDEO`, `EXTRACT_AUDIO`, `GENERATE_THUMBNAIL`, `CONVERT_AUDIO`, `EXTRACT_METADATA` | Según la medición |
| `WORKER_TOKEN` | Token de rol `servicio` que emite el Nodo A con `python -m scripts.generar_credenciales --solo-worker <archivo>`; con él el worker reporta sub-tareas y sin él el coordinador responde 401. Vence a los 30 días (`--dias`). Nunca el `JWT_SECRET` ni `API_TOKEN` | Sí |
| `TLS_CA_FILE` | Ruta de `ca.pem` en esa máquina (la copia desde el Nodo A). Obligatorio con TLS activo; con `TLS_ENABLED=false` puede omitirse | Sí |
| `REDIS_HOST` | `<IP_TAILSCALE_NODO_A>` | Sí |
| `COORDINATOR_URL` | `https://<IP_TAILSCALE_NODO_A>:8443` | Sí |
| `MINIO_ENDPOINT` | `<IP_TAILSCALE_NODO_A>:9000` | Sí |
| `REDIS_PASSWORD` | Obligatorio; el Compose del Nodo A no arranca sin él | Sí |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Propias, no `minioadmin`, que es un valor público | Sí |
| `WORKER_ID` | **Vacío** | Sí |
| `WORKER_QUEUES`, `WORKER_CONCURRENCY` | Opcional: `.env.example` trae las cinco operaciones y 2 | Puede variar |
| `HWACCEL` | Vacío, salvo en un nodo GPU (§8) | Puede variar |

Los contenedores del Nodo A ignoran `REDIS_HOST`, `COORDINATOR_URL` y `MINIO_ENDPOINT`, porque su Compose usa nombres de servicio. Esos valores los usan `run_load` y los demás scripts nativos. En el Nodo A, Compose solo usa `NODE_IP` de la identidad; `NODE_NAME` se llena igual por coherencia. El resto de variables está comentado en `.env.example`.

Si faltan `ADMISSION_MARGIN_BYTES` o alguna `FOOTPRINT_<OP>_BYTES`, el worker falla al leer la configuración (`src/workers/config.py`), el contenedor se reinicia en bucle y `GET /workers` devuelve `[]`. Los valores reales dependen de la medición M1 §4.1, aún pendiente; no se inventan.

`NODE_NAME` va en el `.env` de cada máquina; en una simulación local con varios workers en una misma máquina no se comparte entre ellos. `CLIENT LIST` de Redis no distingue nodos tras un puerto publicado (todos llegan desde la misma IP de la red de Docker); ver la evidencia de simulación local en `docs/evidencia/F-38_tres_nodos_simulacion_local_2026-11-11.md`.

Genera las contraseñas una vez, en el Nodo A, y compártelas por un canal privado del equipo. Hexadecimal evita caracteres que Compose interpretaría, como `$`:

```bash
python3 -c "import secrets; print(secrets.token_hex(24))"
```

**Nodo A:**

```bash
cp .env.example .env
nano .env
python3 -m scripts.generar_credenciales --solo-worker worker-token.env   # JWT_SECRET, WORKER_TOKEN y API_TOKEN en .env
```

`worker-token.env` contiene solo `WORKER_TOKEN`: cópialo por un canal privado al `.env` de cada nodo worker. El `JWT_SECRET` se queda en el Nodo A.

**Nodos B, C y D.** PowerShell y Git pueden dejar CRLF, BOM o UTF-16, así que, después de editar, el archivo se reescribe en UTF-8 sin BOM y con LF. Cierra antes cualquier otra ventana de Notepad: el bloque espera a que cierres la que abre, con el archivo ya guardado.

```powershell
Copy-Item .env.example .env
Start-Process notepad .env -Wait
$ruta = Join-Path $PWD ".env"
$texto = [IO.File]::ReadAllText($ruta) -replace "`r`n", "`n"
[IO.File]::WriteAllText($ruta, $texto, [Text.UTF8Encoding]::new($false))
```

No escribas el `.env` con `>` ni con `Out-File`.

### Tres errores que rompen la identidad

- **`WORKER_ID` fijo.** Con un valor fijo en los tres `.env`, los tres nodos se pisan en una sola entrada de `GET /workers`. Déjalo vacío: se genera como `worker-<hostname>`.
- **`NODE_NAME` repetido.** Dos máquinas con el mismo `hostname` colisionan en `worker_id`.
- **`NODE_NAME` o `NODE_IP` en el shell con otro valor.** Compose interpola `hostname` del shell, que tiene prioridad sobre `--env-file`, mientras que `NODE_NAME` llega al proceso por `env_file`. Si difieren, `host` y `hostname` divergen y la aceptación lo detecta, porque un `host` con sub-tareas no estaría entre los `hostname` activos. Un `NODE_IP` del shell también sustituye al del archivo, y la aceptación solo lo detecta si queda repetido o fuera de `100.64.0.0/10`. Ambos comandos deben salir sin resultados:

  ```bash
  env | grep -E '^NODE_(NAME|IP)='
  ```

  ```powershell
  Get-ChildItem Env:NODE_NAME, Env:NODE_IP -ErrorAction SilentlyContinue
  ```

## 4. Arranque

El orden importa: primero el Nodo A, después cada worker.

### Nodo A (bash)

Tailscale debe estar activo antes de `docker compose up`, porque los puertos se publican en esa IP.

**Certificados (F-27).** Antes de levantar, genera la CA y el certificado del Nodo A, fuera del repo (requiere `openssl` y `python3`):

```bash
NODE_IP=$(tailscale ip -4) NODE_NAME=$(hostname) CERTS_DIR=$HOME/.ms-certs bash deploy/tls/generar_certs.sh
```

En el `.env` del Nodo A: `CERTS_DIR` (la misma ruta), `CERTS_UID=$(id -u)` y `CERTS_GID=$(id -g)`. Con ellos `coordinator`, `redis` y `minio` corren con ese UID para leer `server.key` (0600); se probó con las imágenes reales en una sola máquina ([evidencia](evidencia/F-27_servidores_tls_local_2026-11-11.md)). `redis-data-init` ajusta la propiedad del volumen de Redis a ese UID. A cada worker copia **solo** `ca.pem` (nunca `ca.key` ni `server.key`) y fija `TLS_CA_FILE` con su ruta en su `.env`.

```bash
tailscale ip -4    # debe coincidir con NODE_IP
docker compose up -d --build
docker compose ps
curl -s -o /dev/null -w "%{http_code}\n" "https://<IP_TAILSCALE_NODO_A>:8443/openapi.json"
```

Esperado: `redis`, `minio` y `coordinator` en `healthy`, `reaper` corriendo y código `200`. Consola de MinIO: `https://<IP_TAILSCALE_NODO_A>:9001`, con las credenciales de tu `.env`.

Captura de TLS para M4 (`tcpdump`, `tshark`, prueba de aceptación): [modulo-M4-seguridad.md](modulo-M4-seguridad.md#tls-entre-nodos-f-27-captura).

MinIO dejó de publicar imágenes públicas, por eso el Compose usa `cgr.dev/chainguard/minio:latest`. Si dejara de estar disponible, define otra en `.env` con `MINIO_IMAGE=...`.

### Conectarse al Nodo A desde Windows (prueba de conexión)

Pasos completos, probados desde un nodo Windows real (`PC-KEVIN`) contra el Nodo A (2026-11-11): `check_connectivity` salió con código 0. **No arranca el worker**: solo comprueba red, TLS y credenciales. Todos los comandos son PowerShell y se ejecutan desde la raíz del repositorio, salvo que se indique otra cosa.

**Qué debe darte quien opera el Nodo A, por un canal privado** (nunca por el repositorio, commits ni chats públicos):

1. La IP de Tailscale del Nodo A (en este despliegue, `100.86.249.90`; confírmala con `tailscale ip -4` en el Nodo A).
2. El archivo `ca.pem` (o su contenido). Es la CA pública; no es secreto. **Nunca** pidas ni uses `ca.key` ni `server.key`.
3. `REDIS_PASSWORD`, `MINIO_ACCESS_KEY` y `MINIO_SECRET_KEY`, que están en el `.env` del Nodo A.
4. La huella SHA-256 de la CA, por un canal distinto al del archivo. En el Nodo A: `openssl x509 -in ~/.ms-certs/ca.pem -noout -fingerprint -sha256`. Sin ese segundo canal, la comprobación del paso 3 solo prueba que el archivo está íntegro, no que sea el correcto.

**Paso 1. Instalar y activar (una sola vez).** Docker Desktop con el motor WSL2, Tailscale con sesión en la misma red que el Nodo A, y Git (comandos de §2). En una ventana de PowerShell como administrador, antes de instalar Docker Desktop, ejecuta `wsl --install --no-distribution` y reinicia Windows: sin WSL2 activo, Docker Desktop no arranca. Probado en una sola máquina, no en todas. Después:

```powershell
git clone https://github.com/KennyRoDi/dispatcher-platform.git
cd dispatcher-platform
git checkout main
git pull origin main
```

**Paso 2. Comprobar la red.** Debe responder `pong` y las tres pruebas deben dar `TcpTestSucceeded : True`:

```powershell
tailscale status
tailscale ping 100.86.249.90
Test-NetConnection 100.86.249.90 -Port 8443
Test-NetConnection 100.86.249.90 -Port 6380
Test-NetConnection 100.86.249.90 -Port 9000
```

Si `tailscale ping` falla, Tailscale no está activo o no estás en la misma red. Si un puerto falla y el ping responde, el Nodo A no está levantado (`docker compose ps` allí).

**Paso 3. Instalar la CA.**

```powershell
New-Item -ItemType Directory -Force C:\certs | Out-Null
notepad C:\certs\ca.pem
```

Pega el contenido de `ca.pem` (de `-----BEGIN CERTIFICATE-----` a `-----END CERTIFICATE-----`), guarda y cierra. Si recibiste el archivo, cópialo a `C:\certs\ca.pem`. Comprueba:

```powershell
Select-String -Path C:\certs\ca.pem -Pattern "PRIVATE KEY"
certutil -dump C:\certs\ca.pem
```

El primer comando **no** debe imprimir nada: si imprime algo, ese archivo contiene una llave privada, bórralo y avisa. En la salida del segundo, la línea `Cert Hash(sha256)` debe coincidir con la huella del punto 4, sin los dos puntos y sin importar mayúsculas. Esa lectura de `certutil` no se ha verificado en esta guía; si el formato difiere, compara con `openssl x509 -in C:\certs\ca.pem -noout -fingerprint -sha256` (por ejemplo, con el `openssl` que trae Git for Windows).

**Paso 4. Probar HTTPS al coordinador.** Usa `curl.exe`, no `curl`, que en PowerShell es un alias de `Invoke-WebRequest`. **Debe llevar `--ssl-no-revoke`**: Windows (Schannel) intenta comprobar la revocación de la CA y, al ser una CA propia, falla con `curl: (60)`. La opción solo desactiva esa consulta; la cadena sigue verificándose contra `ca.pem`.

```powershell
curl.exe --ssl-no-revoke --cacert C:\certs\ca.pem https://100.86.249.90:8443/openapi.json -o NUL -w "%{http_code}`n"
```

Esperado: `200`. No uses `-k` ni `--insecure`: anulan lo que se quiere comprobar.

**Paso 5. Crear el `.env`.**

```powershell
Copy-Item .env.example .env
Start-Process notepad .env -Wait
$ruta = Join-Path $PWD ".env"
$texto = [IO.File]::ReadAllText($ruta) -replace "`r`n", "`n"
[IO.File]::WriteAllText($ruta, $texto, [Text.UTF8Encoding]::new($false))
```

Antes de guardar, deja estas variables exactamente así (las demás se quedan como en `.env.example`). Si una variable aparece comentada o repetida, deja una sola línea activa:

```text
REDIS_HOST=100.86.249.90
REDIS_PORT=6380
REDIS_PASSWORD=<el que te pasaron>
COORDINATOR_URL=https://100.86.249.90:8443
MINIO_ENDPOINT=100.86.249.90:9000
MINIO_ACCESS_KEY=<el que te pasaron>
MINIO_SECRET_KEY=<el que te pasaron>
MINIO_SECURE=true
TLS_ENABLED=true
TLS_CA_FILE=C:\certs\ca.pem
NODE_NAME=<salida de: hostname>
NODE_IP=<salida de: tailscale ip -4>
WORKER_ID=
WORKER_MEM_LIMIT=2g
```

- `WORKER_ID` va **vacío** (ver «Tres errores que rompen la identidad»).
- `TLS_CA_FILE` es la ruta de Windows; el Compose la monta en `/certs/ca.pem` dentro del contenedor.
- `WORKER_MEM_LIMIT` es obligatorio: sin él Compose falla con `define WORKER_MEM_LIMIT en .env`. **`2g` es un marcador para esta prueba de conexión: no está medido y no vale como dato.** Hay que medirlo antes de arrancar el worker real.
- **No añadas** `ADMISSION_MARGIN_BYTES` ni `FOOTPRINT_*_BYTES`: `check_connectivity` no las lee, y un valor inventado (por ejemplo `1`) haría que el worker admitiera todo sin límite cuando se arranque. Se definen solo con valores medidos (M1 §4.1), justo antes de arrancar el worker real.
- No escribas el `.env` con `>` ni con `Out-File`, y no lo subas a git (`.gitignore` ya lo excluye).
- `NODE_NAME` y `NODE_IP` no deben estar definidos en el shell con otro valor: `Get-ChildItem Env:NODE_NAME, Env:NODE_IP -ErrorAction SilentlyContinue` no debe imprimir nada.

**Paso 6. Verificar el `.env` y probar de extremo a extremo.** Reconstruye antes la imagen: una imagen `deploy-worker` anterior a F-27 no incluye TLS y la prueba falla aunque todo lo demás esté bien. La primera construcción tarda varios minutos.

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml build worker
docker compose --env-file .env -f deploy/docker-compose.worker.yml config --quiet
$LASTEXITCODE
docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity
$LASTEXITCODE
```

Esperado: ambos códigos `0` y, en el segundo comando:

```text
[OK] redis: Redis OK en 100.86.249.90:6380
[OK] coordinator: Coordinador OK en https://100.86.249.90:8443
[OK] minio: MinIO OK en 100.86.249.90:9000, pero el bucket 'dataset' aun no existe
[OK] ffmpeg: ffmpeg OK (...)
[OK] work_dir: WORK_DIR escribible: /scratch
```

El aviso del bucket `dataset` es normal: el worker lo crea al iniciar. Aquí termina la prueba de conexión. **No ejecutes `python scripts/start_worker.py` todavía.** Antes hay que medir `WORKER_MEM_LIMIT`, `ADMISSION_MARGIN_BYTES` y las cinco `FOOTPRINT_*_BYTES` (M1 §4.1) y, con la autenticación de F-26 (PR #112), tener `WORKER_TOKEN` en el worker y `JWT_SECRET` en el Nodo A (que debe recrearse). Mientras tanto, un worker sin token recibiría 401 del coordinador.

**Operador del Nodo A: comprobación previa.** Antes de que nadie pruebe, en el Nodo A:

```bash
tailscale ip -4                      # debe coincidir con NODE_IP de su .env
docker compose ps                    # redis, minio y coordinator en healthy; reaper corriendo
curl -s --cacert ~/.ms-certs/ca.pem -o /dev/null -w "%{http_code}\n" https://$(tailscale ip -4):8443/openapi.json
```

El tercer comando debe dar `200`. Si el certificado se regenera (`generar_certs.sh`), cambia la huella y todos los nodos necesitan el `ca.pem` nuevo.

### Cada nodo worker (PowerShell)

`--env-file .env` es obligatorio: el archivo de Compose está en `deploy/` y Compose no buscaría allí el `.env` de la raíz.

```powershell
hostname            # debe coincidir con NODE_NAME
tailscale ip -4     # debe coincidir con NODE_IP
Get-ChildItem Env:NODE_NAME, Env:NODE_IP -ErrorAction SilentlyContinue
docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity
$LASTEXITCODE
```

Exige salida `0`, con `[OK]` en `redis`, `coordinator`, `minio` y `work_dir`. `ffmpeg` solo avisa si falta, pero la imagen lo incluye. Si el bucket aún no existe, `minio` sale en `[OK]` y lo indica: el worker lo crea al iniciar. `--create-buckets` lo crea desde esta comprobación. Si falla, ve a §7 antes de seguir.

```powershell
python scripts/start_worker.py
docker compose --env-file .env -f deploy/docker-compose.worker.yml ps
docker compose --env-file .env -f deploy/docker-compose.worker.yml logs -f
```

### Comprobar los tres workers, desde el Nodo A

```bash
curl -s "https://<IP_TAILSCALE_NODO_A>:8443/workers" | python3 -m json.tool
```

Debe haber tres entradas con `alive: true`, y en cada una `host` y `hostname` iguales a su `NODE_NAME`, e `ip` igual a su `NODE_IP`. Desde Windows: `Invoke-RestMethod https://<IP_TAILSCALE_NODO_A>:8443/workers`.

### Detener

```bash
docker compose down        # Nodo A; con -v también borra los datos de Redis y MinIO
```

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml down
```

Un worker termina la sub-tarea en curso antes de salir: `stop_grace_period` permite hasta 31 minutos.

## 5. Corrida y evidencia (Parte 2)

La ejecuta la persona, en el Nodo A y con el venv activo. Destino: `docs/evidencia/F-38_tres_nodos_<fecha>.md` y el JSON de `run_load`. Los archivos `carga_*` que ya están en `docs/evidencia/` no sirven como evidencia de F-38.

### 5.1 Generar el dataset

`dataset/media/` no se versiona. Se genera una vez, con la misma imagen del worker para usar su FFmpeg. El servicio `reaper` usa esa imagen:

```bash
docker compose run --rm --no-deps -v "$PWD/dataset:/app/dataset" reaper \
    python -m scripts.build_dataset --out dataset --files 480 --seed 42
```

También reescribe `dataset/manifest.json`, `cases.json` y `README.md`, que están versionados. Revisa `git status` y no los incluyas en el commit de evidencia. Composición del dataset: `dataset/README.md`.

### 5.2 Registrar los nodos y correr la carga

```bash
source .venv/bin/activate
curl -s "https://<IP_TAILSCALE_NODO_A>:8443/workers" | python3 -m json.tool
tailscale status
docker compose exec redis redis-cli CLIENT LIST
python3 -m scripts.run_load --dataset dataset --upload --limit 20
```

`run_load` lee el `.env` del Nodo A. `--upload` sube todo el manifiesto, también con `--limit` (480 archivos y 655.7 MB, según `dataset/README.md`), y omite lo que ya existe con el mismo tamaño. `--limit` solo limita los casos enviados. Otras opciones: `--concurrency`, `--high-fraction`, `--seed`, `--kinds`, `--timeout`, `--poll` y `--out`.

Escribe `docs/evidencia/carga_<AAAAMMDD_HHMMSS>.json` y `.md`, e imprime la ruta del `.md`. Sale con `2` si se agotó el tiempo: esa corrida está incompleta y la aceptación la rechaza.

### 5.3 Prueba de aceptación

Con los workers todavía activos, porque la prueba consulta `GET /workers`:

```bash
COORDINATOR_URL="https://<IP_TAILSCALE_NODO_A>:8443" \
RUN_LOAD_JSON="docs/evidencia/carga_<AAAAMMDD_HHMMSS>.json" \
python3 -m pytest -q -m acceptance tests/acceptance/test_tres_nodos.py
```

**Exige `1 passed`. `skipped` no cuenta:** si faltan `COORDINATOR_URL` o `RUN_LOAD_JSON`, la prueba se omite y pytest sale con 0. La prueba no lee estas variables del `.env`.

Comprueba: al menos tres workers con `alive`, con `hostname` e `ip` distintos, e `ip` dentro de `100.64.0.0/10`; al menos tres hosts con sub-tareas `completed`, todos entre los `hostname` activos; y `timed_out` falso.

### 5.4 Tabla de sub-tareas por `hostname`

Sale de `metrics.subtasks_per_host` del JSON, y `run_load` la incluye en el `.md`:

```bash
python3 -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1]))["metrics"]["subtasks_per_host"], indent=2))' docs/evidencia/carga_<AAAAMMDD_HHMMSS>.json
```

**Esa cifra incluye las fallidas.** Un host puede aparecer con solo fallos, y puede aparecer `reaper`, que reporta las sub-tareas perdidas. La aceptación, en cambio, solo cuenta `completed`. Decláralo así en la evidencia y no leas la tabla como «procesadas con éxito».

Hosts con sub-tareas `completed` en cada caso:

```bash
python3 -c 'import json, sys; r = json.load(open(sys.argv[1]))["reports"]; print(*(f"{c} {sorted({s["host"] for ss in ((i or {}).get("subtasks_by_operation") or {}).values() for s in ss if s.get("status") == "completed" and s.get("host")})}" for c, i in r.items()), sep="\n")' docs/evidencia/carga_<AAAAMMDD_HHMMSS>.json
```

### 5.5 Qué contiene la evidencia

- Por cada nodo: `hostname`, `tailscale ip -4`, `docker compose ps` y `check_connectivity`.
- `GET /workers` con los tres nodos activos e IP por nodo.
- `tailscale status`. **Puede mostrar nombres de cuenta: ocúltalos antes de versionar, porque el repositorio es público.** Muestra las máquinas de la red, no prueba que un worker corra en cada una; eso lo prueba `docker compose ps` en cada nodo.
- `CLIENT LIST`, con el origen de cada conexión visto desde Redis. Si no distingue los nodos, pierde valor como observación independiente y se declara así.
- La tabla de §5.4, la ruta del JSON de `run_load` y la salida de pytest.
- Dónde se atascó quien siguió la guía (RNF-22, SUP-21).

`NODE_NAME` y `NODE_IP` son declarados, por eso importan las dos observaciones independientes. El tiempo y el reparto se registran tal como salgan, sin interpretarlos como rendimiento: `run_load` usa operaciones multimedia y demuestra distribución, no el sistema completo.

### 5.6 Lista de comprobación

- [ ] Prerrequisitos listos y las cuatro máquinas en la misma red de Tailscale (§2).
- [ ] Cada `.env` con `NODE_NAME` único, su `NODE_IP`, `WORKER_ID` vacío, credenciales propias y sin versionar (§3).
- [ ] `NODE_NAME` y `NODE_IP` sin definir en el shell de cada máquina (§3).
- [ ] Nodo A levantado, sin workers y con los puertos solo en su IP de Tailscale (§1, §4).
- [ ] `check_connectivity` con salida `0` en los tres nodos worker (§4).
- [ ] Tres entradas `alive: true` en `GET /workers`, con su `hostname` e `ip` (§4).
- [ ] `run_load` con salida `0` (§5.2).
- [ ] Aceptación con `1 passed`; `skipped` no cuenta (§5.3).
- [ ] Tabla por `hostname`, declarando que incluye fallidas (§5.4).
- [ ] Sub-tareas de un mismo caso completadas en hosts distintos (§5.4). La aceptación no lo exige, porque las colas no lo garantizan; si ningún caso lo muestra, se declara.
- [ ] Evidencia completa y `tailscale status` sin nombres de cuenta (§5.5).

## 6. Pruebas automatizadas

Sin Docker, Redis ni FFmpeg reales; las que requieren FFmpeg se omiten si no está instalado:

```bash
pytest -q -m "not integration and not acceptance"
```

## 7. Problemas

Ninguna fila se ha reproducido sobre nodos reales. «Sin comprobar» marca lo que el SPEC deja abierto: no se conoce el resultado.

### Despliegue

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `check_connectivity` falla en el contenedor, pero en el host `Test-NetConnection <IP_TAILSCALE_NODO_A> -Port 6380` responde | **Sin comprobar.** Un contenedor de Docker Desktop en WSL2 no alcanza la red Tailscale del host. Es la base de esta topología | **La Parte 2 se detiene** y se devuelve a `plan`: `python scripts/flujo.py devolver plan "motivo"`. No improvises otra red |
| `curl: (60)` o error de revocación en Windows con `curl.exe` | Schannel no puede comprobar la revocación de una CA propia. Reproducido en un nodo Windows real | Añade `--ssl-no-revoke` al `curl.exe` y conserva `--cacert` (ver «Conectarse al Nodo A desde Windows», paso 4) |
| `define WORKER_MEM_LIMIT en .env` | Falta `WORKER_MEM_LIMIT` en `.env` o está vacía | Defínelo; para la prueba de conexión sirve `2g` (no medido) |
| `ADMISSION_MARGIN_BYTES es obligatoria...` durante la prueba de conexión | No debería salir: algo arrancó el worker en vez de `check_connectivity` | Revisa el comando del paso 6. Al arrancar el worker real sí se exigen: mídelas (M1 §4.1), no las inventes |
| `check_connectivity` falla con TLS aunque `.env` y red estén bien | Imagen `deploy-worker` antigua, anterior a F-27. Ocurrió en un nodo Windows real | `docker compose --env-file .env -f deploy/docker-compose.worker.yml build worker` y repite |
| `Test-NetConnection` tampoco responde | Tailscale inactivo en alguna máquina, o el Nodo A sin levantar | `tailscale status`, `tailscale ping <IP_TAILSCALE_NODO_A>` y, en el Nodo A, `docker compose ps` |
| `docker compose up` falla al publicar puertos en el Nodo A | **Sin comprobar.** Tailscale inactivo o `NODE_IP` distinto de `tailscale ip -4`. También podría ocurrir tras reiniciar, si Docker arranca antes que Tailscale | Activa Tailscale, corrige `NODE_IP` y repite `docker compose up -d` |
| `required variable NODE_NAME is missing a value` | Falta `--env-file .env`, comando fuera de la raíz o `.env` sin completar | Repite desde la raíz con `--env-file .env` |
| Compose no reconoce variables que sí están en `.env` | **Sin comprobar.** `.env` con BOM o UTF-16 | Reescríbelo como indica §3 |
| Docker rechaza el `hostname` | **Sin comprobar.** Nombre de máquina Windows no aceptado | Corrige en la Parte 2, por el ciclo normal |
| Sin permiso para escribir `dataset/` en §5.1 | **Sin comprobar.** El contenedor corre como `appuser`, cuyo UID puede no coincidir con el dueño de la carpeta | Ajusta el dueño de `dataset/` y repite |
| `CLIENT LIST` no distingue los nodos | **Sin comprobar.** IP de origen a través del puerto publicado | Se declara en la evidencia |

### Identidad y aceptación

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `1 skipped` | Faltan `COORDINATOR_URL` o `RUN_LOAD_JSON` | Defínelas como en §5.3. No cuenta como aceptación |
| Una sola entrada para los tres nodos, `nodos activos distintos: 1` | `WORKER_ID` fijo, o `NODE_NAME` repetido | Vacía `WORKER_ID` o corrige `NODE_NAME`, y recrea el contenedor |
| `ip ... fuera de 100.64.0.0/10` | `NODE_IP` no es la de Tailscale | Corrige con `tailscale ip -4` |
| `host ... no es un hostname activo` | `NODE_NAME` del shell distinto al del `.env`, o el worker se cayó tras la corrida | Revisa `Get-ChildItem Env:NODE_NAME, Env:NODE_IP -ErrorAction SilentlyContinue` y `docker compose ps` |
| `hosts con sub-tareas completadas: N` menor que 3 | Un nodo no completó nada, solo tuvo fallos, o la corrida fue corta | Revisa sus logs y `failure_breakdown`; repite con un `--limit` mayor |
| `run_load termino con timed_out` | Corrida incompleta | Repite con un `--timeout` mayor |

### Operación

| Síntoma | Causa | Qué hacer |
|---|---|---|
| Worker no conecta a Redis | `REDIS_PASSWORD` incorrecto o `REDIS_HOST` no alcanzable | Revisa `.env` y repite `check_connectivity` |
| `MinIO no responde` | `MINIO_ENDPOINT` o credenciales erróneas | Prueba la consola en el puerto 9001; revisa `MINIO_ACCESS_KEY` y `MINIO_SECRET_KEY` |
| `pull access denied for minio/minio` | La imagen oficial ya no es pública | Usa el Compose actual o `MINIO_IMAGE=...` |
| `POST /cases` responde 422 | Operación inválida, caso sin sub-tareas o `priority` distinta de `normal` y `high` | El detalle de la respuesta indica el valor inválido |
| Sub-tareas `failed` con `StorageError` | `file_path` no existe en el bucket `dataset` | Sube el archivo (`seed_minio`, `submit_case` o `run_load --upload`) y usa la clave sin el nombre del bucket |
| Sub-tareas mucho tiempo en `assigned` o `running` | Worker muerto; el reaper tarda hasta `HEARTBEAT_TTL + REAPER_INTERVAL`, unos 25 s | Espera: se reencola y el caso pasa a `retrying`. Si no ocurre, revisa `reaper` en el Nodo A |
| `reports:pending` crece sin parar | Coordinador caído o `COORDINATOR_URL` errónea | Revisa `docker compose logs coordinator` |
| Timeout de FFmpeg en sub-tareas largas | `FFMPEG_TIMEOUT` vacío: proporcional a la duración, tope 1800 s, o 600 s si se desconoce. Con un valor bajo, rige ese | Vacíalo o súbelo en `.env` |

## 8. Referencia de operación

### Enviar casos

```bash
python -m scripts.submit_case --dir <carpeta> [--prefix <nombre>] [--mode auto|mixed|<operacion>] \
    [--no-upload] [--repeat N] [--priority normal|high] [--cancel-after S] [--timeout S] [--poll T]
```

| Opción | Significado |
|---|---|
| `--dir` | Obligatoria. Carpeta con archivos multimedia |
| `--prefix` | Prefijo en MinIO. Por defecto, el nombre de la carpeta |
| `--mode auto` | Envía `task_type: "auto"` y el coordinador detecta por extensión: video a `transcode_video`, audio a `convert_audio`, otro a `extract_metadata`. El script omite los que no son audio ni video |
| `--mode mixed` | Cicla operaciones en el cliente. Video: transcode, extract_audio, generate_thumbnail, metadata. Audio: convert, metadata |
| `--mode <operacion>` | Una de las cinco operaciones |
| `--no-upload` | No sube a MinIO |
| `--repeat N` | Crea N casos en paralelo |
| `--priority` | `normal` por defecto; `high` usa `queue:{op}:high` |
| `--cancel-after S` | Cancela S segundos después de enviar (`POST /cases/{id}/cancel`) |
| `--timeout S`, `--poll T` | Espera máxima, 600 s por defecto, e intervalo de consulta, 2 s |

Al llegar a un estado terminal imprime el reporte consolidado: prioridad, totales por tipo y operación, fallos y promedio por host. Salida: 0 si todos terminaron, 2 si alguno superó `--timeout`, 1 si hubo error.

`submit_case` sube los archivos por sí mismo. Para subir sin enviar casos: `python -m scripts.seed_minio <carpeta> --prefix <nombre>`. Crea claves `<nombre>/<archivo>` en el bucket `dataset`, y esa clave, sin el bucket, es el `file_path` de `POST /cases`.

Casos aleatorios adicionales, de 100 a 500, con archivos del manifiesto ya subidos:

```bash
python -m scripts.generate_dataset --url https://<IP_TAILSCALE_NODO_A>:8443 --seed 1
python -m scripts.generate_dataset --dry-run    # solo muestra los payloads
```

Con TLS activo el Nodo A sirve `https://...:8443`, pero `dashboard/app.py` (campo «URL del servidor») y el valor por defecto de `--url` en `scripts/generate_dataset.py` siguen en `http://localhost:8000`. No cambian: fija la URL `https://<IP_TAILSCALE_NODO_A>:8443`. Los scripts que usan `src/infrastructure/tls.py` (`submit_case`, `generate_dataset`) leen `TLS_CA_FILE`; el dashboard usa `requests` directo y necesita `REQUESTS_CA_BUNDLE=<ruta de ca.pem>`.

### Monitorear

```bash
BASE=https://<IP_TAILSCALE_NODO_A>:8443
curl "$BASE/stats"                       # colas, casos por estado, workers vivos
curl "$BASE/workers"                     # heartbeat de cada worker, con "alive"
curl "$BASE/cases?status=retrying"       # casos por estado
curl "$BASE/cases/<case_id>/report"      # reporte consolidado
curl "$BASE/subtasks/<subtask_id>"       # una sub-tarea
curl -X POST "$BASE/cases/<case_id>/cancel"
```

Redis, desde el Nodo A; el contenedor ya tiene la contraseña en `REDISCLI_AUTH`:

```bash
docker compose exec redis redis-cli SMEMBERS workers:registry
docker compose exec redis redis-cli HGETALL worker:<worker_id>
docker compose exec redis redis-cli HGETALL subtask:<subtask_id>
docker compose exec redis redis-cli LLEN queue:transcode_video:high
docker compose exec redis redis-cli LLEN reports:pending
```

Cada sub-tarea de `GET /cases/<case_id>/report` incluye `host`, `worker_id`, `processing_s` y `encoder`, por ejemplo `libx264` o `h264_nvenc`, y el reporte trae `avg_processing_s_by_host`. Los logs de cada worker también nombran sus sub-tareas.

### Bajar resultados

```bash
python -m scripts.fetch_results <case_id> [<case_id> ...] --out resultados [--only-completed]
```

Baja del bucket `results`, con claves `<caso>/<subtarea>/...`, a `resultados/<caso>/<operacion>/<subtarea>/`, y escribe `reporte.json` y `reporte.md`. También se ven en la consola de MinIO.

### Nodo GPU (F-32, fuera de esta topología base)

`HWACCEL=nvenc` en el `.env` de ese nodo pide NVENC en `transcode_video`. Si falla o no hay GPU, cae a CPU, y un `hwaccel` explícito en los parámetros de la sub-tarea tiene prioridad. Requiere driver NVIDIA y soporte de GPU en Docker Desktop con WSL2; en Linux, `nvidia-container-toolkit`.

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml -f deploy/docker-compose.worker-gpu.yml up -d --build
```

Comprueba `gpu`, `nvenc_ok` y `hwaccel` en `GET /workers`. La GPU se detecta con una codificación NVENC real (`detect_hw_encoders`), no solo mirando `ffmpeg -encoders`. Para un nodo de video, combina `WORKER_QUEUES=transcode_video,extract_audio` con `HWACCEL=nvenc`; el campo `encoder` confirma qué se usó.

### Worker nativo (fuera de esta topología)

La aceptación de F-38 se hace con Compose. El worker también corre sin Docker, con el mismo `.env`, Python 3.13 o superior, un venv con `requirements.txt` y FFmpeg (`winget install --id Gyan.FFmpeg -e`):

```powershell
py -m scripts.check_connectivity
py -m src.workers.worker_node
```

### Prueba local en una sola máquina

Para desarrollo. No demuestra distribución: levanta todo y tres réplicas en un solo equipo, sin `.env` y sin Tailscale.

```bash
docker compose -f deploy/docker-compose.local.yml up -d --build
cp .env.demo .env    # solo en un clon de desarrollo: reemplaza el .env del nodo
python -m scripts.submit_case --dir <carpeta> --mode mixed --timeout 120
docker compose -f deploy/docker-compose.local.yml down
```

Coordinador en `http://localhost:8000/docs`, MinIO en `http://localhost:9001`. Demo con casos que llegan solos: `docs/DEMO.md`.

## 9. Pruebas de tolerancia a fallos

Con una carga en curso, observa la recuperación con `GET /stats`, `GET /workers` y `GET /cases?status=retrying`. Justificación: `docs/DECISIONES_DISENO.md`, decisión 8. Los escenarios formales son de F-33 a F-37.

| Falla | Cómo provocarla | Qué debe ocurrir |
|---|---|---|
| Worker muere a mitad de una sub-tarea | `docker kill <contenedor>` | El heartbeat expira en 15 s y el reaper reencola en su siguiente ciclo, unos 25 s en total. El caso pasa a `retrying` con `retries` + 1 y otro worker la termina |
| Worker se reinicia | Reiniciar el contenedor; `worker_id` se conserva porque `hostname` es fijo | `recover_own_inflight()` reencola sus sub-tareas sin esperar al reaper |
| Coordinador caído | `docker compose stop coordinator` unos 30 a 60 s, luego `docker compose start coordinator` | Los workers siguen. Sus reportes se reintentan (1, 2, 4, 8, 16 s) y quedan en `reports:pending`; al volver se entregan, cada 15 s, sin perder ni duplicar |
| Redis se reinicia | `docker compose restart redis` | Recarga su AOF; los workers reconectan con espera exponencial, de 1 a 30 s |
| Sub-tarea agota `MAX_ATTEMPTS` | Matar repetidamente a los workers que la toman | El reaper reporta `failed` con `error_type=WorkerLostError` |

## 10. Workers de análisis tipados (F-43)

> **Estado:** ninguno de estos pasos se ha ejecutado en nodos reales. Los valores de memoria y de huellas están sin medir y marcados «Medición pendiente»; no se inventan.

Los workers de análisis consumen `queue:text`, `queue:image` y `queue:audio`. Se levantan con `deploy/docker-compose.analisis.yml` y la imagen `Dockerfile.analisis` (Python 3.13, `requirements-texto|imagen|audio.txt`, `torch` solo CPU, FFmpeg). `Dockerfile.worker` queda para el worker FFmpeg, el reaper y el coordinador. Los tres servicios (`worker-texto`, `worker-imagen`, `worker-audio`) conservan el endurecimiento de F-30: usuario `10001:10001`, `read_only`, `cap_drop: ALL`, `no-new-privileges`, `scratch` y `tmpfs`, `mem_limit` igual a `memswap_limit`, `hostname` desde `NODE_NAME` y sin `--scale`. Cada servicio tiene su propio `WORKER_ID` (`worker-<NODE_NAME>-<tipo>`), porque comparten `hostname` en el mismo nodo.

### 10.1 Variables nuevas

Van en el `.env` de cada nodo worker (`.env.example` las trae comentadas):

| Variable | Valor | ¿Igual en los nodos? |
|---|---|---|
| `COMPOSE_PROFILES` | Tipos que corre ese nodo: `texto`, `imagen` y `audio`, separados por coma | No |
| `WORKER_KIND` | Lo fija el Compose por servicio (`text`, `image`, `audio`); no se define en `.env` | Fijo |
| `OBJECTS_BUCKET` | Bucket de los objetos cifrados; el mismo que usa el coordinador (por defecto `objetos`) | Sí, e igual al del Nodo A |
| `KEK_FILE` | Ruta de la KEK **en esa máquina** (§10.3). El Compose la monta de solo lectura en `/run/secrets/kek` y pasa esa ruta al contenedor | La ruta puede variar; el contenido, no |
| `WORKER_MEM_LIMIT_TEXT`, `_IMAGE`, `_AUDIO` | Límite de memoria por tipo. **Sin valor por defecto. Medición pendiente (M1)** | Según la medición |
| `ADMISSION_MARGIN_BYTES` | Margen de admisión. **Obligatorio, sin valor por defecto. Medición pendiente (M1 §4.1)** | Según la medición |
| `FOOTPRINT_TEXT_BYTES`, `FOOTPRINT_IMAGE_BYTES`, `FOOTPRINT_AUDIO_BYTES` | Huella por tipo. **Obligatorias, sin valor por defecto. Medición pendiente (M1 §4.1)** | Sí: es propiedad del tipo, no del nodo |
| `FRAME_EVERY_S`, `FRAME_MAX` | Muestreo de video (SUP-48). Si faltan, el Compose usa 5 y 20. **Provisionales, sin medir** | Sí |
| `CONFIG_DIR`, `HF_HOME`, `XDG_CACHE_HOME`, `YOLO_WEIGHTS_DIR` | Los fija el Compose: `/app/config`, `/models/huggingface`, `/models/cache`, `/models/yolo` | Fijos |

Compose interpola todo el archivo aunque un perfil esté inactivo, así que cada nodo debe definir las tres variables `WORKER_MEM_LIMIT_*` y las tres `FOOTPRINT_*_BYTES`, también las de los tipos que no corre. El límite de un tipo inactivo no consume memoria: solo cuenta si su perfil está activo. Si falta alguna, `docker compose` se niega con el nombre de la variable y no arranca ningún contenedor.

### 10.2 Reparto por nodo

Cada tipo debe correr en al menos dos nodos para reasignar sub-tareas tras una caída (ARQUITECTURA §6). Tres procesos con `torch` y los modelos de HuggingFace, YOLO y Whisper pueden no caber juntos en un nodo, y las huellas no están medidas, así que el reparto es **provisional (Medición pendiente)**:

| Nodo | `COMPOSE_PROFILES` | Corre |
|---|---|---|
| B | `texto,imagen` | `worker-texto`, `worker-imagen` |
| C | `imagen,audio` | `worker-imagen`, `worker-audio` |
| D | `audio,texto` | `worker-audio`, `worker-texto` |

Cada tipo queda en dos nodos. Si M1 muestra que dos tipos no caben en un nodo, se reasigna cambiando solo `COMPOSE_PROFILES`, siempre que cada tipo siga en dos nodos. El Nodo A no corre workers.

Comprobación del presupuesto y arranque, desde PowerShell en cada nodo (`--analisis` suma el worker FFmpeg; `--solo-analisis` corre únicamente los tipados):

```powershell
python scripts/preflight.py --solo-analisis
python scripts/start_worker.py --solo-analisis
docker compose --env-file .env -f deploy/docker-compose.analisis.yml ps
```

Sin `--env-file .env`, Compose no lee el `.env` de la raíz. El preflight valida `NODE_NAME`, `NODE_IP`, los límites y la suma contra la RAM del nodo, y que `ADMISSION_MARGIN_BYTES` y la huella de cada tipo activo sean enteros positivos.

**Pesos de modelos.** Con `read_only`, los pesos de HuggingFace y de YOLO viven en el volumen `modelos` (`/models`). No están en el repositorio: la primera carga descarga de internet, o se precargan según la decisión pendiente del SPEC (pregunta 8). El volumen conserva los pesos entre reinicios. Los pesos de YOLO deben tener el `sha256` fijado en `config/imagen.toml`.

### 10.3 Distribución de la KEK a los tres nodos

La KEK es un secreto de 32 bytes que envuelve las llaves de los objetos (AD-16, SUP-30). Los tres nodos worker y el Nodo A usan **el mismo valor**, porque leen los mismos objetos. **Nunca se guarda en el repositorio** (es público; B.5 M4), ni en `.env`, ni en un volumen de Docker, ni en el historial de comandos. `.gitignore` excluye `*.kek` y `kek*` solo como red de seguridad.

`FileKeyProvider` exige un archivo regular con modo exactamente `0400` o `0600`; con otro modo, el worker falla cerrado con `KeyUnavailable`. El contenedor corre como UID 10001, así que en los workers el archivo debe pertenecer a ese UID para que `0400` sea legible.

**1. Generarla una vez, en el Nodo A, fuera del repositorio:**

```bash
install -d -m 700 "$HOME/.ms-kek"
umask 077
openssl rand -out "$HOME/.ms-kek/kek" 32
chmod 0400 "$HOME/.ms-kek/kek"
stat -c '%a %s' "$HOME/.ms-kek/kek"        # debe dar: 400 32
```

En el Nodo A, `KEK_FILE=$HOME/.ms-kek/kek` (ruta absoluta) en su `.env`. El coordinador corre con `CERTS_UID`, que es quien generó el archivo, así que lo lee.

**2. Copiarla a cada nodo por un canal privado** (por ejemplo `scp` sobre Tailscale o el gestor de secretos del equipo; nunca por chat, correo ni `git`). Se borra cualquier copia intermedia.

**3. Instalarla en cada nodo worker.** Docker Desktop sobre WSL2 puede mostrar un bind mount desde NTFS con modo `0777` en el contenedor, y el worker rechazaría la llave. Por eso la KEK vive en el sistema de archivos de la distro WSL2 y se monta desde ahí. En la terminal de la distro:

```bash
install -d -m 700 "$HOME/.ms-kek"
# copiar aquí el archivo recibido como $HOME/.ms-kek/kek
sudo chown 10001:10001 "$HOME/.ms-kek/kek"
sudo chmod 0400 "$HOME/.ms-kek/kek"
stat -c '%a %u %s' "$HOME/.ms-kek/kek"     # debe dar: 400 10001 32
```

`KEK_FILE` en el `.env` del nodo es la ruta de ese archivo tal como la ve el motor de Docker. **No verificado:** si el Compose se lanza desde PowerShell, la ruta de la distro (`\\wsl$\<distro>\...`) puede no montarse con el modo `0400`; en ese caso se lanza `docker compose` desde la terminal de la distro, con una copia del repositorio dentro de ella y `KEK_FILE=/home/<usuario>/.ms-kek/kek`. **Debe probarse en un nodo real antes de darlo por procedimiento.**

**4. Comprobar lo que ve el contenedor**, sin arrancar el worker:

```bash
docker compose --env-file .env -f deploy/docker-compose.analisis.yml run --rm --no-deps worker-texto stat -c '%a %u %s' /run/secrets/kek
```

Esperado: `400 10001 32`. Cualquier otro modo o un error de permiso se corrige antes de arrancar. Comprueba también que el repositorio no la contiene: `git status --short` no debe listar la llave.

**Pérdida, filtración y rotación.** Sin la KEK no se descifra ningún objeto. Si se filtra, hay que regenerarla y recifrar los objetos; la rotación queda fuera de alcance (SUP-30). La variable `KEK` en base64 queda solo para desarrollo.

### 10.4 Nodo A

`docker-compose.yml` pasa ahora `OBJECTS_BUCKET`, `STAGING_DIR` y `KEK_FILE` al coordinador, que sin ellos no puede comprobar las fuentes de `POST /cases` ni cifrar subidas. Define `KEK_FILE` en el `.env` del Nodo A (ruta del archivo del §10.3): Compose lo exige y lo monta `:ro`. `staging-init` deja el volumen `coordinator-staging` a nombre de `CERTS_UID`. Reconstruye con `docker compose up -d --build`.

### 10.5 Verificación en el repositorio

```bash
python -m scripts.verificar_workers
pytest -q tests/unit/test_despliegue_compose.py tests/unit/test_f16_preflight.py
```

`verificar_workers` revisa los tres Compose de workers y los dos Dockerfile. Sin comprobar aún: construir la imagen con `torch` en un nodo, que los workers tipados arranquen contra el Nodo A y que `GET /workers` los muestre; eso es la corrida real de F-43.
