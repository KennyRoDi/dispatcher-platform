# SPEC F-07: Worker de texto

**Fase:** documentacion
**Base:** feat/F-07-2-inferir-con-spacy-y-huggingface
**Verificación IA:** documentacion e411601
**Historia:** US-07 · **Requisitos:** RF-06, RNF-25; RF-14 (referencia a la evidencia); SUP-07, SUP-12, SUP-15; [B.4 Workers de análisis], [B.3], [B.7 Texto] · **Responsable:** J

## Objetivo

El analista necesita encontrar las conversaciones relevantes de un caso sin leerlas todas. [B.4 Workers de análisis] exige un worker de texto con «palabras clave, clasificación temática, sentimiento, lenguaje ofensivo o amenazas», y [B.1] exige que el análisis use modelos ya entrenados (RNF-25). Hoy el repositorio no analiza texto: `src/workers/` solo ejecuta operaciones de FFmpeg y `src/adapters/` está vacío. F-07 entrega el analizador de texto que implementa el puerto `Analyzer`: recibe una conversación, la divide en lotes y produce por cada lote las cuatro salidas como `Finding`, cada una con referencia a los mensajes que la originan (RF-14), y con la severidad que fijan reglas en configuración (SUP-07). Sus hallazgos son los que consumen el reporte (F-11) y las alertas (F-14), y el worker de audio (F-09) lo reutiliza sobre la transcripción (RF-08).

## Alcance

**Incluye:**

- Lógica pura de dominio: división en lotes de tamaño configurable (SUP-12), ranking de palabras clave, tema por léxico, agregación de sentimiento por lote y reglas de severidad (SUP-07).
- Caso de uso de aplicación que convierte mensajes en `Finding` a través de un puerto interno de modelos, `TextModels`.
- Adaptador `TextAnalyzer` que implementa `Analyzer` (`analyze(path) -> list[Finding]`), con el `ConversationParser` inyectado.
- Archivos de configuración: reglas de severidad, léxico de temas y patrones de amenaza, en TOML, leído con `tomllib` de la biblioteca estándar.
- Adaptador de modelos reales: spaCy para lemas y patrones, y un modelo preentrenado de HuggingFace para sentimiento y ofensas (AD-19), solo inferencia.
- Comprobación de conformidad `comprobar_analyzer` en `tests/contratos.py`, que también sirve a F-08 y F-09.
- Prueba de aceptación con tabla de aciertos contra una verdad de referencia, con su evidencia medida.

**No incluye:**

- Parsers de WhatsApp y Telegram ni normalización a UTF-8 y UTC: son F-02 (Nahúm). F-07 consume `ChatMessage` ya normalizado (SUP-15) y prueba con `FakeConversationParser`.
- Descomposición del caso en sub-tareas y routing a la cola de texto: F-05 y F-32.
- Bucle del worker, subproceso por sub-tarea y cancelación: F-12 (AD-08). Conectar el analizador al bucle del worker queda como pregunta abierta.
- Guardar hallazgos (`FindingStore`, F-13), reporte (F-11) y alertas (F-14, que reutiliza las reglas de severidad).
- Dataset sintético y manifiesto de etiquetas: F-03 y F-04 (Kenni).
- Contenedor por tipo de worker, `mem_limit` y huella de memoria del modelo: F-16 y F-17. Benchmark de modelos por nodo: F-32.
- Entrenar o ajustar modelos [B.1], RNF-25.
- Documentos `.txt` sueltos de SUP-11: entran cuando F-02 o F-05 los conviertan en `ChatMessage`.

## Criterios de aceptación

Copiados de `docs/backlog/cola-workers.md`, US-07:

- **Dado** una conversación etiquetada
- **Cuando** se procesa
- **Entonces** cada lote produce las cuatro salidas con referencia a sus mensajes

- **Pruebas:** U con analizador falso. I con modelo real sobre muestra. A aciertos contra verdad de referencia.
- **Demuestra:** prueba A. **Evidencia:** tabla de aciertos.

Criterios adicionales derivados de los requisitos:

- RF-06: las cuatro salidas existen para todo lote, también cuando no hay ofensas; la ausencia se reporta como salida, no como silencio.
- SUP-07: un mensaje con amenaza explícita produce severidad `alta`; las reglas se leen de un archivo de configuración y cambiar el archivo cambia la severidad sin tocar código.
- RF-14: cada `Finding` lleva `EvidenceRef` con el SHA-256 del objeto analizado y la posición de sus mensajes.
- RNF-25: el repositorio no contiene código de entrenamiento; solo se cargan pesos publicados.

## Diseño

### Contratos

| Contrato | Rol de F-07 | Fuente |
|---|---|---|
| `Analyzer.analyze(path) -> list[Finding]` | Lo implementa `TextAnalyzer` | `src/application/ports.py:18` |
| `ConversationParser.parse(path) -> Iterable[ChatMessage]` | Lo usa; se inyecta. En pruebas, `FakeConversationParser` de `tests/dobles.py` | `src/application/ports.py:23`; F-02 aún pendiente |
| `ChatMessage(timestamp_utc, sender, text, source_ref)` | Lo consume | `src/domain/chat_message.py` |
| `Finding`, `EvidenceRef`, `Severity` | Los produce | `src/domain/finding.py` |

