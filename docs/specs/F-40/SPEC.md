# SPEC F-40: Matriz, historial y bitácora

**Fase:** pr
**Base:** main
**Verificación IA:** revision 693cf26
**Historia:** US-40 · **Requisitos:** RNF-17, RNF-18, RNF-19, RNF-20; [Parte I §3, §4, §8], [Anexos 1 y 3], [B.9], [B.10] · **Responsable:** K

## Objetivo

Quien evalúa necesita juzgar la contribución individual: «una matriz de responsabilidades [...] que indique qué integrante es responsable principal de cada tema o módulo» y un historial de Git que «refleje la matriz» [Parte I §3]; además, una bitácora con «al menos una entrada por cada tema o módulo técnico en el que se haya usado IA» y «al menos dos casos documentados de error o imprecisión de la IA» [Parte I §4]. Hoy `docs/responsabilidades.md` existe, pero con la columna de apoyo en «Por definir», rutas aproximadas y sin la verificación contra el historial. La bitácora vive en la rama `estado` y la copia de `main` está desactualizada. F-40 deja los tres artefactos comprobables con comandos, y **declara con honestidad** lo que el historial no cumple todavía, sin rellenarlo.

## Alcance

**Incluye:**

- Actualizar `docs/responsabilidades.md` con el formato del Anexo 1: una fila por módulo M1 a M5 con responsable principal, apoyo, ruta real y ficha. Las rutas se comprueban contra el repositorio y los responsables contra `docs/EQUIPO.md`; ninguna se inventa.
- Agregar filas de los componentes que no son módulo (pipeline, dataset, carga y fallos, entrega) con su responsable según `docs/backlog/`, porque RNF-17 y RNF-18 cubren «M1–M5 y pipeline». El conjunto exacto lo decide la persona (pregunta 3).
- Una sección «Verificación» en `docs/responsabilidades.md` con los comandos exactos que el evaluador repite: `git shortlog -sn --all`, `git shortlog -sne --all`, `git log --all --format='%an %ad' --date=short` agrupado por día y `git log --stat --author=<nombre> -- <ruta>` por módulo. Con la salida **real y fecha de captura** en esa sección, no estimada.
- Una sección «Límites del historial» con lo que los comandos muestran hoy y no cumple RNF-18 (ver Riesgos): sin esconderlo ni corregirlo.
- Estado de la bitácora: comprobar que `origin/estado:docs/BITACORA_IA.md` tiene el formato del Anexo 3 (`python scripts/conformidad.py`), que hay entrada o declaración por módulo y que hay al menos dos errores de la IA con su validación. Anotar el resultado en `docs/responsabilidades.md`, con enlace a la bitácora.
- Llevar la bitácora a `main` por una PR aparte (`git checkout origin/estado -- docs/BITACORA_IA.md`), como manda `AGENTS.md`, para que el entregable esté en `main` y no solo en `estado`.

**No incluye:**

- Escribir entradas de bitácora de otros integrantes, o declarar «no se usó IA» en su nombre: lo registra cada responsable principal con `flujo.py bitacora` [Parte I §4].
- Crear, reescribir o simular commits ni fechas [Parte I §3]. Tampoco reescribir autoría del historial.
- Un script nuevo para medir la distribución del historial: el enunciado no lo pide y `git shortlog` basta.
- Fichas de evidencia (F-41), informe y README (F-42), `docs/reutilizacion.md` (F-39).
- Renombrar `docs/BITACORA_IA.md` a `docs/bitacora_ia.md`: es SUP-20, pendiente del profesor.
- Cambiar `docs/EQUIPO.md` ni `docs/REQUERIMIENTOS.md` (ver pregunta 1 sobre SUP-01).

## Criterios de aceptación

Copiados de `docs/backlog/entrega.md`, US-40:

- **Dado** el repositorio
- **Cuando** se revisan la matriz, el historial y la bitácora
- **Entonces** cada módulo tiene responsable, cada integrante tiene al menos un módulo y commits propios, hay entradas por módulo y ≥ 2 errores reales de la IA documentados
- **Pruebas:** A `git shortlog -sn --all`; revisión contra Anexos 1 y 3.
- **Demuestra:** comandos y documentos. **Evidencia:** `docs/responsabilidades.md`, `docs/BITACORA_IA.md`.

