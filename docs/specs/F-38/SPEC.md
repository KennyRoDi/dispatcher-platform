# SPEC F-38: Despliegue en tres nodos

**Fase:** plan
**Base:** main
**Verificación IA:** plan 495f58d
**Historia:** US-38 · **Requisitos:** RNF-01, RNF-22; [B.2], [B.8], [B.10] · **Responsable:** K

## Objetivo

El equipo y quien evalúa necesitan ver distribución real: «al menos tres nodos worker en entidades de ejecución separadas [...] con comunicación por red» [B.2]. Hoy el repositorio tiene un Compose por máquina, pero en contenedor **no prueba esa distribución**: tres réplicas en un solo equipo ya muestran tres `hostname` distintos. F-38 hace que `GET /workers` identifique la máquina real, deja un Compose e instrucciones que levantan cada nodo, y define la corrida con la que la persona responsable obtiene la evidencia.

## Alcance

**Incluye:**

- Identidad de nodo en contenedor: `hostname` e `ip` del heartbeat corresponden a la máquina, no al contenedor (AD-23 propuesta).
- Compose completo por nodo: coordinador, Redis, MinIO y reaper en el Nodo A (AD-24 propuesta); un worker en cada uno de los tres nodos, incluido el A (SUP-04).
- `Dockerfile.worker` con Python 3.13, como manda AD-22.
- Instrucciones de `docs/DEPLOY_WORKERS.md` alineadas con la topología A, B y C [B.8], RNF-22.
- Pruebas estáticas de la configuración y prueba de aceptación ejecutable sobre los nodos.
- Corrida real con reparto por nodo y su evidencia, **a cargo de la persona, en la Parte 2**.

**No incluye:**

- TLS (F-27), autenticación (F-26) ni endurecimiento sin privilegios (F-30). Los puertos 8000, 6379 y 9000 siguen sin TLS hasta F-27.
- Un contenedor por tipo de worker y `mem_limit` (F-16, AD-05); `stop_grace_period` (F-12).
- Workers de texto, imagen y audio (F-07 a F-09). La corrida usa las operaciones heredadas del I Proyecto.
- Nodo GPU y routing (F-32). `deploy/docker-compose.worker-gpu.yml` no cambia.
- Sección de despliegue del `README.md` (F-42), escenarios de carga y fallos (F-33 a F-37), diagramas de arquitectura.
- Cualquier cuarta máquina: la Máquina D opcional de la guía heredada se retira (AD-02, SUP-04).

## Criterios de aceptación

Copiados de `docs/backlog/entrega.md`, US-38:

- **Dado** tres máquinas en red con Docker
- **Cuando** se siguen las instrucciones y se levanta el Compose de cada nodo
- **Entonces** tres `hostname` distintos aparecen como workers activos y procesan sub-tareas

- **Pruebas:** I `scripts/check_connectivity.py` existente. A corrida con reparto por nodo.
- **Demuestra:** tabla de sub-tareas por `hostname`. **Evidencia:** log de `GET /workers` e IP por nodo.

Criterio adicional de RNF-01: tres `hostname` **e IP** distintos aparecen como workers activos. Criterio de RNF-22: una persona externa al equipo puede seguir las instrucciones de despliegue. Los tres diagramas de RNF-22 no se cubren aquí: se dejan a F-42, que también cubre RNF-22.

## Diseño

### Lo que existe, comprobado en el código