No se modifica ningún contrato compartido. `tests/contratos.py` recibe una función nueva, `comprobar_analyzer`, que valida al doble y al adaptador: devuelve una lista de `Finding`, cada uno con `EvidenceRef` no vacío y confianza en [0, 1]. Es un agregado, no un cambio de contrato, pero toca un archivo compartido: se avisa a quienes usan `Analyzer`.

**Referencia al objeto.** `Analyzer` recibe solo `path`, y `EvidenceRef` exige `object_sha256`. `TextAnalyzer` calcula el SHA-256 del archivo que recibe, que es el texto en claro: coincide con la clave del almacén de AD-11. Así no hace falta cambiar el puerto.

### Flujo

```
TextAnalyzer.analyze(path)
  sha = sha256(path)
  mensajes = parser.parse(path)
  analyze_conversation(mensajes, sha, models, reglas, lexico, tamaño_lote)
    por cada lote de dominio.lotes(mensajes, tamaño_lote):
      analisis = models.analyze_messages([m.text for m in lote])
      4 Finding: palabras_clave, tema, sentimiento, y amenaza | ofensivo | sin_ofensa
```

### Capas y archivos

Todos son nuevos y de José Andrés (`docs/CONTRATOS.md`), salvo los compartidos señalados.

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/text_analysis.py` | `MessageAnalysis` (lemas, etiqueta y puntaje de sentimiento, puntaje de ofensa, patrones de amenaza encontrados); `lotes(mensajes, tamaño)`; `palabras_clave(lemas, n)` por frecuencia; `tema(lemas, lexico)`; agregación de sentimiento por lote |
| Dominio | `src/domain/severity.py` | `SeverityRules` desde un `dict`: por categoría, umbral de confianza y `Severity`. Sin lectura de archivos. `docs/ARQUITECTURA.md` §4 ya lista `severity` en dominio |
| Aplicación | `src/application/analyze_text.py` | Puerto interno `TextModels.analyze_messages(texts) -> list[MessageAnalysis]` y caso de uso `analyze_conversation`, que arma los cuatro `Finding` por lote |
| Adaptador | `src/adapters/text_analyzer.py` | `TextAnalyzer(parser, models, reglas, lexico, tamaño_lote)`: implementa `Analyzer`, calcula el SHA-256 y lee la configuración TOML |
| Adaptador | `src/adapters/spacy_hf_text_models.py` | `TextModels` real: spaCy para lemas, palabras vacías y `Matcher` de patrones de amenaza; `pipeline` de HuggingFace para sentimiento y ofensa. Importación diferida, para que las pruebas unitarias no carguen modelos |
| Configuración | `config/texto.toml` | Tamaño de lote, número de palabras clave, reglas de severidad, léxico de temas, patrones de amenaza e identificadores de modelo con su revisión |
| Dependencias | `requirements-texto.txt` | spaCy, transformers y torch CPU, con versión fija. Separado de `requirements.txt` para que CI y los demás workers no instalen torch; la imagen por tipo es de F-16 (AD-05) |
| Compartido | `tests/contratos.py` | `comprobar_analyzer`, agregado |

`TextModels` no va en `src/application/ports.py`: no es un punto de contacto entre módulos, sino una costura interna de F-07 para probar con un modelo falso. Si F-09 lo reutiliza, sigue siendo del mismo responsable.

### Las cuatro salidas por lote

| `category` | `detail` | `confidence` | `severity` | `evidence.position` |
|---|---|---|---|---|
| `palabras_clave` | Los `n` lemas más frecuentes, sin palabras vacías | 1.0: es un conteo determinista, no una probabilidad | Por regla; por defecto `baja` | Rango del lote: `mensajes 12-23` |
| `tema` | Tema del léxico con más coincidencias, o `sin_tema` | Proporción de lemas del lote que coinciden con ese tema | Por regla; por defecto `baja` | Rango del lote |
| `sentimiento` | `positivo`, `neutral` o `negativo` | Media del puntaje del modelo para la etiqueta elegida | Por regla; por defecto `baja` | Rango del lote |
| `amenaza`, `ofensivo` o `sin_ofensa` | Índice, `timestamp_utc` y `source_ref` de los mensajes marcados | Puntaje máximo de los mensajes marcados; 1.0 si hay patrón de amenaza | `amenaza` → `alta` (SUP-07); `ofensivo` → `media`; `sin_ofensa` → `baja`, según `config/texto.toml` | Índices de los mensajes marcados: `mensajes 15,18`; rango del lote si no hay |

Los índices son la posición del mensaje en el orden de `parse`, de modo que la posición resuelve al objeto y al mensaje (RF-14); `source_ref` conserva la línea original (`docs/ARQUITECTURA.md` §9). La cuarta salida usa una sola categoría por lote: si hay amenaza y ofensa a la vez, prevalece `amenaza`.

### Reglas de severidad en configuración

Refactor de la fila F-07 de `docs/IMPLEMENTACION.md` §4. Ejemplo de forma, con umbrales provisionales que se calibran con la tabla de aciertos, como pide SUP-17 para los parámetros sin valor:

```toml
[[severidad]]
categoria = "amenaza"
umbral = 0.5
nivel = "alta"

