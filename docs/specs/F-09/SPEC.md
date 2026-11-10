# SPEC F-09: Worker de audio

**Fase:** verificacion
**Base:** feat/F-09-1-worker-de-audio
**Verificación IA:** verificacion d0c3846
**Historia:** US-09 · **Requisitos:** RF-08, RNF-25; RF-06 (análisis reutilizado); RF-14 (segmento de audio con timestamp); RNF-04, RNF-05; SUP-07, SUP-11, SUP-15; [B.4 Workers de análisis], [B.4 Reporte consolidado], [B.1], [B.3], [B.7 Audio] · **Responsable:** J

## Objetivo

El analista necesita tratar las notas de voz de un caso como texto: leer lo que se dijo, saber en qué segundo se dijo y que pase por el mismo análisis que los mensajes. [B.4 Workers de análisis] exige un worker de audio con «speech-to-text y análisis del texto transcrito», [B.4 Reporte consolidado] pide fragmentos de evidencia como «segmento de audio con timestamp» (RF-14) y [B.1] exige modelos ya entrenados (RNF-25). Hoy el repositorio analiza texto (F-07) e imágenes (F-08), pero no audio: `src/workers/multimedia_processor.py` solo ejecuta FFmpeg. F-09 entrega el analizador de audio que implementa el puerto `Analyzer`: transcribe la nota con faster-whisper preentrenado (AD-19), emite un hallazgo `transcripcion` por segmento con su texto y sus timestamps, y pasa los segmentos por el análisis de texto de F-07 sin duplicarlo, de modo que una amenaza dicha en voz produce severidad alta (SUP-07). El audio que F-05 extrae de los videos llega al mismo analizador (SUP-11). Sus hallazgos los consumen el reporte (F-11) y las alertas (F-14), y el transcriptor es la carga que miden M1 (F-17, F-19) y M5 (F-31).

## Alcance

**Incluye:**

- Lógica pura de dominio: `TranscriptSegment` (inicio y fin en segundos, texto, confianza) y la conversión de segmentos en `ChatMessage` para reutilizar el análisis de texto.
- Caso de uso de aplicación `analyze_audio` que compone un puerto interno de transcripción, `Transcriber`, con `analyze_conversation` de F-07.
- Refactor mínimo de `analyze_conversation` para que la posición de la evidencia se exprese en segmentos con timestamps en vez de índices de mensaje, sin cambiar la salida del texto.
- Adaptador `AudioAnalyzer` que implementa `Analyzer` (`analyze(path) -> list[Finding]`), calcula el SHA-256 de la nota y reutiliza los ajustes de `config/texto.toml`.
- Adaptador de transcripción real con faster-whisper, modelo `base` preentrenado, solo inferencia en CPU e importación diferida, configurado en `config/audio.toml`.
- Prueba de aceptación que compara la transcripción con la esperada sobre una muestra pequeña de notas de voz sintéticas o públicas con licencia [B.3], con su evidencia medida.

**No incluye:**

- Extraer el audio de un video: F-05 (SUP-11). F-09 recibe un archivo de audio.
- Descomposición del caso y routing a la cola de audio: F-05 y F-32.
- Bucle del worker, subproceso por sub-tarea y cancelación: F-12 (AD-08).
- Guardar hallazgos (F-13), reporte (F-11) y alertas (F-14).
- Las 150 notas de voz del dataset y su manifiesto: F-03 y F-04. La muestra de la prueba A es otra, pequeña y de F-09.
- Contenedor del worker, `mem_limit`, huella del modelo y estrategias de carga: F-16, F-17 y F-19. Benchmark CPU frente a GPU o int8 frente a float32: F-31.
- Validar formatos en la ingesta: F-02. Aquí solo se rechaza el archivo que el decodificador no puede abrir.
- Entrenar o ajustar modelos [B.1], RNF-25. Diarización (quién habla), detección de idioma múltiple y traducción.

## Criterios de aceptación

Copiados de `docs/backlog/cola-workers.md`, US-09:

- **Dado** una nota de voz con transcripción conocida
- **Cuando** se procesa
- **Entonces** se obtiene la transcripción con timestamps y el análisis de US-07

- **Pruebas:** U composición. I con modelo real. A comparación con la transcripción esperada.
- **Demuestra:** prueba A. **Evidencia:** muestra en el informe.

Criterios adicionales derivados de los requisitos:

- RF-08: una nota con voz produce un `Finding` `transcripcion` por segmento no vacío, en orden, con su texto en `detail` y sus timestamps en la posición, y además los hallazgos de RF-06 (`palabras_clave`, `tema`, `sentimiento` y uno de `amenaza`, `ofensivo` o `sin_ofensa`) calculados sobre el texto transcrito.
- RF-14: cada `Finding` lleva `EvidenceRef` con el SHA-256 de la nota y una posición con segmentos y timestamps, por ejemplo `segmento 2 t=4.20-7.85s`; ninguna posición de audio usa índices de mensaje.
- SUP-07: un segmento que contiene una amenaza explícita produce un `Finding` `amenaza` de severidad `alta`, con las reglas de `config/texto.toml`, igual que en texto.
- RNF-25: el repositorio no contiene código de entrenamiento; solo se cargan pesos publicados, con revisión fijada.
- [B.3], RNF-04 y RNF-05: cada nota de la muestra declara procedencia y licencia; ninguna es voz de terceros sin licencia.
- El análisis de texto de F-07 no cambia: sus pruebas existentes siguen en verde sin modificarse.

## Diseño

### Contratos

| Contrato | Rol de F-09 | Fuente |
|---|---|---|
| `Analyzer.analyze(path) -> list[Finding]` | Lo implementa `AudioAnalyzer` | `src/application/ports.py:18` |
| `Finding`, `EvidenceRef`, `Severity` | Los produce | `src/domain/finding.py` |
| `ChatMessage` | Lo produce internamente a partir de segmentos, sin usar `ConversationParser` | `src/domain/chat_message.py` |
| `analyze_conversation`, `TextModels`, `TextSettings` | Los reutiliza | `src/application/analyze_text.py`, F-07 |
| `SeverityRules` | Lo reutiliza a través de `TextSettings` | `src/domain/severity.py`, F-07 |
| `sha256_de_archivo` | Lo reutiliza | `src/adapters/hashing.py`, F-08 |
| `comprobar_analyzer` | Lo usa en sus pruebas | `tests/contratos.py` |

No se modifica ningún contrato compartido. Todo lo reutilizado es del mismo responsable.

### Flujo

```
AudioAnalyzer.analyze(path)
  sha = sha256_de_archivo(path)
  segmentos = transcriber.transcribe(path)          # list[TranscriptSegment]
  analyze_audio(segmentos, sha, models, ajustes_texto)
    descarta segmentos de texto vacío
    1 Finding "transcripcion" por segmento: texto, confianza, "segmento i t=a-bs"
    mensajes = segmentos_como_mensajes(segmentos)    # ChatMessage por segmento
    analyze_conversation(mensajes, sha, models, ajustes_texto, posiciones=SegmentPositions)
```

Una nota sin voz, o cuyos segmentos quedan vacíos, devuelve una lista vacía (pregunta 4).

### Capas y archivos

