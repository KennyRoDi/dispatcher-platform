# SPEC F-03: Dataset sintético

**Fase:** verificacion
**Base:** feat/F-03-1-dataset-sintetico
**Verificación IA:** implementacion 648b23a
**Historia:** US-03 · **Requisitos:** RF-18, RF-19, RF-20, RF-21, RF-22, RNF-04, RNF-05 · **Responsable:** K

## Objetivo

El equipo obtiene un dataset reproducible que cumple el mínimo de [B.3 Dataset mínimo] (40 casos, 10 heterogéneos, 20 000 mensajes, 300 imágenes, 150 audios, 5 casos con archivos ≥ 200 MB) sin datos de terceros [B.3 Consideraciones éticas], para probar con volumen el pipeline y las mediciones M1–M5. Todo el dataset es sintético y lo genera el equipo: chats, imágenes y audio. No se usan datasets públicos, para evitar consideraciones legales y de licencia. Un validador cuenta el cumplimiento sobre el dataset real; su salida es la evidencia de `docs/dataset.md`.

## Alcance

**Incluye:**
- Plan determinista de casos (dominio puro) por semilla.
- Generador de exportaciones de chat sintéticas estilo WhatsApp y Telegram (20 000 mensajes en total).
- Imágenes (300) y audios (150) sintéticos, con proporción de contenido positivo conocida y etiqueta de verdad asignada por el generador, producidos por el propio equipo con `ffmpeg`.
- Casos pesados (≥ 200 MB) generados en local, en una ruta configurable, no versionados.
- 10 casos heterogéneos: 5 livianos y 5 pesados; los otros 30 casos pueden ser de uno o pocos tipos.
- Manifiesto con origen, licencia y conteos por tipo; validador de mínimos B.3.
- `docs/dataset.md` con la procedencia («generado por el equipo», con la licencia del repo), qué casos cumplen cada condición, la salida real del validador, la limitación de los patrones sintéticos y cómo los integrantes obtienen los casos pesados.

**No incluye:** comparador y fallo por licencia ausente (F-04); parsers y validación de formatos de ingesta (F-02); subir los casos a la API (F-01); análisis de los archivos (F-07 a F-09). Entrenar modelos [B.1]. Datasets públicos de terceros. Versionar el dataset pesado o los medios. Publicar el dataset en Google Drive: lo hace la persona, fuera del repo.

## Criterios de aceptación

- **Dado** el generador con una semilla
- **Cuando** se ejecuta
- **Entonces** hay ≥ 40 casos, ≥ 10 heterogéneos (5 livianos y 5 pesados), ≥ 20 000 mensajes, ≥ 300 imágenes, ≥ 150 audios y ≥ 5 casos con archivos ≥ 200 MB

Adicionales derivados del enunciado: misma semilla produce el mismo manifiesto (mismos nombres, conteos y hashes de contenido); el manifiesto declara la proporción de contenido positivo por categoría de imagen (RF-20) y duraciones distintas de audio (RF-21); todos los archivos tienen origen `sintetico` y la licencia del repo (RNF-04); cada caso pesado es heterogéneo.

## Diseño

**Contratos.** Ninguno de `docs/CONTRATOS.md`: F-03 no tiene dependencias ni toca puertos ni archivos de otro dueño. Solo crea archivos propios de Kenni.

**Capas y archivos (nuevos).**
- Dominio: `src/domain/dataset_plan.py`. Funciones puras: `plan_dataset(seed, params) -> DatasetPlan` (casos, heterogéneos livianos y pesados, conteos de mensajes, imágenes, audios, proporción positiva) y `check_minimums(plan) -> list[str]` (incumplimientos del plan; la validación del manifiesto real es de la parte 5). Sin E/S, sin reloj, sin `random` global: `random.Random(seed)`. `params` por configuración.
- Adaptadores (`src/adapters/`): `chat_export_generator.py` (texto WhatsApp/Telegram, UTF-8, timestamps y remitentes sintéticos), `media_generator.py` (imágenes y audios sintéticos con etiqueta del generador, vía `ffmpeg`, ejecutor inyectado), `heavy_case_generator.py` (archivo grande ≥ 200 MiB de los casos pesados, mismo ejecutor).
- Script: `scripts/dataset_sintetico.py`, CLI `--seed`, `--out`, `--params`, `--validar`. Escribe fuera del repo.
- Documento: `docs/dataset.md`.

