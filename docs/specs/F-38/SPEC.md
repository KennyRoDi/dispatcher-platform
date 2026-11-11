# SPEC F-38: Despliegue en tres nodos

**Fase:** tests
**Base:** main
**Verificación IA:** tests 4d3d79b
**Historia:** US-38 · **Requisitos:** RNF-01, RNF-22; [B.2], [B.8], [B.10] · **Responsable:** K

## Objetivo

El equipo y quien evalúa necesitan ver distribución real: «al menos tres nodos worker en entidades de ejecución separadas [...] con comunicación por red» [B.2]. Hoy el repositorio tiene un Compose por máquina, pero en contenedor **no prueba esa distribución**: tres réplicas en un solo equipo ya muestran tres `hostname` distintos. F-38 hace que `GET /workers` identifique la máquina real, deja un Compose e instrucciones que levantan cada nodo, y define la corrida con la que la persona responsable obtiene la evidencia.

## Alcance

**Incluye:**

- Topología de cuatro máquinas (AD-02, SUP-04). Nodo A, Linux: coordinador, Redis, MinIO y reaper, sin workers. Nodos B, C y D, Windows 11 con Docker Desktop sobre WSL2: un worker cada uno.
- Red Tailscale: `NODE_IP` es la salida de `tailscale ip -4` de cada máquina; `REDIS_HOST`, `COORDINATOR_URL` y `MINIO_ENDPOINT` usan la IP de Tailscale del Nodo A.
- Identidad de nodo en contenedor: `hostname` e `ip` del heartbeat corresponden a la máquina, no al contenedor (AD-23).
- Compose completo del Nodo A, con el coordinador (AD-24), y Compose de worker para los tres nodos, con puertos publicados solo en la IP de Tailscale.
- `Dockerfile.worker` con Python 3.13, como manda AD-22.
- Instrucciones en `docs/DEPLOY_WORKERS.md` para esta topología [B.8], RNF-22: PowerShell en los nodos Windows, bash en Linux, y la instalación de Docker y Tailscale como prerrequisito.
- Pruebas estáticas de la configuración y prueba de aceptación ejecutable sobre los nodos.
- Corrida real con reparto por nodo y su evidencia, **a cargo de la persona, en la Parte 2**.

**No incluye:**

- TLS (F-27), autenticación (F-26) ni endurecimiento sin privilegios (F-30). **Tailscale no sustituye a TLS:** RF-36 exige una captura entre nodos que muestre TLS, así que F-27 sigue obligatoria. Los puertos 8000, 6379 y 9000 siguen sin TLS hasta F-27.
- Un contenedor por tipo de worker y `mem_limit` (F-16, AD-05); `stop_grace_period` (F-12).
- Workers de texto, imagen y audio (F-07 a F-09). La corrida usa las operaciones multimedia reutilizadas del I Proyecto.
- Nodo GPU y routing (F-32). La configuración de `deploy/docker-compose.worker-gpu.yml` no cambia; solo se actualizan sus comandos de ejemplo en comentarios.
- Sección de despliegue del `README.md` (F-42), escenarios de carga y fallos (F-33 a F-37), diagramas de arquitectura salvo el ajuste de topología de §6.

## Criterios de aceptación

Copiados de `docs/backlog/entrega.md`, US-38:

- **Dado** tres máquinas en red con Docker
- **Cuando** se siguen las instrucciones y se levanta el Compose de cada nodo
- **Entonces** tres `hostname` distintos aparecen como workers activos y procesan sub-tareas

- **Pruebas:** I `scripts/check_connectivity.py` existente. A corrida con reparto por nodo.
- **Demuestra:** tabla de sub-tareas por `hostname`. **Evidencia:** log de `GET /workers` e IP por nodo.