Precisión de «commits propios»: se mide **desde el inicio del II Proyecto** (primer commit de `main` del 03/nov/26) y por ruta del módulo, no solo con el total de `--all`, porque ese total incluye el historial importado del I Proyecto (ver Riesgos). Un integrante sin commits propios en su módulo se **reporta como incumplido**; el SPEC no lo da por cumplido.

## Diseño

Es una feature documental, sin código de producto ni capas afectadas, sin contratos de `docs/CONTRATOS.md` ni decisiones `AD-XX` nuevas. No reutiliza código del I Proyecto.

| Archivo | Dueño | Acción |
|---|---|---|
| `docs/responsabilidades.md` | K (F-40) | Modificar. Ya lo exige `scripts/conformidad.py` como pieza de F-40. |
| `docs/BITACORA_IA.md` | Cada responsable, vía `flujo.py bitacora` | Solo se copia desde `estado`; no se edita a mano. Va en una PR `chore/`, porque el check `alcance` rechaza `docs/BITACORA_IA.md` en una rama de feature. |
| `docs/EQUIPO.md` | Todos | Solo lectura: fuente de la letra y el usuario de cada integrante. |

Fuentes de verdad de cada columna de la matriz:

| Columna | Fuente |
|---|---|
| Responsable principal | `docs/EQUIPO.md` (módulos por usuario) y el responsable de cada US en `docs/backlog/` |
| Ruta | `git ls-files` de lo que el módulo ya tiene en `main`; lo aún inexistente se marca «pendiente», no se lista |
| Ficha | Nombre de `docs/modulo-MX-nombre.md` (F-41); hoy solo existe la de M1 |
| Apoyo | Decisión del equipo (pregunta 2); hasta entonces «Por definir», como está |

Hoy, según `docs/EQUIPO.md`: K = M4; N = M2; J = M1 y M5; V = M3.

Revisión de la bitácora (solo lectura, sobre `origin/estado:docs/BITACORA_IA.md`): 45 entradas y 41 líneas «Error de la IA» al 10/nov/26. Hay entradas de M1 (José), M3 (Melany), pipeline y dataset (José, Kenni), ciclo de trabajo y despliegue (Kenni). **No hay entradas de M2 ni de M5, y ninguna de Nahúm Murillo.** Tampoco hay de M4 propiamente (las de Kenni son ciclo de trabajo, despliegue y dataset). Si no hubo trabajo ni uso de IA en ese módulo, el responsable lo declara con `flujo.py bitacora --sin-ia`; si hubo uso, escribe la entrada. No lo hace F-40.

## Pruebas

F-33 a F-42 no siguen TDD [IMPLEMENTACION.md §4]. La verificación es por comprobación.

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | No aplica: sin código. | — |
| Integración | `python scripts/conformidad.py` (modo repositorio) sin problemas, y `python scripts/conformidad.py pr <base>` en cada PR. | Existe la pieza `docs/responsabilidades.md`, cada responsable de `docs/backlog/` está en `docs/EQUIPO.md`, y la bitácora tiene los campos del Anexo 3. |
| Aceptación | Revisión contra el Anexo 1 (filas y columnas) y el Anexo 3 (campos), con `git shortlog -sn --all` repetido por quien evalúa; `git log --author=<nombre> --stat -- <ruta>` por módulo; `grep -c "Error de la IA" docs/BITACORA_IA.md` ≥ 2 y lectura de dos casos con su validación. | Cada módulo tiene responsable, cada integrante aparece en el historial, la bitácora tiene entradas y errores reales; lo incumplido queda declarado. |

## Mediciones