**Decisiones.**
- **AD-25 aprobada por la persona:** generador nuevo y determinista en vez de ampliar `scripts/build_dataset.py`, que solo cubre video y audio, no tiene texto ni imágenes y su manifiesto trae `generated_at` (no reproducible). Alternativa: extender el heredado. Criterio: RF-18 a RF-22 exigen texto e imágenes y reproducibilidad. El arquitecto no toca `docs/ARQUITECTURA.md` en esta fase: registrar AD-25 en §8 es tarea de la fase documentación (parte 6).
- Dataset totalmente sintético, decisión de la persona: sin datasets públicos (Kaggle, Hugging Face, Roboflow, LibriSpeech, ESC-50) para evitar consideraciones legales y de licencia. Procedencia declarada en `docs/dataset.md`: «generado por el equipo», con la licencia del repo. Si se usa IA para redactar plantillas, se declara en `docs/BITACORA_IA.md`.
- Ruta de salida: parámetro `--out`. Ubicación de desarrollo decidida por la persona: `~/scratch/dataset`, fuera del repo (hay 106 GB libres y no depende de `/scratch`, que no existe). Debe ser disco, no `tmpfs`, que cuenta en el cgroup (`docs/ARQUITECTURA.md` §4). `dataset/media/` ya está en `.gitignore`. Solo se versionan el manifiesto y `docs/dataset.md`.
- Distribución: el repo es público, así que los casos pesados no se versionan. Se generan en local; la persona los sube a Google Drive y los demás integrantes los descargan y los usan en local. El enlace, el procedimiento y la verificación por `sha256` del manifiesto se documentan en `docs/dataset.md`, sin llaves ni credenciales en el repo.
- Mensajes de chat: plantillas con vocabulario neutro y un subconjunto con frases de amenaza ficticias para F-07, aprobadas por la persona; sin personas ni datos reales.
- Imágenes: patrones sintéticos generados con `ffmpeg` (`lavfi`) o equivalente, con proporción positiva conocida por categoría y etiqueta (positivo/negativo) asignada por el generador. Audios: tonos o ruido con duraciones distintas y etiqueta del generador, reutilizando las constantes `AUDIO_*` de `scripts/build_dataset.py`.
- Limitación a documentar en `docs/dataset.md`: F-08 medirá la detección sobre patrones sintéticos, no sobre fotos reales; sus resultados no se extrapolan a imágenes reales.
- Heterogéneos (opción A): 10 casos, 5 livianos (texto, imagen, audio y documento) y 5 pesados (≥ 200 MB; texto, imagen, audio y video o documento). Los 5 pesados son parte de los 10 y de los ≥ 5 pesados de B.3. Los otros 30 casos pueden ser de uno o pocos tipos.
- Casos pesados: el archivo grande es video sintético con bitrate fijo hasta superar 200 MiB (o documento grande); el generador falla si el archivo queda por debajo. El resto de sus archivos (texto, imagen, audio) sale de los mismos generadores.
- Manifiesto (`manifest.json`) con campos `case`, `kind` (`texto|imagen|audio|video|documento`), `path`, `bytes`, `sha256`, `origen` (siempre `sintetico`), `licencia` (la del repo), `semilla`, `etiqueta` (verdad asignada por el generador, en imágenes y audio) y `heterogeneo` (`liviano|pesado|no`). Sin marca de tiempo. F-04 lo extiende; no se renombran campos.

