# F-38 parte 2: tres workers en una sola máquina (simulación local)

**SIMULACIÓN LOCAL: tres contenedores en una sola máquina; no acredita B.2 ni Tailscale ni entidades de ejecución separadas**

Fecha: 2026-11-11. Ejecutada por un agente (developer/medidor) bajo orden explícita de la persona; la persona no ejecutó estos comandos. Esta evidencia no sustituye a `docs/evidencia/F-38_tres_nodos_<fecha>.md` de los nodos reales, que sigue pendiente. No es una medición de SO (M1 a M5) ni de rendimiento.

## Entorno

- Una máquina Linux (`uname -sr`: `Linux 6.12.115+deb13.1-amd64`; el heartbeat informa 8 CPU y 7,51 GB), Docker `26.1.5+dfsg1`, Compose `2.26.1-4`.
- Nodo A simulado: `docker compose up -d --build` en la raíz, con `NODE_IP=172.17.0.1` (IP de `docker0`, no de Tailscale) para que los contenedores worker alcancen los puertos publicados. Sin Tailscale ni `sudo`.
- Tres workers: un proyecto Compose por worker (`-p f38-w1`, `-p f38-w2`, `-p f38-w3`), cada uno en su propia red bridge, con `NODE_NAME` y `NODE_IP` distintos.
- Los `NODE_IP` de los workers (`100.64.0.11`, `.12`, `.13`) son **declarados por la simulación**, no son IP reales de ninguna interfaz. Por eso la comprobación de rango `100.64.0.0/10` de la aceptación **no es significativa** aquí: se cumple por construcción.
- Sin `tcpdump`: no hay observación de paquetes.

## Preparación

`.env` de la raíz (ignorado por git): copia de `.env.example` con `<IP_TAILSCALE_NODO_A>` sustituido por `172.17.0.1`, contraseñas y claves generadas con `python3 -c "import secrets; print(secrets.token_hex(24))"` (no se publican), `NODE_NAME=nodo-a-sim`, `NODE_IP=172.17.0.1`, `WORKER_MEM_LIMIT=1g`, `WORKER_ID` vacío.

`env | grep -E '^NODE_(NAME|IP)='` no devolvió nada.

Un archivo de entorno por worker (fuera del repositorio) con solo `NODE_NAME=worker-sim-N`, `NODE_IP=100.64.0.1N`, `WORKER_MEM_LIMIT=1g`, y un archivo de override (fuera del repositorio) que fija en `environment` el `NODE_NAME` y las variables de admisión de F-17 (véase Hallazgos):

```yaml
services:
  worker:
    environment:
      NODE_NAME: ${NODE_NAME}
      ADMISSION_MARGIN_BYTES: "134217728"
      FOOTPRINT_TRANSCODE_VIDEO_BYTES: "268435456"
      FOOTPRINT_EXTRACT_AUDIO_BYTES: "268435456"
      FOOTPRINT_GENERATE_THUMBNAIL_BYTES: "268435456"
      FOOTPRINT_CONVERT_AUDIO_BYTES: "268435456"
      FOOTPRINT_EXTRACT_METADATA_BYTES: "268435456"
```

**Los valores de huella (256 MiB) y margen (128 MiB) son placeholders de simulación, NO medidos.** La ficha M1 §4.1 los tiene como pendientes.

Dataset (guía §5.1, sin cambios):

```bash
docker compose run --rm --no-deps -v "$PWD/dataset:/app/dataset" reaper \
    python -m scripts.build_dataset --out dataset --files 480 --seed 42
```

Salida final: `listo: 480 archivos, 655.7 MB, 135 casos` (3:12 min en total). `dataset/manifest.json` y `dataset/README.md` quedaron modificados y se descartaron con `git checkout`; `dataset/media/` no se versiona.

## Nodo A

```bash
docker compose up -d --build
docker compose ps
curl -s -o /dev/null -w "%{http_code}\n" "http://172.17.0.1:8000/openapi.json"   # 200
```