Todos son de José Andrés (`docs/CONTRATOS.md`: `src/adapters/*_analyzer.py`, `analyze_text.py`, `config/texto.toml`), salvo los compartidos señalados.

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/transcription.py` | `TranscriptSegment(inicio, fin, texto, confianza)` con validación: `0 <= inicio <= fin`, confianza en [0, 1], texto recortado; `segmentos_como_mensajes(segmentos) -> list[ChatMessage]` con `sender = "audio"` y `source_ref = "t=4.20-7.85s"` |
| Aplicación | `src/application/analyze_text.py` | Refactor: `analyze_conversation(..., posiciones=MessagePositions())`. `PositionFormat` agrupa las tres funciones de formato que hoy son privadas (`_rango`, `_lista`, `_detalle`); la implementación por defecto produce exactamente la salida actual |
| Aplicación | `src/application/analyze_audio.py` | Puerto interno `Transcriber.transcribe(path) -> list[TranscriptSegment]`, `SegmentPositions` (posiciones con índice de segmento y timestamps) y caso de uso `analyze_audio` |
| Adaptador | `src/adapters/audio_analyzer.py` | `AudioAnalyzer(transcriber, models, ajustes_texto)` con `from_config(transcriber, models, ruta_texto)`: implementa `Analyzer` y calcula el SHA-256 |
| Adaptador | `src/adapters/text_analyzer.py` | Refactor: extraer `cargar_ajustes_de_texto(ruta) -> TextSettings` de `TextAnalyzer.from_config`, para que el audio lea `config/texto.toml` sin duplicar la carga |
| Adaptador | `src/adapters/whisper_transcriber.py` | `Transcriber` real con faster-whisper: carga el modelo una vez por proceso, transcribe en CPU con idioma fijo, convierte cada segmento a `TranscriptSegment` con tipos nativos y confianza `exp(avg_logprob)` acotada a [0, 1]. Importación diferida. Un archivo que no se puede decodificar se rechaza con `ValueError` |
| Configuración | `config/audio.toml` | Modelo (`base`), revisión fijada de los pesos, idioma (`es`), `compute_type` (`int8`), `beam_size` y hilos de CPU |
| Dependencias | `requirements-audio.txt` | `faster-whisper` con versión fija; incluye `-r requirements-texto.txt` porque el audio también usa los modelos de texto. Separado de `requirements.txt` para que CI no lo instale |

`Transcriber` no va en `src/application/ports.py`: es una costura interna de F-09, como `TextModels` y `ObjectDetector`. `ChatMessage.timestamp_utc` exige zona horaria; los mensajes de audio usan `1970-01-01T00:00:00Z` más el inicio del segmento, porque el analizador solo recibe la ruta y no conoce la hora de la nota. Con `SegmentPositions` ese instante no aparece en ningún hallazgo (pregunta 5).

### Los hallazgos de audio

| `category` | `detail` | `confidence` | `severity` | `evidence.position` |
|---|---|---|---|---|
| `transcripcion` | Texto del segmento | `exp(avg_logprob)` del segmento, acotada a [0, 1] | `baja`, sin regla | `segmento 2 t=4.20-7.85s` |
| `palabras_clave`, `tema`, `sentimiento`, `sin_ofensa` | Los de F-07 | Los de F-07 | Por `config/texto.toml` | Rango de segmentos del lote: `segmentos 0-5 t=0.00-21.30s` |
| `amenaza`, `ofensivo` | Segmentos marcados con su tiempo: `2 t=4.20-7.85s` | Los de F-07 | `amenaza` → `alta` (SUP-07) | Segmentos marcados: `segmentos 2,4 t=4.20-7.85s,12.00-15.10s` |

Los timestamps son segundos desde el inicio del audio, con dos decimales. Ejemplo de forma de `config/audio.toml`, con valores provisionales (SUP-17):

```toml
[modelo]
nombre = "base"
revision = "se fija en la parte 2 con el commit del repositorio de pesos"
idioma = "es"
compute_type = "int8"
beam_size = 5
hilos = 0
```

Un idioma vacío, un `compute_type` desconocido o un `beam_size` menor que 1 hacen fallar la carga con `ValueError`.

### Decisiones

Aplica AD-19 (faster-whisper), AD-26 (análisis de texto de F-07), AD-11 (SHA-256 del contenido en claro), AD-22 (Python 3.13 en imágenes de workers ML), SUP-07, SUP-11 y SUP-15. Reutiliza de F-07 `analyze_conversation`, `TextModels`, `TextSettings` y las reglas; de F-08, `sha256_de_archivo`.

Se propone, provisional, registrada en `docs/ARQUITECTURA.md` §8:

| ID | Decisión | Alternativas | Criterio |
|---|---|---|---|
| AD-28 | Transcripción con faster-whisper `base` preentrenado, CPU e `int8`, idioma `es` fijo; un hallazgo `transcripcion` por segmento; los segmentos pasan como mensajes por el análisis de texto de F-07, con posiciones de segmento y timestamp | Vosk; whisper de OpenAI sobre torch; modelo `tiny` o `small`; analizar la transcripción completa como un solo mensaje | faster-whisper es el que fija AD-19 y [B.7 Audio] sugiere; usa CTranslate2 sin torch y menos memoria que whisper original (AD-06, F-17); `int8` es la variante que compara M5; `base` coincide con el comando de F-31. Segmentos como mensajes reutilizan F-07 sin duplicarlo y dan el timestamp que pide RF-14. faster-whisper (SYSTRAN) y los pesos de Whisper (OpenAI) usan licencia MIT; se citan (Parte I §9). **Medición pendiente:** comparación de transcripción de F-09 (parte 3) y huella de F-17 |

### Código del I Proyecto

No se reutiliza código de `src/workers/`: `multimedia_processor.py` solo ejecuta FFmpeg y `worker_node.py` no consume `Subtask` (lo reemplaza F-12). faster-whisper decodifica con PyAV, así que no necesita llamar a FFmpeg. Se reutiliza código de F-07 y F-08, del mismo responsable, como se indica arriba.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_audio_analyzer.py::test_transcripcion_pasa_por_analisis_de_texto`: un `Transcriber` falso devuelve dos segmentos, uno con una amenaza, y un `TextModels` falso de F-07 la marca, sobre un archivo temporal | Prueba roja de `docs/IMPLEMENTACION.md` §4: dos `transcripcion` con texto y timestamps, los hallazgos de RF-06 y una `amenaza` de severidad `alta` con posición `segmentos 1 t=...`, todos con el SHA-256 del archivo |
| Unitaria | `tests/unit/test_audio_analyzer.py`: sin segmentos, segmentos de texto vacío, más segmentos que el tamaño de lote, orden de los segmentos, conformidad con `comprobar_analyzer`, `from_config` con `config/texto.toml` en `tmp_path` | Lista vacía sin voz; un hallazgo por segmento; lotes y posiciones de segmentos correctos |
| Unitaria | `tests/unit/test_transcription.py`: `TranscriptSegment` rechaza tiempos negativos, `fin < inicio` y confianza fuera de [0, 1]; `segmentos_como_mensajes` puro | Lógica de dominio determinista, sin modelo |
| Unitaria | `tests/unit/test_text_analyzer.py`, existente: sin cambios | El refactor de posiciones no cambia la salida del texto |
| Unitaria | `tests/unit/test_arquitectura.py`, existente | Se propone agregar `faster_whisper`, `ctranslate2` y `av` a `TERCEROS_PROHIBIDOS` |
| Unitaria | `tests/unit/test_whisper_config.py`: carga de `config/audio.toml` válido e inválido en `tmp_path`, sin importar faster-whisper | Configuración validada al cargar |
| Integración | `tests/integration/test_whisper_transcriber_real.py`, marcador `integration`, con `pytest.importorskip("faster_whisper")`: `WhisperTranscriber` sobre una nota de la muestra y sobre un archivo que no es audio | El adaptador real devuelve segmentos ordenados, con tiempos dentro de la duración y texto no vacío, y rechaza el archivo inválido con `ValueError`. Requiere los pesos ya descargados |
| Aceptación | `tests/acceptance/test_audio_transcripcion.py`, marcador `acceptance`, y `scripts/comparar_transcripcion.py`: `AudioAnalyzer` real, con faster-whisper y los modelos reales de F-07, sobre la muestra | Por nota: transcripción obtenida frente a esperada, tasa de error por palabra (WER) tras normalizar mayúsculas, tildes y puntuación, timestamps por segmento y hallazgos de RF-06; la nota con amenaza produce `amenaza` `alta`. El WER se registra tal como salga, sin umbral inventado |