Criterio adicional de RNF-01: tres `hostname` **e IP** distintos aparecen como workers activos. Criterio de RNF-22: una persona externa al equipo puede seguir las instrucciones de despliegue; se aplica con el límite declarado en SUP-21. Los tres diagramas de RNF-22 no se cubren aquí: se dejan a F-42, que también cubre RNF-22.

## Diseño

### Lo que existe, comprobado en el código

| Pieza | Estado |
|---|---|
| `GET /workers` | Existe (`src/coordinator/rutas_monitoreo.py:44`). Devuelve el heartbeat completo más `alive`: incluye `host`, `hostname` e `ip`. No cambia. |
| `hostname` | `socket.gethostname()` (`src/workers/heartbeat.py:148`). **En contenedor es el ID del contenedor** (`.env.example:20`, `docs/WORKER_CONTRACT.md:211`). |
| `ip` | `local_ip(REDIS_HOST)` (`src/workers/heartbeat.py:88`). **En red bridge es la IP interna del contenedor**, y dos nodos pueden repetirla. No es la de Tailscale. |
| `host` | `NODE_NAME` (`src/workers/config.py:156`). Es lo que se anota en cada sub-tarea (`src/workers/worker_node.py:323`). Vacío en `.env.example`, cae al ID del contenedor. |
| `worker_id` | `worker-<hostname>` si `WORKER_ID` está vacío (`src/workers/config.py:26`). |
| Reparto por nodo | `scripts/run_load.py` ya escribe `subtasks_per_host` y una tabla en `docs/evidencia/` (líneas 320 y 353). Se reutiliza. |
| Conectividad | `scripts/check_connectivity.py` existe, con pruebas unitarias en `tests/test_scripts.py`. Se reutiliza. |
| Compose de Nodo A | `docker-compose.yml`: Redis, MinIO y reaper. **El coordinador corre nativo**, lo que contradice «se levanta el Compose de cada nodo». |
| Compose de worker | `deploy/docker-compose.worker.yml`. No fija identidad de nodo. |
| Bloque de coordinador | Ya escrito en `deploy/docker-compose.local.yml`, reutilizable. |
| Imagen | `Dockerfile.worker` usa `python:3.14-slim`; CI usa 3.13. Ya corre como `appuser`. |
| Guía | `docs/DEPLOY_WORKERS.md` (679 líneas) describe A, B, C y D opcional, coordinador nativo, `--scale` y red local. |

### Cambios

| Archivo | Cambio | Dueño |
|---|---|---|
| `deploy/docker-compose.worker.yml` | `hostname: ${NODE_NAME:?...}` y `NODE_IP: ${NODE_IP:?...}`, ambos obligatorios. Se retira el comentario de `--scale` y el comentario de cabecera apunta a Tailscale. | Kenni |
| `docker-compose.yml` | Servicio `coordinator` tomado de `deploy/docker-compose.local.yml`, con `REDIS_HOST: redis`, `MINIO_ENDPOINT: minio:9000` y puerto 8000. El reaper apunta a `http://coordinator:8000`. Los puertos de coordinador, Redis y MinIO se publican en `${NODE_IP:?...}`, la IP de Tailscale del Nodo A. | Kenni |
| `Dockerfile.worker` | `FROM python:3.13-slim` (AD-22). | Kenni |
| `.env.example` | Agrega `NODE_IP`, salida de `tailscale ip -4`; `NODE_NAME` pasa a ser obligatorio en Docker y debe ser la salida de `hostname` de la máquina. `REDIS_HOST`, `COORDINATOR_URL` y `MINIO_ENDPOINT` usan como ejemplo un marcador de la IP de Tailscale del Nodo A. | Kenni |
| `src/workers/config.py`, `src/workers/heartbeat.py` | Cambio aditivo: `node_ip` opcional en `Settings`; el heartbeat publica `settings.node_ip or local_ip(...)`. Sin `NODE_IP`, el comportamiento actual sigue igual. | **José Andrés**: Kenni le avisa |
| `docs/DEPLOY_WORKERS.md`, `docs/WORKER_CONTRACT.md` | Nodo A y tres nodos worker, instalación de Docker y Tailscale, comandos en bash y PowerShell, puertos y lista de comprobación; semántica de `hostname` e `ip`. | Documentación |