```
NAME                    IMAGE                             COMMAND                  SERVICE       CREATED              STATUS                        PORTS
redis-server            redis:7-alpine                    "docker-entrypoint.s…"   redis         About a minute ago   Up About a minute (healthy)   172.17.0.1:6379->6379/tcp
wt-f-38-coordinator-1   wt-f-38-coordinator               "python -m uvicorn s…"   coordinator   About a minute ago   Up About a minute (healthy)   172.17.0.1:8000->8000/tcp
wt-f-38-minio-1         cgr.dev/chainguard/minio:latest   "/usr/bin/minio serv…"   minio         About a minute ago   Up About a minute (healthy)   172.17.0.1:9000-9001->9000-9001/tcp
wt-f-38-reaper-1        wt-f-38-reaper                    "python -m scripts.r…"   reaper        About a minute ago   Up About a minute             
```

## Workers

Función de ayuda usada (`$S` es el directorio fuera del repo con los archivos descritos arriba):

```bash
W() { n=$1; shift; docker compose -p f38-w$n --env-file $S/w$n.env -f deploy/docker-compose.worker.yml -f $S/override.yml "$@"; }
W 1 run --rm worker python -m scripts.check_connectivity   # salida 0
for n in 1 2 3; do W $n up -d; done
for n in 1 2 3; do W $n ps; done
```

`check_connectivity` del worker 1 (salida 0; solo se ejecutó en el worker 1):

```
Config: worker_id=worker-worker-sim-1 queues=transcode_video,extract_audio,generate_thumbnail,convert_audio,extract_metadata concurrency=2 threads_per_job=4 redis=172.17.0.1:6379 coordinator_url=http://172.17.0.1:8000 minio_endpoint=172.17.0.1:9000
[OK] redis: Redis OK en 172.17.0.1:6379
[OK] coordinator: Coordinador OK en http://172.17.0.1:8000
[OK] minio: MinIO OK en 172.17.0.1:9000, pero el bucket 'dataset' aun no existe (el worker lo crea al iniciar; o corre este chequeo con --create-buckets)
[OK] ffmpeg: ffmpeg OK: ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers
[OK] work_dir: WORK_DIR escribible: /tmp/mm-worker
```

`W N ps` (workers 1, 2 y 3), tras la carga:

```
NAME              IMAGE           COMMAND                  SERVICE   CREATED          STATUS          PORTS
f38-w1-worker-1   f38-w1-worker   "python -m src.worke…"   worker    50 seconds ago   Up 49 seconds   
f38-w2-worker-1   f38-w2-worker   "python -m src.worke…"   worker    50 seconds ago   Up 49 seconds   
f38-w3-worker-1   f38-w3-worker   "python -m src.worke…"   worker    49 seconds ago   Up 49 seconds   
```

IP de cada contenedor en su red (`docker inspect`):

```
f38-w3-worker-1 f38-w3_default=172.21.0.2
f38-w2-worker-1 f38-w2_default=172.20.0.2
f38-w1-worker-1 f38-w1_default=172.19.0.2
wt-f-38-reaper-1 wt-f-38_default=172.18.0.5
wt-f-38-coordinator-1 wt-f-38_default=172.18.0.4
redis-server wt-f-38_default=172.18.0.2
wt-f-38-minio-1 wt-f-38_default=172.18.0.3
```

## Carga

```bash
python3 -m scripts.run_load --dataset dataset --upload --limit 20
```

Salida 0; escribió `docs/evidencia/carga_20261111_052821.md` y `.json` (versionados con esta evidencia; las horas del log de `run_load` están en hora local, UTC-6). Subida: `{'uploaded': 480, 'skipped': 0, 'failed': 0}`. Resumen del `.md`: 20 casos `completed`, 135 sub-tareas enviadas y 135 finalizadas, 15,35 s totales.

Todas las sub-tareas fueron `convert_audio` (así lo muestra la tabla «Promedios por operación» del `.md`): `--limit 20` tomó los primeros 20 casos. No se ejercitaron las otras cuatro operaciones.

### GET /workers (tras la carga)

```bash
curl -s "http://172.17.0.1:8000/workers" | python3 -m json.tool
```

