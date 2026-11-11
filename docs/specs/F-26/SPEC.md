# SPEC F-26: Autenticación y roles

**Fase:** plan
**Base:** main
**Verificación IA:** pendiente
**Historia:** US-26 · **Requisitos:** RF-35, RNF-12 (accesos denegados por rol) · **Responsable:** K

## Objetivo

Hoy cualquiera que alcance el coordinador puede crear y cancelar casos y ver el estado del clúster. El enunciado exige «autenticación y control de acceso por roles (mínimo: analista, supervisor, administrador)» y como evidencia «accesos denegados por rol» [B.5 M4]. Esta feature hace que cada rol haga solo lo permitido: sin token se responde 401 y con un rol insuficiente 403 (RF-35). Los secretos nunca entran al repositorio, que es público [B.5 M4].

## Alcance

**Incluye:**
- Matriz rol-acción pura en `src/domain/rbac.py`, única fuente de verdad.
- Verificación de JWT firmado y dependencia FastAPI que responde 401 o 403.
- Aplicación a los routers existentes desde `main.py`, sin editar las rutas de otros dueños.
- Emisión de tokens de demo con un script que lee el secreto del entorno.
- Prueba I con JWT real y guion de accesos denegados para la ficha M4.

**No incluye:**
- Endpoint de login, registro o base de usuarios: el enunciado no los pide; los tokens los emite el administrador con el script.
- Renovación o revocación de tokens, MFA, OAuth, auditoría de accesos.
- Autenticación del dashboard de Streamlit (de Melany) y de otros endpoints que aún no existen (`rutas_archivos.py`, F-14): cuando existan, su dueño los registra en la matriz.
- TLS (F-27), cifrado en reposo (F-28) y cadena de custodia (F-29).
- Roles dentro de Redis o MinIO.

## Criterios de aceptación

Copiados de `docs/backlog/m4-seguridad.md`:

- **Dado** usuarios analista, supervisor y administrador
- **Cuando** cada uno intenta cada acción, o no presenta token
- **Entonces** se cumple la matriz de permisos, con 401 sin token y 403 sin permiso

Concretado:
1. Sin cabecera `Authorization: Bearer`, con token mal formado, firma inválida, algoritmo distinto o expirado: 401 con `WWW-Authenticate: Bearer`.
2. Token válido con rol sin permiso para la acción: 403.
3. Token válido con permiso: la respuesta es la de hoy, sin cambios.
4. Un rol desconocido en el token se trata como sin permiso (403), no como error 500.
5. Sin secreto configurado el coordinador no arranca la verificación y responde 401 a todo (falla cerrado), nunca acepta tokens.

### Matriz de permisos (provisional, SUP-28)

Solo acciones de rutas que existen hoy en `src/coordinator/`.

| Acción | Ruta | analista | supervisor | administrador | servicio |
|---|---|---|---|---|---|
| `crear_caso` | `POST /cases` | sí | no | sí | no |
| `consultar_caso` | `GET /cases`, `/cases/{id}`, `/cases/{id}/report`, `/subtasks/{id}` | sí | sí | sí | no |
| `cancelar_caso` | `POST /cases/{id}/cancel` | no | sí | sí | no |
| `ver_monitoreo` | `GET /workers`, `/stats`, `/hardware` | no | sí | sí | no |
| `reportar_subtarea` | `POST /subtasks/report` | no | no | no | sí |
| (pública) | `GET /health` | sin token | sin token | sin token | sin token |

`servicio` es el principal de los workers, que hoy llaman `POST /subtasks/report`; sin él, proteger esa ruta los rompería (AD-33).

## Diseño

**Contratos.** Implementa `rbac` y `seguridad.py` de Kenni, listados en `docs/CONTRATOS.md` («Quién toca qué»). Aplica la autenticación como indica «Autenticación sin tocar rutas ajenas»: `include_router(..., dependencies=[...])` en `main.py`. No usa contratos de otros responsables.