No aplica. No son M1–M5 ni B.6. Las cifras del historial son datos del repositorio, no mediciones de SO; se citan con comando y fecha de captura.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Todo es documental, así que ninguna PR cuenta líneas de código.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-40): actualizar la matriz de responsabilidades y verificar el historial` | `docs/responsabilidades.md`: filas completas, enlace a la bitácora, sección «Verificación» con comandos y salida real fechada, sección «Límites del historial». Rama `feat/F-40-1-matriz-historial-y-bitacora`. |
| Aparte | `chore(docs): copiar la bitacora de IA desde la rama estado` | `git checkout origin/estado -- docs/BITACORA_IA.md`. No es parte de la pila de F-40; se hace al final y repetida justo antes de entregar, para que `main` lleve las últimas entradas. |

Si la persona decide documentar el estado por módulo en un segundo documento, sería una parte 2 de solo documentos; hoy se propone una sola PR.

## Riesgos y preguntas abiertas

Riesgos, comprobados con los comandos de la sección Verificación al 10/nov/26:

1. **El historial no cumple RNF-18 por completo.** `git shortlog -sn --all`: José Andrés Loría Herrera 595, Kenni Rodriguez 363, Melany Vindas 37, `krd` 24, `Auditoria` 20, Nahúm Murillo 17. Los 37 commits de Melany son todos del 10/nov/26, el día de entrega; y de los commits de José y Kenni hay 293 y 236 en esa misma fecha. «Un historial con uno o pocos commits masivos al final [...] evidencia insuficiente» [Parte I §3]. F-40 lo declara; no lo corrige.
2. **Nahúm Murillo no tiene commits del II Proyecto.** Sus 17 commits son del 25/sep al 01/oct/26, anteriores a la importación del 03/nov/26 (historial del I Proyecto). Desde el 01/nov/26 tiene 0 y no figura en la bitácora. M2 (F-20, F-21) y sus features del pipeline siguen sin trabajo suyo en el historial. El criterio «cada integrante tiene commits propios» **no se cumple hoy** para él.
3. **`shortlog` mezcla historiales.** Los commits anteriores al 03/nov/26 vienen del I Proyecto importado (25/sep a 03/oct): Kenni 41, José 17, Nahúm 17 (todos los suyos). Hay que decidir cómo presentar un historial «distribuido a lo largo de las tres semanas» [Parte I §3] sin usar commits ajenos al II Proyecto como evidencia (pregunta 5).
4. **Autores sin persona.** `krd` (24, el mismo correo que Kenni) y `Auditoria` (20 commits del 03/nov/26, correo `a@e.invalid`) aparecen como autores distintos y rompen «el autor debe coincidir con la matriz» [CONTRIBUTING.md]. No existe `.mailmap`.
5. **Bitácora en dos lugares.** La copia de `main` (353 líneas) está atrasada frente a `estado` (584 líneas); entregar con la de `main` pierde entradas. Se resuelve con la PR `chore/` aparte, pero hay que repetirla tras cada entrada nueva hasta la entrega.
6. **Posible contradicción de `SUP-01`.** `docs/REQUERIMIENTOS.md` aún dice que falta el usuario de Melany Vindas y la aceptación de Nahúm Murillo. `docs/EQUIPO.md` ya tiene `Mel28Vinso` y `gh api repos/.../collaborators` lista a Melany como colaboradora, mientras que la invitación de Nahúm sigue pendiente (`gh api repos/.../invitations`), así que `SUP-01` sigue vigente en lo de Nahúm. Debe actualizar `SUP-01` quien tenga la decisión; este SPEC no lo toca.
7. **Una bitácora con errores solo de la IA del equipo.** Hay entradas con «Error de la IA» abundantes, pero los conteos (41 líneas) no son 41 errores distintos; la aceptación exige leer al menos dos casos con su validación, no contar líneas.

Preguntas para la persona que aprueba (decisión pendiente, no resuelta aquí):

1. ¿Se actualiza `SUP-01` (usuarios de GitHub ya registrados) y quién lo hace? Aquí solo se avisa.
2. **SUP-nuevo (apoyo; SUP-23 ya lo usa F-16) propuesto:** ¿quién es el apoyo de cada módulo? Hoy «Por definir». Sin dato del equipo, queda «Por definir» y se declara. ¿O se asigna ahora?
3. ¿Qué filas no-módulo entran en la matriz: pipeline (F-01 a F-15), dataset (F-03, F-04), carga y fallos (F-33 a F-37), entrega (F-38 a F-42)? ¿Con el responsable de cada US del backlog o con una fila por área?
4. **SUP-nuevo (Nahúm; SUP-24 ya lo usa el preflight) propuesto:** Nahúm Murillo no tiene commits ni entradas de bitácora del II Proyecto. ¿Se declara así en `docs/responsabilidades.md` («incumplido a la fecha»), o hay trabajo suyo no registrado? No se inventa ni se atribuyen commits ajenos.
5. ¿Se presenta el historial del I Proyecto como evidencia de proceso, o solo desde el 03/nov/26 (primer commit del II Proyecto en `main`, 03/nov/26)? Afecta cuántos commits «propios» muestra cada integrante.
6. ¿Se agrega `.mailmap` para unir `krd` con Kenni Rodriguez? Cambia la salida de `shortlog` sin tocar historial; `Auditoria` no tiene persona asociada y requiere decisión del equipo. Prohibido reescribir historia.
7. ¿Los módulos sin entrada de bitácora (M2, M4, M5) llevan declaración «no se usó IA», o los responsables la registrarán con el uso real antes de entregar? La hora de entrega del 10/nov/26 sigue sin definir (SUP-03).

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador Sonnet 5.5; subagente arquitecto general-purpose) | 2026-11-10 | SPEC F-40 sin campos pendientes (grep), solo toca el SPEC, commit empujado. Recontado: git shortlog -sn --all coincide con el informe (Jose 595, Kenni 364, Melany 37, krd 24, Auditoria 20, Nahum 17); bitacora en estado con 45 entradas. No verifique fechas por autor ni errores de IA individuales. (fb53d33) |
| plan | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de tests | Claude Code (orquestador Sonnet 5.5; sin subagente) | 2026-11-10 | F-40 es solo documental (SPEC): sin pruebas ni codigo; la rama solo difiere de main en el SPEC. Verificacion no independiente. (f94c592) |
| tests | Kenni Rodriguez | 2026-11-10 | feature solo documental, sin pruebas ni codigo; aprobacion delegada por la persona |
| verificación IA de implementacion | Claude Code (orquestador Sonnet 5.5; sin subagente) | 2026-11-10 | F-40 es solo documental (SPEC): sin pruebas ni codigo; la rama solo difiere de main en el SPEC. Verificacion no independiente. (b604e3a) |
| implementacion | Kenni Rodriguez | 2026-11-10 | feature solo documental, sin pruebas ni codigo; aprobacion delegada por la persona |
| verificación IA de verificacion | Claude Code (orquestador Sonnet 5.5; sin subagente: verificacion no independiente) | 2026-11-10 | Ejecute PYTHONPATH=. python scripts/conformidad.py: 'Conformidad: 0 problema(s)' sobre la matriz actual. Capture git shortlog -sn --all y -sne --all el 2026-11-11 (UTC): Jose 595, Kenni 373, Melany 37, krd 24, Auditoria 20, Nahum 17 (el conteo de Kenni sube por mis commits de esta sesion). Salida guardada para la documentacion; sin cambios de codigo. (b2dd928) |
| verificacion | Kenni Rodriguez | 2026-11-10 | verificacion del orquestador sin QA independiente: feature solo documental; aprobacion delegada por la persona |
| verificación IA de documentacion | Claude Code (orquestador Sonnet 5.5; subagente documentador general-purpose) | 2026-11-10 | Diff solo toca docs/responsabilidades.md y SPEC. Ejecute conformidad.py: 0 problemas. Recontado: git shortlog -sn origin/main (Jose 395, Kenni 262, krd 24, Nahum 17), bitacora en estado 45 entradas; SUP-23 y SUP-24 ya existen en REQUERIMIENTOS:129 y ARQUITECTURA:240, corregido el SPEC. No re-ejecute pytest (solo docs). (98c774e) |
| documentacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de revision | Claude Code (orquestador Sonnet 5.5; subagente revisor general-purpose) | 2026-11-10 | Revisor DEVUELTO con 2 hallazgos (colaboradores en SPEC:101, deriva de recuentos); reproduje gh api collaborators (KennyRoDi, Mel28Vinso, joselhcr) y corregi ambos; conformidad 0 problemas. Resto verificado por el revisor (shortlog, rutas, bitacora, pytest 1637). (693cf26) |
| revision | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