| Pieza | Estado |
|---|---|
| `GET /workers` | Existe (`src/coordinator/rutas_monitoreo.py:44`). Devuelve el heartbeat completo más `alive`: incluye `host`, `hostname` e `ip`. No cambia. |
| `hostname` | `socket.gethostname()` (`src/workers/heartbeat.py:148`). **En contenedor es el ID del contenedor** (`.env.example:20`, `docs/WORKER_CONTRACT.md:211`). |
| `ip` | `local_ip(REDIS_HOST)` (`src/workers/heartbeat.py:88`). **En red bridge es la IP interna del contenedor**, y dos nodos pueden repetirla. |
| `host` | `NODE_NAME` (`src/workers/config.py:156`). Es lo que se anota en cada sub-tarea (`src/workers/worker_node.py:323`). Vacío en `.env.example`, cae al ID del contenedor. |
| `worker_id` | `worker-<hostname>` si `WORKER_ID` está vacío (`src/workers/config.py:26`). |
| Reparto por nodo | `scripts/run_load.py` ya escribe `subtasks_per_host` y una tabla en `docs/evidencia/` (líneas 320 y 353). Se reutiliza. |
| Conectividad | `scripts/check_connectivity.py` existe, con pruebas unitarias en `tests/test_scripts.py`. Se reutiliza. |
| Compose de Nodo A | `docker-compose.yml`: Redis, MinIO y reaper. **El coordinador corre nativo**, lo que contradice «se levanta el Compose de cada nodo». |
| Compose de worker | `deploy/docker-compose.worker.yml`. No fija identidad de nodo. |
| Bloque de coordinador | Ya escrito en `deploy/docker-compose.local.yml`, reutilizable. |
| Imagen | `Dockerfile.worker` usa `python:3.14-slim`; CI usa 3.13. Ya corre como `appuser`. |
| Guía | `docs/DEPLOY_WORKERS.md` (679 líneas) describe A, B, C y D opcional, coordinador nativo y `--scale`. |

### Cambios

| Archivo | Cambio | Dueño |
|---|---|---|
| `deploy/docker-compose.worker.yml` | `hostname: ${NODE_NAME:?...}` y `NODE_IP: ${NODE_IP:?...}`, ambos obligatorios. Se retira el comentario de `--scale`. | Kenni |
| `docker-compose.yml` | Servicio `coordinator` tomado de `deploy/docker-compose.local.yml`, con `REDIS_HOST: redis`, `MINIO_ENDPOINT: minio:9000` y puerto 8000. El reaper apunta a `http://coordinator:8000`. | Kenni |
| `Dockerfile.worker` | `FROM python:3.13-slim` (AD-22). | Kenni |
| `.env.example` | Agrega `NODE_IP`; `NODE_NAME` pasa a ser obligatorio en Docker y debe ser la salida de `hostname` de la máquina. | Kenni |
| `src/workers/config.py`, `src/workers/heartbeat.py` | Cambio aditivo: `node_ip` opcional en `Settings`; el heartbeat publica `settings.node_ip or local_ip(...)`. Sin `NODE_IP`, el comportamiento actual sigue igual. | **José Andrés**: requiere aviso, ver pregunta 1 |
| `docs/DEPLOY_WORKERS.md`, `docs/WORKER_CONTRACT.md` | Topología de tres nodos, comandos por nodo, puertos y lista de comprobación; semántica de `hostname` e `ip`. | Documentación |

Comando de arranque de un worker, con `--env-file` explícito para que `${NODE_NAME}` y `${NODE_IP}` no dependan de dónde busque Compose el `.env`, ya que el archivo está en `deploy/`:

```bash
docker compose --env-file .env -f deploy/docker-compose.worker.yml up -d --build
```

### Contratos

No implementa ni usa ningún puerto de `docs/CONTRATOS.md`: F-38 es de infraestructura y no depende de otra feature. Los campos `hostname` e `ip` del heartbeat conservan nombre y tipo, y `GET /workers` no cambia. Capa: infraestructura (`deploy/`), más el cambio aditivo en la configuración del worker.

### Decisiones

Aplica AD-01, AD-02, AD-22 y SUP-04. Dos decisiones nuevas, que se registran en `docs/ARQUITECTURA.md` §8 al aprobarse este plan y antes de implementar:

| ID propuesto | Decisión | Alternativas | Criterio |
|---|---|---|---|
| AD-23 | Compose fija `hostname` con `NODE_NAME` y el heartbeat publica `NODE_IP` | `network_mode: host`; usar solo `host` y capturar la IP aparte | `network_mode: host` no da la identidad real en Docker Desktop sobre WSL2, que ARQUITECTURA §6 admite para un nodo, y quita aislamiento de red. Usar solo `host` deja en `GET /workers` una IP interna que puede repetirse e incumple RNF-01 |
| AD-24 | Coordinador en el Compose del Nodo A | Mantenerlo nativo | El criterio pide levantar el Compose de cada nodo. Evita instalar Python en el Nodo A solo para el coordinador. Revierte la decisión del I Proyecto de `docs/DECISIONES_DISENO.md`, que F-39 debe declarar como modificada |