Comando de arranque de un worker, en PowerShell, con `--env-file` explícito para que `${NODE_NAME}` y `${NODE_IP}` no dependan de dónde busque Compose el `.env`, ya que el archivo está en `deploy/`:

```powershell
docker compose --env-file .env -f deploy/docker-compose.worker.yml up -d --build
```

### Contratos

No implementa ni usa ningún puerto de `docs/CONTRATOS.md`: F-38 es de infraestructura y no depende de otra feature. Los campos `hostname` e `ip` del heartbeat conservan nombre y tipo, y `GET /workers` no cambia. Capa: infraestructura (`deploy/`), más el cambio aditivo en la configuración del worker.

### Decisiones

Aplica AD-01, AD-02, AD-22 y SUP-04. Kenni aprobó AD-23 y AD-24 en este plan; quedan registradas en `docs/ARQUITECTURA.md` §8:

| ID | Decisión | Alternativas | Criterio |
|---|---|---|---|
| AD-23 | Compose fija `hostname` con `NODE_NAME` y el heartbeat publica `NODE_IP` | `network_mode: host`; usar solo `host` y capturar la IP aparte | Según la documentación general de Docker, `network_mode: host` en Docker Desktop actúa sobre su VM, no sobre Windows, que es la plataforma de los tres nodos worker; no se ha probado aquí. Usar solo `host` deja en `GET /workers` una IP interna que puede repetirse e incumple RNF-01 |
| AD-24 | Coordinador en el Compose del Nodo A | Proceso nativo | El criterio pide levantar el Compose de cada nodo, y [B.8] menciona Docker Compose por nodo. F-39 declara `docker-compose.yml` como reutilizado y modificado |

**Consecuencia de AD-23.** `hostname` fijo implica que `--scale` hace chocar el `worker_id` entre réplicas: compartirían heartbeat y lista `inflight`. Se deja de ofrecer `--scale`. La concurrencia por nodo se ajusta con `WORKER_CONCURRENCY`. F-16 debe dar un `WORKER_ID` propio a cada servicio al crear un contenedor por tipo, por ejemplo `worker-${NODE_NAME}-texto`.

**Límite de AD-23.** `NODE_NAME` y `NODE_IP` son declarados: alguien podría falsearlos en un solo equipo. Por eso la evidencia añade dos observaciones independientes: `redis-cli CLIENT LIST`, con el origen de cada conexión visto desde Redis, y `tailscale status`, con las máquinas de la red. La segunda no prueba que un worker corra en cada una; lo prueba `docker compose ps` en cada nodo.

**Otras decisiones tomadas por Kenni:**

