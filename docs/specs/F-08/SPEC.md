# SPEC F-08: Worker de imagen

**Fase:** verificacion
**Base:** feat/F-08-1-worker-de-imagen
**Verificación IA:** verificacion 080eddb
**Historia:** US-08 · **Requisitos:** RF-07, RNF-25; RF-14 (referencia a la evidencia); RNF-04, RNF-05; SUP-07, SUP-11, SUP-22; [B.4 Workers de análisis], [B.1], [B.3], [B.7 Imagen] · **Responsable:** J

## Objetivo

El analista necesita saber qué imágenes de un caso muestran contenido sensible sin revisarlas una por una. [B.4 Workers de análisis] exige un worker de imagen con «clasificación o detección de objetos/contenido sensible», y [B.1] exige usar modelos ya entrenados (RNF-25). Hoy el repositorio no analiza imágenes: `src/workers/multimedia_processor.py` solo ejecuta FFmpeg y `src/adapters/` está vacío en `main`. F-08 entrega el analizador de imagen que implementa el puerto `Analyzer`: recibe una imagen, la pasa por un detector de objetos preentrenado (YOLO, AD-19) y convierte cada detección de una clase sensible en un `Finding` con categoría, confianza, severidad por reglas (SUP-07: arma en imagen es severidad alta) y la caja de la detección como posición de la evidencia (RF-14). Sus hallazgos los consumen el reporte (F-11) y las alertas (F-14), y los fotogramas que F-05 extrae de los videos llegan al mismo analizador (SUP-11).

## Alcance

**Incluye:**

- Lógica pura de dominio: `Detection` (etiqueta del modelo, confianza, caja) y la conversión de detecciones en hallazgos por categoría sensible, con un mapa configurable de clases del modelo a categorías (SUP-22) y un umbral mínimo de confianza.
- Caso de uso de aplicación que convierte una imagen en `Finding` a través de un puerto interno de detección, `ObjectDetector`.
- Adaptador `ImageAnalyzer` que implementa `Analyzer` (`analyze(path) -> list[Finding]`), calcula el SHA-256 de la imagen y lee `config/imagen.toml`.
- Reutilización de `SeverityRules` de F-07 para la severidad, con la categoría obligatoria como parámetro en vez de fija en `amenaza`.
- Adaptador de detección real con Ultralytics YOLO, variante nano preentrenada en COCO (AD-19), solo inferencia y con importación diferida.
- Prueba de aceptación con tabla de aciertos sobre una muestra etiquetada propia o pública con licencia [B.3], con su evidencia medida.

**No incluye:**

- Extraer fotogramas de video: F-05 (SUP-11). F-08 recibe una imagen ya extraída.
- Descomposición del caso y routing a la cola de imagen: F-05 y F-32.
- Bucle del worker, subproceso por sub-tarea y cancelación: F-12 (AD-08).
- Guardar hallazgos (F-13), reporte (F-11) y alertas (F-14).
- Las 300 imágenes del dataset y su manifiesto de etiquetas: F-03 y F-04. La muestra de la prueba A es otra, pequeña y de F-08.
- Contenedor del worker de imagen, `mem_limit` y huella del modelo: F-16 y F-17. Benchmark por nodo: F-31 y F-32; [IMPLEMENTACION §1.3] recorte 3 permite que M5 no use YOLO.
- Validar formatos en la ingesta: F-02. Aquí solo se rechaza el archivo que el detector no puede abrir.
- Entrenar, ajustar o reetiquetar modelos [B.1], RNF-25. Por eso no hay detección de armas de fuego ni de desnudez (ver SUP-22 y preguntas abiertas).
- Desenfocar o recortar la región detectada.

## Criterios de aceptación

Copiados de `docs/backlog/cola-workers.md`, US-08:

- **Dado** una imagen con contenido positivo conocido
- **Cuando** se procesa
- **Entonces** se reportan categoría y confianza

- **Pruebas:** U con detector falso. I con modelo real. A aciertos sobre muestra etiquetada.
- **Demuestra:** prueba A. **Evidencia:** tabla de aciertos.

