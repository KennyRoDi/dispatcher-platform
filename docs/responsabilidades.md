# Matriz de responsabilidades

Distribución aceptada por el equipo [Parte I §3, Anexo 1]. Los responsables salen de [EQUIPO.md](EQUIPO.md) y del backlog ([backlog/](backlog/README.md)). Las rutas se comprobaron con `git ls-files` sobre `main` el 2026-11-11 (UTC); lo que aún no existe se marca «pendiente» y no se lista como hecho. El apoyo no está definido: se declara «Por definir» y no se rellena.

## Módulos M1 a M5

| Módulo | Responsable principal | Apoyo | Ruta en el repositorio | Ficha de evidencia |
|---|---|---|---|---|
| M1 · Gestión de memoria | José Andrés Loría Herrera | Por definir | Existe: `src/workers/`, `src/domain/admission.py`, `src/domain/node_budget.py`, `src/infrastructure/cgroup_resources.py`. Pendiente: `src/domain/oom_policy.py` | `docs/modulo-M1-memoria.md` (existe) |
| M2 · Planificación de cargas | Nahúm Murillo | Por definir | Existe: `src/coordinator/rutas_casos.py`, `src/coordinator/rutas_subtareas.py`. Pendiente: `src/domain/scheduling.py`, `case_state.py`, `retry.py` | `docs/modulo-M2-planificacion.md` (pendiente, F-41) |
| M3 · E/S y almacenamiento | Melany Vindas | Por definir | Existe en `main`: `dashboard/`. Pendiente en `main`: `src/domain/chunks.py`, `src/adapters/minio_object_store.py`, `src/coordinator/rutas_archivos.py`. Los archivos de F-22 (`src/domain/chunks.py`, `src/application/chunked_upload.py`, `src/adapters/disk_chunk_staging.py`) están solo en la rama `feat/F-22-1-chunks-verificados` | `docs/modulo-M3-es-almacenamiento.md` (pendiente, F-41) |
| M4 · Protección y seguridad | Kenni Rodriguez | Por definir | Existe: `deploy/`. Pendiente: `src/domain/rbac.py`, `src/domain/custody_chain.py`, `src/coordinator/seguridad.py` | `docs/modulo-M4-seguridad.md` (pendiente, F-41) |
| M5 · Cómputo heterogéneo | José Andrés Loría Herrera | Por definir | Pendiente: `scripts/measure/`, `src/domain/routing.py` (`benchmarks/benchmark_transcode.py` existe, de antes del II Proyecto, sin asignar a M5 en `docs/CONTRATOS.md`) | `docs/modulo-M5-computo.md` (pendiente, F-41) |

Los archivos de cada responsable salen de «Quién toca qué» en [CONTRATOS.md](CONTRATOS.md). El detalle por funcionalidad está en [IMPLEMENTACION.md](IMPLEMENTACION.md) §2.

## Componentes que no son módulo

RNF-17 y RNF-18 cubren M1 a M5 y el pipeline. El responsable es el de cada historia en `docs/backlog/`; varias áreas tienen más de una persona. El conjunto de filas está pendiente de decisión del equipo (pregunta 3 del SPEC de F-40).

| Componente | Features | Responsable según el backlog | Apoyo |
|---|---|---|---|
| Pipeline: recepción, cola y workers | F-01, F-02, F-05, F-06 (Nahúm Murillo); F-07, F-08, F-09 (José Andrés Loría Herrera) | Nahúm Murillo, José Andrés Loría Herrera | Por definir |
| Pipeline: estados, reporte y dashboard | F-10, F-11 (Nahúm Murillo); F-12 (José Andrés Loría Herrera); F-13, F-14 (Kenni Rodriguez); F-15 (Melany Vindas) | Nahúm Murillo, José Andrés Loría Herrera, Kenni Rodriguez, Melany Vindas | Por definir |
| Dataset sintético | F-03, F-04 | Kenni Rodriguez | Por definir |
| Carga y fallos [B.6] | F-33 (Kenni Rodriguez); F-34, F-35 (Nahúm Murillo); F-36, F-37 (José Andrés Loría Herrera) | Kenni Rodriguez, Nahúm Murillo, José Andrés Loría Herrera | Por definir |
| Entrega | F-38, F-40 (Kenni Rodriguez); F-39 (Nahúm Murillo); F-41 (cada responsable); F-42 (todos) | Kenni Rodriguez, Nahúm Murillo, todos | Por definir |

## Verificación

Quien evalúa repite estos comandos desde la raíz del repositorio. Captura del 2026-11-11 (UTC), tomada antes del commit de esta PR; el conteo de Kenni Rodriguez sube con los commits posteriores. La salida es la real, no estimada.

### Commits por autor

```bash
git shortlog -sn --all
```

```text
   595	José Andrés Loría Herrera
   376	Kenni Rodriguez
    37	Melany Vindas
    24	krd
    20	Auditoria
    17	Nahúm Murillo
```