```json
[
    {
        "hwaccel": "none",
        "nvenc_ok": "0",
        "cpu_percent": "2.4",
        "ffmpeg_version": "ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers",
        "host": "worker-sim-1",
        "hostname": "worker-sim-1",
        "active_subtasks": "0",
        "threads_per_job": "4",
        "worker_id": "worker-worker-sim-1",
        "mem_percent": "58.5",
        "mem_total_gb": "7.51",
        "gpu_encoders": "h264_nvenc,h264_qsv,h264_vaapi",
        "ip": "100.64.0.11",
        "concurrency": "2",
        "queues": "transcode_video,extract_audio,generate_thumbnail,convert_audio,extract_metadata",
        "failed_count": "0",
        "gpu": "none",
        "started_at": "2026-11-11T11:27:40.298356+00:00",
        "cpu_count": "8",
        "last_seen": "2026-11-11T11:28:25.341913+00:00",
        "completed_count": "44",
        "alive": true
    },
    {
        "hwaccel": "none",
        "nvenc_ok": "0",
        "cpu_percent": "2.3",
        "ffmpeg_version": "ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers",
        "host": "worker-sim-2",
        "hostname": "worker-sim-2",
        "active_subtasks": "0",
        "threads_per_job": "4",
        "worker_id": "worker-worker-sim-2",
        "mem_percent": "58.5",
        "mem_total_gb": "7.51",
        "gpu_encoders": "h264_nvenc,h264_qsv,h264_vaapi",
        "ip": "100.64.0.12",
        "concurrency": "2",
        "queues": "transcode_video,extract_audio,generate_thumbnail,convert_audio,extract_metadata",
        "failed_count": "0",
        "gpu": "none",
        "started_at": "2026-11-11T11:27:40.564828+00:00",
        "cpu_count": "8",
        "last_seen": "2026-11-11T11:28:25.605351+00:00",
        "completed_count": "48",
        "alive": true
    },
    {
        "hwaccel": "none",
        "nvenc_ok": "0",
        "cpu_percent": "2.3",
        "ffmpeg_version": "ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers",
        "host": "worker-sim-3",
        "hostname": "worker-sim-3",
        "active_subtasks": "0",
        "threads_per_job": "4",
        "worker_id": "worker-worker-sim-3",
        "mem_percent": "58.5",
        "mem_total_gb": "7.51",
        "gpu_encoders": "h264_nvenc,h264_qsv,h264_vaapi",
        "ip": "100.64.0.13",
        "concurrency": "2",
        "queues": "transcode_video,extract_audio,generate_thumbnail,convert_audio,extract_metadata",
        "failed_count": "0",
        "gpu": "none",
        "started_at": "2026-11-11T11:27:40.798792+00:00",
        "cpu_count": "8",
        "last_seen": "2026-11-11T11:28:25.836232+00:00",
        "completed_count": "43",
        "alive": true
    }
]
```

### CLIENT LIST

```bash
docker compose exec redis redis-cli CLIENT LIST
```

Se recortan los campos de memoria, que no aportan al origen (`addr`, `flags`, `age`, `cmd` quedan tal cual):

```
id=40 addr=172.18.0.4:60090 age=22 flags=N cmd=exec
id=41 addr=172.18.0.4:60092 age=22 flags=N cmd=exec
id=27 addr=172.18.0.1:38732 age=48 flags=b cmd=blpop
id=24 addr=172.18.0.1:38712 age=48 flags=b cmd=blpop
id=4 addr=172.18.0.5:36650 age=110 flags=N cmd=rpop
id=15 addr=172.18.0.4:43258 age=65 flags=N cmd=exec
id=19 addr=172.18.0.1:47154 age=49 flags=P cmd=ping
id=20 addr=172.18.0.1:47166 age=49 flags=P cmd=ping
id=21 addr=172.18.0.1:38694 age=48 flags=P cmd=ping
id=22 addr=172.18.0.1:38706 age=48 flags=b cmd=blpop
id=46 addr=172.18.0.4:58600 age=12 flags=N cmd=exec
id=43 addr=172.18.0.4:58588 age=17 flags=N cmd=exec
id=44 addr=172.18.0.4:58590 age=17 flags=N cmd=exec
id=23 addr=172.18.0.1:38708 age=48 flags=N cmd=exec
id=25 addr=172.18.0.1:38714 age=48 flags=N cmd=exec
id=26 addr=172.18.0.1:38726 age=48 flags=b cmd=blpop
id=28 addr=172.18.0.1:38742 age=48 flags=b cmd=blpop
id=29 addr=172.18.0.1:38756 age=48 flags=N cmd=exec
id=30 addr=172.18.0.1:38760 age=48 flags=b cmd=blpop
id=38 addr=172.18.0.4:60072 age=22 flags=N cmd=exec
id=39 addr=172.18.0.4:60080 age=22 flags=N cmd=hgetall
id=50 addr=127.0.0.1:58486 age=0 flags=N cmd=client|list
```

