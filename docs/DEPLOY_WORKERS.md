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
| `TLS_CA_FILE` | Ruta de `ca.pem` en esa máquina (la copia desde el Nodo A) | Sí |
| `REDIS_HOST` | `<IP_TAILSCALE_NODO_A>` | Sí |
| `COORDINATOR_URL` | `https://<IP_TAILSCALE_NODO_A>:8443` | Sí |
| `MINIO_ENDPOINT` | `<IP_TAILSCALE_NODO_A>:9000` | Sí |
| `REDIS_PASSWORD` | Obligatorio; el Compose del Nodo A no arranca sin él | Sí |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Propias, no `minioadmin`, que es un valor público | Sí |
| `WORKER_ID` | **Vacío** | Sí |
| `WORKER_QUEUES`, `WORKER_CONCURRENCY` | Opcional: `.env.example` trae las cinco operaciones y 2 | Puede variar |
| `HWACCEL` | Vacío, salvo en un nodo GPU (§8) | Puede variar |

Los contenedores del Nodo A ignoran `REDIS_HOST`, `COORDINATOR_URL` y `MINIO_ENDPOINT`, porque su Compose usa nombres de servicio. Esos valores los usan `run_load` y los demás scripts nativos. En el Nodo A, Compose solo usa `NODE_IP` de la identidad; `NODE_NAME` se llena igual por coherencia. El resto de variables está comentado en `.env.example`.

Genera las contraseñas una vez, en el Nodo A, y compártelas por un canal privado del equipo. Hexadecimal evita caracteres que Compose interpretaría, como `$`:

```bash
python3 -c "import secrets; print(secrets.token_hex(24))"
```

**Nodo A:**

```bash
cp .env.example .env
nano .env
```

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

En el `.env` del Nodo A: `CERTS_DIR` (la misma ruta), `CERTS_UID=$(id -u)` y `CERTS_GID=$(id -g)`. Con ellos `coordinator`, `redis` y `minio` corren con ese UID para leer `server.key` (0600); no se probó con las imágenes reales. A cada worker copia **solo** `ca.pem` (nunca `ca.key` ni `server.key`) y fija `TLS_CA_FILE` con su ruta en su `.env`.

```bash
tailscale ip -4    # debe coincidir con NODE_IP
docker compose up -d --build
docker compose ps
curl -s -o /dev/null -w "%{http_code}\n" "https://<IP_TAILSCALE_NODO_A>:8443/openapi.json"
```

Esperado: `redis`, `minio` y `coordinator` en `healthy`, `reaper` corriendo y código `200`. Consola de MinIO: `https://<IP_TAILSCALE_NODO_A>:9001`, con las credenciales de tu `.env`.

MinIO dejó de publicar imágenes públicas, por eso el Compose usa `cgr.dev/chainguard/minio:latest`. Si dejara de estar disponible, define otra en `.env` con `MINIO_IMAGE=...`.

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