Las unitarias no usan red, `sleep`, reloj real ni modelos. El transcriptor falso se define en la propia prueba; el `TextModels` falso se reutiliza del de `tests/unit/test_text_analyzer.py` o se mueve a `tests/dobles.py` si lo usan dos archivos.

### Muestra con transcripción conocida

`tests/datos/audio/` con unas 5 notas de voz cortas (de 5 a 30 s) en `.ogg` Opus, como las de mensajería, y `tests/datos/audio/transcripciones.json` con, por nota, el texto esperado, la procedencia y la licencia [B.3]. Al menos una contiene una amenaza explícita sintética y otra es neutra. La propuesta es que José Andrés grabe su propia voz leyendo guiones sintéticos escritos por el equipo, sin datos de terceros (pregunta 3).

### Evidencia, a cargo de la persona

Destino: `docs/evidencia/F-09_transcripcion_<fecha>.md`, con el comando exacto, la versión de faster-whisper y CTranslate2, el modelo y su revisión, `compute_type`, idioma, la procedencia de la muestra y, por nota, la transcripción esperada, la obtenida con sus timestamps, el WER y los hallazgos de RF-06. Esa tabla es la «muestra en el informe» del backlog. Ningún valor se escribe de antemano.

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-audio.txt
pytest -m integration tests/integration/test_whisper_transcriber_real.py
python -m scripts.comparar_transcripcion --muestra tests/datos/audio --esperadas tests/datos/audio/transcripciones.json --salida docs/evidencia/F-09_transcripcion_<fecha>.md
pytest -m acceptance tests/acceptance/test_audio_transcripcion.py
```

La parte 2 fijó `faster-whisper==1.2.1` en `requirements-audio.txt`, que incluye `requirements-texto.txt` con `torch==2.15.0` CPU de F-07, y la revisión `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` de `Systran/faster-whisper-base` en `config/audio.toml`. Los pesos se descargan a la caché de Hugging Face en la primera carga; la prueba de integración toma la nota de `F09_NOTA` y se salta si faster-whisper no está instalado.

## Mediciones

No aplica. F-09 no es M1–M5 ni un escenario de B.6. La huella de memoria de faster-whisper es de F-17 (ficha M1), la comparación de estrategias de carga de F-19 (ficha M1) y la latencia por configuración de cómputo de F-31 (ficha M5). La comparación de transcripción es evidencia funcional de US-09, no una medición de SO.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimaciones por comprobar al implementar.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-09): analizar transcripciones como texto con timestamps` | `src/domain/transcription.py`, `src/application/analyze_audio.py`, `src/adapters/audio_analyzer.py`, refactor de posiciones en `src/application/analyze_text.py` y de `cargar_ajustes_de_texto` en `src/adapters/text_analyzer.py`, y pruebas unitarias con transcriptor y modelos falsos. Unas 150 líneas fuera de `tests/` y `docs/`. Base `main`. **No cierra la feature** |
| 2 | `feat(F-09): transcribir con faster-whisper` | `src/adapters/whisper_transcriber.py`, `config/audio.toml`, `requirements-audio.txt`, cita de faster-whisper y Whisper con su licencia MIT en el código y la documentación, prueba de integración. Unas 100 líneas |
| 3 | `test(F-09): comparar transcripción con la esperada` | `scripts/comparar_transcripcion.py` con el WER, prueba de aceptación, muestra con `transcripciones.json` y evidencia `docs/evidencia/F-09_transcripcion_<fecha>.md`. Unas 110 líneas sin contar los audios. Cierra con `cierre --final` |

## Riesgos y preguntas abiertas

**Decisiones pendientes de aprobación, para José Andrés:**