Criterios adicionales derivados de los requisitos:

- RF-07: una imagen positiva de la muestra produce un `Finding` con la categoría esperada y confianza en [0, 1].
- SUP-07: una detección de la categoría `arma` con confianza igual o mayor al umbral produce severidad `alta`; las reglas se leen de `config/imagen.toml` y cambiar el archivo cambia la severidad sin tocar código.
- SUP-22: solo las clases del modelo listadas en el mapa de `config/imagen.toml` producen hallazgos; una clase fuera del mapa o bajo el umbral mínimo de confianza no produce ninguno.
- RF-14: cada `Finding` lleva `EvidenceRef` con el SHA-256 de la imagen y la caja de la detección en píxeles.
- RNF-25: el repositorio no contiene código de entrenamiento; solo se cargan pesos publicados, con versión fijada.
- [B.3], RNF-04 y RNF-05: cada imagen de la muestra etiquetada declara procedencia y licencia; ninguna es de terceros sin licencia.

## Diseño

### Contratos

| Contrato | Rol de F-08 | Fuente |
|---|---|---|
| `Analyzer.analyze(path) -> list[Finding]` | Lo implementa `ImageAnalyzer` | `src/application/ports.py:18` |
| `Finding`, `EvidenceRef`, `Severity` | Los produce | `src/domain/finding.py` |
| `SeverityRules` | Lo reutiliza | `src/domain/severity.py`, creado por F-07, PR #28 aún abierta |
| `comprobar_analyzer` | Lo usa en sus pruebas | `tests/contratos.py`, agregado por F-07, PR #28 aún abierta |

No se modifica ningún contrato compartido. `ImageAnalyzer` no usa `ConversationParser`: lee la imagen directamente a través del detector.

**Referencia al objeto.** Como en F-07, `ImageAnalyzer` calcula el SHA-256 del archivo que recibe, que es el contenido en claro y coincide con la clave del almacén (AD-11). La función de F-07 `_sha256` de `src/adapters/text_analyzer.py` se mueve a un módulo común, `src/adapters/hashing.py`, para no duplicarla.

### Flujo

```
ImageAnalyzer.analyze(path)
  sha = sha256_de_archivo(path)
  detecciones = detector.detect(path)            # list[Detection]
  analyze_image(detecciones, sha, ajustes)
    filtra por umbral mínimo y por mapa clase -> categoría
    agrupa por categoría; toma la detección de mayor confianza
    1 Finding por categoría: categoría, confianza, severidad por regla, caja
```

Una imagen sin detecciones sensibles devuelve una lista vacía (ver pregunta 4).

### Capas y archivos

