# F-27: servidores TLS del Nodo A, prueba local (2026-11-11)

**PRUEBA LOCAL: una sola máquina, sin nodos reales ni captura de red; no acredita M4.**

Imágenes reales: `redis:7-alpine` (Redis 7.4.12), `cgr.dev/chainguard/minio:latest` (RELEASE.2026-11-09T00-10-40Z), coordinador y reaper construidos con `Dockerfile.worker` (Python 3.13). Todo en `127.0.0.1`, con `CERTS_UID=1000` y `CERTS_GID=1000` (el UID del usuario que generó los certificados). Las salidas son las observadas; se omiten líneas repetidas de log.

## Preparación

```bash
NODE_IP=127.0.0.1 NODE_NAME=localhost CERTS_DIR=$SCRATCH/certs bash deploy/tls/generar_certs.sh
# .env (ignorado por git, borrado al terminar): NODE_IP=127.0.0.1, CERTS_DIR, CERTS_UID=$(id -u), CERTS_GID=$(id -g),
# REDIS_PASSWORD y JWT_SECRET de prueba
docker compose up -d redis minio
docker compose up -d --build coordinator reaper
```

## Fallos encontrados con el compose tal como estaba (commit e5973c7)

1. **Redis no arrancaba.** Con `user: 1000:1000` el volumen `redis-data` (creado con la propiedad de la imagen, `999:1000`, modo 0755) no es escribible:

   ```text
   redis-server  | 1:M ... # Can't open or create append-only dir appendonlydir: Permission denied
   redis-server  | Restarting (1)
   ```

2. **El healthcheck de MinIO nunca pasaba.** `mc ready local --insecure` con ese UID:

   ```text
   mc: <ERROR> Unable to save new mc config. mkdir /.mc: permission denied.
   ```

   Con `--config-dir /tmp/.mc` el error cambia, porque el alias `local` de `mc` apunta a `http://localhost:9000` y el servidor solo habla TLS (`--insecure` no cambia el esquema):

   ```text
   The cluster 'local' is not ready      (se repite sin terminar)
   ```

   Con `MC_HOST_local=https://localhost:9000` (sin credenciales; la ruta de readiness es pública) y `--config-dir /tmp/.mc`: `The cluster 'local' is ready`.

## Correcciones mínimas (con prueba en `tests/unit/test_tls_compose.py`)

- `docker-compose.yml`: servicio `redis-data-init` (root, `chown -R ${CERTS_UID}:${CERTS_GID} /data`, `restart: "no"`); `redis` depende de él con `service_completed_successfully`.
- `docker-compose.yml`: healthcheck de MinIO `CMD-SHELL` con `MC_HOST_local=https://localhost:9000 mc --config-dir /tmp/.mc ready local --insecure`.
- Las pruebas nuevas fallaron antes del cambio de Redis (rojo comprobado). La del healthcheck de MinIO se escribió junto con la corrección; el fallo real se observó con la imagen, arriba.

## Resultados con las correcciones

`docker compose ps` tras el arranque:

```text
redis        Up 3 minutes (healthy)
coordinator  Up 18 seconds (healthy)
minio        Up 40 seconds (healthy)
reaper       Up 17 seconds
```

### Redis (TLS 1.3, UID propio)

```text
$ docker exec redis-server id
uid=1000 gid=1000(redis) groups=1000(redis)
$ docker exec redis-server ls -ln /certs /data/appendonlydir
-rw-------  1 1000 1000 241  server.key        # 0600, lo lee el proceso
-rw-------  1 1000 1000  89  appendonly.aof.1.base.rdb      # escribe en /data
$ docker exec redis-server redis-cli --tls --cacert /certs/ca.pem -h localhost -p 6380 ping
PONG
$ docker exec redis-server redis-cli -p 6379 ping
Could not connect to Redis at 127.0.0.1:6379: Connection refused
$ docker exec redis-server redis-cli --tls --cacert /certs/ca.pem -p 6380 config get port
port
0
```

Desde el host, `PING` en claro a `127.0.0.1:6380` devuelve `b''` (conexión cerrada). `openssl s_client -connect 127.0.0.1:6380 -CAfile ca.pem -verify_hostname localhost`: `Verification: OK`, `Verified peername: localhost`, `New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384`; con `-tls1_2`: `tlsv1 alert protocol version`.

### MinIO (certs-dir, UID propio)

```text
$ docker compose ps minio --format '{{.Status}}'
Up 14 seconds (healthy)
$ openssl s_client -connect 127.0.0.1:9000 -CAfile ca.pem -verify_hostname localhost
Verified peername: localhost / New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256 / Verify return code: 0 (ok)
$ curl --cacert ca.pem https://localhost:9000/minio/health/ready      -> 200
$ curl http://127.0.0.1:9000/minio/health/ready                        -> 400
```

`private.key` (0600, UID 1000) se leyó sin error. `/data` del volumen venía 0777 de la imagen, sin ajuste.

### Coordinador (`uvicorn --ssl-*`, UID propio)

```text
$ docker exec wt-fix-f-27-coordinator-1 id
uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)
$ curl --cacert ca.pem https://localhost:8443/openapi.json   -> 200
$ curl https://localhost:8443/openapi.json                   -> 000   (sin CA: rechazado)
$ curl http://127.0.0.1:8443/openapi.json                    -> 000
$ curl --cacert ca.pem https://localhost:8443/health
{"status":"ok","redis":"redis:6380"}                          -> 200
$ curl --cacert ca.pem --tlsv1.2 --tls-max 1.2 https://localhost:8443/openapi.json   -> 200
```

El `/health` por HTTPS confirma que el coordinador llega a Redis por `rediss`. El reaper quedó en ejecución sin errores en el log. Con TLS 1.2 el coordinador responde 200: uvicorn no fija un mínimo de TLS 1.3 (límite ya declarado en AD-37).

## Limpieza

```text
docker compose down -v          # volúmenes y red eliminados
docker ps -aq | wc -l           # 0
```

Certificados temporales, `.env` y las imágenes construidas del coordinador y el reaper se borraron.

## Sin probar

- Captura de red (`tcpdump`/`tshark`), tres nodos reales, Tailscale y Windows: pendientes, necesarios para la ficha M4.
- `CERTS_UID` distinto de 1000: el UID del usuario `appuser` de la imagen del coordinador coincide con el de esta máquina, así que la prueba no distingue si `user:` hizo falta; los de Redis y MinIO sí leyeron `server.key`/`private.key` 0600 con UID 1000.
- Redis y MinIO bajo un UID que no sea el del dueño de la llave (debe fallar: es el propósito de `CERTS_UID`).
- El dueño `65532` observado en `/data/.minio.sys` de MinIO no se investigó (el directorio es 0777, MinIO escribió sin error).