[[severidad]]
categoria = "ofensivo"
umbral = 0.5
nivel = "media"
```

Una categoría sin regla o bajo el umbral queda en `baja`. Una regla con nivel desconocido hace fallar la carga, para no degradar en silencio una severidad alta.

### Decisiones

Aplica AD-19 (spaCy y un modelo preentrenado de HuggingFace para sentimiento y ofensas), AD-11 (SHA-256 del texto en claro como identidad del objeto), SUP-07, SUP-12 y SUP-15. AD-08 es de F-12 y no se aplica aquí.

Se propone **AD-26**, provisional, registrada en `docs/ARQUITECTURA.md` §8. Se usa el número 26 porque la rama de F-03 ya propone AD-25.

| ID | Decisión | Alternativas | Criterio |
|---|---|---|---|
| AD-26 | Análisis de texto por lote: palabras clave por frecuencia de lemas de spaCy; tema por léxico configurable; sentimiento y ofensa con un modelo preentrenado de HuggingFace; amenaza por patrones del `Matcher` de spaCy; severidad por reglas en TOML | Clasificación temática *zero-shot* con un modelo NLI; amenaza solo con un clasificador de toxicidad; un LLM | Un solo modelo grande cabe mejor en el límite de memoria (AD-06, F-17); el léxico y los patrones son explicables en la defensa y se ajustan sin entrenar (RNF-25); coincide con el recorte 4 de `docs/IMPLEMENTACION.md` §1.3. **Medición pendiente:** tabla de aciertos de F-07 y huella de F-17 |

### Código del I Proyecto

No se reutiliza código de `src/workers/`. `multimedia_processor.py` solo ejecuta FFmpeg; `worker_node.py` consume un *hash* de Redis con `operation` y `file_path`, no `Subtask`, y su bucle de hilos lo reemplaza F-12 (AD-08). `config.py` valida `WORKER_QUEUES` contra las operaciones de FFmpeg, así que tampoco sirve para la configuración del texto. Se reutiliza la muestra sintética `tests/datos/chat_whatsapp.txt` como forma de referencia, sin modificarla.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_text_analyzer.py::test_texto_con_amenaza_produce_categoria_y_severidad`: `FakeConversationParser` con un mensaje de amenaza ficticio y un `TextModels` falso que marca el patrón | Prueba roja de `docs/IMPLEMENTACION.md` §4: categoría `amenaza` con severidad `alta` y la posición del mensaje |
| Unitaria | `tests/unit/test_text_analyzer.py`: lote sin ofensas, varios lotes, conversación vacía, lote final incompleto, SHA-256 en `EvidenceRef`, conformidad con `comprobar_analyzer` | Cuatro salidas por lote, `sin_ofensa` explícito, referencias correctas; ninguna salida si no hay mensajes |
| Unitaria | `tests/unit/test_text_analysis.py`: `lotes`, `palabras_clave`, `tema`, agregación de sentimiento | Lógica pura, determinista y sin modelos |
| Unitaria | `tests/unit/test_severity.py`: regla aplicada, bajo el umbral, categoría sin regla, nivel desconocido rechazado, cambio de archivo TOML en `tmp_path` cambia la severidad | SUP-07 y el refactor de reglas en configuración |
| Unitaria | `tests/unit/test_arquitectura.py`, existente | El dominio y la aplicación no importan spaCy ni transformers. Se propone agregar `spacy`, `transformers` y `torch` a `TERCEROS_PROHIBIDOS` |
| Integración | `tests/integration/test_text_models_real.py`, marcador `integration`, con `pytest.importorskip("spacy")` y `importorskip("transformers")`: `SpacyHfTextModels` sobre una muestra sintética corta, con los pesos ya descargados | El adaptador real devuelve `MessageAnalysis` válido y la amenaza ficticia de la muestra se marca. Requiere los modelos en el equipo; descargarlos necesita red y no corre en las unitarias |
| Aceptación | `tests/acceptance/test_texto_aciertos.py`, marcador `acceptance`, y `scripts/aciertos_texto.py`: `TextAnalyzer` real sobre una conversación etiquetada; compara cada lote con su etiqueta | Las cuatro salidas por lote y la tabla de aciertos por categoría (amenaza, ofensivo, sentimiento, tema). La prueba exige las cuatro salidas en todo lote; los aciertos se registran tal como salgan, sin umbral mínimo inventado |

Las unitarias no usan red, `sleep`, reloj real ni modelos. `TextModels` falso se define en la propia prueba, porque no es un contrato entre módulos.

### Evidencia, a cargo de la persona

