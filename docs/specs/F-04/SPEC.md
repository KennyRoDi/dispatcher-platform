# SPEC F-04: Verdad de referencia y procedencia

**Fase:** revision
**Base:** feat/F-04-1-verdad-de-referencia-y-procedencia
**Verificación IA:** revision 725a9d2
**Historia:** US-04 · **Requisitos:** RF-23, RNF-04, RNF-05, RNF-06 · **Responsable:** K

## Objetivo

El evaluador obtiene dos comprobaciones que hoy no existen en el repo: (1) cuántos aciertos y errores tiene el análisis por categoría frente a una verdad de referencia, y (2) si cada fuente del dataset declara origen y licencia admitidos. El enunciado exige «etiquetas esperadas (*ground truth*) para al menos una muestra, de modo que se puedan reportar aciertos y errores del análisis» y que `docs/dataset.md` declare «la procedencia y licencia de cada fuente de datos» [B.3 Dataset mínimo, B.3 Consideraciones éticas]. Sin ambas comprobaciones, la calidad del análisis queda sin evidencia (Parte I §5) y una fuente sin licencia podría entrar al dataset sin que nadie lo detecte (RNF-04, RNF-05, RNF-06).

F-03 dejó el manifiesto con `etiqueta`, `categoria`, `positivo`, `origen`, `licencia` y `semilla`. Su validador solo admite `origen = sintetico` y `licencia = MIT`, y cuenta mínimos. F-04 agrega la parte general: admite también fuentes propias y públicas con licencia documentada, y compara salidas contra etiquetas. El comparador recibe las salidas como dato: no ejecuta modelos ni inventa resultados.

## Alcance

**Incluye:**
- **Comparador** (dominio puro): dadas las etiquetas esperadas por elemento y las categorías obtenidas por el análisis, reporta por categoría verdaderos positivos (VP), falsos positivos (FP), falsos negativos (FN) y verdaderos negativos (VN), con aciertos (VP + VN), errores (FP + FN), precisión y exhaustividad (`None` si el denominador es 0), y la exactitud global. Mismo criterio que `scripts/aciertos_imagen.py` (F-08), pero genérico y reutilizable.
- **Validador de procedencia y licencia** (dominio puro): cada fuente debe tener un origen admitido (`sintetico`, `propio` o `publico`) y una licencia no vacía; una fuente `publico` exige además una licencia de una lista admitida (SUP-27). Una fuente sin licencia hace fallar la validación. Devuelve todos los defectos, no solo el primero.
- **Forma de la muestra etiquetada**: un JSON propio de F-04 (ver Diseño) y una conversión desde las filas de imagen del manifiesto de F-03 (`positivo` → `{categoria}`, `neutro` → `{}`).
- **Lectores y CLI** `scripts/dataset_verdad.py`: `procedencia` valida el manifiesto o una muestra; `comparar` valida la procedencia de la muestra, lee las salidas del análisis desde un JSON y escribe la tabla en texto o Markdown.
- Registro de la decisión (AD-32) y de los supuestos (SUP-26, SUP-27) en `docs/ARQUITECTURA.md` §8 y `docs/REQUERIMIENTOS.md`.
- Sección de procedencia y licencia por fuente en `docs/dataset.md`, con el recuento real del manifiesto de F-03. La tabla de aciertos solo se escribe si existe una salida real de análisis sobre la muestra; si no, queda marcada «pendiente».

**No incluye:**
- Ejecutar o cargar modelos de texto, imagen o audio, ni entrenar [B.1]. Producir las salidas del análisis es de F-07 a F-09 (José Andrés); F-04 solo las lee como dato.
- Inventar, estimar o simular resultados de análisis. Los datos de las pruebas son dobles de prueba y se declaran como tales; no son mediciones.
- Cambiar `scripts/aciertos_texto.py`, `scripts/aciertos_imagen.py`, `scripts/comparar_transcripcion.py` ni el validador de mínimos de F-03 (`validate_manifest`). Migrarlos al comparador común, si se decide, es otra feature.
- Etiquetar nuevas imágenes, audios o chats, ni descargar datasets públicos. El dataset de F-03 es sintético y se mantiene así.
- Validar mínimos de B.3 (cantidad de casos, mensajes, etc.): ya lo hace F-03.
- Mediciones de SO.