**Capas y archivos** (`tests/unit/test_arquitectura.py` hace cumplir las dependencias):

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/rbac.py` | `Role` (enum), `Action` (enum), `can(role, action) -> bool`; la matriz es un `dict` inmutable. Sin FastAPI ni JWT. |
| Aplicación | `src/application/ports.py` (una línea añadida) | Puerto `TokenVerifier.verify(token) -> Identity`, con `Identity(subject, role)` y `InvalidToken`. |
| Adaptador | `src/adapters/jwt_tokens.py` | `JwtTokenVerifier` con PyJWT; `issue_token(...)` usado solo por el script y las pruebas. |
| Adaptador (HTTP) | `src/coordinator/seguridad.py` | `autorizar`: dependencia FastAPI que lee `Authorization`, llama al puerto, busca la acción de la ruta, aplica `can` y responde 401 o 403; contiene el mapa ruta-acción. |
| Composición | `src/coordinator/main.py` | `include_router(..., dependencies=[Depends(autorizar)])` en cada router. |
| Script | `scripts/emitir_token.py` | Emite un token para un rol y duración dados. |

Como `rutas_casos.py` mezcla crear, cancelar y consultar en un mismo router, la acción se decide por ruta con un mapa `(método, patrón) -> Action` declarado en `seguridad.py`, junto a la matriz. Una sola dependencia, `Depends(autorizar)`, se aplica a los tres `include_router` de `main.py` y resuelve la acción con `request.scope["route"]`. Así no se edita ninguna ruta de Nahúm. Una prueba exige que toda ruta de `app.routes` esté en el mapa o marcada pública: una ruta nueva sin clasificar rompe la prueba.

**JWT (AD-33, provisional).**
- Algoritmo `HS256`, fijado en la verificación (`algorithms=["HS256"]`) para rechazar `none` y confusión de algoritmo.
- Claims obligatorios: `sub`, `role`, `iat`, `exp`. Expiración por defecto 60 min; el script acepta otra duración. Tolerancia de reloj: 0 s (sin margen sin medir).
- Un solo secreto simétrico porque el coordinador es el único que emite y verifica; asimétrico no aporta hoy.
- Secreto: variable `JWT_SECRET_FILE` (ruta a un archivo fuera del repo, permisos `0400`, montado igual que la KEK de AD-16) o, para desarrollo, `JWT_SECRET`. Longitud mínima de 32 bytes; menos se rechaza. Nunca en el código, en `.env` versionado ni en el historial. Se añade `.env` y el patrón del archivo a `.gitignore` si faltan.
- Tokens de demo: `JWT_SECRET_FILE=... python scripts/emitir_token.py --rol analista --sub demo --minutos 30` imprime el token en salida estándar. No guarda nada y el secreto de demo se genera con `openssl rand -hex 32` fuera del repo. Las pruebas generan un secreto aleatorio por ejecución; no hay ningún token ni secreto fijo en `tests/`.

**Puertos y dobles.** El dominio no depende de nadie. Para la dependencia FastAPI, `tests/dobles.py` añade `FakeTokenVerifier` (diccionario token a identidad), de modo que las pruebas unitarias de `seguridad.py` no usan criptografía. `tests/contratos.py` añade una prueba de contrato `TokenVerifier` que corren el doble y `JwtTokenVerifier`. Redis se sustituye por `fakeredis`, como en `tests/test_coordinator.py`.

**Reutilización.** Del I Proyecto no se reutiliza nada; la API de FastAPI y los routers son del propio repositorio. Terceros: PyJWT (MIT), citado en el código y en `docs/modulo-M4-seguridad.md` [Parte I §9].

**Decisiones nuevas** (se registran en `docs/ARQUITECTURA.md` §8 en la parte 1):
- **AD-33**, JWT HS256 con secreto fuera del repo, rol `servicio` para workers y mapa ruta-acción verificado por prueba. Alternativas: Basic auth (sin expiración ni roles firmados); API keys por rol en Redis (estado a operar, sin expiración); RS256 (dos llaves sin necesidad hoy); mTLS (lo cubre F-27 para nodos, no identifica rol de usuario). Medición pendiente: no aplica, no depende de datos.
- **SUP-28**, la matriz exacta de permisos y la expiración de 60 min, porque el enunciado fija solo los tres roles.
- **SUP-29**, `GET /health` pública, para sondas de despliegue; no expone datos de casos.

Números comprobados libres en todas las ramas remotas: el mayor visto es SUP-27 y AD-32.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_matriz_rol_accion` parametrizada con todos los pares rol por acción contra la tabla esperada escrita aparte en la prueba | La matriz cumple lo acordado; ningún par queda sin cubrir (`Role` por `Action`) |
| Unitaria | `test_rol_desconocido_no_tiene_permisos` | Rol inválido se deniega |
| Unitaria | `test_sin_token_es_401`, `test_token_malformado_es_401`, `test_token_expirado_es_401`, `test_firma_invalida_es_401`, `test_algoritmo_none_es_401` | Cada fallo de autenticación da 401 con `WWW-Authenticate` |
| Unitaria | `test_rol_insuficiente_es_403` con `FakeTokenVerifier` | La dependencia separa 401 de 403 |
| Unitaria | `test_toda_ruta_esta_clasificada` | Una ruta nueva sin acción o sin marcar pública rompe la prueba |
| Unitaria | `test_sin_secreto_falla_cerrado`, `test_secreto_corto_se_rechaza` | Sin llave nadie entra |
| Integración | `test_api_con_jwt_real_por_rol` parametrizada (rol por ruta) con `TestClient`, `fakeredis` y tokens emitidos con un secreto aleatorio | Con JWT real la API da 200/201 donde la matriz permite y 403 donde no; 401 sin token |
| Integración | `test_worker_reporta_con_token_servicio` | Los workers siguen pudiendo reportar |
| Aceptación | `tests/acceptance/test_accesos_denegados.py` con el guion de `curl` por rol contra el coordinador levantado | Los códigos 401 y 403 de la demo, usados como evidencia de la ficha M4 |

