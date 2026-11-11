# Módulo M4: seguridad

> BORRADOR. Solo la sección de autenticación y roles (F-26). Sin mediciones: lo marcado «pendiente: se mide en la demo» no se ha ejecutado.

## Autenticación y roles (F-26)

### Matriz rol por acción

Fuente: `src/domain/rbac.py` (`PERMISOS`).

| Rol | crear_caso | consultar_caso | cancelar_caso | ver_monitoreo | reportar_subtarea |
|---|---|---|---|---|---|
| analista | sí | sí | no | no | no |
| supervisor | no | sí | sí | sí | no |
| administrador | sí | sí | sí | sí | no |
| servicio | no | no | no | no | sí |

El rol `servicio` es para los workers (`POST /subtasks/report`).

### Token

- JWT firmado con HS256 (decisión AD-33), con PyJWT (licencia MIT, https://github.com/jpadilla/pyjwt).
- Claims usados: `sub`, rol, `iat`, `exp`. El coordinador rechaza `sub` vacío y fechas no finitas.
- Se envía como `Authorization: Bearer <token>`.

### Secreto

El secreto nunca va en el repositorio. Generarlo fuera de él:

```bash
openssl rand -hex 32 > ~/jwt.secret
chmod 600 ~/jwt.secret
export JWT_SECRET_FILE=~/jwt.secret
```

`JWT_SECRET` (variable directa) se admite, pero se prefiere el archivo. `.gitignore` cubre `jwt.secret`, `*.key` y `.env`.

### AUTH_ENABLED

Activa por defecto. Solo `0`, `false`, `no` u `off` la desactivan (`src/coordinator/main.py`). Desactivarla es solo para pruebas locales.

### Emitir un token

```bash
PYTHONPATH=. python scripts/emitir_token.py --rol supervisor --sub demo-supervisor --minutos 30
```

Roles: `analista`, `supervisor`, `administrador`, `servicio`.

### Comandos por rol

```bash
TOKEN=$(PYTHONPATH=. python scripts/emitir_token.py --rol analista --sub demo-analista)
curl -i -X POST http://localhost:8000/cases -H "Authorization: Bearer $TOKEN" ...   # crear
curl -i http://localhost:8000/cases -H "Authorization: Bearer $TOKEN"              # consultar
curl -i http://localhost:8000/stats -H "Authorization: Bearer $TOKEN"              # monitoreo
curl -i http://localhost:8000/cases                                                # sin token
```

(El cuerpo de `POST /cases` se omite; ver `docs/DEMO.md`.)

| Caso | Código esperado | Resultado |
|---|---|---|
| Sin token o token inválido/vencido | 401 | pendiente: se mide en la demo |
| Rol sin permiso (analista en `/stats`, supervisor en `POST /cases`) | 403 | pendiente: se mide en la demo |
| Rol con permiso | 2xx | pendiente: se mide en la demo |
| `GET /health` sin token | 200 (ruta pública) | pendiente: se mide en la demo |

### Límites conocidos

Ver «Notas» en `docs/specs/F-26/SPEC.md`.