Destino: `docs/evidencia/F-07_aciertos_<fecha>.md`, con el comando exacto, los identificadores y revisiones de los modelos, el tamaño de lote y la tabla de aciertos y errores por categoría. Ningún valor se escribe de antemano.

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-texto.txt
pytest -m integration tests/integration/test_text_models_real.py
python -m scripts.aciertos_texto --conversacion tests/datos/aciertos_texto_conversacion.json --etiquetas tests/datos/aciertos_texto_etiquetas.json --salida docs/evidencia/F-07_aciertos_<fecha>.md
pytest -m acceptance tests/acceptance/test_texto_aciertos.py
```

La parte 2 fijó los modelos y sus revisiones en `config/texto.toml`; el modelo de spaCy se instala como *wheel* desde `requirements-texto.txt`, así que no hace falta `spacy download`. Los pesos de HuggingFace, unos 870 MB, se descargan en la primera carga y necesitan red. El script corre como módulo desde la raíz del repositorio y usa el tamaño de lote del archivo de etiquetas (10), no el de `config/texto.toml` (50). La evidencia del 2026-11-07 está en `docs/evidencia/F-07_aciertos_2026-11-07.md`.

## Mediciones

No aplica. F-07 no es M1–M5 ni un escenario de B.6. La huella de memoria del modelo es de F-17 (ficha M1) y el tiempo por tipo de nodo de F-32 (ficha M5). La tabla de aciertos es evidencia funcional de US-07, no una medición de SO.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimaciones por comprobar al implementar.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-07): analizar lotes de texto con reglas de severidad` | `src/domain/text_analysis.py`, `src/domain/severity.py`, `src/application/analyze_text.py`, `src/adapters/text_analyzer.py`, `config/texto.toml`, `comprobar_analyzer` y pruebas unitarias con parser y modelos falsos. Unas 250 líneas fuera de `tests/` y `docs/`. Se fusiona sin modelos reales. **No cierra la feature** |
| 2 | `feat(F-07): inferir con spaCy y HuggingFace` | `src/adapters/spacy_hf_text_models.py`, `requirements-texto.txt`, identificadores y revisiones de modelo en `config/texto.toml`, cita de modelos y licencias en el código y en la documentación (Parte I §9; `docs/reutilizacion.md` aún no existe y lo crea F-39), prueba de integración. Unas 120 líneas |
| 3 | `test(F-07): medir aciertos contra verdad de referencia` | `scripts/aciertos_texto.py`, prueba de aceptación, conversación etiquetada y evidencia `docs/evidencia/F-07_aciertos_<fecha>.md`; calibración de umbrales en `config/texto.toml` si la tabla lo justifica. Unas 100 líneas. Cierra con `cierre --final` |

## Riesgos y preguntas abiertas

**Preguntas abiertas, para José Andrés:**

1. **Modelo de HuggingFace concreto.** *Resuelta por José Andrés para la parte 2:* dos modelos en español. Sentimiento con `pysentimiento/robertuito-sentiment-analysis` (etiquetas `POS`, `NEG`, `NEU`, que se traducen a `positivo`, `negativo`, `neutral`) y ofensa con `pysentimiento/robertuito-hate-speech` (multietiqueta `HS`, `TR`, `AG`). Ambos dependen de datasets de uso no comercial, válido para el uso académico del proyecto; se citan con su licencia en el código y en la documentación (Parte I §9).
2. **Modelo de spaCy.** *Resuelta por José Andrés para la parte 2:* `es_core_news_sm`, licencia GPL-3.0, para lemas, palabras vacías y `Matcher` de patrones de amenaza. Se cita con su licencia en el código y en la documentación (Parte I §9).
3. **Idioma.** Se supone que las conversaciones sintéticas están en español, como `tests/datos/chat_whatsapp.txt`. Si F-03 genera otro idioma o mezcla, cambia la elección de modelos.
4. **Qué es «un lote».** SUP-12 dice que una sub-tarea puede ser «un lote de mensajes de tamaño configurable». Si F-05 ya parte la conversación en lotes, `TextAnalyzer` recibe un lote y produce un solo grupo de cuatro salidas; si recibe la conversación completa, la parte él. El diseño admite ambos casos con `tamaño_lote`. ¿Qué tamaño por defecto se usa (se propone 50 mensajes) y quién parte: F-05 o F-07?
5. **Clasificación temática por léxico.** AD-26 propone léxico en configuración en lugar de un modelo *zero-shot*, por memoria y explicabilidad. ¿Se acepta, y qué temas define el equipo? Deben coincidir con las etiquetas de la verdad de referencia.
6. **Amenaza por patrones.** Se propone `Matcher` de spaCy con patrones en configuración, porque no se encontró un clasificador de amenazas en español ya identificado. ¿Se acepta? Un patrón no detecta amenazas implícitas; se declarará así en la evidencia.
7. **Umbrales de severidad.** 0.5 es provisional. SUP-07 define qué es alta, no el umbral. Se calibran con la tabla de aciertos de la Parte 3. *Sin resolver al cerrar F-07:* la muestra de la parte 3 no permite calibrarlos y siguen provisionales; ver «Límites conocidos al cerrar F-07».
8. **Verdad de referencia.** *Resuelta por José Andrés para la parte 3:* conversación etiquetada sintética redactada con IA, revisada por José Andrés y declarada en la bitácora, en `tests/datos/`; la parte 3 se limita a lo mínimo (script, prueba de aceptación, conversación y evidencia) y las observaciones menores de QA quedan anotadas sin corregir. Las etiquetas formales son de F-04 (Kenni), aún pendiente, y F-03 está en plan. Para no depender de otro responsable, se propone que la Parte 3 use una conversación etiquetada sintética, corta, escrita por José Andrés en `tests/datos/`, sin personas reales [B.3]; si se redacta con IA, se declara en la bitácora. Cuando F-04 exista, la misma prueba se repite sobre su manifiesto. ¿Se acepta? F-03 pregunta además si sus plantillas incluirán frases de amenaza ficticias para F-07 (pregunta 5 de su SPEC).
9. **Formato de `EvidenceRef.position`.** Se propone `mensajes 12-23` y `mensajes 15,18`, índices en el orden de `parse`. Lo leerán el reporte y las alertas de Kenni (F-11, F-14). ¿Se acuerda con Kenni ahora o se deja como está hasta que F-11 lo necesite?
10. **Conexión con el worker.** El bucle heredado no consume `Subtask` y F-12 lo reemplaza. Se propone no conectar `TextAnalyzer` al worker en F-07 y que F-12, también de José Andrés, invoque cualquier `Analyzer` por tipo de contenido. ¿Se acepta, o se agrega una Parte 4 que lo conecte al worker actual?
11. **Dueño de `src/domain/severity.py`.** `docs/CONTRATOS.md` no lo asigna. F-07 lo crea y F-14 lo reutiliza. Se propone que sea de José Andrés y avisar a Kenni.