**Reutiliza del I Proyecto:** `ffmpeg_args` y constantes de duración de `scripts/build_dataset.py`, sin copiar historial. Se copia solo lo necesario, con cita en comentario.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_generador_cumple_minimos_de_b3` | `plan_dataset` con una semilla y parámetros por defecto cumple todos los mínimos de B.3 |
| Unitaria | `test_plan_tiene_cinco_heterogeneos_livianos_y_cinco_pesados` | 10 heterogéneos; los 5 pesados incluyen texto, imagen, audio y video o documento |
| Unitaria | `test_misma_semilla_produce_el_mismo_plan` | Determinismo; semillas distintas dan planes distintos |
| Unitaria | `test_plan_bajo_el_minimo_se_reporta` | `check_minimums` nombra cada mínimo incumplido |
| Unitaria | `test_plan_declara_proporcion_positiva_y_duraciones_distintas` | Cada categoría de imagen tiene proporción positiva declarada y los audios tienen duraciones distintas (RF-20, RF-21) |
| Unitaria | `test_exportacion_whatsapp_se_parsea_con_timestamp_y_remitente` | Formato realista, UTF-8, con el parser existente o su doble |
| Unitaria | `test_medios_llevan_etiqueta_y_origen_sintetico` | Con ejecutor falso: cada imagen y audio sale con etiqueta del generador, origen `sintetico` y licencia del repo |
| Unitaria | `test_caso_pesado_falla_si_no_alcanza_200_mib` | Con ejecutor falso; sin `ffmpeg` real ni red |
| Integración | `test_generacion_reducida_escribe_manifiesto` | Parámetros reducidos con `ffmpeg` real en `tmp_path`: archivos y manifiesto coherentes |
| Aceptación | `test_validador_sobre_dataset_completo` | Marcada `acceptance`: el validador sobre la ruta de `--out` cumple B.3; su salida va a `docs/dataset.md` |

## Mediciones

No aplica. F-03 no mide el SO. El dataset alimenta M3 (RNF-11, tasa de deduplicación) y los casos ≥ 200 MB alimentan F-33 a F-37, que miden aparte.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-03): planear el dataset y validar los minimos de B.3` | `src/domain/dataset_plan.py`: `plan_dataset`, `check_minimums`, parámetros, heterogéneos livianos y pesados. Dominio puro, ~150 líneas |
| 2 | `feat(F-03): generar exportaciones de chat sinteticas` | `src/adapters/chat_export_generator.py`, WhatsApp y Telegram, ~120 líneas |
| 3 | `feat(F-03): generar imagenes y audio sinteticos etiquetados` | `src/adapters/media_generator.py` con ejecutor de `ffmpeg` inyectado: imágenes con proporción positiva y audios de duraciones distintas, ~150 líneas |
| 4 | `feat(F-03): generar archivos grandes de los casos pesados` | `src/adapters/heavy_case_generator.py`: video o documento ≥ 200 MiB, falla si no alcanza, ~100 líneas |
| 5 | `feat(F-03): componer casos heterogeneos y manifiesto con CLI` | `scripts/dataset_sintetico.py`: arma los 10 heterogéneos, manifiesto, `--validar`, ~150 líneas |
| 6 | `docs(F-03): registrar procedencia, distribucion y salida del validador` | `docs/dataset.md` (procedencia «generado por el equipo», limitación sintética, casos por condición, enlace de Drive, salida real del validador) y AD-25 en `docs/ARQUITECTURA.md` §8. Sin código; va al final porque necesita el dataset generado |

## Riesgos y preguntas abiertas

**Riesgos.**
- Disco: ≥ 5 archivos ≥ 200 MiB más medios necesitan espacio libre en la ruta de `--out`; `/scratch` no existe en la máquina de desarrollo, la ruta es parámetro.
- Generar 5 videos de 200 MiB con `ffmpeg` puede tardar; el tiempo real solo se conocerá al ejecutarlo. No se estima aquí.
- La reproducibilidad de bytes de `ffmpeg` puede variar entre versiones; se garantiza el plan y el manifiesto planeado, no necesariamente el `sha256` entre versiones de `ffmpeg`.
- Validez: los patrones sintéticos no equivalen a fotos reales; F-08 mide detección sobre ellos y la limitación se declara en `docs/dataset.md`.
- Distribución: el enlace de Google Drive depende de la persona y queda fuera del repo; si no se sube, los demás integrantes deben regenerar los casos en local.

**Preguntas abiertas.**
1. Formato y ubicación del documento grande de los casos pesados cuando no se use video (documento ≥ 200 MB): tipo de archivo, a definir en la fase de tests.

**Resueltas por la persona (2026-11-10).** AD-25 aprobada; mensajes siempre sintéticos y frases de amenaza ficticias aprobadas; dataset pesado en local y distribuido por Google Drive fuera del repo; opción A para heterogéneos (5 livianos y 5 pesados, los pesados incluidos); todo el dataset sintético (chats, imágenes y audio) generado por el equipo, se descartan los datasets públicos (Kaggle, Hugging Face, Roboflow, LibriSpeech, ESC-50) por consideraciones legales y de licencia, lo que cierra las preguntas de selección de datasets y de redistribución.


## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose) | 2026-11-05 | Leí SPEC completo: sin campos pendientes (grep), commit 78301a4 pusheado, árbol limpio, solo toca SPEC. Contrasté con ENUNCIADO B.3 (mínimos y ética), REQUERIMIENTOS RF-18..22/RNF-04/05, build_dataset.py (ffmpeg_args:203, AUDIO_*), .gitignore dataset/media/, ARQUITECTURA §8 (último AD-24, AD-25 libre). No ejecuté pruebas (fase sin código). No verificado: parser WhatsApp existente (no hallé uno en src), espacio/ffmpeg en /scratch. (78301a4) |
| verificación IA de plan | Claude Code (orquestador, Sonnet 5.5) | 2026-11-10 | Releido el SPEC: sin campos pendientes (grep), cubre mínimos de B.3 y ética RNF-04/05, árbol limpio, commit empujado. Sin código ni pruebas en esta fase. (34573a4) |
| plan | Kenni Rodriguez | 2026-11-10 |  |
| devuelta de tests | Kenni Rodriguez | 2026-11-10 | Incorporar: imágenes y audio de datasets públicos licenciados (Kaggle) con fallback sintético; chats sintéticos; casos pesados en local/Drive; opción A: 10 heterogéneos, 5 livianos y 5 pesados solapados |
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | SPEC releído tras la devolución: sin campos pendientes (grep), solo toca SPEC, commit empujado, árbol limpio. Recoge opción A (10 heterogéneos: 5 livianos y 5 pesados), chats sintéticos, imágenes y audio públicos con fallback sintético, pesados en local y Drive, pila de 6 PR. Sin código ni pruebas en esta fase. (49972ce) |
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | SPEC releído: todo sintético, sin media_source ni referencias a datasets públicos fuera de No incluye y decisiones (grep), sin campos pendientes, solo toca SPEC, commit empujado, árbol limpio. Mantiene opción A, pesados en local y Drive, pila de 6 PR. Sin código ni pruebas en esta fase. (bc1ea57) |
| plan | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de tests | Claude Code (subagente developer, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Reejecuté pytest en tests/unit/test_dataset_plan.py: 1 error de colección por ModuleNotFoundError de src.domain.dataset_plan (rojo por código ausente, no por sintaxis). Solo se añadió ese archivo de pruebas, src/ intacto, commit empujado. Leí las 7 pruebas: cubren mínimos B.3, 5 livianos y 5 pesados, determinismo, proporción positiva, duraciones y reporte de cada mínimo. Ajusté el SPEC: ruta ~/scratch/dataset y check_minimums sobre el plan. (f386432) |
| tests | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code (subagente developer, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Reejecuté pytest -m 'not integration and not acceptance': 695 passed, 3 skipped. Solo se añadió src/domain/dataset_plan.py (117 líneas), pruebas intactas, imports solo random/dataclasses/enum (sin E/S ni reloj), sin comentarios, commit empujado. (d3bb399) |
| implementacion | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de verificacion | Claude Code (subagente qa-tester, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Reejecuté pytest: 717 passed, 3 skipped, 6 xfailed. src/ intacto, solo pruebas nuevas (ed9ed39) empujadas, árbol limpio. Reproduje la observación 1 (cases=3 devuelve 10 casos). QA reporta 3 observaciones menores no bloqueantes, dejadas como xfail estricto. (ed9ed39) |
| verificacion | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de documentacion | Claude Code (subagente documentador, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Documentador no cambió archivos: README no menciona dataset, docs/reutilizacion.md no existe, docs/dataset.md y AD-25 son de la parte 6. Árbol limpio y sin commits nuevos. Entregó borrador de bitácora con hechos del historial; los 3 defectos de QA se registran como abiertos (xfail), no corregidos. (afe8672) |
| documentacion | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de revision | Claude Code (subagente revisor, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Revisión de la parte 1: APROBADO sin bloqueantes. Comprobé en el código las observaciones de dataset_plan.py (mínimos fijos en check_minimums, exigencia solo de 10 heterogéneos en total, nombre HEAVY_KINDS). Árbol limpio, commit empujado, pruebas en verde en la fase anterior. (8a01b29) |
| revision | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de tests | Claude Code (subagente developer, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Reejecuté pytest en tests/unit/test_chat_export_generator.py: 1 error de colección por ModuleNotFoundError de src.adapters.chat_export_generator (rojo por módulo ausente, no por sintaxis). Solo se añadió ese archivo de pruebas (27 funciones), src/ intacto, commit empujado, árbol limpio. La API (generate_chat, render_whatsapp, render_telegram, export_plan_chats) la fijó el developer porque el SPEC no la define. (aa33e8c) |
| tests | Kenni Rodriguez | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code (subagente developer, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | Reejecuté pytest -m 'not integration and not acceptance': 748 passed, 3 skipped, 6 xfailed. Se añadió src/adapters/chat_export_generator.py (132 líneas, importa solo src.domain, sin comentarios). Revisé el único cambio a pruebas: la regex de datos reales ignora la línea date_unixtime de Telegram, porque la prueba roja era inconsistente (exigía int() y a la vez prohibía 7+ dígitos); el resto de la comprobación sigue intacto. Commit empujado. (648b23a) |
| implementacion | Kenni Rodriguez | 2026-11-10 |  |