Lectura: **no distingue los nodos.** Las 12 conexiones de los workers (6 `blpop`, 3 de pub/sub y 3 `exec`; edad de unos 48 s, la del arranque de los workers) llegan todas con origen `172.18.0.1`, la puerta de enlace de la red del Nodo A, aunque cada worker está en una red distinta (`172.19.0.2`, `172.20.0.2`, `172.21.0.2`). Las de `172.18.0.4` y `172.18.0.5` son el coordinador y el reaper (según `docker inspect`). Es el riesgo que la guía marcaba como «Sin comprobar»: en esta simulación se confirma que la observación no es independiente. Con Tailscale real podría ser distinto; aquí no se probó.

### Sub-tareas por `hostname`

```bash
python3 -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1]))["metrics"]["subtasks_per_host"], indent=2))' docs/evidencia/carga_20261111_052821.json
```

```
{
  "worker-sim-1": 44,
  "worker-sim-2": 48,
  "worker-sim-3": 43
}
```

Esa cifra incluye las fallidas; `failed_count` es `0` en los tres workers del `GET /workers`, así que aquí coincide con las completadas. Hosts con sub-tareas `completed` por caso (20 casos, comando de la guía §5.4): 17 casos con los tres workers, 2 con `worker-sim-1` y `worker-sim-2`, 1 con `worker-sim-1` y `worker-sim-3`.

### Aceptación

```bash
COORDINATOR_URL="http://172.17.0.1:8000" \
RUN_LOAD_JSON="docs/evidencia/carga_20261111_052821.json" \
python3 -m pytest -q -m acceptance tests/acceptance/test_tres_nodos.py
```

```
.                                                                        [100%]
1 passed in 0.07s
```

Pasa, con las salvedades de «Entorno»: las IP son declaradas y el rango Tailscale se cumple por construcción. Aquí solo demuestra que tres identidades de worker distintas se registran y procesan trabajo.

## Hallazgos de la guía y del Compose

1. **Error real (bloqueante): faltan `FOOTPRINT_<OP>_BYTES` y `ADMISSION_MARGIN_BYTES` en `.env.example`, en `docs/DEPLOY_WORKERS.md` y en el Compose de los workers.** Desde F-17 (`src/workers/config.py`, `load_admission_config`) son obligatorias y sin valor predeterminado. Siguiendo la guía al pie de la letra, `check_connectivity` sale 0 pero los tres workers entran en bucle de reinicio (`Restarting (1)`) con `ValueError: ADMISSION_MARGIN_BYTES es obligatoria y debe ser un entero en bytes`, y `GET /workers` devuelve `[]`. Los valores reales dependen de la medición pendiente de la ficha M1 §4.1, así que no se corrigió la guía con cifras inventadas; queda a la persona o a F-17/F-18 (José) decidir cómo documentarlas.
2. `NODE_NAME` solo llega al proceso por `env_file` (común a los tres nodos al compartir un clon); para tres identidades en una máquina hubo que repetirlo en `environment`. En nodos reales (un `.env` por máquina) no ocurre.
3. `worker_id` resulta `worker-worker-sim-N` porque `NODE_NAME` empieza por `worker-`; no es un error.

## No probado

- Tailscale, IP reales en `100.64.0.0/10`, puertos publicados solo en esa IP, ni Windows 11, WSL2 o Docker Desktop.
- Entidades de ejecución separadas (B.2): los tres workers comparten CPU, memoria, disco y kernel.
- Rutas de nodo real: `check_connectivity` en los workers 2 y 3, reinicio de nodos, `tailscale status`, latencia de red entre máquinas.
- Las operaciones distintas de `convert_audio` y la carga completa de 135 casos.
- Valores medidos de huella y margen de memoria (F-17).
