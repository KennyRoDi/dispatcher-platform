# SPEC F-30: Workers sin privilegios

**Fase:** implementacion
**Base:** feat/F-38-1-despliegue-en-tres-nodos
**Verificación IA:** tests 8d643e9
**Historia:** US-30 · **Requisitos:** RNF-07, RNF-12 · **Responsable:** K

## Objetivo

Limitar el daño de un worker comprometido [B.5 M4]: el proceso corre con UID distinto de 0, sin capacidades de Linux, sin poder ganar privilegios y con la raíz del contenedor de solo lectura. Hoy `Dockerfile.worker` ya fija `USER appuser`, pero los compose de worker no endurecen el contenedor, y la escritura de temporales cae en `/tmp` de una raíz escribible. Sin esto, el módulo M4 no puede mostrar «workers sin root» en su ficha (RNF-12) y su nota máxima es 2 [Parte I §5].

## Alcance

**Incluye:**
- `deploy/docker-compose.worker.yml` (nodos B/C/D) y el servicio `worker` de `deploy/docker-compose.local.yml`: `user` numérico fijo, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`.
- Escritura solo en volúmenes explícitos: `/scratch` (volumen con nombre, sin `tmpfs`, porque `tmpfs` cuenta en el cgroup y un video de 200 MB agotaría el límite; ARQUITECTURA §6) y `/tmp` como `tmpfs` pequeño para temporales de Python/FFmpeg.
- `Dockerfile.worker`: `WORK_DIR=/scratch`, directorio creado y de `appuser`, UID numérico fijo.
- Verificador de configuración `scripts/verificar_workers.py`, que parsea Dockerfile y compose con `yaml` y lista incumplimientos.
- Ficha M4, sección workers: estructura y comandos; salidas «pendiente» hasta tener nodos.

**No incluye:** cgroups y límites de memoria (F-05/M1); TLS (F-27); JWT (F-26); perfiles seccomp/AppArmor, `userns-remap` y rootless Docker (fuera de [B.5 M4]); endurecer coordinador, Redis, MinIO o reaper (el enunciado pide workers); el override GPU, que no toca estas claves; medir el costo del endurecimiento.

## Criterios de aceptación

- **Dado** los workers desplegados en los tres nodos, **cuando** se inspeccionan, **entonces** su UID es distinto de 0, la raíz es de solo lectura, se eliminan capacidades y procesan normalmente (US-30).
- Se añade `no-new-privileges` (SUP-32). Una sub-tarea completa bajo esa configuración, con video grande en `/scratch`.

## Diseño

**Contratos:** no implementa ni cambia ninguno de `docs/CONTRATOS.md`; es configuración de despliegue. Usa `WORK_DIR` (`src/workers/config.py`, hoy `tempfile.gettempdir()/mm-worker`) sin tocar código `src/`.

**Capas:** solo infraestructura (`deploy/`, `Dockerfile.worker`) y `scripts/`. `docs/IMPLEMENTACION.md` §4 declara que F-30 no lleva TDD de lógica; las pruebas unitarias verifican la configuración, no el comportamiento del SO.

**Archivos:** `Dockerfile.worker`, `deploy/docker-compose.worker.yml`, `deploy/docker-compose.local.yml`, `scripts/verificar_workers.py`, `tests/unit/test_workers_sin_privilegios.py`, `tests/integration/test_workers_sin_privilegios.py`, `docs/modulo-M4-seguridad.md`.

**Configuración objetivo por servicio worker:**
```yaml
user: "10001:10001"
read_only: true
cap_drop: [ALL]
security_opt: ["no-new-privileges:true"]
volumes: ["scratch:/scratch"]
tmpfs: ["/tmp:size=64m,mode=1777"]
```
`cap_drop: ALL` sin `cap_add`. El worker GPU solo añade `deploy.resources`, no `cap_add`.

**Decisiones:**
- **AD-36 (provisional):** workers con `user` numérico, raíz de solo lectura, `cap_drop: ALL` y `no-new-privileges`. Alternativas: solo `USER` del Dockerfile (no demuestra raíz de solo lectura ni capacidades); rootless Docker o `userns-remap` (cambia el host de cada nodo, fuera del enunciado); seccomp personalizado (costo alto sin que el enunciado lo pida). Criterio: cumple literalmente US-30 con configuración por contenedor. Fuente: documentación de Docker Engine (`--read-only`, `--cap-drop`, `--security-opt`); [B.5 M4]. Medición pendiente: que FFmpeg y la sub-tarea funcionen con esta configuración.
- **SUP-32 (provisional):** `no-new-privileges` se añade aunque US-30 no lo lista, porque impide la escalada por binarios setuid y `AGENTS.md` pide workers sin privilegios.
- `/scratch` y `/tmp`: `/scratch` con volumen con nombre (se borra por sub-tarea, ARQUITECTURA §6); `/tmp` en `tmpfs` de 64 MB, solo para temporales pequeños.

**Reutiliza:** el patrón de F-38 (`tests/unit/test_despliegue_compose.py`: parseo con `yaml`, `_ejecuta_worker`) y el `USER appuser` ya presente en `Dockerfile.worker`.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_workers_sin_privilegios.py`: verificador sobre cada servicio worker de los compose (`read_only` es `true`, `cap_drop` contiene `ALL` y no hay `cap_add`, `no-new-privileges` presente, `user` numérico distinto de 0) | La configuración cumple, sin Docker |
| Unitaria | Mismo archivo: `Dockerfile.worker` tiene `USER` no root, `WORK_DIR` bajo un volumen declarado, y todo servicio worker monta `/scratch`; compose de ejemplo incumplidor produce un mensaje por incumplimiento | El verificador detecta regresiones |
| Integración | `tests/integration/test_workers_sin_privilegios.py`, marca `integration`: `docker exec <w> id -u` distinto de 0; `touch /x` falla; `docker inspect` da `ReadonlyRootfs=true`, `CapDrop=[ALL]` y `no-new-privileges`. Se salta sin Docker o sin contenedor | Prueba I del backlog |
| Aceptación | Una sub-tarea completa (imagen y video) con el worker endurecido, contra nodos reales. Se salta sin variables | Procesa normalmente (prueba A) |

