# SPEC F-03: Dataset sintético

**Fase:** plan
**Base:** main
**Verificación IA:** plan 34573a4
**Historia:** US-03 · **Requisitos:** RF-18, RF-19, RF-20, RF-21, RF-22, RNF-04, RNF-05 · **Responsable:** K

## Objetivo

El equipo obtiene un dataset reproducible por semilla que cumple el mínimo de [B.3 Dataset mínimo] (40 casos, 10 heterogéneos, 20 000 mensajes, 300 imágenes, 150 audios, 5 casos con archivos ≥ 200 MB) sin datos de terceros [B.3 Consideraciones éticas], para probar con volumen el pipeline y las mediciones M1–M5. Un validador cuenta el cumplimiento sobre el dataset real; su salida es la evidencia de `docs/dataset.md`.

## Alcance

**Incluye:** plan determinista de casos (dominio puro); generador de exportaciones de chat sintéticas estilo WhatsApp y Telegram; generación de imágenes y audios sintéticos; casos pesados ≥ 200 MB; manifiesto con origen (`sintetico`), licencia propia y conteos por tipo; validador de mínimos B.3; `docs/dataset.md` con procedencia, licencia y la salida real del validador.

**No incluye:** etiquetas de verdad de referencia, comparador y fallo por licencia ausente (F-04); parsers y validación de formatos de ingesta (F-02); subir los casos a la API (F-01); análisis de los archivos (F-07 a F-09). Entrenar modelos [B.1]. Versionar el dataset pesado.

## Criterios de aceptación

- **Dado** el generador con una semilla
- **Cuando** se ejecuta
- **Entonces** hay ≥ 40 casos, ≥ 10 heterogéneos, ≥ 20 000 mensajes, ≥ 300 imágenes, ≥ 150 audios y ≥ 5 casos con archivos ≥ 200 MB

Adicionales derivados del enunciado: misma semilla produce el mismo manifiesto (mismos nombres, conteos y hashes de contenido); el manifiesto declara la proporción de contenido positivo por categoría de imagen (RF-20) y duraciones distintas de audio (RF-21); ninguna fuente tiene origen distinto de `sintetico` (RNF-04).

## Diseño

**Contratos.** Ninguno de `docs/CONTRATOS.md`: F-03 no tiene dependencias ni toca puertos ni archivos de otro dueño. Solo crea archivos propios de Kenni.

**Capas y archivos (nuevos).**
- Dominio: `src/domain/dataset_plan.py`. Funciones puras: `plan_dataset(seed, params) -> DatasetPlan` (casos, heterogéneos, conteos de mensajes, imágenes, audios y pesados) y `check_minimums(manifest) -> list[str]` (incumplimientos). Sin E/S, sin reloj, sin `random` global: `random.Random(seed)`. `params` por configuración (el refactor de IMPLEMENTACION §4).
- Adaptadores (`src/adapters/`): `chat_export_generator.py` (texto WhatsApp/Telegram, UTF-8, timestamps y remitentes sintéticos), `media_generator.py` (imágenes y audios vía `ffmpeg`, ejecutor inyectado).
- Script: `scripts/dataset_sintetico.py`, CLI `--seed`, `--out`, `--params`, `--validar`. Escribe el dataset fuera del repo.
- Documento: `docs/dataset.md`.

**Decisiones.**
- Salida por defecto en `/scratch/dataset` (volumen en disco, no `tmpfs`, que cuenta en el cgroup, `docs/ARQUITECTURA.md` §4). `dataset/media/` ya está en `.gitignore`; el dataset pesado no se versiona. Solo se versionan el manifiesto y `docs/dataset.md`.
- Nueva decisión a registrar en §8 (**AD-25**, propuesta): generador nuevo y determinista en vez de ampliar `scripts/build_dataset.py`, que solo cubre video y audio, no tiene texto ni imágenes y su manifiesto trae `generated_at` (no reproducible). Alternativa: extender el heredado. Criterio: RF-18 a RF-22 exigen texto e imágenes y reproducibilidad por semilla.
- Imágenes: patrones sintéticos generados con `ffmpeg` (`lavfi`), sin dependencias nuevas; la «proporción de contenido positivo» es una etiqueta asignada por el generador (categorías y proporción por parámetro), no contenido real violento. Las etiquetas formales las toma F-04 del manifiesto.
- Audios: tonos y ruido de `ffmpeg` con duraciones distintas, reutilizando las constantes `AUDIO_*` de `scripts/build_dataset.py`. Mensajes de chat: plantillas con vocabulario neutro y un subconjunto con frases de amenaza ficticias para uso posterior en F-07; sin personas ni datos reales.
- Casos pesados: video sintético generado con bitrate fijo hasta superar 200 MiB; el generador falla si el archivo queda por debajo.
- Manifiesto (`manifest.json`) con campos `case`, `kind` (`texto|imagen|audio|video|documento`), `path`, `bytes`, `sha256`, `origen`, `licencia`, `semilla`. Sin marca de tiempo. F-04 lo extiende; no se renombran campos.