**Riesgos:**

- **Tamaño y memoria del modelo.** Un modelo de tipo RoBERTa con torch puede ocupar cientos de MB en RAM. Si no cabe junto a los otros modelos en el límite del contenedor, F-17 obliga a cambiarlo. No se ha medido.
- **Dependencias pesadas.** torch en CPU es grande y puede no publicar *wheels* para 3.14; AD-22 fija 3.13. `requirements-texto.txt` aislado evita que CI lo instale, pero la imagen de F-16 sí lo necesita. Sin comprobar.
- **Descarga de pesos.** Los modelos se bajan de HuggingFace y de spaCy. Se fija la revisión para que la evidencia sea reproducible; la descarga necesita red y no puede ocurrir en las unitarias.
- **Calidad del análisis.** Un modelo entrenado con tuits puede rendir distinto sobre chats sintéticos, y una verdad de referencia pequeña da una tabla poco representativa. Se declara el tamaño de la muestra. [B.1] dice que el análisis no es el foco, pero las cuatro salidas no se recortan.
- **Datos sensibles en `detail`.** La cuarta salida incluye `source_ref` y `timestamp_utc` del mensaje marcado. Solo hay datos sintéticos [B.3], pero el reporte los mostrará: F-11 decide cuánto exponer.
- **Choque de números de AD.** AD-25 está propuesta en la rama de F-03, aún sin fusionar. Si cambia, se renumera AD-26 al fusionar.
- **Archivos compartidos.** `tests/contratos.py` y, si se aprueba, `tests/unit/test_arquitectura.py` son compartidos. Cambios aditivos de pocas líneas.

### Pendientes para la parte 2

Observaciones del QA de la parte 1 que José Andrés decidió posponer. O6, O1 y O3 se corrigieron en la parte 1 durante la verificación.

- O2: dos reglas de la misma categoría: gana la última sin avisar (`src/domain/severity.py`).
- O4: configuración mal formada da `KeyError`/`TypeError`/`AttributeError` en vez de `ValueError` con mensaje.
- O5: `tamano_lote` se valida al analizar, no al cargar; `true` se toma como 1.
- O7: la etiqueta de sentimiento del modelo no se valida contra positivo/neutral/negativo.

José Andrés decidió que O2, O4, O5 y O7 entran en la parte 2, junto con validar que `sentiment_score` y `offense_score` del modelo estén en [0, 1]:

- O2: dos reglas de la misma categoría se rechazan con `ValueError`.
- O4: una configuración mal formada (regla sin `categoria`, `nivel` o `umbral`; `severidad` que no es lista; `temas` que no es tabla de listas) se rechaza con `ValueError` y mensaje claro.
- O5: `tamano_lote` y `n_palabras_clave` se validan al cargar como enteros positivos; se rechazan `bool`, flotantes y texto.
- O7: una etiqueta de sentimiento fuera de positivo/neutral/negativo se rechaza con `ValueError`.
- Puntajes: `sentiment_score` u `offense_score` fuera de [0, 1] se rechazan con `ValueError` claro, en vez del error de `Finding`.

### Pendientes para la parte 3