Todos son de José Andrés (`docs/CONTRATOS.md`: `src/adapters/*_analyzer.py` y `src/workers/`), salvo los compartidos señalados.

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/image_detection.py` | `Detection(label, confidence, box)` con validación de confianza en [0, 1] y caja de enteros no negativos; `sensitive_findings(detecciones, sha, mapa, umbral_minimo, reglas)` que filtra, agrupa por categoría y arma los `Finding` |
| Dominio | `src/domain/severity.py` | Refactor mínimo: `SeverityRules.from_dict(datos, obligatoria="amenaza")`. El texto sigue exigiendo `amenaza`; la imagen exige `arma` (SUP-07) |
| Aplicación | `src/application/analyze_image.py` | Puerto interno `ObjectDetector.detect(path) -> list[Detection]`, `ImageSettings` y caso de uso `analyze_image` |
| Adaptador | `src/adapters/image_analyzer.py` | `ImageAnalyzer(detector, ajustes)` con `from_config(detector, ruta)`: implementa `Analyzer`, calcula el SHA-256 y valida `config/imagen.toml` con `ValueError` y mensaje claro |
| Adaptador | `src/adapters/hashing.py` | `sha256_de_archivo(path)`, extraída de `text_analyzer.py`, que pasa a importarla |
| Adaptador | `src/adapters/yolo_detector.py` | `ObjectDetector` real con Ultralytics YOLO: carga los pesos una vez, infiere en CPU y traduce cada caja a `Detection`. Importación diferida, para que las unitarias no carguen `ultralytics` ni `torch`. Un archivo que no es imagen se rechaza con `ValueError` |
| Configuración | `config/imagen.toml` | Umbral mínimo de confianza, mapa clase → categoría, reglas de severidad, archivo de pesos y su SHA-256 |
| Dependencias | `requirements-imagen.txt` | `ultralytics` con versión fija y torch CPU. Separado de `requirements.txt`, como `requirements-texto.txt` de F-07, para que CI no instale torch |

`ObjectDetector` no va en `src/application/ports.py`: es una costura interna de F-08, como `TextModels` en F-07.

### El hallazgo de imagen

| `category` | `detail` | `confidence` | `severity` | `evidence.position` |
|---|---|---|---|---|
| Categoría del mapa, inicialmente `arma` | Clase del modelo y número de cajas: `knife ×2` | Confianza de la detección de mayor puntaje de esa categoría | Por regla de `config/imagen.toml`; `arma` → `alta` (SUP-07); sin regla o bajo el umbral, `baja` | Caja de esa detección en píxeles de la imagen original: `caja 12,40,180,220` (x1, y1, x2, y2) |

Si varias clases del modelo van a la misma categoría, se agrupan en un solo hallazgo. Ejemplo de forma de la configuración, con valores provisionales que se revisan con la tabla de aciertos, como pide SUP-17:

```toml
umbral_minimo = 0.25

[clases]
knife = "arma"

[[severidad]]
categoria = "arma"
umbral = 0.5
nivel = "alta"