```bash
git shortlog -sne --all
```

```text
   595	José Andrés Loría Herrera <josealhcr@gmail.com>
   376	Kenni Rodriguez <ken.rodriguez@estudiantec.cr>
    37	Melany Vindas <melany28@estudiantec.cr>
    24	krd <ken.rodriguez@estudiantec.cr>
    20	Auditoria <a@e.invalid>
    17	Nahúm Murillo <n4hummuro227@gmail.com>
```

El total de `--all` incluye las ramas `feat/*` y `estado`. Solo en `main` (`git shortlog -sn origin/main`) la captura da: José Andrés Loría Herrera 395, Kenni Rodriguez 262, `krd` 24, Nahúm Murillo 17. Los commits de Melany Vindas y de `Auditoria` no están en `main`: los de Melany están en `origin/feat/F-22-1-chunks-verificados` y `origin/estado`; los de `Auditoria`, solo en `origin/estado`.

### Commits por día desde el 03/nov/26

El II Proyecto empieza el 03/nov/26 (commit `3681665`, «chore: importar el I Proyecto con su historial»). Comando (se filtra por fecha de autor con `awk`; con `git log --since` la misma captura dio recuentos menores):

```bash
git log --all --format='%an|%ad' --date=short | awk -F'|' '$2>="2026-11-03"{c[$2" "$1]++} END{for(k in c) print c[k], k}' | sort -k2
```

```text
20 2026-11-03 Auditoria
42 2026-11-03 Kenni Rodriguez
15 2026-11-03 krd
4 2026-11-05 José Andrés Loría Herrera
43 2026-11-05 Kenni Rodriguez
1 2026-11-05 krd
1 2026-11-06 Kenni Rodriguez
1 2026-11-06 krd
109 2026-11-07 José Andrés Loría Herrera
57 2026-11-08 José Andrés Loría Herrera
115 2026-11-09 José Andrés Loría Herrera
293 2026-11-10 José Andrés Loría Herrera
249 2026-11-10 Kenni Rodriguez
7 2026-11-10 krd
37 2026-11-10 Melany Vindas
```

Total de la captura: 1069 commits (`--all`); 586 llevan fecha del 10/nov/26.

### Commits por ruta de módulo

Por módulo, con las rutas de la tabla (existentes y pendientes; las ausentes no aportan commits), desde el 03/nov/26:

```bash
git log --all --format='%an|%ad' --date=short -- <rutas del módulo> | awk -F'|' '$2>="2026-11-03"{c[$1]++} END{for(k in c) print c[k], k}'
git log --all --stat --author=<nombre> -- <ruta del módulo>
```

| Módulo | Rutas consultadas | Commits desde el 03/nov/26 por autor |
|---|---|---|
| M1 | `src/workers/ src/domain/admission.py src/domain/node_budget.py src/infrastructure/cgroup_resources.py src/domain/resources.py` | José Andrés Loría Herrera 3, Kenni Rodriguez 2 |
| M2 | `src/coordinator/rutas_casos.py src/coordinator/rutas_subtareas.py src/domain/scheduling.py src/domain/case_state.py src/domain/retry.py src/domain/priority.py` | José Andrés Loría Herrera 1, Kenni Rodriguez 2, `krd` 1; Nahúm Murillo 0 |
| M3 | `dashboard/ src/domain/chunks.py src/application/chunked_upload.py src/adapters/disk_chunk_staging.py` | Melany Vindas 4 (en `origin/feat/F-22-1-chunks-verificados`, sin fusionar en `main`) |
| M4 | `deploy/ src/domain/rbac.py src/domain/custody_chain.py src/coordinator/seguridad.py` | José Andrés Loría Herrera 1, Kenni Rodriguez 2 |
| M5 | `benchmarks/ scripts/measure/ src/domain/routing.py` | Ninguno |

Ejemplo del `--stat` de M3, real:

```bash
git log --all --stat --format='%h %ad %an %s' --date=short --author=Melany -- src/domain/chunks.py src/application/chunked_upload.py src/adapters/disk_chunk_staging.py
```

```text
9517dcf 2026-11-10 Melany Vindas fix(F-22): verificar sha256 sobre el mismo flujo entregado al almacen

 src/application/chunked_upload.py | 42 ++++++++++++++++++++++++++-------------
 1 file changed, 28 insertions(+), 14 deletions(-)
316b0de 2026-11-10 Melany Vindas feat(F-22): agregar staging de chunks en disco

 src/adapters/disk_chunk_staging.py | 66 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 66 insertions(+)
b4cfbc4 2026-11-10 Melany Vindas feat(F-22): reensamblar chunks verificados por sha-256

 src/application/chunked_upload.py | 99 +++++++++++++++++++++++++++++++++++++++
 1 file changed, 99 insertions(+)
95292a4 2026-11-10 Melany Vindas feat(F-22): agregar dominio y puerto de chunks verificados

 src/domain/chunks.py | 79 ++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 79 insertions(+)
```