## Mediciones

M4, sin TDD [Anexo 2]; ficha `docs/modulo-M4-seguridad.md`, sección workers. Una repetición por nodo (configuración, no rendimiento):
- `docker exec <worker> id -u`
- `docker inspect -f '{{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}}' <worker>`
- `docker exec <worker> sh -c 'touch /x'` (debe fallar)

Las salidas reales no existen aún: la ficha queda «pendiente», sin cifras inventadas. Se captura en los tres nodos.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-30): endurecer workers sin privilegios` | Claves de seguridad en ambos compose, `WORK_DIR=/scratch` y UID fijo en `Dockerfile.worker`, `scripts/verificar_workers.py` (estimado: 120 líneas). Pruebas, AD-36, SUP-32 y ficha M4 pendiente. |

## Riesgos y preguntas abiertas

1. Con `read_only`, ¿hay escrituras no previstas (caché de Python, `~/.cache`, Redis o MinIO clients)? Se detecta solo ejecutando; si aparece alguna, se añade un volumen y se registra.
2. `/scratch` con volumen con nombre persiste entre reinicios: ¿se acepta que el worker lo limpie al arrancar, o se prefiere `tmpfs` con límite alto pese al cgroup?
3. ¿Se aprueba `no-new-privileges` (SUP-32) y el UID 10001 fijo (AD-36)?
4. ¿Se endurece también el servicio `worker` de `deploy/docker-compose.local.yml` (desarrollo), o solo `deploy/docker-compose.worker.yml`? Propuesta: ambos.
5. Aceptación y ficha M4 requieren los tres nodos reales (José, Nahúm, Melany); sin ellos, la evidencia queda pendiente.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador Sonnet 5.5; subagente arquitecto general-purpose) | 2026-11-11 | SPEC F-30 sin campos pendientes (grep 0); diff contra main solo el SPEC. Hallazgo del arquitecto (Dockerfile.worker ya tiene USER) comprobado con grep. AD-36/SUP-32 libres segun arquitecto (no re-verifique). Pila de 1 parte. 5 preguntas abiertas; decision provisional: aceptar, endurecer tambien el compose local, UID 10001, /scratch con volumen nombrado. (4f7548d) |
| plan | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-11 | Diff contra main: SPEC y 3 archivos de test nuevos (unit, integracion, aceptacion); src, scripts y deploy intactos. Ejecute la unitaria: error de coleccion ModuleNotFoundError scripts.verificar_workers (rojo). Integracion y aceptacion se saltan sin docker/entorno. API asumida: incumplimientos_compose, incumplimientos_dockerfile, main(argv) con --compose/--dockerfile; exige user numerico, read_only, cap_drop ALL, no-new-privileges:true, tmpfs /tmp con size, volumen scratch y WORK_DIR=/scratch. (8d643e9) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