## Criterios de aceptación

Copiados de `docs/backlog/recepcion-dataset.md`:

- **Dado** el manifiesto con etiquetas, procedencia y licencia
- **Cuando** se comparan las salidas con las etiquetas
- **Entonces** se reportan aciertos y errores por categoría, y una fuente sin licencia hace fallar la validación

Derivados del enunciado y de este diseño:
- Una muestra con una fuente sin licencia, con licencia en blanco o con un origen no admitido hace que `comparar` termine con código 1 sin calcular nada (RNF-04, RNF-05, RNF-06).
- Un elemento etiquetado sin salida, una salida sin etiqueta o un elemento repetido es un error explícito, no un cero silencioso: nunca se completan resultados.
- Una exactitud, precisión o exhaustividad sin denominador se informa como no definida (`None` o `n/d`), no como 0 ni como 1.

## Diseño

**Contratos de `docs/CONTRATOS.md`.** Usa `Finding` (compartido, solo lectura: `category`) para convertir hallazgos en categorías obtenidas. No implementa ni modifica ningún contrato, no agrega puertos y no depende de otro responsable: el comparador recibe datos, no un `Analyzer`. Para pruebas usa `Finding` reales y no necesita un doble nuevo; si una prueba de la CLI requiere un archivo de salidas, lo crea en `tmp_path`.

**Capas y archivos (todos nuevos y de Kenni).**
- Dominio, `src/domain/ground_truth.py`: `GroundTruthItem(item_id, expected: frozenset[str])`, `ObservedItem(item_id, observed: frozenset[str])`, `observed_from_findings(item_id, findings)`, `CategoryScore(category, tp, fp, fn, tn)` con las propiedades `hits`, `errors`, `precision`, `recall`, `Comparison(scores, total, exact_matches)` con `accuracy`, y `compare(truth, observed, categories=None) -> Comparison`. Sin E/S, sin reloj, sin red. `accuracy` = `exact_matches / total` es global: cuenta los elementos cuyo conjunto obtenido coincide exactamente con el esperado e ignora `categories`. Con `total` 0 hoy lanza `ZeroDivisionError` (el criterio pide «no definida»): hallazgo de QA abierto, xfail estricto en `tests/unit/test_ground_truth_qa.py`. Si los `item_id` repetidos son de tipos mezclados, `sorted` da `TypeError` en vez de `ValueError` (xfail en el mismo archivo). Orden de las categorías: alfabético; si `categories` es `None`, es la unión de las esperadas y las obtenidas. `ValueError` si la muestra está vacía, si hay `item_id` repetidos, si un elemento no tiene salida o una salida no tiene etiqueta.
- Dominio, `src/domain/provenance.py`: `SourceRecord(path, origin, license)`, `ProvenancePolicy(admitted_origins, public_licenses, rejected_licenses)` con los valores por defecto de SUP-27 y `validate_provenance(records, policy=ProvenancePolicy()) -> list[str]`, con el mismo formato de mensajes que `validate_manifest` de F-03 (`<ruta>: <defecto>`). `SourceRecord` y `ProvenancePolicy` son dataclasses congeladas; `origin` y `license` aceptan `str | None`. Compara origen y licencia sin distinguir mayúsculas (`casefold`) ni espacios exteriores. Un origen no admitido y una licencia en blanco o de relleno son defectos distintos: una fuente con ambos da dos mensajes, uno por defecto.
- Adaptadores, `src/adapters/dataset_truth_files.py`: leen el manifiesto de F-03, la muestra y las salidas desde JSON y construyen los tipos de dominio; rechazan con `ValueError` rutas absolutas, con `..` o con `\x00`, y campos que no sean escalares. Un campo de origen o licencia ausente se convierte en `None`, para que lo reporte el validador y no el lector. `sample_from_manifest(rows)` convierte solo las filas de `imagen` con `categoria` y `etiqueta` (`positivo` → `{categoria}`, `neutro` → `{}`); las demás no tienen verdad de contenido. `render_markdown(comparison)` y `render_text(comparison)` formatean la tabla.
- Entrada, `scripts/dataset_verdad.py`: subcomandos `procedencia` y `comparar`; solo analiza argumentos y orquesta los demás módulos. Usa `Path` y no escribe fuera de `--salida`.