- **Máquinas:** cuatro, tres con Windows 11 y una con Linux. La de Linux es el Nodo A y no ejecuta workers, porque no es muy potente; [B.2] se cumple con los otros tres nodos.
- **Red:** Tailscale, sin alternativa de red local documentada.
- **Puertos del Nodo A:** se publican solo en su IP de Tailscale.
- **Aceptación:** la prueba exige `ip` dentro de `100.64.0.0/10`, porque la red es Tailscale.
- **Mediciones de M1:** todos los workers corren en WSL2, así que la ficha M1 declara que los cgroups medidos son los de la VM de WSL2 (ARQUITECTURA §6). No afecta a F-38; afecta a F-16 a F-19. La ficha no se crea aquí.
- **Validación de las instrucciones:** Kenni, como líder (SUP-21). [B.8] no pide que sea externa; ese añadido es de RNF-22, y Kenni no es externo.
- **Cambio en `src/workers/`:** Kenni avisa a José Andrés.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_despliegue_compose.py`: con PyYAML, sin Docker ni red, lee los Compose, `Dockerfile.worker` y `.env.example` | Worker con `NODE_NAME` y `NODE_IP` obligatorios; Nodo A con coordinador, Redis, MinIO y reaper, sin worker y con puertos publicados en `NODE_IP`; imagen 3.13; `USER` distinto de root |
| Unitaria | `tests/test_config.py`, `tests/test_heartbeat.py`: casos nuevos con `NODE_IP` definido y vacío | El heartbeat publica `NODE_IP`, y sin él conserva `local_ip` |
| Integración | En cada nodo worker: `docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity`, con salida 0 | Cada nodo worker alcanza Redis, coordinador y MinIO del Nodo A por Tailscale. **Pendiente de la persona: requiere Docker y nodos** |
| Aceptación | `tests/acceptance/test_tres_nodos.py`, marcador `acceptance`: lee `GET /workers` de `COORDINATOR_URL` y el JSON de `run_load`. Se omite si esas variables no están | Al menos tres workers con `alive`, con `hostname` e `ip` distintos, e `ip` dentro de `100.64.0.0/10`, el rango de Tailscale, lo que descarta una IP bridge; al menos tres hosts con sub-tareas procesadas, todos entre los `hostname` activos. **Pendiente de la persona** |

F-38 no sigue TDD según `docs/IMPLEMENTACION.md` §4, pero en la Parte 1 hay código y configuración, así que las pruebas unitarias sí se escriben en rojo y cumplen las fases 2 y 3.

### Evidencia, a cargo de la persona

Destino: `docs/evidencia/F-38_tres_nodos_<fecha>.md` y el JSON de `run_load`. Ningún valor se escribe de antemano. Los archivos `carga_*` ya presentes en `docs/evidencia/` no sirven como evidencia de F-38.

**Prerrequisitos.** En el Nodo A, instalar `docker` y `tailscale` y comprobarlos con `which`. En B, C y D, Docker Desktop sobre WSL2 y Tailscale. Las cuatro máquinas deben estar en la misma red de Tailscale antes de levantar nada.

**Nodo A (bash):**

```bash
hostname
tailscale ip -4
docker compose up -d --build
```

**Cada nodo worker (PowerShell):**

```powershell
hostname
tailscale ip -4
docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity
docker compose --env-file .env -f deploy/docker-compose.worker.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.worker.yml ps
```

**Desde el Nodo A, con los workers activos (bash):**

```bash
curl -s "http://<IP_TAILSCALE_NODO_A>:8000/workers" | python3 -m json.tool
tailscale status
docker compose exec redis redis-cli CLIENT LIST
python3 -m scripts.run_load --dataset dataset --upload --limit 20
```

1. `run_load` necesita antes los archivos generados según `dataset/README.md`.
2. La tabla de sub-tareas por `hostname` sale de `subtasks_per_host` del JSON de `run_load`.
3. Al final corre `tests/acceptance/test_tres_nodos.py` con `pytest -m acceptance`, y las variables de entorno que defina la prueba.
4. El repositorio es público. Antes de versionar la salida de `tailscale status`, se revisa y se ocultan los nombres de cuenta que muestre.

Kenni sigue las instrucciones de principio a fin y anota dónde se atascó (RNF-22, SUP-21).

## Mediciones

No aplica. F-38 no es M1–M5 ni un escenario de B.6: su evidencia es la de la sección anterior. El tiempo y el reparto de la corrida se registran tal como salgan, sin interpretarse como rendimiento.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimación de la Parte 1: bastante menos de 100 líneas fuera de `tests/` y `docs/`; se comprueba al implementar.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-38): levantar cada nodo con compose e identidad real` | Cambios de la tabla, guía, pruebas unitarias y prueba de aceptación. Se puede fusionar sin nodos. **No cierra la feature** |
| 2 | `docs(F-38): registrar evidencia de despliegue en tres nodos` | Corrida real, evidencia, y correcciones a instrucciones o Compose que la corrida revele. Se abre con `flujo.py trabajar F-38 "evidencia tres nodos"` y cierra con `cierre --final` |