[modelo]
pesos = "yolo11n.pt"
sha256 = "se fija en la parte 2 con el archivo descargado"
```

Una clase mapeada a categoría vacía, un umbral fuera de [0, 1], una regla con nivel desconocido o la falta de regla para `arma` hacen fallar la carga, para no degradar en silencio una severidad alta.

### Decisiones

Aplica AD-19 (YOLO variante nano), AD-11 (SHA-256 del contenido en claro), AD-22 (Python 3.13 en imágenes de workers ML), SUP-07 y SUP-11. Reutiliza de F-07 `SeverityRules`, `comprobar_analyzer` y el cálculo de SHA-256.

Se proponen, provisionales:

- **AD-27**, registrada en `docs/ARQUITECTURA.md` §8. Se usa 27 porque F-03 propone AD-25 y F-07 AD-26, ambas sin fusionar.

| ID | Decisión | Alternativas | Criterio |
|---|---|---|---|
| AD-27 | Detección de contenido sensible en imagen con Ultralytics YOLO11n preentrenado en COCO, solo inferencia en CPU; clases sensibles por mapa configurable; un hallazgo por categoría con la detección de mayor confianza; severidad con las reglas de F-07 | Clasificador de imagen completo (ImageNet o un clasificador NSFW de HuggingFace); YOLO con pesos ajustados por terceros para armas de fuego; OpenCV DNN con ONNX | Un solo modelo pequeño para el límite de memoria (AD-06, F-17); detectar da la caja que pide RF-14 como posición; COCO trae `knife`, que cubre el «arma en imagen» de SUP-07 sin entrenar (RNF-25); pesos de terceros para armas de fuego tienen licencia y procedencia dudosas. Ultralytics y sus pesos usan AGPL-3.0: compatible con un repositorio público; se cita en el código y la documentación (Parte I §9). **Medición pendiente:** tabla de aciertos de F-08 y huella de F-17 |

- **SUP-22 ⚠**, registrado en `docs/REQUERIMIENTOS.md` §3: «contenido sensible en imagen» son las clases de COCO del mapa de configuración; inicialmente `knife` → `arma`. [B.4] no define las categorías.

### Código del I Proyecto

No se reutiliza código de `src/workers/`: `multimedia_processor.py` solo ejecuta FFmpeg y `worker_node.py` no consume `Subtask` (lo reemplaza F-12). Se reutiliza código de F-07, del mismo responsable, como se indica arriba.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `tests/unit/test_image_analyzer.py::test_imagen_produce_categoria_y_confianza`: un `ObjectDetector` falso devuelve una detección `knife` con confianza 0.9 sobre un archivo temporal | Prueba roja de `docs/IMPLEMENTACION.md` §4: un `Finding` con categoría `arma`, confianza 0.9, severidad `alta`, SHA-256 del archivo y la caja como posición |
| Unitaria | `tests/unit/test_image_analyzer.py`: sin detecciones, clase fuera del mapa, bajo el umbral mínimo, dos cajas de la misma categoría, dos clases a la misma categoría, conformidad con `comprobar_analyzer`, `from_config` con TOML válido e inválido en `tmp_path` | Lista vacía sin contenido sensible; un hallazgo por categoría con la mayor confianza; configuración validada al cargar |
| Unitaria | `tests/unit/test_image_detection.py`: `Detection` rechaza confianza fuera de [0, 1] y cajas inválidas; `sensitive_findings` puro | Lógica de dominio determinista, sin modelo |
| Unitaria | `tests/unit/test_severity.py`, existente de F-07: se agrega el caso de categoría obligatoria parametrizada | El refactor no cambia el comportamiento del texto |
| Unitaria | `tests/unit/test_arquitectura.py`, existente | Se propone agregar `ultralytics`, `torch` y `cv2` a `TERCEROS_PROHIBIDOS` |
| Integración | `tests/integration/test_yolo_detector_real.py`, marcador `integration`, con `pytest.importorskip("ultralytics")`: `YoloDetector` sobre una imagen positiva de la muestra y sobre un archivo que no es imagen | El adaptador real devuelve `Detection` válidas con la clase `knife`, y rechaza el archivo inválido con `ValueError`. Requiere los pesos ya descargados |
| Aceptación | `tests/acceptance/test_imagen_aciertos.py`, marcador `acceptance`, y `scripts/aciertos_imagen.py`: `ImageAnalyzer` real sobre la muestra etiquetada | Cada imagen positiva produce categoría y confianza, y la tabla de aciertos por categoría (verdaderos y falsos positivos y negativos). Los aciertos se registran tal como salgan, sin umbral mínimo inventado |

Las unitarias no usan red, `sleep`, reloj real ni modelos. El detector falso se define en la propia prueba.

### Muestra etiquetada

`tests/datos/imagenes/` con unas 20 imágenes reducidas a 640 px de lado mayor, mitad positivas y mitad negativas, y `tests/datos/imagenes/etiquetas.json` con, por imagen, la categoría esperada (o ninguna), la procedencia y la licencia [B.3]. La propuesta es que sean fotos tomadas por José Andrés de objetos, sin personas ni datos de terceros (pregunta 3).

### Evidencia, a cargo de la persona

Destino: `docs/evidencia/F-08_aciertos_<fecha>.md`, con el comando exacto, la versión de `ultralytics` y torch, el archivo de pesos y su SHA-256, el umbral mínimo, el tamaño y la procedencia de la muestra, y la tabla por categoría. Ningún valor se escribe de antemano.

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-imagen.txt
pytest -m integration tests/integration/test_yolo_detector_real.py
python -m scripts.aciertos_imagen --muestra tests/datos/imagenes --etiquetas tests/datos/imagenes/etiquetas.json --salida docs/evidencia/F-08_aciertos_<fecha>.md
pytest -m acceptance tests/acceptance/test_imagen_aciertos.py
```

La versión de torch se toma de F-07 y se confirma en la parte 2.

## Mediciones

