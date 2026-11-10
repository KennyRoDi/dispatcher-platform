# SPEC F-03: Dataset sintético

**Fase:** plan
**Base:** main
**Verificación IA:** plan 49972ce
**Historia:** US-03 · **Requisitos:** RF-18, RF-19, RF-20, RF-21, RF-22, RNF-04, RNF-05 · **Responsable:** K

## Objetivo

El equipo obtiene un dataset reproducible que cumple el mínimo de [B.3 Dataset mínimo] (40 casos, 10 heterogéneos, 20 000 mensajes, 300 imágenes, 150 audios, 5 casos con archivos ≥ 200 MB) sin datos de terceros sin licencia [B.3 Consideraciones éticas], para probar con volumen el pipeline y las mediciones M1–M5. Los mensajes son siempre sintéticos; imágenes y audios provienen preferentemente de datasets públicos con licencia académica, con fallback sintético. Un validador cuenta el cumplimiento sobre el dataset real; su salida es la evidencia de `docs/dataset.md`.

## Alcance

**Incluye:**
- Plan determinista de casos (dominio puro) por semilla.
- Generador de exportaciones de chat sintéticas estilo WhatsApp y Telegram (20 000 mensajes en total, siempre sintéticos).
- Imágenes (300) y audios (150): construidos desde un directorio de origen con datasets públicos licenciados, con etiquetas de verdad derivadas de las del dataset; fallback sintético (ver «Fuentes de imágenes y audio»).
- Casos pesados (≥ 200 MB) generados en local, en una ruta configurable, no versionados.
- 10 casos heterogéneos: 5 livianos y 5 pesados; los otros 30 casos pueden ser de uno o pocos tipos.
- Manifiesto con origen, licencia y conteos por tipo; validador de mínimos B.3.
- `docs/dataset.md` con procedencia y licencia exactas de cada fuente, qué casos cumplen cada condición, la salida real del validador y cómo los integrantes obtienen los casos pesados.

**No incluye:** comparador y fallo por licencia ausente (F-04); parsers y validación de formatos de ingesta (F-02); subir los casos a la API (F-01); análisis de los archivos (F-07 a F-09). Entrenar modelos [B.1]. Versionar el dataset pesado o los medios. Publicar el dataset en Google Drive: lo hace la persona, fuera del repo.

## Criterios de aceptación

- **Dado** el generador con una semilla y los directorios de origen configurados (o el fallback sintético)
- **Cuando** se ejecuta
- **Entonces** hay ≥ 40 casos, ≥ 10 heterogéneos (5 livianos y 5 pesados), ≥ 20 000 mensajes, ≥ 300 imágenes, ≥ 150 audios y ≥ 5 casos con archivos ≥ 200 MB

Adicionales derivados del enunciado: misma semilla y mismo origen producen el mismo manifiesto (mismos nombres, conteos y hashes de contenido); el manifiesto declara la proporción de contenido positivo por categoría de imagen (RF-20) y duraciones distintas de audio (RF-21); cada fuente de imagen o audio declara procedencia y licencia, y los mensajes tienen origen `sintetico` (RNF-04); cada caso pesado es heterogéneo.

## Fuentes de imágenes y audio

**Criterio de selección.** Una fuente solo se usa si cumple todo:
- Licencia que permite uso académico, documentada con texto y enlace exactos.
- Imágenes: proporción de contenido positivo conocida (etiquetas del dataset), suficiente para 300 imágenes con positivas y negativas.
- Audio: duraciones variadas, suficientes para 150 audios con duraciones distintas.
- Sin datos reales de terceros sin licencia [B.3].
- Disponible sin pago y reproducible: se registra versión o fecha de descarga y, si existe, el hash del archivo comprimido.

**Obtención.** La API de Kaggle está configurada en la máquina de la persona; el CLI puede no estar instalado. La descarga es manual o con el CLI y queda fuera de las pruebas: el generador no usa red. Recibe un directorio de origen por parámetro.

**Etiquetas.** El generador construye los casos desde ese directorio y deriva las etiquetas de verdad (positivo/negativo por imagen, duración por audio) de las del dataset, y las escribe en el manifiesto con la fuente de cada archivo.

**Fallback.** Si ningún dataset cumple el mínimo y la licencia, se usan imágenes y audios sintéticos de `ffmpeg` (patrones y tonos o ruido) con la etiqueta asignada por el generador. Se registra en `docs/dataset.md` qué parte vino de cada origen y por qué. No se nombran datasets concretos en este SPEC; la selección final es pregunta abierta.

## Diseño

**Contratos.** Ninguno de `docs/CONTRATOS.md`: F-03 no tiene dependencias ni toca puertos ni archivos de otro dueño. Solo crea archivos propios de Kenni.