La Parte 2 no escribe pruebas nuevas si la corrida no revela errores, así que las fases 2 y 3 requerirían `aprobar --excepcion`, autorizada por la persona. Si hay correcciones, siguen el ciclo normal.

## Riesgos y preguntas abiertas

**Preguntas abiertas:** ninguna.

**Sin comprobar. No se conoce el resultado:**

- Que un contenedor de Docker Desktop en WSL2 alcance la red Tailscale del host Windows. Es la base de la topología. Si falla, la Parte 2 se detiene y se devuelve a `plan`.
- Qué IP de origen muestra `CLIENT LIST` a través del puerto publicado. Si no distingue los nodos, pierde valor como observación independiente y se declara así en la evidencia.
- Que Docker acepte como `hostname` el nombre de una máquina Windows, y que publique puertos en la IP de Tailscale cuando esa interfaz aún no está activa. Las instrucciones piden activar Tailscale primero.
- Que la VM de WSL2 exponga cgroups v2, como suponen RF-24 y los comandos de medición de M1. No afecta a F-38; lo debe comprobar F-16.
- Compose, imagen, `--env-file` y `run_load` en red: nada de esto se ha ejecutado. La prueba estática solo comprueba la forma de la configuración.

**Riesgos:**

- **Nodo A sin preparar.** La máquina Linux de Kenni, futuro Nodo A, hoy no tiene `docker` ni `tailscale` instalados (comprobado con `which`). Es prerrequisito de la Parte 2 y queda en la guía.
- **Fecha.** La entrega es el 10/nov/26 (SUP-03) y el hito H1 de SUP-02 ya pasó. F-27, F-30 y F-33 a F-37 dependen de F-38. La Parte 1 se puede fusionar sin nodos para que se apilen sobre ella, pero sus criterios reales siguen pendientes hasta la Parte 2. Los escenarios de B.6 tampoco se pueden ejecutar sin nodos.
- **Validación no independiente.** Kenni es responsable de F-38 y conoce el sistema, así que puede pasar por alto pasos implícitos que alguien externo sí notaría (SUP-21).
- **Punto único de falla.** Sin el Nodo A no hay coordinador, Redis ni MinIO, y el sistema depende de que Tailscale esté activo en las cuatro máquinas. [B.6] no exige alta disponibilidad (ARQUITECTURA §6).
- **`.env` en Windows.** PowerShell y Git pueden escribir CRLF, BOM o UTF-16. `check_connectivity` solo avisa de CRLF si el `.env` está a su alcance, y la imagen no lo incluye. La guía indica guardarlo en UTF-8 con LF.
- **Imagen 3.13.** CI instala `requirements.txt` en 3.13 sobre Linux, lo que da confianza pero no prueba la imagen `slim`.
- **`hostname` repetido.** Si dos máquinas se llaman igual, colisionarían en `worker_id` y la aceptación fallaría. Las instrucciones lo avisan: `NODE_NAME` debe ser único.
- **Conflicto con otras features.** F-16, F-12, F-27 y F-30 previsiblemente editarán `deploy/docker-compose.worker.yml`, y AD-20 agrega datos al heartbeat. `deploy/` es de Kenni (`docs/CONTRATOS.md`), así que F-16 debe coordinarse con él. El cambio de F-38 se mantiene en pocas líneas para reducir el conflicto.
- **Exposición en red.** Hasta F-27 y F-26, Redis, MinIO y el coordinador van sin TLS, y los valores `minioadmin` son públicos. Publicar los puertos solo en la IP de Tailscale evita ofrecerlos en otras interfaces; un cortafuegos como `ufw` no basta, porque las reglas de Docker para puertos publicados pueden saltárselo. Las credenciales propias van en `.env`, nunca versionadas.
- **Corrida parcial.** `run_load` usa operaciones multimedia, no el análisis forense. Demuestra distribución; el sistema completo en los tres nodos lo comprueban F-33 a F-37.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Opus 5.5), orquestador; arquitecto en subagente | 2026-11-05 | Lei el SPEC completo y el diff contra main: solo docs/specs/F-38/SPEC.md, 166 lineas, sin campos pendientes (grep = 0). Criterios de US-38 presentes. Contraste con el codigo: heartbeat.py:88 y :148, config.py:26 y :156, rutas_monitoreo.py:44, worker_node.py:323, run_load.py:320, :353 y --limit, Dockerfile.worker 3.14 y USER appuser, docker-compose.yml sin coordinador, ARQUITECTURA AD-22 en 3.13, CONTRATOS.md:38 y :40. Hallazgo sin bloqueo: responsabilidades.md:7 asigna deploy/ a M1 y CONTRATOS.md:40 a Kenni. Sin comprobar: Docker, Compose, imagen y run_load en red; WSL2 con network_mode host; estimacion de lineas. (495f58d) |
| verificación IA de plan | Claude Code (Opus 5.5), orquestador; arquitecto en subagente | 2026-11-05 | Segunda verificacion del plan, sobre a2f31bc. Lei el SPEC y el diff de ARQUITECTURA, REQUERIMIENTOS y responsabilidades: solo documentos, sin campos pendientes, respuestas de Kenni reflejadas. grep confirma que ENUNCIADO no contiene extern, base de SUP-21. python -m scripts.conformidad repo: 0 problemas. pytest no ejecutado: no esta instalado en este entorno y no hay codigo en el diff. Sin comprobar: Docker, Compose, imagen, alcance de Tailscale desde contenedores en WSL2, CLIENT LIST. Pendiente de confirmar por Kenni: anadidos del subagente, Nodo A sin workers, puertos en NODE_IP y rango 100.64.0.0/10. (a2f31bc) |
| verificación IA de plan | Claude Code (Opus 5.5), orquestador; arquitecto en subagente | 2026-11-05 | Tercera verificacion del plan, sobre 2f5a6cd. Lei el diff: solo SPEC y ARQUITECTURA; decisiones finales de Kenni aplicadas, sin preguntas abiertas ni campos pendientes. conformidad repo: 0 problemas. pytest no ejecutado: no esta instalado y no hay codigo. Sin comprobar: Docker, Compose, imagen, Tailscale desde WSL2, cgroups v2 en WSL2. (2f5a6cd) |
| plan | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de tests | Claude Code (Opus 5.5), orquestador; developer en subagente | 2026-11-05 | Verificacion de tests sobre bc1fe65. Diff: solo tests/. Lei las pruebas y ejecute la suite con un venv del scratchpad: 18 failed, 650 passed, 3 skipped, 1 deselected; las 600 preexistentes siguen en verde. Las 18 rojas fallan por falta de funcionalidad: Settings sin node_ip, heartbeat con la IP detectada, sin coordinator, puertos sin NODE_IP, python 3.14, NODE_IP ausente. Devolvi un hallazgo al developer: nodo solo con fallidas contaba como procesa; corregido y reproducido por mi con datos sinteticos. Aceptacion se omite sin variables. conformidad repo: 0 problemas. Sin comprobar: aceptacion contra nodos reales y contra un servidor con la logica nueva; Docker y Compose. (bc1fe65) |
| tests | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de implementacion | Claude Code (Opus 5.5), orquestador; developer en subagente | 2026-11-05 | Verificacion de implementacion sobre ab0bccf. Lei el diff completo contra el SPEC: 6 archivos, 61 inserciones y 25 borrados, sin tocar docs. git diff de tests desde la fase anterior vacio: pruebas no debilitadas. Suite: 668 passed, 3 skipped, 1 deselected. conformidad repo: 0 problemas. grep confirma que el coordinador solo lee REDIS_* y que ningun script ni CI levanta docker-compose.yml. Sin comprobar: docker compose config y up, build de imagen 3.13, interpolacion real, pruebas integration y acceptance, nodos reales. (ab0bccf) |
| implementacion | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5), orquestador; qa-tester en subagente | 2026-11-05 | Verificacion sobre 5af74f3. QA dio APROBADO con 9 hallazgos no bloqueantes y agrego 73 lineas de pruebas, solo en tests/. Lei ese diff y ejecute la suite: 682 passed, 3 skipped, 1 deselected. conformidad repo: 0 problemas. Reproduje: NODE_IP sin validar se conserva tal cual, WORKER_ID comun da nodos activos distintos: 1, ip marcador rechazada, tres nodos validos sin problemas. Dos mutantes propios en copia temporal, worker sin env_file y heartbeat sin node_ip: ambos detectados. Sin comprobar: Docker, Compose, imagen, Tailscale, CLIENT LIST y run_load real; US-38 y RNF-01 quedan para la Parte 2. Sin mediciones en el SPEC. (5af74f3) |
| verificacion | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de documentacion | Claude Code (Opus 5.5), orquestador; documentador en subagente | 2026-11-05 | Verificacion de documentacion sobre e3ab57f. Lei DEPLOY_WORKERS lineas 1 a 264 y el diff de Compose, Dockerfile y REQUERIMIENTOS: en deploy y Dockerfile solo cambian comentarios. Suite: 682 passed, 3 skipped, 1 deselected; conformidad: 0 problemas. Contraste con el codigo: load_dotenv en config.py:125, stop_grace_period 31m, build_dataset --files y --seed, 655.7 MB en dataset/README, upload_dataset sin limite, reaper como host en recovery.py:50, --create-buckets. Lineas 265 a 421 de la guia y WORKER_CONTRACT revisadas solo por grep y por el diff resumido. Sin comprobar: ningun comando de la guia se ejecuto; Docker, Compose, winget, script de PowerShell, Tailscale, escritura de appuser en dataset montado. Bitacora en borrador, sin publicar. (e3ab57f) |
| verificación IA de documentacion | Claude Code (Opus 5.5), orquestador; documentador en subagente | 2026-11-05 | Repeticion sobre 5ffa85b, tras cambio aprobado por Kenni. Diff: una linea en DECISIONES_DISENO.md:45, sin --scale. Suite: 682 passed, 3 skipped, 1 deselected; conformidad: 0 problemas. Lo no comprobado de la verificacion anterior sigue igual: ningun comando de la guia se ejecuto. (5ffa85b) |
| documentacion | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de revision | Claude Code (Opus 5.5), orquestador; revisor en subagente | 2026-11-05 | Verificacion de revision sobre 97219bd. Revisor: DEVUELTO en la primera ronda con 6 hallazgos de documentos, todos confirmados por mi; corregidos por el documentador; APROBADO en la segunda ronda. Lei el delta de SPEC, DECISIONES_DISENO y la lista 5.6 de la guia; el resto del diff lo lei en las fases previas. Suite: 682 passed, 3 skipped, 1 deselected; conformidad: 0 problemas. Quedan para Kenni: python3.13 en el venv, cifra de lineas de la bitacora, hallazgos preexistentes. Sin comprobar: Docker, Compose, imagen, PowerShell, Tailscale, run_load real; US-38 y RNF-01 quedan para la Parte 2. (97219bd) |
| revision | Kenni Rodriguez | 2026-11-05 |  |
| verificación IA de tests | orquestador | 2026-11-11 | Simulacion local corrida por agente; evidencia en docs/evidencia/F-38_tres_nodos_simulacion_local_2026-11-11.md (4d3d79b); 0 contenedores restantes; sin pruebas nuevas (SPEC fila 2) (4d3d79b) |