No aplica. F-08 no es M1–M5 ni un escenario de B.6. La huella de memoria de YOLO es de F-17 (ficha M1) y su tiempo por tipo de nodo, si se mide, de F-31 (ficha M5). La tabla de aciertos es evidencia funcional de US-08, no una medición de SO.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimaciones por comprobar al implementar.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-08): convertir detecciones de imagen en hallazgos` | `src/domain/image_detection.py`, `src/application/analyze_image.py`, `src/adapters/image_analyzer.py`, `src/adapters/hashing.py`, refactor de `src/domain/severity.py` y `src/adapters/text_analyzer.py`, `config/imagen.toml` y pruebas unitarias con detector falso. Unas 200 líneas fuera de `tests/` y `docs/`. Requiere la PR #28 de F-07 en su base. **No cierra la feature** |
| 2 | `feat(F-08): detectar objetos con YOLO` | `src/adapters/yolo_detector.py`, `requirements-imagen.txt`, pesos y SHA-256 en `config/imagen.toml`, cita de Ultralytics y AGPL-3.0 en el código y la documentación, prueba de integración. Unas 90 líneas |
| 3 | `test(F-08): medir aciertos sobre muestra etiquetada` | `scripts/aciertos_imagen.py`, prueba de aceptación, muestra con `etiquetas.json` y evidencia `docs/evidencia/F-08_aciertos_<fecha>.md`. Unas 110 líneas sin contar las imágenes. Cierra con `cierre --final` |

## Riesgos y preguntas abiertas

**Decisiones pendientes de aprobación, para José Andrés:**

1. **Modelo.** Se recomienda Ultralytics YOLO11n (`yolo11n.pt`, COCO, unos 5 MB, AGPL-3.0), que es la variante nano de AD-19. Alternativa: YOLOv8n, igual de pequeño y más documentado. Decisión pendiente de aprobación.
2. **Categorías sensibles (SUP-22 ⚠).** Se recomienda empezar con `knife` → `arma`, la única clase de COCO que es un arma. COCO no tiene armas de fuego, así que «arma» significa arma blanca; se declarará como límite. Alternativas: agregar `scissors` o `baseball bat` como `arma`, con más falsos positivos; o sumar un clasificador NSFW de HuggingFace como segundo modelo, con más memoria y una categoría que [B.4] no exige. Decisión pendiente de aprobación.
3. **Muestra etiquetada [B.3].** Se recomienda que José Andrés tome unas 20 fotos de objetos (cuchillos de cocina y escenas sin cuchillo), sin personas, con licencia propia declarada en `etiquetas.json`, porque [B.3] admite imágenes «producidas por el propio equipo» y no necesita red. Alternativa: imágenes de COCO val2017 filtradas por licencia CC BY, con atribución por imagen. Si se generan con IA, se declara en la bitácora. Decisión pendiente de aprobación.
4. **Imagen sin contenido sensible.** Se propone devolver una lista vacía, porque RF-07 solo pide reportar lo positivo y un hallazgo es evidencia de algo. F-07 emite `sin_ofensa` porque RF-06 exige las cuatro salidas; aquí no hay tal requisito. ¿Se acepta, o se emite un hallazgo `sin_contenido_sensible` para que el reporte distinga «analizada sin hallazgos» de «no analizada»?
5. **Dependencia de F-07.** La parte 1 reutiliza `SeverityRules`, `comprobar_analyzer` y el cálculo de SHA-256 de la PR #28, aún abierta. Se propone esperar a que #28 se fusione en `main` antes de la fase de pruebas de la parte 1. Alternativa: apilar la parte 1 sobre `feat/F-07-1-worker-de-texto`. No se duplica el código.
6. **Umbrales.** `umbral_minimo = 0.25` es el valor por defecto de Ultralytics y `umbral = 0.5` para `alta` sigue a F-07. Son provisionales (SUP-17) y se revisan con la tabla de la parte 3.
7. **Formato de `EvidenceRef.position`.** Se propone `caja x1,y1,x2,y2` en píxeles de la imagen original. Para fotogramas de video, el timestamp del fotograma lo aporta F-05 al extraerlo; ¿se acuerda con Nahúm y con Kenni (F-11) ahora o cuando F-11 lo necesite?
8. **Conexión con el worker.** Como en F-07, se propone no conectar `ImageAnalyzer` al bucle del worker en F-08 y que F-12 invoque cualquier `Analyzer` por tipo de contenido.

**Riesgos:**

- **Dataset sintético de F-03.** F-03 propone imágenes sintéticas generadas con FFmpeg (su pregunta 3). YOLO no detecta cuchillos en patrones sintéticos, así que la proporción de positivos de RF-20 no sería medible con el modelo. Hay que avisar a Kenni: las imágenes positivas deben ser fotos propias o públicas con licencia.
- **AGPL-3.0.** Ultralytics y sus pesos son AGPL-3.0. El repositorio es público, así que se cumple publicando el código; se cita en el código y la documentación.
- **Dependencias pesadas.** `ultralytics` trae torch, OpenCV y numpy. Puede no haber *wheels* para Python 3.14; AD-22 fija 3.13 en las imágenes de workers. Sin comprobar.
- **Descarga de pesos.** `yolo11n.pt` se descarga de GitHub en la primera carga y necesita red; se fija su SHA-256 para que la evidencia sea reproducible. Nunca en las unitarias.
- **Calidad.** Una muestra de 20 imágenes da una tabla pequeña y no representativa; se declara su tamaño. Detectar solo cuchillos cubre una parte mínima de «contenido sensible».
- **Choque de números.** AD-25 (F-03), AD-26 (F-07) y AD-27 (F-08) están sin fusionar y en la misma tabla; si cambia el orden de fusión, se renumera y se resuelve el conflicto de líneas.
- **Archivos compartidos.** `src/domain/severity.py` y `src/adapters/text_analyzer.py` son de F-07, del mismo responsable; `tests/unit/test_arquitectura.py` es compartido. Cambios aditivos de pocas líneas.

### Pendientes para la parte 2

Observaciones del QA de la parte 1 sin corregir. D1, D2 y R1 se corrigieron en la parte 1 durante la verificación (1beeb6c).

- La caja con `x2 < x1` o `y2 < y1` se acepta (`src/domain/image_detection.py`).
- Una `Detection` con `label` vacío se acepta.
- `ImageSettings` guarda el mapa de clases por referencia: cambiarlo después de crear los ajustes cambia el análisis.
- `YoloDetector` debe convertir a `int` y `float` nativos las coordenadas y confianzas de numpy, porque `Detection` rechaza los enteros de numpy en la caja y `numpy.float32` en la confianza.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador; subagente arquitecto general-purpose) | 2026-11-08 | Lei SPEC completo y git diff de 0cffc1c: solo SPEC, 1 fila AD-27 en ARQUITECTURA §8 y 1 fila SUP-22 en REQUERIMIENTOS §3. SPEC sin campos pendientes (grep). Criterios de US-08 copiados tal cual; adicionales trazan a RF-07, SUP-07, RF-14, RNF-25, B.3. Contrasté con ENUNCIADO: B.4 pide clasificacion o deteccion de objetos/contenido sensible, B.7 sugiere YOLO; AD-19 ya fija YOLO nano; prueba roja coincide con IMPLEMENTACION §4 linea 127. PR #28 abierta (gh pr view); SeverityRules y _sha256 existen en feat/F-07-1; torch==2.15.0 coincide con requirements-texto.txt de F-07-2/3. Plan de pila 3 PR estimadas 200/90/110 lineas (menos de 400). Sin llaves ni datos de terceros. No verificado: licencia AGPL de Ultralytics y pesos, wheels para 3.13/3.14. Re-registrada: la anterior (a92f221, revertida en 19b2add) contenia el caracter de campo pendiente. (19b2add) |
| plan | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de tests | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-08 | git diff 5327f5a..09d2bb4: solo tests/ (5 archivos, +279/-1), nada en src, config ni requirements. Lei test_image_analyzer.py y test_image_detection.py completos y los diffs de test_severity.py y test_arquitectura.py: cubren cada fila unitaria del SPEC (prueba roja de IMPLEMENTACION §4, lista vacia, fuera del mapa, bajo umbral, agrupacion, comprobar_analyzer, from_config valido e invalido, Detection, sensitive_findings, obligatoria parametrizada, ultralytics y cv2 prohibidos). py -m pytest -q -m 'not integration and not acceptance': 3 errores de coleccion por ModuleNotFoundError de src.adapters.hashing, src.adapters.image_analyzer y src.domain.image_detection; ignorandolos, 745 pasan y 1 falla (TypeError por el parametro obligatoria inexistente). Todos los fallos se deben a funcionalidad faltante. Interpretaciones del developer aceptadas: umbral minimo inclusivo, caja sin exigir x2>=x1. Detalle menor: test_severity.py sin salto de linea final. (09d2bb4) |
| tests | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de implementacion | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-08 | git diff 251af80 -- tests vacio: pruebas no se tocaron ni debilitaron. git diff --numstat 251af80: 148 lineas mas y 17 menos en src y config (menos de 400). Lei el diff completo: el dominio (image_detection, severity) solo importa stdlib y src.domain; la aplicacion (analyze_image) no importa adaptadores; ImageAnalyzer en adaptadores con tomllib; sha256 extraido a hashing.py sin duplicar (grep: no quedan _sha256 ni BLOQUE_LECTURA en text_analyzer). config/imagen.toml sin hash inventado. py -m pytest -q -m 'not integration and not acceptance': 784 passed, 1 deselected, 0 fallos. Decisiones no fijadas por pruebas: detail siempre con cuenta y orden alfabetico (knife x1), desempate por caja, umbral_minimo 0.25 por defecto. No verificado: lint (ruff no instalado). (4938666) |
| implementacion | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de verificacion | Claude Code (orquestador; subagentes qa-tester y developer general-purpose) | 2026-11-08 | QA (1 ronda, retomado tras corte de sesion) comprobo cada criterio de la parte 1; los que dependen del modelo real y la muestra quedan fuera de esta parte (partes 2 y 3). Hallo D1 (config mal formada da AttributeError/KeyError/TypeError en vez de ValueError) y D2 (regla duplicada de arma degrada la severidad a baja en silencio) y dejo 5 pruebas rojas en fd6f3b6. Reproduje ambos con py -c: D2 daba Severity.BAJA a 0.95, D1 daba AttributeError. El developer corrigio en 1beeb6c (severity.py valida lista, campos y duplicados; ImageSettings valida Mapping y rechaza espacios al borde, R1). git diff fd6f3b6 -- tests: solo una prueba nueva, sin lineas borradas. Tras la correccion: D1 y D2 dan ValueError con mensaje; py -m pytest -q -m 'not integration and not acceptance': 792 passed, 0 fallos. Parte: 191 lineas en src y config. Sin mediciones de SO en el SPEC. Observaciones menores sin corregir: caja x2<x1, label vacio, mapa guardado por referencia; tipos numpy para la parte 2. No verificado: lint (ruff no instalado). (1beeb6c) |
| verificacion | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de documentacion | Claude Code (orquestador; subagente documentador general-purpose) | 2026-11-08 | git diff cf47823..802c592: solo docs (ARQUITECTURA, CONTRATOS, REQUERIMIENTOS, SPEC; 15 lineas mas y 6 menos). Contrasté con el código: image_detection, analyze_image, hashing e imagen.toml existen en src y config; la tabla de capas de ARQUITECTURA §4 y la fila de dueños de CONTRATOS los listan sin perder entradas previas (texto.toml sigue). AD-27 sigue provisional con medición pendiente. SUP-22 pierde la marca de confirmación porque José Andrés aprobó el plan. La sección Pendientes para la parte 2 del SPEC coincide con las observaciones de QA. Sin fichas de medición (el SPEC no las tiene). El documentador reporta conformidad repo 0 problemas y 792 passed. Borrador de bitácora revisado: errores D1, D2, R1, mutaciones y el carácter rechazado por aprobar, con commits reales. Pendiente humano: avisar a Kenni del cambio de validación en severity.py (CONTRATOS lo pide por F-14). (802c592) |
| documentacion | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de revision | Claude Code (orquestador; subagente revisor general-purpose) | 2026-11-08 | Revisor independiente: APROBADO sin bloqueantes; criterio a criterio contra el SPEC de la parte 1, pytest 792 passed, conformidad 0 problemas, commits validos. Lo comprobé yo: git diff --name-only 5327f5a..7e694b7 solo trae archivos de la parte 1 y documentos, nada de las partes 2 y 3; 174 lineas mas y 17 menos en src y config; git diff 09d2bb4 -- tests sin lineas borradas; releí image_analyzer.py:20-25 y confirmé N3 (sin clases o sin umbral_minimo se usan valores por defecto sin aviso). No bloqueantes: N1 ambito refactor(F-07) en e7bd288; N2 aviso a Kenni por severity.py pendiente (accion humana); N3 valores por defecto silenciosos, a considerar en la parte 2; N4 test_severity.py sin salto de linea final. (7e694b7) |
| revision | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de tests | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-08 | git diff f18cb6e..dc1857d: solo tests (4 archivos, 346 lineas nuevas, 0 borradas en los archivos existentes). py -m pytest -q -m 'not integration and not acceptance' ignorando test_yolo_detector.py: 10 failed, 793 passed; los 10 son DID NOT RAISE de caja invertida, etiqueta, N3 y la mutacion del mapa, por validaciones que faltan. test_yolo_detector.py falla al cargar con ModuleNotFoundError de src.adapters.yolo_detector. La integracion se salta porque ultralytics no esta instalado. Leí las pruebas de sha256: ninguna fija un hash concreto; test_config_del_repositorio_fija_los_pesos_con_su_sha256 exige un hash de 64 hex en config/imagen.toml, que solo se puede calcular sobre el archivo yolo11n.pt descargado (decision pendiente de la persona antes de implementar). N3 esta fuera del SPEC original, pero lo pidio la revision para la parte 2. (dc1857d) |
| tests | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de implementacion | Claude Code (orquestador; subagente developer general-purpose) | 2026-11-08 | git diff 9455ea4 -- tests vacio (0 bytes): no se tocaron ni debilitaron pruebas. git diff --numstat 9455ea4: 91 lineas mas y 6 menos fuera de tests y docs. Leí el diff completo: yolo_detector.py en adaptadores, con importacion diferida de ultralytics y cita de Ultralytics y AGPL-3.0; el dominio y la aplicacion no importan terceros. config/imagen.toml fija el sha256 0ebbc80d que calculé con sha256sum sobre yolo11n.pt de la release v8.4.0 (5613764 bytes), y coincide con el digest de GitHub. *.pt en .gitignore; los pesos no estan en el repositorio. Confirmé ultralytics 8.4.208 con pip index versions. py -m pytest -q -m 'not integration and not acceptance': 821 passed, 1 skipped (la integracion, porque ultralytics no esta instalado). No verificado: YOLO real e integracion, wheels de torch 2.15.0 y ultralytics para Python 3.13, lint (ruff no instalado). (73f32ef) |
| implementacion | José Andrés Loría Herrera | 2026-11-08 |  |
| verificación IA de verificacion | Claude Code (orquestador; subagente qa-tester general-purpose) | 2026-11-08 | QA (1 ronda, sin instalar ultralytics por acuerdo con la persona) comprobo cada criterio de la parte 2 y recalculo el SHA-256 de yolo11n.pt (0ebbc80d, 5613764 bytes), que coincide con config/imagen.toml. Hizo 19 mutaciones: 14 detectadas, 4 equivalentes y 1 que sobrevivia (sin rechazar resultados vacios), que ahora detecta la prueba de 080eddb (solo agrega 15 lineas en tests). Sin defectos en el alcance. Reproduje sus riesgos con un modelo falso via py -c: cls fuera de names da KeyError 99, coordenada inf da OverflowError y -0.6 da ValueError por la caja (-1,2,3,4). py -m pytest -q -m 'not integration and not acceptance': 822 passed, 1 skipped (integracion). No verificado: YOLO real (parte 3), que excepcion lanza ultralytics 8.4.208 ante un archivo corrupto, y wheels para Python 3.13. (080eddb) |