**Capas y archivos (nuevos).**
- Dominio: `src/domain/dataset_plan.py`. Funciones puras: `plan_dataset(seed, params) -> DatasetPlan` (casos, heterogéneos livianos y pesados, conteos de mensajes, imágenes, audios) y `check_minimums(manifest) -> list[str]` (incumplimientos). Sin E/S, sin reloj, sin `random` global: `random.Random(seed)`. `params` por configuración.
- Adaptadores (`src/adapters/`): `chat_export_generator.py` (texto WhatsApp/Telegram, UTF-8, timestamps y remitentes sintéticos), `media_source.py` (lee el directorio de origen, selecciona y etiqueta imágenes y audios, y cae al fallback), `media_generator.py` (medios sintéticos y casos pesados vía `ffmpeg`, ejecutor inyectado).
- Script: `scripts/dataset_sintetico.py`, CLI `--seed`, `--out`, `--origen-imagenes`, `--origen-audio`, `--params`, `--validar`. Escribe fuera del repo.
- Documento: `docs/dataset.md`.

**Decisiones.**
- **AD-25 aprobada por la persona:** generador nuevo y determinista en vez de ampliar `scripts/build_dataset.py`, que solo cubre video y audio, no tiene texto ni imágenes y su manifiesto trae `generated_at` (no reproducible). Alternativa: extender el heredado. Criterio: RF-18 a RF-22 exigen texto e imágenes y reproducibilidad. El arquitecto no toca `docs/ARQUITECTURA.md` en esta fase: registrar AD-25 en §8 es tarea de la fase documentación (parte 6).
- Ruta de salida: parámetro `--out`, sin valor por defecto bajo `/scratch` (no existe en la máquina de desarrollo). Ejemplo: `~/scratch/dataset`. Debe ser disco, no `tmpfs`, que cuenta en el cgroup (`docs/ARQUITECTURA.md` §4). `dataset/media/` ya está en `.gitignore`. Solo se versionan el manifiesto y `docs/dataset.md`.
- Distribución: el repo es público, así que los casos pesados no se versionan. Se generan en local; la persona los sube a Google Drive y los demás integrantes los descargan y los usan en local. El enlace, el procedimiento y la verificación por `sha256` del manifiesto se documentan en `docs/dataset.md`, sin llaves ni credenciales en el repo.
- Mensajes de chat: siempre sintéticos. Plantillas con vocabulario neutro y un subconjunto con frases de amenaza ficticias para F-07, aprobadas por la persona; sin personas ni datos reales. Si una IA redacta plantillas, se declara en `docs/BITACORA_IA.md`.
- Imágenes y audios: de datasets públicos licenciados según «Fuentes de imágenes y audio»; fallback sintético con `ffmpeg` (`lavfi`), reutilizando las constantes `AUDIO_*` de `scripts/build_dataset.py`.
- Heterogéneos (opción A): 10 casos, 5 livianos (texto, imagen, audio y documento) y 5 pesados (≥ 200 MB; texto, imagen, audio y video o documento). Los 5 pesados son parte de los 10 y de los ≥ 5 pesados de B.3. Los otros 30 casos pueden ser de uno o pocos tipos.
- Casos pesados: el archivo grande es video sintético con bitrate fijo hasta superar 200 MiB (o documento grande); el generador falla si el archivo queda por debajo. El resto de sus archivos (texto, imagen, audio) sale de las mismas fuentes.
- Manifiesto (`manifest.json`) con campos `case`, `kind` (`texto|imagen|audio|video|documento`), `path`, `bytes`, `sha256`, `origen` (`sintetico` o la fuente pública), `licencia`, `semilla`, `etiqueta` (cuando el dataset la aporta) y `heterogeneo` (`liviano|pesado|no`). Sin marca de tiempo. F-04 lo extiende; no se renombran campos.

