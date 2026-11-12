# F-33: ráfaga de B.6 en simulación local

> **SIMULACIÓN LOCAL: tres contenedores worker en una sola máquina. No acredita B.2, ni Tailscale, ni entidades de ejecución separadas.** No reemplaza la prueba en tres nodos reales, que sigue **PENDIENTE** (F-38 con nodos reales). Se acepta provisionalmente como criterio de cierre de F-33 por decisión de la persona. No es una medición de SO (M1 a M5).

Fecha de la corrida: 2026-11-12, 17:35 a 17:39 UTC. La ejecutó un agente (QA y medidor) bajo autorización explícita de la persona; la persona no corrió estos comandos. Commit del código: `dabd565` (rama `feat/F-33-2-rafaga`, con `scenarios/burst.py` de la parte 1).

Datos crudos en `docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/`, un subdirectorio por corrida (`rep1`, `rep2`, `rep3` y `opcional_40casos`). Cada uno tiene `carga_*.json` y `carga_*.md` (salida de `run_load`), `latencia_por_caso.csv`, `recursos_por_nodo.csv`, `veredicto.json` (salida estándar de `scenarios.burst`), `rc.txt` (código de salida), `inicio_utc.txt`, `fin_utc.txt` y `workers_antes.json` / `workers_despues.json` (contadores de `GET /workers`, acumulados desde el arranque de los workers). Los `carga_*` llevan la hora local del equipo (UTC-6) en el nombre. `stderr` quedó vacío en todas y se borró.

## Entorno

- Una máquina Linux (`uname -sr`: `Linux 6.12.116+deb13-amd64`; 8 CPU, 7,51 GB según el heartbeat), Docker `26.1.5+dfsg1`, Compose `2.26.1-4`.
- Nodo A: el `docker-compose.yml` de la raíz, **con TLS activo** (Redis 6380 TLS 1.3, MinIO y coordinador 8443), proyecto `f33-nodoa`, puertos publicados en `172.17.0.1` (IP de `docker0`, no de Tailscale). CA y certificado de demo creados con `deploy/tls/generar_certs.sh` para `NODE_IP=172.17.0.1`.
- Tres workers con `deploy/docker-compose.worker.yml`, un proyecto Compose por worker (`f33-w1`, `f33-w2`, `f33-w3`), cada uno en su propia red bridge, `read_only`, `cap_drop: ALL`, usuario `10001:10001`, `mem_limit` 1 GiB, `WORKER_CONCURRENCY=2` (comprobado con `docker inspect`).
- `NODE_NAME` `worker-sim-1/2/3`; `NODE_IP` `100.64.0.11/12/13` **declarados, no son IP de ninguna interfaz real**.
- Credenciales: `JWT_SECRET`, `WORKER_TOKEN` (rol `servicio`) y `API_TOKEN` (rol administrador) generados con `scripts/generar_credenciales` (vigencia 3 días); contraseñas de Redis y MinIO con `secrets.token_hex(24)`. Todo en archivos fuera del repositorio, ninguno versionado; el `.env` de la raíz no se tocó.
- **Huellas y margen de admisión (F-17) son placeholders, NO medidos:** `ADMISSION_MARGIN_BYTES=134217728` (128 MiB) y cinco `FOOTPRINT_*_BYTES=268435456` (256 MiB), los mismos de la simulación de F-38. La ficha M1 §4.1 sigue pendiente.
- Dataset: regenerado con el generador actual en la imagen del worker (FFmpeg 7.1.5): `listo: 480 archivos, 655.7 MB, 135 casos` en 2 min 40 s. Su `cases.json` es idéntico al versionado en `dataset/`; `manifest.json` solo difiere en los tamaños en bytes de algunos archivos (salida de FFmpeg) y en 2 líneas del `README.md`. Se generó fuera del repositorio.
- Con `--limit 20` y `--limit 40` el escenario toma los primeros casos de `cases.json`. Los 20 primeros son todos homogéneos y de `convert_audio` (135 sub-tareas); los 40 primeros incluyen `transcode_video` y `generate_thumbnail`.

## Comandos