**Consecuencia de AD-23.** `hostname` fijo implica que `--scale` hace chocar el `worker_id` entre réplicas: compartirían heartbeat y lista `inflight`. Se deja de ofrecer `--scale`. La concurrencia por nodo se ajusta con `WORKER_CONCURRENCY`. F-16 debe dar un `WORKER_ID` propio a cada servicio al crear un contenedor por tipo, por ejemplo `worker-${NODE_NAME}-texto`.

**Límite de AD-23.** `NODE_NAME` y `NODE_IP` son declarados: alguien podría falsearlos en un solo equipo. Por eso la evidencia añade una observación independiente, `redis-cli CLIENT LIST`, que muestra el origen de cada conexión visto desde Redis.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_despliegue_compose.py`: con PyYAML, sin Docker ni red, lee los Compose, `Dockerfile.worker` y `.env.example` | Worker con `NODE_NAME` y `NODE_IP` obligatorios; Nodo A con coordinador, Redis, MinIO y reaper; imagen 3.13; `USER` distinto de root |
| Unitaria | `tests/test_config.py`, `tests/test_heartbeat.py`: casos nuevos con `NODE_IP` definido y vacío | El heartbeat publica `NODE_IP`, y sin él conserva `local_ip` |
| Integración | Por nodo: `docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity`, con salida 0 | Cada nodo alcanza Redis, coordinador y MinIO por red. **Pendiente de la persona: requiere Docker y nodos** |
| Aceptación | `tests/acceptance/test_tres_nodos.py`, marcador `acceptance`: lee `GET /workers` de `COORDINATOR_URL` y el JSON de `run_load`. Se omite si esas variables no están | Al menos tres workers con `alive`, con `hostname` e `ip` distintos y distintos de `unknown`; al menos tres hosts con sub-tareas procesadas, todos entre los `hostname` activos. **Pendiente de la persona** |

F-38 no sigue TDD según `docs/IMPLEMENTACION.md` §4, pero en la Parte 1 hay código y configuración, así que las pruebas unitarias sí se escriben en rojo y cumplen las fases 2 y 3.

### Evidencia, a cargo de la persona

Destino: `docs/evidencia/F-38_tres_nodos_<fecha>.md` y el JSON de `run_load`. Ningún valor se escribe de antemano. Los datos de la carga del I Proyecto en `docs/evidencia/` no sirven como evidencia de F-38.

1. En cada nodo, registrar `hostname` e IP real de la máquina (`ip -4 route get <IP_NODO_A>`; en Windows, `ipconfig`).
2. En el Nodo A: `docker compose up -d --build`, y después el worker. En B y C: el worker.
3. Conectividad en los tres nodos, con el comando de la tabla.
4. Log de `GET /workers`: `curl -s http://<IP_NODO_A>:8000/workers | python -m json.tool`.
5. En el Nodo A: `docker compose exec redis redis-cli CLIENT LIST`.
6. Generar los archivos según `dataset/README.md` y correr `python -m scripts.run_load --dataset dataset --upload --limit 20`.
7. Tabla de sub-tareas por `hostname`, tomada de `subtasks_per_host`.
8. `COORDINATOR_URL=... pytest -m acceptance tests/acceptance/test_tres_nodos.py`, con la variable del JSON que defina la prueba.

Una persona que no haya escrito las instrucciones las sigue y anota dónde se atascó (RNF-22).

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

**Preguntas para quien aprueba:**