Pruebas existentes de `tests/test_coordinator.py` y similares pasan a usar un fixture que inyecta `FakeTokenVerifier` vía `dependency_overrides`, para no emitir tokens en cada una.

## Mediciones

No aplica. F-26 aporta a la ficha M4 el producto «accesos denegados por rol» (RNF-12): comandos `curl` y códigos por rol, que son resultados de ejecución, no mediciones de SO M1–M5. Se registran en `docs/modulo-M4-seguridad.md` con el comando exacto; sin ejecutarlos no se escribe ningún resultado.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-26): matriz de permisos por rol en el dominio` | `src/domain/rbac.py` (`Role`, `Action`, `can`); registro de AD-33, SUP-28 y SUP-29 en `docs/ARQUITECTURA.md` y `docs/REQUERIMIENTOS.md`. Aprox. 60 líneas de código. |
| 2 | `feat(F-26): verificación de JWT y dependencia 401/403` | Puerto `TokenVerifier`, `jwt_tokens.py`, `seguridad.py` con el mapa ruta-acción, doble y prueba de contrato, dependencia en `requirements.txt`. Aprox. 150 líneas. |
| 3 | `feat(F-26): aplicar autenticación al coordinador y emitir tokens de demo` | Cableado en `main.py`, `scripts/emitir_token.py`, `.gitignore`, ajuste de fixtures existentes, pruebas I y A, borrador de la sección en `docs/modulo-M4-seguridad.md`. Aprox. 90 líneas. |

## Riesgos y preguntas abiertas

1. **Matriz (SUP-28).** ¿Es correcto que el supervisor no cree casos y que el analista no vea `/workers`, `/stats` ni `/hardware`? Es una interpretación: el enunciado no define permisos.
2. **Rol `servicio` (AD-33).** El enunciado menciona tres roles; el cuarto es técnico para los workers. Alternativa: dejar `POST /subtasks/report` sin proteger hasta F-27 (mTLS), lo cual deja el endpoint abierto. Requiere coordinar con José Andrés, que debe configurar el token en los workers (variable de entorno); sin su cambio, los workers fallan con 401 al activar la parte 3. Decidir si se activa con una variable `AUTH_ENABLED` por defecto activa.
3. **Dashboard de Streamlit** (Melany) llama a `GET /cases`, `/workers`, `/stats`: necesitará un token de rol supervisor; se avisa al dueño. No se toca `dashboard/`.
4. **Mediciones previas.** F-26 añade una verificación de firma por petición; no se estima su costo. Si M1 a M3 ya tienen mediciones, evaluar si repetirlas (`docs/IMPLEMENTACION.md` §7).
5. **Rutas futuras** (`rutas_archivos.py`, alertas) quedan fuera de la matriz y la prueba `test_toda_ruta_esta_clasificada` obligará a clasificarlas al fusionarse, lo que puede bloquear a su dueño: confirmar que se acepta.
6. **Expiración de 60 min y HS256** son provisionales (SUP-28, AD-33); no hay dato que las respalde.
7. **PyJWT:** versión exacta se fija en la parte 2 tras comprobarla con `pip`; no se afirma aquí.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