**Reutiliza del I Proyecto:** `ffmpeg_args` y constantes de duración de `scripts/build_dataset.py`, sin copiar historial. Se copia solo lo necesario, con cita en comentario.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_generador_cumple_minimos_de_b3` | `plan_dataset` con una semilla y parámetros por defecto cumple todos los mínimos de B.3 |
| Unitaria | `test_plan_tiene_cinco_heterogeneos_livianos_y_cinco_pesados` | 10 heterogéneos; los 5 pesados incluyen texto, imagen, audio y video o documento |
| Unitaria | `test_misma_semilla_produce_el_mismo_plan` | Determinismo; semillas distintas dan planes distintos |
| Unitaria | `test_plan_bajo_el_minimo_se_reporta` | `check_minimums` nombra cada mínimo incumplido |
| Unitaria | `test_exportacion_whatsapp_se_parsea_con_timestamp_y_remitente` | Formato realista, UTF-8, con el parser existente o su doble |
| Unitaria | `test_origen_sin_licencia_documentada_se_rechaza` | La fuente de imagen o audio sin procedencia y licencia no entra al manifiesto |
| Unitaria | `test_etiquetas_del_dataset_pasan_al_manifiesto` | Con un directorio de origen falso en `tmp_path`: positivos y negativos se derivan de las etiquetas dadas |
| Unitaria | `test_origen_insuficiente_cae_al_fallback_sintetico` | Con menos de 300 imágenes o 150 audios, completa con sintéticos y lo registra |
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
| 3 | `feat(F-03): leer imagenes y audio de datasets publicos` | `src/adapters/media_source.py`: directorio de origen, selección, etiquetas, licencia y procedencia, ~150 líneas |
| 4 | `feat(F-03): generar medios sinteticos de fallback y casos pesados` | `src/adapters/media_generator.py` con ejecutor de `ffmpeg` inyectado: fallback y archivos ≥ 200 MiB, ~150 líneas |
| 5 | `feat(F-03): componer casos heterogeneos y manifiesto con CLI` | `scripts/dataset_sintetico.py`: arma los 10 heterogéneos, manifiesto, `--validar`, ~150 líneas |
| 6 | `docs(F-03): registrar procedencia, distribucion y salida del validador` | `docs/dataset.md` (fuentes con licencia, casos por condición, enlace de Drive, salida real del validador) y AD-25 en `docs/ARQUITECTURA.md` §8. Sin código; va al final porque necesita el dataset generado |

## Riesgos y preguntas abiertas

**Riesgos.**
- Disco: ≥ 5 archivos ≥ 200 MiB más medios necesitan espacio libre en la ruta de `--out`; `/scratch` no existe en la máquina de desarrollo, la ruta es parámetro.
- Generar 5 videos de 200 MiB con `ffmpeg` puede tardar; el tiempo real solo se conocerá al ejecutarlo. No se estima aquí.
- La reproducibilidad de bytes de `ffmpeg` puede variar entre versiones; se garantiza el plan y el manifiesto planeado, no necesariamente el `sha256` entre versiones de `ffmpeg`. Los medios públicos se fijan por versión o hash de la descarga.
- Licencia: un dataset con licencia ambigua o no académica incumple [B.3]; se descarta y se usa el fallback. Imágenes con contenido sensible o personas reales exigen revisar la licencia y la política de la fuente antes de usarlas.
- Distribución: el enlace de Google Drive depende de la persona y queda fuera del repo; si no se sube, los demás integrantes deben regenerar los casos en local. Los enlaces con acceso público no deben ir en el repo si la política de la fuente lo prohíbe.
- Los datasets públicos pueden no alcanzar la proporción positiva o las duraciones requeridas; el fallback cubre el faltante y lo declara.
- El CLI de Kaggle puede no estar instalado; la descarga es un paso manual documentado, no parte de las pruebas.

**Preguntas abiertas.**
1. Selección final de datasets de imágenes y de audio (nombre, versión, licencia, proporción positiva, duraciones). Una investigación de candidatos corre en paralelo y alimentará esta respuesta.
2. Si la licencia de la fuente elegida permite redistribuir los archivos en Google Drive entre los integrantes del equipo, o solo descargarlos de la fuente original.
3. Formato y ubicación del documento grande de los casos pesados cuando no se use video (documento ≥ 200 MB): tipo de archivo, a definir en la fase de tests.

**Resueltas por la persona (2026-11-10).** AD-25 aprobada; mensajes siempre sintéticos y frases de amenaza ficticias aprobadas; dataset pesado en local y distribuido por Google Drive fuera del repo; imágenes y audios de datasets públicos con fallback sintético (supera la pregunta de imágenes sintéticas con etiqueta del generador); opción A para heterogéneos (5 livianos y 5 pesados, los pesados incluidos).


## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose) | 2026-11-05 | Leí SPEC completo: sin campos pendientes (grep), commit 78301a4 pusheado, árbol limpio, solo toca SPEC. Contrasté con ENUNCIADO B.3 (mínimos y ética), REQUERIMIENTOS RF-18..22/RNF-04/05, build_dataset.py (ffmpeg_args:203, AUDIO_*), .gitignore dataset/media/, ARQUITECTURA §8 (último AD-24, AD-25 libre). No ejecuté pruebas (fase sin código). No verificado: parser WhatsApp existente (no hallé uno en src), espacio/ffmpeg en /scratch. (78301a4) |
| verificación IA de plan | Claude Code (orquestador, Sonnet 5.5) | 2026-11-10 | Releido el SPEC: sin campos pendientes (grep), cubre mínimos de B.3 y ética RNF-04/05, árbol limpio, commit empujado. Sin código ni pruebas en esta fase. (34573a4) |
| plan | Kenni Rodriguez | 2026-11-10 |  |
| devuelta de tests | Kenni Rodriguez | 2026-11-10 | Incorporar: imágenes y audio de datasets públicos licenciados (Kaggle) con fallback sintético; chats sintéticos; casos pesados en local/Drive; opción A: 10 heterogéneos, 5 livianos y 5 pesados solapados |
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose; orquestador Sonnet 5.5) | 2026-11-10 | SPEC releído tras la devolución: sin campos pendientes (grep), solo toca SPEC, commit empujado, árbol limpio. Recoge opción A (10 heterogéneos: 5 livianos y 5 pesados), chats sintéticos, imágenes y audio públicos con fallback sintético, pesados en local y Drive, pila de 6 PR. Sin código ni pruebas en esta fase. (49972ce) |