Variables de entorno de la corrida (sin imprimir secretos): `REDIS_HOST=172.17.0.1 REDIS_PORT=6380 COORDINATOR_URL=https://172.17.0.1:8443 MINIO_ENDPOINT=172.17.0.1:9000 MINIO_SECURE=true TLS_ENABLED=true TLS_CA_FILE=<ca.pem>` y `API_TOKEN`; exportadas, de modo que ganan sobre cualquier `.env`.

```bash
# Nodo A (S = carpeta fuera del repo con nodoa.env, certs/ y los overrides)
NODE_IP=172.17.0.1 NODE_NAME=nodo-a-sim CERTS_DIR=$S/certs bash deploy/tls/generar_certs.sh
docker compose -p f33-nodoa --env-file $S/nodoa.env -f docker-compose.yml -f $S/override-nodoa.yml build
docker compose -p f33-nodoa --env-file $S/nodoa.env -f docker-compose.yml -f $S/override-nodoa.yml up -d

# Workers, n = 1, 2, 3
W() { n=$1; shift; docker compose -p f33-w$n --env-file $S/w$n.env -f deploy/docker-compose.worker.yml -f $S/override-w$n.yml "$@"; }
W 1 run --rm worker python -m scripts.check_connectivity   # salida 0, redis, coordinador, minio, ffmpeg y work_dir OK
for n in 1 2 3; do W $n build; W $n up -d; done

# Dataset (fuera del repo) y subida a MinIO
docker run --rm --user 1000:1000 -v <destino>:/out f33-w1-worker python -m scripts.build_dataset --out /out --files 480 --seed 42
python - <<'PY'   # equivale a `run_load --upload` sin enviar casos; salida: {'uploaded': 480, 'skipped': 0, 'failed': 0}
from pathlib import Path
from scripts import run_load
from src.workers.config import Settings
from src.workers.storage import Storage
s = Settings.from_env(); d = Path("<destino>")
m, _ = run_load.load_dataset(d)
print(run_load.upload_dataset(Storage(s), m, d / "media", s.dataset_bucket, 8))
PY

# Ráfaga (una vez por repetición, con unos 20 s de pausa entre ellas)
PYTHONPATH=. python -m scenarios.burst --dataset <destino> --limit 20 --concurrency 20 --timeout 1800 --out docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/rep<N>
# Opcional
PYTHONPATH=. python -m scenarios.burst --dataset <destino> --limit 40 --concurrency 40 --timeout 1800 --out docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/opcional_40casos

# Gráficos (desde los CSV)
python docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/graficar.py
```

`GET /workers` (con `Authorization: Bearer $API_TOKEN` y `--cacert ca.pem`) mostró los tres hosts vivos antes de cada corrida. Los dos archivos de override (por nodo) están descritos en «Desviaciones»; no se versionan porque contienen rutas locales y el `env_file` apunta a archivos con secretos.

## Resultado de cada repetición

Veredicto de `scenarios.burst` en las cuatro corridas: `{"cumple": true, "problemas": []}`, código de salida 0.

| Corrida | Casos | Estado de los casos | Sub-tareas finalizadas | Tiempo total (s) | Throughput (sub-tareas/min) | Sub-tareas por host (1 / 2 / 3) | Veredicto |
|---|---|---|---|---|---|---|---|
| rep1 | 20 | 20 `completed` | 135 de 135 | 15,521 | 521,87 | 52 / 41 / 42 | cumple |
| rep2 | 20 | 20 `completed` | 135 de 135 | 15,527 | 521,68 | 45 / 43 / 47 | cumple |
| rep3 | 20 | 20 `completed` | 135 de 135 | 20,572 | 393,74 | 41 / 51 / 43 | cumple |
| opcional 40 | 40 | 39 `completed`, 1 `partially_completed` | 263 de 263 (2 fallidas) | 81,237 | 194,25 | 113 / 80 / 70 | cumple |

Las tres repeticiones se reportan completas. La rep3 tardó 5 s más que las otras dos (393,74 contra unos 522 sub-tareas/min); no se investigó la causa (una sola máquina; no se aisló de otras cargas durante la corrida).

### Latencia por caso (de `latencia_por_caso.csv`, recalculada)

