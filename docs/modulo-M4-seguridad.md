# Módulo M4: seguridad

Estado: borrador de F-30 y F-26. **Mediciones pendientes**: no hay salidas reales en este documento. Sin datos medidos, el módulo M4 tiene máximo 2 [Parte I §5].

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

### F-26 Autenticación y roles

Pendiente: sin ejecución en la demo.

| Caso | Código esperado | Resultado |
|---|---|---|
| Sin token o token inválido/vencido | 401 | pendiente: se mide en la demo |
| Rol sin permiso (analista en `/stats`, supervisor en `POST /cases`) | 403 | pendiente: se mide en la demo |
| Rol con permiso | 2xx | pendiente: se mide en la demo |
| `GET /health` sin token | 200 (ruta pública) | pendiente: se mide en la demo |

## 5. Interpretación

### F-30 Workers sin privilegios

Pendiente. Las pruebas unitarias y `python -m scripts.verificar_workers` respaldan que la configuración está escrita, no que el kernel la aplique en los nodos. Sin evidencia medida en los tres nodos reales, el módulo M4 tiene máximo 2 [Parte I §5].

### F-26 Autenticación y roles

Pendiente. Las pruebas unitarias respaldan la matriz y la verificación del token, no el comportamiento medido en la demo. Límites conocidos: ver «Notas» en `docs/specs/F-26/SPEC.md`. Sin evidencia medida, el módulo M4 tiene máximo 2 [Parte I §5].