Observaciones del QA de la parte 2, sin hallazgos H. José Andrés decidió no corregirlas en la parte 3, que se limitó al alcance mínimo, y siguen abiertas, salvo la última, que la parte 3 resolvió. En la parte 2 se corrigieron la prueba del camino feliz de `from_config`, el `ValueError` ante una salida mal formada del pipeline y la detección de «Vas a ver» con mayúscula inicial.

- Puntajes del pipeline: un `NaN` en una etiqueta que no gana se ignora, y un empate se resuelve por el orden de salida del pipeline.
- Validador de patrones de amenaza: es más estricto o más laxo que spaCy según el caso. Acepta un token vacío `{}`, claves extra y atributos mal escritos, y no rechaza nombres de patrón repetidos.
- Reglas de severidad: `amenaza` y `Amenaza` coexisten como categorías distintas, y las claves desconocidas en la raíz de `config/texto.toml` se ignoran sin aviso, por ejemplo `tamano_lotes`.
- `from_config` sin spaCy instalado da `ModuleNotFoundError` sin indicar que falta `requirements-texto.txt`, y acepta `revision = "main"`, que no fija una versión.
- No se aplica `preprocess_tweet` de pysentimiento antes de inferir ni se configura `batch_size` en los pipelines.
- *Resuelta en la parte 3:* la prueba de integración `tests/integration/test_text_models_real.py` no se había ejecutado. El 2026-11-07 corrió con los modelos reales en un venv aparte: 2 passed.

### Límites conocidos al cerrar F-07

Ejecución real del 2026-11-07 en Windows, en un venv aparte con torch 2.15.0+cpu, spacy 3.8.18, transformers 5.22.2 y `es_core_news_sm` 3.8.0: integración 2 passed y aceptación 1 passed. Tabla: tema 4/4, sentimiento 4/4, amenaza 1/1, ofensivo 1/1 y sin ofensa 2/2.

La tabla prueba el funcionamiento de punta a punta, no la precisión. Lo que sigue viene de pruebas exploratorias de QA con los modelos reales, no de la evidencia formal:

- El lote ofensivo acierta por 2 de 10 insultos, con puntaje cercano a 0.99; los otros 8 quedan entre 0.014 y 0.033. El modelo de odio no detecta insultos genéricos.
- Las amenazas sin patrón, como «te voy a matar» o «sé dónde vivís», no se detectan, y la ironía se lee como positiva.
- Los puntajes de ofensa de la muestra quedan en 0.133 o menos y en 0.981 o más, así que `umbral_ofensa` no se puede calibrar con ella. Los umbrales siguen provisionales (pregunta 7).
- La tabla depende del tamaño de lote 10, y en un lote la amenaza tapa a ofensivo.
- La conversación la redactó IA conociendo el léxico y los patrones, así que favorece los aciertos.

Corregido en la parte 3: la evidencia declara sus límites (H1) y el patrón `vas_a_ver` quedó en «vas» y «van», porque «voy» y «vamos a ver», introducidos en la parte 2, daban amenazas altas falsas.

Sin corregir, por el alcance mínimo de la parte 3:

- Un archivo inexistente o un JSON mal formado salen como traceback, no como `error:` con código 1. Un JSON con BOM se rechaza.
- El comando registrado en la evidencia no lleva comillas ni las versiones de torch y transformers.
- La etiqueta `tema` del archivo de etiquetas no se valida contra los temas del léxico.
- El script solo corre como `python -m` desde la raíz del repositorio.
- Las palabras clave incluyen ruido como «vo», «sos» o «enviastir».
- Siguen abiertos los pendientes de la parte 2 listados arriba.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador; subagente arquitecto general-purpose) | 2026-11-05 | Lei SPEC completo y diff (solo SPEC y una fila AD-26 en ARQUITECTURA §8). grep de puntos suspensivos = 0; py -m scripts.conformidad repo = 0 problemas; arbol limpio. Contraste citas: RF-06, RF-14, RNF-25, SUP-07/12/15/17 en REQUERIMIENTOS; B.4 en ENUNCIADO:302; recorte 4 en IMPLEMENTACION §1.3; FakeConversationParser en tests/dobles.py; TERCEROS_PROHIBIDOS en test_arquitectura.py:7; AD-25 propuesta en SPEC de F-03 (git grep). Criterio de US-07 copiado. No verificado: licencias/tamano de modelos HF y spaCy, estimacion de lineas por parte. (941a52f) |
| verificación IA de plan | Claude Code (orquestador; subagente arquitecto general-purpose) | 2026-11-07 | Reverificacion tras corregir mi resumen anterior, que contenia el marcador de campo vacio. Contenido del SPEC sin cambios desde 941a52f (git diff solo toca la fila de verificacion). Comprobaciones previas siguen validas: citas contrastadas, conformidad repo 0 problemas, 0 marcadores. (70f4adb) |
| plan | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de tests | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-07 | Lei el diff completo desde 70f4adb: solo tests/ y filas del script en SPEC; nada en src/ ni config/. Rojo: py -m pytest de test_text_analyzer, test_text_analysis y test_severity da 3 errores de coleccion por ModuleNotFoundError de src.adapters.text_analyzer y src.domain.text_analysis (falta de funcionalidad). Suite completa con --continue-on-collection-errors: 683 pasan, 3 fallan (test_contract.py, preexistentes), 3 errores (los nuevos). Pruebas cubren criterio US-07 (4 salidas por lote, sin_ofensa explicito), SUP-07 (amenaza alta, TOML cambia severidad), RF-14 (sha256 y posicion). comprobar_analyzer es aditivo y el doble la pasa. No verificado: firmas elegidas por el developer que el SPEC no fija. (0310411) |
| tests | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de implementacion | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-07 | git diff b5eddfa -- tests vacio: pruebas no se tocaron ni debilitaron. Lei los 5 archivos nuevos: dominio solo stdlib y src.domain, aplicacion sin adaptadores, sin spacy/transformers/torch. 236 lineas fuera de tests/docs (git diff --numstat). py -m pytest -q -m 'not integration and not acceptance': 713 pasan, 3 fallan en tests/test_contract.py, preexistentes y ajenas a F-07: PurePosixPath(...).name no separa rutas de Windows (lineas 129, 233), solo fallan en Windows. Pruebas de F-07 y arquitectura: 43 pasan. conformidad repo: 0 problemas. Decisiones no fijadas por pruebas: umbral_ofensa 0.5 en TOML, confianza sin_ofensa = 1 - max ofensa. No verificado: lint (ruff no instalado); zip trunca si el modelo devuelve menos analisis que mensajes. (2468160) |
| verificación IA de implementacion | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-07 | Reverificacion tras merge de origin/main (PR #27, arreglo de rutas de Windows en tests/test_contract.py, fusionada con autorizacion de Jose Andres). git diff 2468160: solo entra tests/test_contract.py de main; codigo de F-07 sin cambios. Pruebas de F-07 sin cambios desde la aprobacion de tests (diff vacio). py -m pytest -q -m 'not integration and not acceptance': 716 passed, 0 failed. Revision previa del codigo sigue valida: capas correctas, 236 lineas fuera de tests/docs. No verificado: lint (ruff no instalado). (e2618ed) |
| implementacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de verificacion | Claude Code (orquestador; subagentes qa-tester y developer general-purpose) | 2026-11-07 | QA devolvio H1 (media): zip truncaba si TextModels devolvia otra cantidad de analisis; agrego test_modelo_con_un_analisis_por_mensaje_distinto_se_rechaza[-1,1] y test_confianza_de_ofensivo_es_el_maximo_de_los_marcados (detecta mutacion max->min). Reproduje H1: 2 failed antes del arreglo. Developer corrigio en analyze_text.py (ValueError si len difiere, zip strict); git diff 1321474 solo toca src/application/analyze_text.py (+3 -1), tests intactos. py -m pytest -q -m 'not integration and not acceptance': 719 passed. 238 lineas fuera de tests/docs. QA: 12 mutaciones, todas detectadas. Criterios US-07 (dobles), RF-06, SUP-07, RF-14, RNF-25 con evidencia. Pendiente decision humana: observaciones O1-O7 (validacion de config, minusculas/tildes en lexico). Pruebas I y A fuera de la parte 1. (09d9cda) |
| verificación IA de verificacion | Claude Code (orquestador; subagentes qa-tester y developer general-purpose) | 2026-11-07 | Tras H1, Jose Andres pidio corregir en la parte 1 las observaciones mas importantes (O6 tildes/mayusculas en tema, O1 regla de amenaza obligatoria, O3 umbrales en [0,1]) y posponer O2, O4, O5, O7 a la parte 2 (anotadas en el SPEC). Rojo comprobado: worktree en f2d9c15 (pruebas nuevas, codigo viejo) da 21 failed, 37 passed. Pruebas existentes sin lineas eliminadas (git diff --numstat 09d9cda -- tests). Diff de src leido: dominio solo stdlib (math, unicodedata); validacion de umbral_ofensa en TextSettings (aplicacion). py -m pytest -q -m 'not integration and not acceptance': 744 passed. 265 lineas fuera de tests/docs. Decision: normalizar convierte ñ en n para comparar con el lexico. No verificado: palabras_clave no normaliza (Deuda y deuda cuentan aparte). (ef359e2) |
| verificacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de documentacion | Claude Code (orquestador; subagente documentador general-purpose) | 2026-11-07 | Lei el diff de 0bc28b2: ARQUITECTURA §4 agrega text_analysis y analyze_text (existen en src); AD-26 refleja lo implementado en la parte 1 sin afirmar modelos reales y sigue provisional con medicion pendiente; CONTRATOS asigna a Jose Andres text_analysis, severity (aviso a Kenni), analyze_text y config/texto.toml, y cita comprobar_analyzer. Sin fichas (F-07 no es M1-M5), sin reutilizacion ni README (no aplica). conformidad repo: 0 problemas. Borrador de bitacora contrastado con git log y la conversacion; corregido: developer actuo en 4 rondas (tests, implementacion, H1, O6/O1/O3), no 3; errores (3) y (5) confirmados por el informe de QA y por la conversacion con Jose Andres. (0bc28b2) |
| documentacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de revision | Claude Code (orquestador; subagente revisor general-purpose) | 2026-11-07 | Revisor APROBADO sin hallazgos bloqueantes. Confirme: git diff --name-only origin/main...HEAD da solo los 14 archivos de la fila 1 del plan (src de F-07, config/texto.toml, pruebas, ARQUITECTURA, CONTRATOS, SPEC); SPEC lineas 19 y 91 citan patrones de amenaza en config/texto.toml que la parte 1 no tiene (observacion 1, para parte 2); arbol limpio; py -m pytest -q -m 'not integration and not acceptance': 744 passed. Releí el codigo de src completo en fases anteriores y el diff posterior (H1, O6, O1, O3). Observaciones del revisor 1-3 son menores y quedan para decision de Jose Andres. (f592a96) |
| revision | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de tests | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-07 | Parte 2, fase tests. git diff 06951cf: solo SPEC (decisiones de modelos de Jose Andres, preguntas 1 y 2 resueltas) y tests/; nada en src/ ni config/; 0 lineas borradas en tests. Rojo: suite rapida con --continue-on-collection-errors da 68 failed, 757 passed, 1 error (coleccion de test_spacy_hf_text_models por ModuleNotFoundError del adaptador nuevo), todos en archivos de F-07; las 744 previas siguen pasando. Integracion se salta (spacy no instalado). Pruebas cubren O2, O4, O5, O7, puntajes en [0,1], adaptador con dobles (una llamada por lote, importacion diferida, citas de licencia) y config de modelos y patrones. Confirme en config.json de HF que robertuito-hate-speech usa hateful/targeted/aggressive (las pruebas aceptan ambos juegos). No verificado: comportamiento real de spaCy Matcher y pipelines. (3d78120) |
| tests | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de implementacion | Claude Code (Opus 5.5) | 2026-11-07 | Pruebas intactas desde 3d78120; 866 verdes, 1 saltada (integracion sin spacy); 227 lineas fuera de tests/docs; capas OK; SHAs de HF y versiones de PyPI comprobados por red (dae36b1) |
| implementacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5) | 2026-11-07 | QA sin hallazgos H; 8 observaciones O (O1: from_config sin prueba del camino feliz). Confirme O1, O2 y O3 por mi cuenta; 866 verdes; integracion saltada sin spacy (4744bb2) |
| verificación IA de verificacion | Claude Code (Opus 5.5) | 2026-11-07 | Corregidas O1 (pruebas de from_config con modulos falsos), O2 (ValueError ante salida mal formada) y patron vas_a_ver con LOWER; 884 verdes; 237 lineas; integracion aun saltada sin spacy (c889c73) |
| verificacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de documentacion | Claude Code (Opus 5.5) | 2026-11-07 | Revise el diff de docs: README instala requirements-texto con citas; ARQUITECTURA R11 y R12; CONTRATOS; SPEC con pendientes para la parte 3 sin campos sin completar; 884 verdes (9f0a540) |
| documentacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de revision | Claude Code (Opus 5.5) | 2026-11-07 | Revisor APROBADO sin bloqueantes; confirme arbol limpio, 884 verdes y la nota de pytest.ini; observaciones menores no bloqueantes (319af90) |
| revision | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de tests | Claude Code (Opus 5.5) | 2026-11-07 | Solo tests/ cambia (567 lineas: conversacion y etiquetas sinteticas, 24 unitarias, aceptacion con importorskip); rojo: error de coleccion por scripts.aciertos_texto inexistente, resto 884 verdes; lei los 40 mensajes: ficticios, sin personas reales (67f12f2) |
| tests | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de implementacion | Claude Code (Opus 5.5) | 2026-11-07 | Pruebas intactas desde 67f12f2; 910 verdes, aceptacion saltada sin spacy; 246 lineas (script 243, analyze_text renombra exigir_entero_positivo); lei construir_analizador y main; sin evidencia ni cifras escritas (68c3672) |
| implementacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de verificacion | Claude Code (Opus 5.5) | 2026-11-07 | Modelos reales ejecutados en venv aparte: integracion 2 y aceptacion 1 pasan; evidencia regenerada con seccion Limites (4/4, 1/1, 1/1, 2/2). QA: tabla no mide precision; corregidos H1 (limites) y falso positivo voy/vamos a ver; confirme margenes clave por mi cuenta; 913 verdes (fe49517) |
| verificacion | José Andrés Loría Herrera | 2026-11-07 |  |
| verificación IA de documentacion | Claude Code (Opus 5.5) | 2026-11-07 | Revise el diff de docs: AD-26 sigue provisional con la medicion funcional y sus limites; SPEC con limites al cerrar F-07 sin campos sin completar; README con comandos de evidencia; CONTRATOS; 913 verdes. Bitacora: corrijo lineas a 267 y agrego componente (e411601) |