**Forma de la muestra etiquetada** (`muestra_etiquetada.json`, lista de objetos):

```json
[{"path": "imagenes/objetos_001.png", "kind": "imagen", "origen": "sintetico", "licencia": "MIT", "esperadas": ["objetos"]}]
```

`esperadas` vacía significa «sin contenido de ninguna categoría» (negativo). `path` es relativo y único. El archivo de salidas del análisis es otra lista, `[{"path": "...", "categorias": ["..."]}]`, producida fuera de F-04.

**Qué mide la comparación sobre el dataset sintético.** Las imágenes de F-03 son colores sólidos y sus categorías (`objetos`, `paisajes`, `documentos`, `personas`) son las del generador, no las de un detector. Comparar con ellas valida el mecanismo, no la calidad de un modelo. La calidad real se reporta con muestras propias o públicas con licencia documentada (por ejemplo, las 20 imágenes de F-08), cuando existan sus salidas como dato.

**Decisiones.**
- AD-32 (nueva, se propone aquí y se registra en `docs/ARQUITECTURA.md` §8 en la parte 1): comparador y validador de procedencia en dominio puro, con entrada por datos. Alternativas: ampliar `validate_manifest` de F-03 (mezcla mínimos con procedencia y la deja atada a `ffmpeg`); un comparador que ejecute los analizadores (acopla F-04 a F-07 a F-09 y a modelos pesados). Criterio: «módulos independientes» y pruebas sin red, reloj ni modelos. Fuente: [B.3]; `docs/specs/F-03/SPEC.md`.
- SUP-26 (supuesto): la verdad de referencia mínima de B.3 («al menos una muestra») se cumple con una muestra de imágenes etiquetadas; texto y audio se agregan solo si existen etiquetas con procedencia y licencia declaradas. Los tonos y el ruido del dataset sintético son una etiqueta de origen del audio, no de contenido, y no entran a la comparación.
- SUP-27 (supuesto, provisional): orígenes admitidos `sintetico`, `propio` y `publico`; una licencia en blanco o con un valor de relleno (`desconocida`, `ninguna`, `sin licencia`, `n/a`, `-`) se rechaza; una fuente `publico` exige una de `CC0-1.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `MIT`, `Apache-2.0`. El enunciado dice «licencia que permita su uso académico» sin enumerarlas; la lista la confirma la persona.

**Límites declarados de la parte 2.** El validador hace menos de lo que parece; cada punto tiene un xfail estricto en `tests/unit/test_provenance_qa.py` (11 casos) o es una observación de QA sin prueba:
- **Entradas que no son texto.** Un `origin` o `license` que no sea `str` ni `None` (`5`, `b"MIT"`, `["MIT"]`) lanza `AttributeError` opaco, sin la ruta de la fuente (xfail, 5 casos). La parte 3, que lee JSON, debe rechazarlos con `ValueError` antes de construir el `SourceRecord`.
- **Solo espacios exteriores.** Se recorta con `str.strip`; un relleno con espacio interior doble, NBSP o tabulador (`sin  licencia`) pasa como licencia válida (xfail, 3 casos).
- **Caracteres invisibles.** Una licencia de solo `U+200B` o `U+FEFF` no cuenta como vacía y pasa (xfail, 3 casos).
- **Rellenos fuera de la lista.** `N/A.`, `unknown` y `none` pasan con origen `sintetico` o `propio`, porque `rejected_licenses` es una lista cerrada que se amplía por política; solo una fuente `publico` los rechaza, y por no estar en `public_licenses`. Es consecuencia de SUP-27, que sigue provisional.
- **`ProvenancePolicy` sin validación de tipos.** Una cadena en `admitted_origins` se recorre por caracteres (`"sintetico"` rechaza todo origen); un elemento no `str` (p. ej. `5`) da `AttributeError`; un `None` o un elemento vacío en `admitted_origins` se normaliza a `""` y admite en silencio un origen vacío, y en `rejected_licenses` no falla. No hay prueba.

**Reutilización.** Del I Proyecto no se toma código. Del repo se reutilizan `Finding` y las constantes de `src/adapters/media_generator.py` (`ORIGIN`, `LICENSE_NAME`, `POSITIVE`, `NEUTRAL`) solo en el adaptador, no en el dominio. El criterio VP/FP/FN/VN sigue a `scripts/aciertos_imagen.py`; no se importa.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_comparador_reporta_aciertos_y_errores` | Con 4 elementos y salidas conocidas, VP, FP, FN y VN por categoría coinciden con el cálculo a mano; aciertos = VP + VN y errores = FP + FN |
| Unitaria | `test_comparador_incluye_categorias_sin_ocurrencias` | Una categoría pasada en `categories` y ausente de los datos aparece con ceros |
| Unitaria | `test_comparador_precision_y_exhaustividad_indefinidas_son_none` | Sin positivos obtenidos o esperados no hay división entre 0 |
| Unitaria | `test_comparador_exactitud_global` | `accuracy` es la fracción de elementos sin ningún error, y no depende del orden de entrada |
| Unitaria | `test_comparador_rechaza_muestra_vacia_repetidos_y_salidas_faltantes` | Muestra vacía, `item_id` repetido, elemento sin salida y salida sin etiqueta dan `ValueError`; nunca se completa |
| Unitaria | `test_salidas_desde_hallazgos_usan_la_categoria` | `observed_from_findings` toma `Finding.category` y colapsa repetidas |
| Unitaria | `test_fuente_sin_licencia_falla_validacion` | Licencia `None`, `""` o `"  "` produce un defecto con la ruta de la fuente |
| Unitaria | `test_licencia_de_relleno_falla_validacion` | `desconocida`, `N/A` y `-` se rechazan sin distinguir mayúsculas |
| Unitaria | `test_origen_no_admitido_falla_validacion` | `real`, `tercero`, `None` y `""` se rechazan (RNF-04) |
| Unitaria | `test_fuente_publica_exige_licencia_admitida` | `publico` con `CC-BY-NC-4.0` falla; con `CC-BY-4.0` pasa |
| Unitaria | `test_fuentes_sinteticas_y_propias_con_licencia_pasan` | Sin falsos rechazos para `sintetico`/`MIT` y `propio`/`CC-BY-4.0` |
| Unitaria | `test_validador_reporta_todos_los_defectos` | Con 3 fuentes malas se devuelven 3 mensajes, uno por fuente, en orden |
| Unitaria | `test_lectores_rechazan_rutas_peligrosas_y_formatos_invalidos` | Ruta absoluta, `..`, `\x00`, no lista y valores no escalares dan `ValueError` |
| Unitaria | `test_sample_from_manifest_solo_convierte_imagenes_con_etiqueta` | `positivo` da `{categoria}`; `neutro`, `{}`; texto, audio, video y documento se omiten |
| Unitaria | `test_acepta_el_manifiesto_que_genera_f03` | Filas con los campos de `MANIFEST_FIELDS` (armadas con `build_manifest` de F-03 y un ejecutor falso, sin `ffmpeg`) pasan el validador |
| Unitaria | `test_cli_procedencia_termina_en_1_con_fuente_sin_licencia` | `main([...])` devuelve 1, imprime la ruta defectuosa y 0 si todo cumple |
| Unitaria | `test_cli_comparar_no_calcula_si_la_muestra_falla_procedencia` | Código 1 y sin tabla |
| Integración | No aplica | No hay red, servicios ni procesos externos; los lectores y la CLI se prueban con `tmp_path` en las unitarias |
| Aceptación | `test_comparacion_sobre_la_muestra_etiquetada` | De punta a punta con `main(["comparar", ...])`: una muestra derivada del manifiesto sintético y salidas de prueba (dobles, declaradas como tales) producen la tabla con aciertos y errores por categoría y código 0. Si existe un manifiesto real en `DATASET_OUT`, también corre `procedencia` sobre él (se omite si no existe, como `test_dataset_completo.py`) |