**Reutiliza del I Proyecto:** `ffmpeg_args` y constantes de duración de `scripts/build_dataset.py`, sin copiar historial. Se copia solo lo necesario, con cita en comentario.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_generador_cumple_minimos_de_b3` | `plan_dataset` con una semilla y parámetros por defecto cumple todos los mínimos de B.3 |
| Unitaria | `test_misma_semilla_produce_el_mismo_plan` | Determinismo; semillas distintas dan planes distintos |
| Unitaria | `test_plan_bajo_el_minimo_se_reporta` | `check_minimums` nombra cada mínimo incumplido |
| Unitaria | `test_exportacion_whatsapp_se_parsea_con_timestamp_y_remitente` | Formato realista, UTF-8, con el parser existente o su doble |
| Unitaria | `test_caso_pesado_falla_si_no_alcanza_200_mib` | Con ejecutor falso; sin `ffmpeg` real ni red |
| Integración | `test_generacion_reducida_escribe_manifiesto` | Parámetros reducidos con `ffmpeg` real en `tmp_path`: archivos y manifiesto coherentes |
| Aceptación | `test_validador_sobre_dataset_completo` | Marcada `acceptance`: el validador sobre `/scratch/dataset` cumple B.3; su salida va a `docs/dataset.md` |

## Mediciones

No aplica. F-03 no mide el SO. El dataset alimenta M3 (RNF-11, tasa de deduplicación) y los casos ≥ 200 MB alimentan F-33 a F-37, que miden aparte.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-03): planear el dataset y validar los minimos de B.3` | `src/domain/dataset_plan.py`: `plan_dataset`, `check_minimums` y parámetros. Dominio puro, ~120 líneas |
| 2 | `feat(F-03): generar exportaciones de chat sinteticas` | `src/adapters/chat_export_generator.py`, WhatsApp y Telegram, ~120 líneas |
| 3 | `feat(F-03): generar imagenes y audios sinteticos` | `src/adapters/media_generator.py` con ejecutor de `ffmpeg` inyectado, ~150 líneas |
| 4 | `feat(F-03): generar casos pesados y manifiesto con CLI` | `scripts/dataset_sintetico.py`: casos ≥ 200 MiB, manifiesto, `--validar`, ~150 líneas |
| 5 | `docs(F-03): registrar procedencia y salida del validador` | `docs/dataset.md` con la salida real del validador y AD-25 en `docs/ARQUITECTURA.md` §8. Sin código; va al final porque necesita el dataset generado |

## Riesgos y preguntas abiertas

**Riesgos.**
- Disco: ≥ 5 archivos ≥ 200 MiB más 450 medios necesitan espacio libre en `/scratch`. No existe `/scratch` en la máquina de desarrollo actual; hay que crearlo o elegir otra ruta.
- Generar 5 videos de 200 MiB con `ffmpeg` puede tardar; el tiempo real solo se conocerá al ejecutarlo. No se estima aquí.
- La reproducibilidad de bytes de `ffmpeg` puede variar entre versiones; se garantiza el plan y el manifiesto planeado, no necesariamente el `sha256` entre versiones de `ffmpeg`.

**Preguntas abiertas.**
1. ¿Se aprueba AD-25 (generador nuevo en vez de ampliar `scripts/build_dataset.py`)?
2. ¿Dónde vive el dataset generado: `/scratch/dataset` (propuesto) o publicado en un almacén para que los otros tres integrantes lo obtengan? Si el repo es público, el dataset pesado no puede ir en él. Probable SUP-XX.
3. ¿La «proporción conocida de contenido positivo» puede ser una etiqueta del generador sobre imágenes sintéticas (propuesto), o el equipo exige imágenes públicas con licencia? Con imágenes sintéticas, F-08 mide detección sobre patrones, no sobre fotos; limita lo que demuestra.
4. ¿Ranura exacta de heterogéneos y pesados: los 5 pesados cuentan como parte de los 10 heterogéneos (propuesto, texto+video) o son aparte?
5. ¿Se usan frases de amenaza ficticias en el chat para F-07? Si se usa IA para redactar plantillas, se declara en la bitácora.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (subagente arquitecto, general-purpose) | 2026-11-05 | Leí SPEC completo: sin campos pendientes (grep), commit 78301a4 pusheado, árbol limpio, solo toca SPEC. Contrasté con ENUNCIADO B.3 (mínimos y ética), REQUERIMIENTOS RF-18..22/RNF-04/05, build_dataset.py (ffmpeg_args:203, AUDIO_*), .gitignore dataset/media/, ARQUITECTURA §8 (último AD-24, AD-25 libre). No ejecuté pruebas (fase sin código). No verificado: parser WhatsApp existente (no hallé uno en src), espacio/ffmpeg en /scratch. (78301a4) |
| verificación IA de plan | Claude Code (orquestador, Sonnet 5.5) | 2026-11-10 | Releido el SPEC: sin campos pendientes (grep), cubre mínimos de B.3 y ética RNF-04/05, árbol limpio, commit empujado. Sin código ni pruebas en esta fase. (34573a4) |
| plan | Kenni Rodriguez | 2026-11-10 |  |
| devuelta de tests | Kenni Rodriguez | 2026-11-10 | Incorporar: imágenes y audio de datasets públicos licenciados (Kaggle) con fallback sintético; chats sintéticos; casos pesados en local/Drive; opción A: 10 heterogéneos, 5 livianos y 5 pesados solapados |