1. **Modelo.** Se recomienda faster-whisper `base`, que coincide con el comando de F-31. Alternativas: `tiny`, más rápido y con más errores; `small`, más preciso y con más memoria; la huella real la mide F-17. Decisión pendiente de aprobación.
2. **Granularidad.** Se recomienda un hallazgo `transcripcion` por segmento de Whisper y que cada segmento sea un «mensaje» para el análisis de F-07, porque da el timestamp de RF-14. Alternativa: timestamps por palabra (`word_timestamps=True`), más finos y más lentos; o un solo hallazgo con la transcripción completa, más simple y sin evidencia por segmento. Decisión pendiente de aprobación.
3. **Muestra [B.3].** Se recomienda que José Andrés grabe unas 5 notas leyendo guiones sintéticos, con licencia propia declarada en `transcripciones.json`, porque [B.3] admite audios «producidos por el propio equipo». Alternativas: clips en español de Mozilla Common Voice (CC0), con transcripción incluida; o voz sintética generada con un TTS de licencia abierta, que Whisper transcribe con menos errores y por eso mide peor la calidad real. Si los guiones se escriben con IA, se declara en la bitácora. Decisión pendiente de aprobación.
4. **Nota sin voz.** Se propone devolver una lista vacía, como la imagen sin contenido sensible de F-08. ¿Se acepta, o se emite un hallazgo `sin_voz` para que el reporte distinga «analizada sin hallazgos» de «no analizada»?
5. **Hora de la nota.** `Analyzer.analyze(path)` solo recibe la ruta, así que los timestamps son relativos al inicio del audio. Se propone que F-11 combine ese desplazamiento con la hora de la nota que trae el caso (SUP-15). ¿Se acuerda con Kenni (F-11) ahora o cuando F-11 lo necesite? Lo mismo aplica al audio extraído de video por F-05 (Nahúm).
6. **Refactor de `analyze_conversation`.** Agregar el parámetro `posiciones` toca código ya aprobado de F-07. Se propone porque evita duplicar el análisis por lote y la salida del texto no cambia. Alternativa: que `AudioAnalyzer` reescriba las posiciones `mensajes i-j` después, lo que acopla al formato de texto. Decisión pendiente de aprobación.
7. **Severidad de `transcripcion`.** Se propone `baja` sin regla, porque la transcripción es un fragmento de evidencia y no un indicio. La severidad del audio la dan los hallazgos de RF-06.
8. **Conexión con el worker.** Como en F-07 y F-08, se propone no conectar `AudioAnalyzer` al bucle del worker en F-09 y que F-12 invoque cualquier `Analyzer` por tipo de contenido.

**Riesgos:**

- **Las partes 2 y 3 de F-07 y F-08 no están en `main`.** Las PR #29, #30, #32 y #33 figuran como fusionadas, pero sus bases eran las ramas de la parte anterior, no `main`: `origin/main` no tiene `requirements-texto.txt`, `src/adapters/spacy_hf_text_models.py` ni `src/adapters/yolo_detector.py` (comprobado con `git ls-tree origin/main`). La parte 1 de F-09 no los necesita; la parte 2 necesita `requirements-texto.txt` y la 3 los modelos reales de texto. Hay que llevar ese código a `main` antes de la parte 2 de F-09. Resuelto: 43416f1 lo llevó a `main` y la parte 2 parte de esa base (0a6d31c); `git ls-tree origin/main` ya muestra los tres archivos.
- **Calidad.** Whisper `base` comete errores en español con ruido o habla rápida, y puede inventar texto en silencios largos. Una muestra de 5 notas no es representativa; se declara su tamaño. Un error de transcripción puede ocultar una amenaza: es un límite que se declara.
- **Descarga de pesos.** El modelo se descarga de Hugging Face en la primera carga y necesita red; se fija su revisión para que la evidencia sea reproducible. Nunca en las unitarias.
- **Dependencias.** faster-whisper trae CTranslate2 y PyAV. Puede no haber *wheels* para Python 3.14; AD-22 fija 3.13 en los workers. La imagen del worker de audio también lleva torch por los modelos de texto. Sin comprobar.
- **Memoria.** Un audio largo aumenta la memoria del proceso; es justo el caso de OOM provocado de F-18. El transcriptor carga el modelo una vez por proceso para que F-19 pueda comparar estrategias.
- **Dataset de F-03.** F-03 propone audio sintético. Si son tonos o ruido, Whisper no produce texto y el análisis de las 150 notas sería vacío. Hay que avisar a Kenni: las notas deben tener voz, propia o con licencia.
- **Archivos compartidos.** `src/application/analyze_text.py` y `src/adapters/text_analyzer.py` son de F-07, del mismo responsable; `tests/unit/test_arquitectura.py` es compartido. Cambios aditivos de pocas líneas.

### Pendientes para la parte 2