## Mediciones

No aplica. F-04 no mide el sistema operativo. La tabla de aciertos es un resultado funcional de calidad del análisis y solo se publica con salidas reales.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-04): comparador de aciertos y errores por categoría` | `src/domain/ground_truth.py` (≈ 110 líneas) y sus pruebas. Documentos: registro de AD-32 en `docs/ARQUITECTURA.md` §8 y de SUP-26 y SUP-27 en `docs/REQUERIMIENTOS.md` |
| 2 | `feat(F-04): validador de procedencia y licencia` | `src/domain/provenance.py` (≈ 90 líneas) y sus pruebas |
| 3 | `feat(F-04): lectores, CLI de procedencia y comparación` | `src/adapters/dataset_truth_files.py` y `scripts/dataset_verdad.py` (≈ 250 líneas), pruebas unitarias de la CLI y la prueba de aceptación |
| 4 | `docs(F-04): procedencia por fuente y tabla de aciertos en dataset.md` | Sección de procedencia y licencia con el recuento real del manifiesto de F-03 y la salida real de `procedencia`. La tabla de aciertos va solo si hay salidas reales de análisis sobre la muestra; si no, queda «pendiente: sin salidas reales de análisis». Bitácora de IA |

Las partes 1 y 2 son independientes entre sí; la 3 depende de ambas. Si la parte 3 supera 400 líneas, se divide en lectores y CLI.

## Riesgos y preguntas abiertas

**Riesgos.**
- **Comparación sin significado sobre el dataset sintético.** Las categorías de las imágenes de F-03 no son las de ningún detector y las imágenes son colores sólidos; un porcentaje obtenido ahí no mide calidad. Mitigación: la sección de Diseño y `docs/dataset.md` lo declaran; la tabla se publica con muestras propias o públicas con licencia.
- **Muestra pequeña.** Los datos reales actuales son 20 imágenes (F-08) y 40 mensajes (F-07): sirven para reportar aciertos y errores, no para afirmar precisión general. Toda tabla debe indicar el tamaño de la muestra.
- **Duplicación con `aciertos_imagen.py` y `aciertos_texto.py`** (de José Andrés). Se deja sin tocar para no invadir su módulo; queda dos veces la lógica de VP/FP/FN/VN hasta que se decida migrar.
- **Lista de licencias (SUP-27).** Una lista errónea acepta una fuente que el profesor no admite, o rechaza una válida. Es provisional.
- **Solapamiento con `validate_manifest` de F-03**, que ya rechaza todo origen distinto de `sintetico`. Los dos coexisten: el de F-03 es estricto para el dataset sintético, el de F-04 es el general. Un dataset con fuentes públicas deberá relajar el de F-03.
- **Colisión de identificadores.** SUP-25 ya lo usa la rama de F-19 (aún no fusionada); AD-31 lo usa la rama de F-12 (aún no fusionada), así que este SPEC usa AD-32; SUP-26 y SUP-27 están libres en todas las ramas a la fecha. Si otra rama fusiona antes, se renumera en la parte 1.

**Preguntas abiertas para quien aprueba.**
1. ¿Se confirma la lista de orígenes y licencias de SUP-27, en particular `propio` como origen admitido y si `MIT` y `Apache-2.0` cuentan como licencias de datos?
2. ¿Basta una muestra de imágenes como «al menos una muestra» de verdad de referencia (SUP-26), o se quiere también una de texto o de audio en esta feature?
3. Para la tabla de la parte 4: ¿se transcriben a un JSON de salidas las respuestas ya medidas en `docs/evidencia/F-08_aciertos_2026-11-09.md` (con su origen citado), o se espera a que José Andrés entregue las salidas en el formato de F-04? Sin una de las dos, la tabla queda «pendiente».
4. ¿Dónde se guarda la muestra etiquetada real: `tests/datos/` (versionada, solo si es pequeña y con licencia) o `dataset/` fuera del repo?
5. ¿Se acepta dejar sin migrar los scripts `aciertos_*` al comparador común?

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador Sonnet 5.5; subagente arquitecto general-purpose) | 2026-11-10 | SPEC F-04 sin campos pendientes (grep), solo toca el SPEC respecto a F-03 parte 8, commit empujado. SUP-26/27 y AD-32 sin uso en origin/main (grep). Preguntas abiertas registradas en CLAUDE.md con decision provisional. No ejecute pruebas (sin codigo). (dd607f2) |
| plan | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de tests | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-10 | Solo tests/unit/test_ground_truth.py (mas log del SPEC). pytest da ModuleNotFoundError src.domain.ground_truth (rojo por falta del modulo). Cubre VP/FP/FN/VN, precision/exhaustividad None, exactitud, ValueError y Finding. Sin codigo de implementacion. (d6a4d71) |
| tests | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de implementacion | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-10 | Solo src/domain/ground_truth.py (92 lineas); tests intactos. Ejecute test_ground_truth + test_arquitectura: verdes. Desviacion aceptada: campo exact_matches y accuracy por coincidencia exacta del conjunto (lo exigen las pruebas). No corri la suite completa (1649 passed segun el developer). (73a68be) |
| implementacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de verificacion | Claude Code (orquestador Sonnet 5.5; subagente qa-tester general-purpose) | 2026-11-10 | QA: 2 xfail estrictos nuevos (accuracy con total 0, ids de tipos mezclados) en test_ground_truth_qa.py; src intacto. Ejecute test_ground_truth y _qa: 14 pasan/xfail segun lo esperado. Hallazgos menores a pendientes; accuracy global se declara en documentacion. No repeti la prueba de 200000 elementos (dato del QA). (b0f1c19) |
| verificacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de documentacion | Claude Code (orquestador Sonnet 5.5; subagente documentador general-purpose) | 2026-11-10 | Diff solo toca ARQUITECTURA (AD-32), REQUERIMIENTOS (SUP-26/27 provisional) y SPEC. conformidad.py: 0 problemas (ejecutado por mi). Numeros libres en main segun grep del documentador. No repeti pytest (solo docs). (8095761) |
| documentacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de revision | Claude Code (orquestador Sonnet 5.5; subagente revisor general-purpose) | 2026-11-10 | Revisor APROBADO con observaciones. Hallazgo medio (AD-31 usado por la rama de F-12) reproducido con grep en todas las ramas remotas: AD-32 libre; renumerado en ARQUITECTURA y SPEC. conformidad 0 problemas. Revisor ejecuto pytest 1649 passed/5 xfailed (no repetido tras el cambio de texto). (bb7a2ce) |
| revision | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de tests | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-10 | Solo tests/unit/test_provenance.py (mas log del SPEC); pytest da error de coleccion ModuleNotFoundError src.domain.provenance (rojo por falta del modulo). Decisiones del developer: origen en blanco se rechaza; una fuente con dos defectos da un mensaje por defecto. test_acepta_el_manifiesto_que_genera_f03 queda para la parte 3. (20a2779) |
| tests | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de implementacion | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-10 | Solo src/domain/provenance.py (61 lineas); tests intactos. Ejecute la suite completa: ver salida de pytest registrada en el informe de fase. (0f8345e) |
| implementacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de verificacion | Claude Code (orquestador Sonnet 5.5; subagente qa-tester general-purpose) | 2026-11-10 | QA: 11 casos xfail estrictos en test_provenance_qa.py; src intacto. Ejecute test_provenance y _qa: pasan/xfail segun lo esperado. Hallazgos (no str, espacios interiores, U+200B) a pendientes y SPEC; la parte 3 debe rechazar no str. No reproduje las observaciones sin xfail. (99b0f6f) |
| verificacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de documentacion | Claude Code (orquestador Sonnet 5.5; subagente documentador general-purpose) | 2026-11-10 | Diff solo toca el SPEC; limites de la parte 2 presentes (grep); conformidad 0 problemas (ejecutado por mi). SUP-27 sigue provisional. Sin pytest nuevo (solo docs). (abcaf2a) |
| documentacion | Kenni Rodriguez | 2026-11-10 | aprobacion delegada: la persona autorizo trabajar sin aprobaciones por fase hasta su regreso |
| verificación IA de revision | Claude Code (orquestador Sonnet 5.5; subagente revisor general-purpose) | 2026-11-10 | Revisor DEVUELTO por un limite falso en SPEC:75 (None da TypeError); reproducido: ProvenancePolicy(admitted_origins=(None,)) admite origen vacio sin error; SPEC corregido. Revisor reprodujo pytest 1669 passed/16 xfailed y conformidad 0 problemas; resto de limites veraces. (725a9d2) |