| Corrida | Mínima (s) | Mediana (s) | Media (s) | p95 (s, rango más cercano) | Máxima (s) | Media prioridad `high` (s) | Media prioridad `normal` (s) |
|---|---|---|---|---|---|---|---|
| rep1 | 1,608 | 6,688 | 6,330 | 10,444 | 11,260 | 1,871 (2 casos) | 6,825 (18 casos) |
| rep2 | 1,605 | 6,074 | 6,321 | 10,859 | 10,973 | 1,917 (2) | 6,811 (18) |
| rep3 | 1,059 | 6,331 | 6,027 | 11,207 | 11,224 | 1,331 (2) | 6,548 (18) |
| opcional 40 | 0,532 | 64,407 | 54,493 | 75,545 | 76,878 | 2,531 (4) | 60,267 (36) |

Los CSV y el `carga_*.json` coinciden caso por caso (se comprobó el orden de las duraciones). La prioridad `high` se asigna a la fracción 0,1 de los casos con la semilla 42 (`run_load`).

### Recursos por nodo (de `recursos_por_nodo.csv`)

| Corrida | Muestras por host | Pico `cpu_percent` (1 / 2 / 3) | Pico de sub-tareas activas por host | `mem_percent` (mín. a máx.) | Máx. simultáneas | Longitud máxima de cola |
|---|---|---|---|---|---|---|
| rep1 | 4 | 76,6 / 76,4 / 75,8 | 2 / 2 / 2 | 50,0 a 53,2 | 6 | `convert_audio` 117 (+12 `high`) |
| rep2 | 4 | 76,4 / 75,9 / 76,0 | 2 / 2 / 2 | 51,3 a 53,5 | 6 | `convert_audio` 117 (+12 `high`) |
| rep3 | 5 | 76,7 / 76,5 / 76,8 | 2 / 2 / 2 | 51,6 a 54,1 | 6 | `convert_audio` 123 (+6 `high`) |
| opcional 40 | 16 | 99,4 / 99,4 / 99,4 | 2 / 2 / 2 | 51,3 a 66,6 | 6 | `convert_audio` 155 (+31), `transcode_video` 50, `generate_thumbnail` 21 |

Gráficos (de los CSV, con `graficar.py`): `docs/evidencia/F-33_rafaga_simulacion_local_2026-11-12/latencia_por_caso.png` y `recursos_por_nodo.png`.

### Cifras recalculadas desde los datos crudos

- Throughput de rep1: `135 / 15,521 s x 60 = 521,87` sub-tareas/min, igual al del JSON. En rep2 sale 521,67 contra 521,68 del JSON: el JSON usa el tiempo sin redondear.
- Sub-tareas por host: la suma por corrida da 135 (rep1: 52+41+42; rep2: 45+43+47; rep3: 41+51+43) y 263 en la de 40 casos (113+80+70). Los contadores de `GET /workers` tras la última corrida (`completed_count` 250 / 215 / 201, `failed_count` 1 / 0 / 1; 666 completadas y 2 fallidas) cuadran con la suma de las cuatro corridas (135 x 3 + 263 = 668).
- Los tres workers procesaron sub-tareas en todas las corridas, así que la evaluación de «al menos tres nodos» se cumple con datos, no por construcción de las series.

## Desviaciones de la receta de F-38 (2026-11-11)

La receta de F-38 es anterior a F-26 (JWT), F-27 (TLS), F-24 y los cambios de Compose. Cambios, uno por uno:

