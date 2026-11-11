# Módulo M4: seguridad

Estado: borrador de F-30. **Mediciones pendientes**: no hay salidas reales en este documento. Sin datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].

## Workers sin privilegios (F-30)

Configuración (AD-36, SUP-32): `user: "10001:10001"`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, volumen `scratch` propio por worker en `/scratch` y `tmpfs` en `/tmp` de 64 MB. Está en `Dockerfile.worker`, `deploy/docker-compose.worker.yml` y `deploy/docker-compose.local.yml`.

### Verificación de configuración (sin Docker)

```bash
python -m scripts.verificar_workers
```

Salida: pendiente: se mide en los tres nodos reales. El código de salida 0 indica sin incumplimientos.

### Comprobación en el contenedor (una repetición por nodo)

Sustituye `<worker>` por el nombre del contenedor.

```bash
docker exec <worker> id -u
docker exec <worker> touch /x
docker inspect --format '{{.Config.User}}' <worker>
docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' <worker>
docker inspect --format '{{.HostConfig.CapDrop}}' <worker>
docker inspect --format '{{.HostConfig.SecurityOpt}}' <worker>
```

| Comando | Esperado | Salida medida |
|---|---|---|
| `id -u` | distinto de 0 | pendiente: se mide en los tres nodos reales |
| `touch /x` | falla (sistema de archivos de solo lectura) | pendiente: se mide en los tres nodos reales |
| `.Config.User` | `10001:10001` | pendiente: se mide en los tres nodos reales |
| `ReadonlyRootfs` | `true` | pendiente: se mide en los tres nodos reales |
| `CapDrop` | contiene `ALL` | pendiente: se mide en los tres nodos reales |
| `SecurityOpt` | contiene `no-new-privileges:true` | pendiente: se mide en los tres nodos reales |

Nodos: José, Nahúm y Melany; cada uno captura sus salidas.