Observaciones menores del QA de la parte 1. Los tiempos infinitos se corrigieron en la parte 1 durante la verificación (f0ce6dc). Las cuatro se resolvieron en la parte 2 (388af7d y c1e58fc).

- Resuelto: un timestamp de 1e12 s o más ya no da `OverflowError` en `segmentos_como_mensajes`: `TranscriptSegment` rechaza con `ValueError` tiempos mayores que `TIEMPO_MAXIMO_S` (`src/domain/transcription.py`).
- Resuelto: `TranscriptSegment` rechaza `bool` como tiempo de inicio o fin.
- Resuelto: `WhisperTranscriber` ordena los segmentos por inicio antes de devolverlos.
- Resuelto: `WhisperTranscriber` convierte a `float` nativo los tiempos y la confianza, incluido `numpy.float32`.

### Pendientes para la parte 3

Observaciones de la parte 2 que José Andrés decide si se corrigen en la parte 3. H1 (NaN en `avg_logprob`) y H2 (excepciones de PyAV sin capturar) se corrigieron en la parte 2 (pruebas en 4f1dc5f y corrección en b1ec7d7).

- Confirmar con PyAV y faster-whisper reales qué excepción se lanza ante un audio ilegible y ante un archivo sin pista de audio; lo capturado se dedujo del código fuente de PyAV 19.0.2, sin ejecutarlo.
- `BugError` de FFmpeg hereda de `RuntimeError` y se reporta como «no es un audio legible», aunque sea un fallo interno de FFmpeg.
- Los segmentos solapados no se corrigen: el adaptador solo los ordena por inicio.
- No se ha comprobado con Python 3.13, que fija AD-22; el equipo de desarrollo usa Python 3.14.
- Las claves extra de `[modelo]` en `config/audio.toml` se ignoran sin aviso.
- La prueba de integración `tests/integration/test_whisper_transcriber_real.py` nunca se ha ejecutado, porque faster-whisper no está instalado en el equipo de desarrollo.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Opus 5.5), subagente arquitecto | 2026-11-09 | Revisé el diff de cf44dfb (SPEC.md y una fila AD-28 en ARQUITECTURA §8); grep confirma 0 campos de puntos suspensivos; el criterio de US-09 está copiado; la prueba roja coincide con IMPLEMENTACION §4; contratos y funciones reutilizadas existen en origin/main (analyze_conversation, TextModels, sha256_de_archivo, from_config); confirmé con git cat-file y gh pr list que las partes 2-3 de F-07/F-08 no están en main (PR #29,#30,#32,#33 con base en ramas de parte); test_conformidad 28/28. No verifiqué estimaciones de líneas ni wheels para Python 3.14. (cf44dfb) |
| verificación IA de plan | Claude Code (Opus 5.5), subagente arquitecto | 2026-11-09 | Revisé el diff de cf44dfb (SPEC.md y fila AD-28 en ARQUITECTURA §8); grep confirma que no quedan campos de puntos suspensivos; criterio de US-09 copiado; prueba roja igual a IMPLEMENTACION §4; reutilizables existen en origin/main; confirmé con git cat-file y gh pr list que partes 2-3 de F-07/F-08 no están en main; test_conformidad 28/28. Re-registro tras quitar el carácter de mi resumen anterior. No verifiqué estimaciones de líneas ni wheels para Python 3.14. (ff2b22e) |
| plan | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de tests | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el diff de bc53051: solo tests/ (test_audio_analyzer.py, test_transcription.py y FakeTextModels en tests/dobles.py), sin src/ ni config/. Leí la prueba roja test_transcripcion_pasa_por_analisis_de_texto: cubre transcripcion con timestamps, RF-06, amenaza alta y SHA-256. Ejecuté pytest de los dos archivos: fallan al recolectar por ModuleNotFoundError de src.adapters.audio_analyzer y src.domain.transcription. La suite completa con --continue-on-collection-errors da 792 passed y 2 errors; test_text_analyzer y los demás siguen en verde. No pude verificar de forma independiente el prototipo temporal que el subagente dice haber borrado. (bc53051) |
| tests | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de implementacion | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el diff 3822528..bd4ece1, que añade 170 líneas y quita 24, todas en src/. La lógica está en domain y application y los adaptadores son delgados. git diff bc53051..HEAD -- tests/ sale vacío, así que las pruebas no se debilitaron. El refactor de analyze_conversation solo mueve _rango, _lista y _detalle a MessagePositions sin cambiar su cuerpo. Ejecuté pytest -q -m 'not integration and not acceptance': 822 passed. No verifiqué con datos reales: eso es de las partes 2 y 3. (bd4ece1) |
| implementacion | José Andrés Loría Herrera | 2026-11-09 |  |
| devuelta de verificacion | José Andrés Loría Herrera | 2026-11-09 | QA: TranscriptSegment acepta tiempos infinitos (transcription.py:22); test_segmento_rechaza_tiempos_no_finitos en rojo |
| verificación IA de implementacion | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el commit f0ce6dc: cambia 3 líneas, solo en src/domain/transcription.py, y añade math.isfinite a la validación de inicio y fin. El diff de tests/ desde bc53051 solo agrega las pruebas de QA de 63f9d3c, sin borrar nada, así que no se debilitó ninguna. Ejecuté pytest -q -m 'not integration and not acceptance': 832 passed, incluida test_segmento_rechaza_tiempos_no_finitos. El resto de la implementación sigue igual que en la verificación anterior (bd4ece1). (f0ce6dc) |
| implementacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5), subagente qa-tester | 2026-11-09 | QA en 2 rondas. La 1.ª devolvió la fase porque TranscriptSegment aceptaba tiempos infinitos; se corrigió en f0ce6dc. La 2.ª da APROBADO. QA probó 17 mutaciones y las pruebas detectaron 16; la restante (transcribir antes del hash) quedó cubierta con una prueba nueva. Comprobé yo: pytest -q -m 'not integration and not acceptance' da 832 passed; reproduje la mutación sin isfinite (2 failed en test_transcription) y la revertí; git status limpio. Mediciones: no aplica según el SPEC. La integración y la aceptación con el modelo real quedan para las partes 2 y 3. (1a5e7f8) |
| verificacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de documentacion | Claude Code (Opus 5.5), subagente documentador | 2026-11-09 | Revisé el diff de db9617c. AD-28 pasa a provisional y describe lo implementado en la parte 1, que coincide con src/ (isfinite, renumeración, formatos de posición, lista vacía sin voz). En CONTRATOS se agregaron transcription.py y analyze_audio.py a los dueños; la tabla de capas está actualizada. En el SPEC quedan los pendientes de QA para la parte 2, iguales a sus informes. El borrador de bitácora coincide con los hashes 63f9d3c, f0ce6dc y ff2b22e y con 832 passed. No hay ficha porque no es M1 a M5. No quedan cambios sin commit. (db9617c) |
| documentacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de revision | Claude Code (Opus 5.5), subagente revisor | 2026-11-09 | El revisor dio APROBADO con 3 hallazgos menores, que quedan para que José Andrés los acepte: FakeTextModels duplicado en test_text_analyzer, TERCEROS_PROHIBIDOS para la parte 2 y los pendientes de QA ya anotados en el SPEC. Releí el diff completo origin/main...HEAD contra el SPEC de la parte 1: solo toca los archivos del plan, con 171 líneas añadidas y 24 borradas en src. pytest -q -m 'not integration and not acceptance': 832 passed. git status limpio. (716a86d) |
| revision | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de tests | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el diff de bc67928: solo toca tests/ (3 archivos nuevos, TERCEROS_PROHIBIDOS con faster_whisper, ctranslate2 y av, y 2 pruebas agregadas a test_transcription sin tocar las existentes). Ejecuté pytest: test_whisper_config y test_whisper_transcriber fallan al recolectar por ModuleNotFoundError de src.adapters.whisper_transcriber; los 5 casos de test_transcription (bool y tiempo fuera de rango) fallan por DID NOT RAISE u OverflowError. El resto da 1085 passed y la integración se salta sin faster-whisper. numpy llega a CI de forma transitiva por pandas, como en F-08. Sin comprobar: qué excepción da PyAV, que es una suposición del developer. (bc67928) |
| tests | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de implementacion | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el diff 3a8ac21..c1e58fc: 139 líneas fuera de tests y docs. git diff bc67928..HEAD -- tests/ sale vacío, así que las pruebas no se debilitaron. faster_whisper se importa solo dentro de from_config, en adaptadores. La validación de segmentos queda fuera del try, de modo que no se confunde con un error de decodificación. Confirmé por mi cuenta que el campo sha de huggingface.co/api/models/Systran/faster-whisper-base es ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 y que faster-whisper 1.2.1 existe en PyPI con licencia MIT. pytest -q -m 'not integration and not acceptance': 1139 passed. La integración se salta porque faster-whisper no está instalado. Sin comprobar: que PyAV lance InvalidDataError subclase de ValueError; el comentario del código lo afirma sin haberlo medido. (c1e58fc) |
| implementacion | José Andrés Loría Herrera | 2026-11-09 |  |
| devuelta de verificacion | José Andrés Loría Herrera | 2026-11-09 | QA: NaN en avg_logprob da confianza 1.0 (H1) y archivo sin pista de audio deja escapar IndexError (H2), whisper_transcriber.py |
| verificación IA de implementacion | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé el commit b1ec7d7, que solo toca src/adapters/whisper_transcriber.py (23 líneas añadidas y 4 borradas). Con eso: H1, un avg_logprob NaN da ValueError; H2, se capturan IndexError y av.error.FFmpegError, este último con importación diferida, mientras RuntimeError y MemoryError genéricos siguen escapando; H3, un segmento inválido da ValueError con la ruta. git diff 4f1dc5f..HEAD -- tests/ sale vacío. pytest -q -m 'not integration and not acceptance': 1148 passed. Sin comprobar: cómo se comporta PyAV en ejecución, porque no está instalado. (b1ec7d7) |
| implementacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5), orquestador sin subagente | 2026-11-09 | Re-verificación NO independiente: José Andrés pidió omitir al QA tester, así que la hizo el orquestador. Antes, en la primera ronda, el QA había devuelto H1 y H2 con pruebas rojas (4f1dc5f), y se corrigieron en b1ec7d7. Mutaciones: quitar la comprobación de NaN hace fallar 1 prueba, y quitar IndexError del except también falla 1; las dos se revirtieron y git status quedó limpio. pytest -q -m 'not integration and not acceptance': 1148 passed. Nadie volvió a probar el resto de los criterios. Sin comprobar: PyAV y faster-whisper reales, que quedan para la parte 3. (63a0aad) |
| verificacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de documentacion | Claude Code (Opus 5.5), subagente documentador | 2026-11-09 | Revisé el diff de 5e58d31. El README del audio coincide con requirements-audio.txt y config/audio.toml. R14 tiene la revisión que comprobé en Hugging Face. AD-28 describe lo implementado en b1ec7d7. CONTRATOS suma los 3 archivos de la parte 2. En el SPEC, los pendientes de la parte 1 quedan resueltos y se agregan los de la parte 3; también marca como resuelto el riesgo de F-07 y F-08 en main, que confirmé antes. El borrador de bitácora usa hashes reales y declara que la re-verificación no fue independiente. Queda desactualizado el esbozo de audio.toml en la línea 115 del SPEC; es menor. (5e58d31) |
| documentacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de revision | Claude Code (Opus 5.5), subagente revisor | 2026-11-09 | El revisor dio APROBADO con 2 hallazgos importantes y 3 menores, todos pendientes de que José Andrés decida. Comprobé los importantes en el código fuente. En faster-whisper 1.2.1, tokenizer.py lanza ValueError ante un idioma inválido, así que ese error se reporta como audio ilegible. En PyAV 19.0.2, av/error.py:213-230 hace que ENOMEM, ETIMEDOUT, EAGAIN y EACCES hereden de MemoryError, TimeoutError, BlockingIOError y PermissionError, y quedan capturados como audio ilegible; la frase de mi verificación anterior sobre MemoryError era imprecisa. Releí el diff completo de la parte 2: 158 líneas fuera de tests y docs. pytest: 1148 passed. git status limpio. (8e262c2) |
| devuelta de revision | José Andrés Loría Herrera | 2026-11-09 | Revisor: idioma invalido se reporta como audio ilegible; errores transitorios de PyAV (ENOMEM, ETIMEDOUT, EAGAIN, EACCES) se reportan como audio ilegible; comentario de decodificacion inexacto; falta prueba de FFmpegError |
| verificación IA de implementacion | Claude Code (Opus 5.5), subagente developer | 2026-11-09 | Revisé 324c2d2, f8b866d, b21d671 y 06df373, que cierran los hallazgos del revisor con TDD. Hallazgo 1: el idioma se valida al cargar contra IDIOMAS_DE_WHISPER, y comparé ese conjunto con _LANGUAGE_CODES de faster-whisper v1.2.1 descargado: los 100 códigos son iguales. Hallazgo 2: los errores transitorios de PyAV se propagan sin convertirse. Hallazgo 3: comentario corregido. Hallazgo 4: nueva prueba de FFmpegError con un av falso. Además encontré una regresión mía, idioma no textual con TypeError, que el developer corrigió con prueba roja previa. Las pruebas existentes no se tocaron: el diff de tests/ solo agrega archivos y casos. pytest -q -m 'not integration and not acceptance': 1183 passed. Sin comprobar: PyAV y faster-whisper reales. Nota: los commits del developer llevan el pie Claude Sonnet 5.5 por el recordatorio de atribución vigente. (06df373) |
| implementacion | José Andrés Loría Herrera | 2026-11-09 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5), subagente qa-tester | 2026-11-09 | QA re-verificó solo lo nuevo y dio APROBADO. Probó 11 mutaciones sobre el idioma y los errores transitorios y todas se detectaron; contrastó por su cuenta los 100 códigos de idioma con faster-whisper v1.2.1 y son idénticos; agregó 5 pruebas en d0c3846, solo en tests/. Repetí yo 2 mutaciones (quitar isinstance falla 3 pruebas, quitar la relanzada de transitorios falla 10), las revertí y git status quedó limpio. pytest -q -m 'not integration and not acceptance': 1188 passed. Observación menor: ConnectionError y BrokenPipeError se reportan como audio ilegible, aceptable para rutas locales. Sin comprobar: PyAV y faster-whisper reales, que quedan para la parte 3. (d0c3846) |