1. **¿Se aprueba AD-23 con el cambio en `src/workers/`?** `config.py` y `heartbeat.py` son de José Andrés según `docs/CONTRATOS.md`. Recomendación: aprobarlo, con aviso a José Andrés, porque es aditivo y no cambia ningún contrato. Sin el cambio, RNF-01 no se puede demostrar en `GET /workers`. Alternativa: que él haga ese cambio, pero F-38 pasaría a depender de otro responsable, contra la regla de módulos independientes de `AGENTS.md`.
2. **¿Se aprueba AD-24?** Recomendación: sí, por el texto del criterio.
3. **¿Qué tres máquinas son los nodos, con qué sistema operativo, en qué red y qué día se corre?** No hay ninguna disponible todavía, y este plan no lo asume. Sin esa respuesta, la Parte 2 no puede empezar. Las mediciones de M1 deben hacerse en un nodo Linux o declarar la diferencia (ARQUITECTURA §6).
4. **¿Red local o Tailscale?** `deploy/docker-compose.worker.yml` menciona ambas. Una red universitaria puede aislar equipos entre sí. `NODE_IP` admite cualquiera de las dos.
5. **¿Quién valida las instrucciones?** RNF-22 dice «externa al equipo». Si no se consigue nadie externo, propongo un integrante que no haya desplegado y declararlo como límite; requeriría un `SUP-XX`.

**Riesgos:**

- **Fecha.** La entrega es el 10/nov/26 (SUP-03) y el hito H1 de SUP-02 ya pasó. F-27, F-30 y F-33 a F-37 dependen de F-38. La Parte 1 se puede fusionar sin nodos para que se apilen sobre ella, pero sus criterios reales siguen pendientes hasta la Parte 2. Los escenarios de B.6 tampoco se pueden ejecutar sin nodos.
- **Nada de Docker está probado.** La máquina local no tiene `docker` ni `nvidia-smi`. Compose, imagen, resolución de `--env-file`, `CLIENT LIST` y `run_load` en red quedan sin ejecutar hasta tener nodos, y pueden revelar errores en la Parte 2. La prueba estática solo comprueba la forma de la configuración.
- **Imagen 3.13.** CI instala `requirements.txt` en 3.13 sobre Linux, lo que da confianza pero no prueba la imagen `slim`.
- **`hostname` repetido.** Dos máquinas pueden llamarse igual, por ejemplo `ubuntu`. Colisionarían en `worker_id` y la aceptación fallaría. Las instrucciones lo avisan: `NODE_NAME` debe ser único.
- **Conflicto con otras features.** F-16, F-12, F-27 y F-30 previsiblemente editarán `deploy/docker-compose.worker.yml`, y AD-20 agrega datos al heartbeat. El cambio de F-38 se mantiene en pocas líneas para reducir el conflicto.
- **Exposición en red.** Hasta F-27 y F-26, Redis, MinIO y el coordinador van sin TLS, y los valores `minioadmin` son públicos. Las instrucciones exigen red de confianza, cortafuegos limitado a los nodos y credenciales propias en `.env`, nunca versionadas.
- **Corrida parcial.** `run_load` usa operaciones heredadas, no el análisis forense. Demuestra distribución; el sistema completo en los tres nodos lo comprueban F-33 a F-37.

**Corrección sobre AD-22.** `docs/ARQUITECTURA.md` ya dice 3.13, no 3.12; la mención a 3.12 solo queda en `docs/BITACORA_IA.md` como error histórico. La discrepancia vigente es `Dockerfile.worker` con 3.14, y este plan la corrige.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Opus 5.5), orquestador; arquitecto en subagente | 2026-11-05 | Lei el SPEC completo y el diff contra main: solo docs/specs/F-38/SPEC.md, 166 lineas, sin campos pendientes (grep = 0). Criterios de US-38 presentes. Contraste con el codigo: heartbeat.py:88 y :148, config.py:26 y :156, rutas_monitoreo.py:44, worker_node.py:323, run_load.py:320, :353 y --limit, Dockerfile.worker 3.14 y USER appuser, docker-compose.yml sin coordinador, ARQUITECTURA AD-22 en 3.13, CONTRATOS.md:38 y :40. Hallazgo sin bloqueo: responsabilidades.md:7 asigna deploy/ a M1 y CONTRATOS.md:40 a Kenni. Sin comprobar: Docker, Compose, imagen y run_load en red; WSL2 con network_mode host; estimacion de lineas. (495f58d) |