1. **TLS activo** (F-38 iba sin TLS): se generaron certificados de demo para `172.17.0.1`; los workers montan `ca.pem`. Los scripts del equipo anfitrión usan `TLS_CA_FILE`.
2. **Autenticación**: `JWT_SECRET` en el coordinador, `WORKER_TOKEN` en cada worker, `API_TOKEN` para los scripts. Antes no existían.
3. **Puertos**: Redis 6380 (TLS) y coordinador 8443, no 6379 y 8000.
4. **No se usó el `.env` de la raíz.** `deploy/docker-compose.worker.yml:15` fija `env_file: ../.env` y `docker-compose.yml:106` (reaper) fija `env_file: .env`: en una máquina compartida, esos archivos serían los reales. Se sustituyeron con un archivo de override (`env_file: !override [...]`, requiere Compose 2.24 o superior) que apunta a un archivo fuera del repositorio. El reaper solo recibe `REDIS_PASSWORD` por `environment`; antes la obtenía del `.env`.
5. **`container_name: redis-server`** (`docker-compose.yml:18`) choca con cualquier otro proyecto Compose en la misma máquina: se renombró a `f33-redis-server` con el override.
6. **Servicio `redis-data-init` y `CERTS_UID` / `CERTS_GID`**: nuevos desde F-27; se fijaron en 1000 / 1000.
7. **Las variables de admisión (F-17) ya están documentadas en `.env.example` y `docs/DEPLOY_WORKERS.md`** (en F-38 faltaban; el Compose del worker las toma del `env_file`): se pasaron por el `env_file` de cada worker, como placeholders sin medir.
8. **El dataset se generó y subió fuera del repositorio**, para no modificar `dataset/manifest.json`, `cases.json` ni `README.md`, que están versionados. `scenarios.burst` no tiene `--upload`, así que la subida se hizo aparte (comando arriba).
9. **Escenario**: F-38 usó `run_load --upload --limit 20`; aquí se usó `scenarios.burst`, que fija `poll=5.0` y `upload=False` (`scenarios/burst.py:101`).

## Límites y problemas encontrados

- **No acredita B.2.** Los tres workers comparten CPU, memoria, disco y kernel. Sin Tailscale, sin latencia de red entre máquinas, sin reinicio de nodos reales.
- **Los recursos por nodo no son por nodo.** `src/workers/heartbeat.py:155-156` reporta `psutil.cpu_percent` y `psutil.virtual_memory().percent`, que dentro de un contenedor leen el host entero. Los tres «nodos» muestran por eso casi el mismo CPU y exactamente el mismo `mem_percent` en cada instante (véase `recursos_por_nodo.png`). No se midió el consumo por contenedor (por ejemplo con `docker stats`).
- **Muy pocas muestras.** `scenarios/burst.py:101` fija `poll=5.0` sin opción en la CLI: una ráfaga de 15 s da 4 muestras por host. No se modificó `scenarios/`.
- **Carga corta.** Los 20 primeros casos son todos de `convert_audio` (cada sub-tarea tarda unos 0,5 s de procesamiento según `run_load`): no ejercitan `transcode_video` ni las demás operaciones, y no producen saturación de memoria ni de CPU sostenida. La corrida opcional de 40 casos sí llega a CPU del host de casi 99 %, con 1 caso `partially_completed`.
- **El veredicto no marca `partially_completed`** (ya declarado: `docs/DEMO.md` y `tests/unit/test_burst_qa.py`). En la corrida de 40 casos, `homogeneo-lote_v04-1` (case_id `28f6a9ab-af28-44dc-a524-ac91f9d798a3`) terminó `partially_completed`, con `failure_breakdown` `CorruptInputError: 1` y `UnsupportedFormatError: 1`, y el veredicto dice `cumple: true`. Es consistente con los 14 archivos «problemáticos» que declara `dataset/README.md`; no se verificó cuáles archivos fueron.
- **Huellas y margen de admisión sin medir.** Los valores usados impiden extrapolar el comportamiento de F-17 a nodos reales.
- **Las IP `100.64.0.1x` son declaradas.** No hay comprobación significativa del rango Tailscale.
- **Backpressure (F-24):** los cuatro veredictos no reportan problemas de envío (`submit_error` haría fallar la evaluación), así que ninguna petición `POST /cases` fue rechazada con `429`; no se buscó en los registros del coordinador.
- **Observación de red:** no se capturó tráfico (`tcpdump` no se usó); no se comprobó el origen de las conexiones a Redis.

## Pendiente (Medición pendiente)

- Ráfaga de B.6 en tres nodos worker reales sobre Tailscale (F-38 con nodos reales), con huellas medidas (M1 §4.1) y más muestras por nodo.
- Corrida con casos que ejerciten las cinco operaciones y la ráfaga de 40 casos (o más) en nodos reales.
- Consumo de CPU y memoria por contenedor o por nodo.

## Limpieza

Al terminar se bajaron los contenedores, redes y volúmenes de la simulación con `docker compose -p f33-nodoa ... down -v` y `docker compose -p f33-w<n> ... down -v`, y se borró el dataset generado fuera del repositorio. Las imágenes públicas (`redis:7-alpine`, `cgr.dev/chainguard/minio`, `python:3.13-slim`) se conservaron.