Último commit de Nahúm Murillo, sin ninguno posterior:

```bash
git log --all --author='Nahúm' --format='%h %ad %s' --date=short | head -1
```

```text
ed51052 2026-10-01 Completely conexion - Tailscale already
```

## Límites del historial

Hechos del historial a la fecha de captura. Se declaran tal cual; no se corrigen ni se reescribe historia [Parte I §3].

- **Historial del I Proyecto anterior al 03/nov/26.** Los commits con fecha anterior al 03/nov/26 vienen del I Proyecto importado (25/sep al 03/oct/26): Kenni Rodriguez 41, José Andrés Loría Herrera 17 y Nahúm Murillo 17. `git shortlog -sn --all` los suma al total. Cómo presentarlos como evidencia o excluirlos está pendiente de decisión del equipo.
- **Autores duplicados.** `krd` (24 commits, mismo correo que Kenni Rodriguez) y `Auditoria` (20 commits del 03/nov/26, correo `a@e.invalid`, todos en `origin/estado`) aparecen como autores distintos. [CONTRIBUTING.md](../CONTRIBUTING.md) pide que el autor coincida con la matriz. No existe `.mailmap`. Si se agrega, y qué hacer con `Auditoria`, está pendiente de decisión del equipo.
- **Concentración del 10/nov/26.** 586 de los 1069 commits llevan fecha del 10/nov/26. Ese día: José Andrés Loría Herrera 293, Kenni Rodriguez 249, `krd` 7, Melany Vindas 37. Los 37 commits de Melany Vindas son todos de ese día. [Parte I §3] considera evidencia insuficiente un historial con pocos commits masivos al final.
- **Nahúm Murillo.** Sus 17 commits van del 25/sep al 01/oct/26, todos anteriores al II Proyecto. Desde el 03/nov/26 tiene 0 commits y no figura en la bitácora. M2 (F-20, F-21) y sus features del pipeline no tienen commits suyos. El criterio «cada integrante tiene commits propios» de US-40 no se cumple a la fecha para él. Si hay trabajo suyo no registrado, queda pendiente de decisión del equipo; no se atribuyen commits ajenos.
- **Melany Vindas.** Sus 37 commits no están en `main`: están en `origin/feat/F-22-1-chunks-verificados` (28) y `origin/estado` (9). A la fecha de captura `gh pr list` no muestra una PR de esa rama.
- **Apoyo.** Ningún módulo ni componente tiene apoyo definido. Pendiente de decisión del equipo.
- **`SUP-01`.** `docs/REQUERIMIENTOS.md` aún dice que falta el usuario de Melany Vindas y la aceptación de Nahúm Murillo. [EQUIPO.md](EQUIPO.md) ya registra a Melany Vindas con `Mel28Vinso`. Lo actualiza quien tenga esa decisión.

## Bitácora de IA

La bitácora vigente está en la rama `estado` (`git show origin/estado:docs/BITACORA_IA.md`); los recuentos de esta sección y de «Verificación» son de la captura y derivan con cada commit o entrada nueva (p. ej. la entrada de F-40 misma); su enlace en `main` es [BITACORA_IA.md](BITACORA_IA.md), cuya copia está atrasada (353 líneas y 27 entradas frente a 584 líneas y 45 entradas en `estado` al 2026-11-11). Subirla a `main` es una PR aparte, `chore/`, y se repite antes de entregar.

Recuento sobre `estado` (comandos: `grep -c '^## '` y `grep -c 'Error de la IA'`):

| Dato | Valor |
|---|---|
| Entradas | 45: Kenni Rodriguez 22, José Andrés Loría Herrera 22, Melany Vindas 1, Nahúm Murillo 0 |
| Líneas «Error de la IA» | 41 (líneas, no errores distintos; la aceptación exige leer casos con su validación). Ejemplos: la primera entrada (cita de «unas 387 pruebas» frente a 474 al ejecutar `pytest`) y la segunda (variable con espacios en `zsh`) |
| Declaraciones «sin IA» | 0 |

Por módulo:

| Módulo | Entradas | Estado |
|---|---|---|
| M1 | Sí (José Andrés Loría Herrera: F-16, F-17, F-19) | Con entrada |
| M2 | No | Sin entrada ni declaración «sin IA». Lo registra su responsable con `flujo.py bitacora` |
| M3 | Sí (Melany Vindas: F-22) | Con entrada |
| M4 | No propiamente: las entradas de Kenni Rodriguez son de ciclo de trabajo, despliegue (F-38) y dataset (F-03) | Sin entrada de M4. Lo registra su responsable |
| M5 | No | Sin entrada ni declaración «sin IA». Lo registra su responsable |

Si hubo uso de IA en un módulo, el responsable escribe la entrada; si no lo hubo, la declara con `--sin-ia`. F-40 no escribe entradas ajenas [Parte I §4]. La conformidad del formato de la copia de `main` se comprueba con `PYTHONPATH=. python scripts/conformidad.py`.
