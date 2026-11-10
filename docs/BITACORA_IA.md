# Bitácora de uso de IA

Registro del uso de IA, con el formato del Anexo 3 [Parte I §4]. Lo escribe `python scripts/flujo.py bitacora`; las entradas no se editan a mano salvo para corregirlas. Cada responsable principal revisa las suyas.

## 2026-11-03 · Kenni Rodriguez · Planificación (`docs/planificacion`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5; subagente con Claude Haiku para explorar el repositorio |
| Componente | Requisitos, arquitectura, plan de implementación y backlog (M1–M5 y pipeline) |
| Propósito | Explorar alternativas técnicas y redactar los documentos de planificación |
| Consulta resumida | Generar requisitos trazables, arquitectura ADD, plan FDD y TDD, y backlog a partir del enunciado y del I Proyecto |
| Resultado obtenido | `REQUERIMIENTOS.md`, `ARQUITECTURA.md`, `IMPLEMENTACION.md` y `BACKLOG.md`, con supuestos marcados |
| Validado / corregido / descartado | Aceptados como propuesta. Las decisiones que dependen de un dato siguen provisionales hasta medirlo. La asignación de módulos sigue sin confirmar |
| Cómo se validó | Script de trazabilidad sobre citas, módulos, hitos y escenarios; lectura en el código del I Proyecto de lo afirmado por el subagente; validación de sintaxis de diagramas con `mermaid` |
| Error de la IA | Citó «unas 387 pruebas» del I Proyecto a partir del conteo de `def test_`. Al ejecutar `pytest` hubo 474 casos, por las pruebas parametrizadas. Corregido en AD-01 |

## 2026-11-03 · Kenni Rodriguez · Ciclo de trabajo (`chore/flujo-agentes`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | `scripts/flujo.py`, comandos y roles de agentes, `CONTRIBUTING.md` |
| Propósito | Automatizar un ciclo común para Claude Code, Codex, Antigravity y personas |
| Consulta resumida | Crear comandos `empezables`, `trabajar` y `cierre`, PR apiladas, fases con aprobación y estado derivado |
| Resultado obtenido | Script con pruebas, plantillas, skills y roles |
| Validado / corregido / descartado | Aceptado. Se descartó el tablero editado a mano en favor de un estado derivado |
| Cómo se validó | `pytest`; ciclo completo en un clon desechable con remoto local y `gh` falso; `claude -p` y `agy -p` confirmaron la carga de reglas y comandos. Codex no se probó |
| Error de la IA | La primera prueba de punta a punta no ejecutó nada: una variable con espacios no se separa en zsh. Se detectó al leer su salida y se repitió usando funciones |
| Error de la IA | La descripción YAML de un comando contenía `: ` sin comillas, lo que la invalidaba. Se detectó al releer el archivo y se puso entre comillas |

## 2026-11-03 · Kenni Rodriguez · Integración en main (`chore/flujo-agentes`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Repositorio: importación del I Proyecto y fusión de PR |
| Propósito | Importar el I Proyecto con su historial y dejar `main` actualizado |
| Consulta resumida | Fusionar todas las PR en `main` |
| Resultado obtenido | PR #2 a #6 fusionadas |
| Validado / corregido / descartado | Corregido: se abrió la PR #6 para llevar el contenido a `main` |
| Cómo se validó | `git rev-list --count origin/main..chore/flujo-agentes` dio 0, sin diferencias de archivos, y `flujo.py empezables` funcionó contra GitHub |
| Error de la IA | `gh pr edit --base main` falló y su salida estaba descartada, por lo que las PR #3, #4 y #5 se fusionaron en sus ramas apiladas y no en `main`. Se detectó al comparar `main` con la pila |

## 2026-11-03 · Kenni Rodriguez · Orquestador (`chore/orquestador`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | `scripts/flujo.py`, rol de orquestador y comando `trabajar` |
| Propósito | Sumar una verificación de IA a la aprobación humana en cada fase |
| Consulta resumida | Agregar un orquestador que vigile a los subagentes antes de pedir aprobación |
| Resultado obtenido | Rol de orquestador y comando `verificar`; `aprobar` exige una verificación vigente |
| Validado / corregido / descartado | Aceptado. Limitación declarada: sin subagentes, la verificación no es independiente |
| Cómo se validó | `pytest` y ciclo completo en un clon desechable con remoto local y `gh` falso |

## 2026-11-03 · Kenni Rodriguez · Conformidad en GitHub (`chore/conformidad`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | `scripts/conformidad.py` y workflow de GitHub Actions |
| Propósito | Verificar en GitHub que todos sigan el mismo patrón y estén las piezas |
| Consulta resumida | Agregar workflows y checks de patrón y completitud, sin compilar el código |
| Resultado obtenido | Workflow `conformidad` con comprobaciones de repositorio y de PR |
| Validado / corregido / descartado | Aceptado. El registro de aprobaciones demuestra que se ejecutó el comando, no quién respondió |
| Cómo se validó | `pytest` y ejecución local de ambos modos sobre el repositorio |

## 2026-11-03 · Kenni Rodriguez · Checks por PR (`ci/checks-por-pr`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Workflows `pr` y `ci`, `scripts/conformidad.py` |
| Propósito | Mostrar en cada PR un check separado por regla |
| Consulta resumida | Dividir la conformidad en checks con nombre, sin revisión humana |
| Resultado obtenido | Ocho checks de PR y tres de repositorio |
| Validado / corregido / descartado | Aceptado. Se descartó marcarlos como requeridos porque `main` no tiene protección |
| Cómo se validó | `pytest`, ejecución local y corrida real en la PR |
| Error de la IA | Interpretó «checks» como git hooks locales; el usuario aclaró con una captura que se refería a checks de PR en GitHub |

## 2026-11-03 · Kenni Rodriguez · Protección de main (`ci/checks-por-pr`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | `scripts/flujo.py`, `scripts/conformidad.py`, protección de `main` |
| Propósito | Exigir los checks para fusionar sin romper la publicación de estado y bitácora |
| Consulta resumida | Proteger `main` para fusionar solo con los checks aprobados |
| Resultado obtenido | Estado y bitácora publicados en la rama `estado`; `main` con checks requeridos |
| Validado / corregido / descartado | Aceptado |
| Cómo se validó | `pytest`, corrida real de los checks y lectura de la protección por API |
| Error de la IA | Configuró Python 3.12 en CI, pero el código heredado usa `os.process_cpu_count`, de 3.13. El check `pruebas (pytest)` lo detectó. AD-22 propone 3.12 para workers ML y debe revisarse |

## 2026-11-03 · Kenni Rodriguez · Backlog e identidad (`chore/backlog-por-area`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Backlog e identidad |
| Propósito | Dividir el backlog y mostrar a cada persona sus features |
| Consulta resumida | Dividir el backlog y pedir el usuario de GitHub para filtrar por módulo |
| Resultado obtenido | docs/backlog por área, docs/EQUIPO.md y comando soy |
| Validado / corregido / descartado | Aceptado. La identidad es una declaración, no una autenticación |
| Cómo se validó | pytest, conformidad y clon desechable con remoto local |
| Error de la IA | Un script de migración abortó y aun así se creó un commit parcial local; se descartó y se repitió deteniendo ante fallos. El check de piezas detectó que F-42 quedaba oculta por su responsable y se corrigió |

## 2026-11-03 · Kenni Rodriguez · Auditoría y guía (`chore/auditoria`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Auditoría y guía |
| Propósito | Auditar el flujo antes de abrirlo al equipo y escribir la guía |
| Consulta resumida | Auditar flujo, integridad y comandos; generar una guía para contribuir |
| Resultado obtenido | Hallazgos corregidos, comando fusionar y docs/GUIA.html |
| Validado / corregido / descartado | Aceptado. Comandos probados contra GitHub real con features desechables |
| Cómo se validó | Clon limpio, ciclo real con PR apilada y 11 checks, retirada de datos de prueba, pytest |
| Error de la IA | CONTRIBUTING.md afirmaba que GitHub cambia la base de una PR apilada al borrar la de abajo; la prueba real mostró que la cierra. También pedía Python 3.10 y AD-22 proponía 3.12, cuando el código requiere 3.13 |

## 2026-11-03 · Kenni Rodriguez · Base del equipo (`main`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Base del equipo |
| Propósito | Dejar la base para que el equipo trabaje en paralelo |
| Consulta resumida | Preparar la base para empezar a contribuir, con la distribución aceptada |
| Resultado obtenido | Coordinador dividido, contratos compartidos y matriz de responsabilidades |
| Validado / corregido / descartado | Aceptado. Los contratos son una primera versión que los responsables pueden ajustar |
| Cómo se validó | OpenAPI idéntico antes y después, 11 checks en cada PR y pytest |
| Error de la IA | Al dividir el coordinador quedaron nombres sin definir (_REDIS_HOST); pyflakes y 3 pruebas lo detectaron antes de publicar |

## 2026-11-03 · Kenni Rodriguez · Auditoría de inicio (`chore/backlog-sin-bloqueos`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Auditoría de inicio |
| Propósito | Comprobar que el equipo pueda empezar sin esperar a nadie |
| Consulta resumida | Auditar comandos, workflows y la base de trabajo de cada integrante |
| Resultado obtenido | Dependencias relajadas, comandos endurecidos y PR apilada probada con fusionar |
| Validado / corregido / descartado | Aceptado. Las dependencias relajadas exigen integrar después con los escenarios F-33 a F-37 |
| Cómo se validó | Clon limpio, PR malas rechazadas por los checks, claude -p y agy -p, grafo del backlog y enlaces |
| Error de la IA | Las dependencias del backlog se fijaron antes de existir los contratos y dejaban a Melany sin tareas; además el número de parte se podía reutilizar tras fusionar y borrar ramas, lo que permitía reusar una entrada de bitácora |

## 2026-11-03 · Kenni Rodriguez · Independencia de módulos (`chore/modulos-independientes`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 |
| Componente | Independencia de módulos |
| Propósito | Permitir que cada módulo se desarrolle de principio a fin sin esperar a otro |
| Consulta resumida | Verificar que el backlog no bloquee entre módulos e integrar con ajustes mínimos |
| Resultado obtenido | Contratos ampliados, dobles, pruebas de conformidad, dueños de archivos y un check de independencia |
| Validado / corregido / descartado | Aceptado. Los contratos no eliminan el ajuste de integración: rendimiento, memoria real y red solo se ven en F-33 a F-37 |
| Cómo se validó | Simulación del backlog por persona: todas sus features completables solas; pytest; 11 checks |
| Error de la IA | La auditoría previa declaró resuelto el bloqueo con dejar tareas libres, pero seguían dos dependencias entre módulos, F-15 y F-24, y faltaban contratos para los demás puntos de contacto |

## 2026-11-05 · Kenni Rodriguez · F-38, despliegue en tres nodos, Parte 1: Compose, identidad de nodo, pruebas y guía (`feat/F-38-1-despliegue-en-tres-nodos`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes arquitecto, developer, QA tester y documentador |
| Componente | F-38, despliegue en tres nodos, Parte 1: Compose, identidad de nodo, pruebas y guía |
| Propósito | Levantar cada nodo con Compose, hacer que GET /workers identifique la máquina real y dejar instrucciones y una prueba de aceptación para la Parte 2 |
| Consulta resumida | Diseñar y aplicar el ciclo de seis fases de F-38 para un Nodo A Linux y tres nodos Windows 11 con Docker Desktop sobre WSL2 por Tailscale, y alinear la guía y el contrato del worker |
| Resultado obtenido | SPEC, AD-23 y AD-24; hostname desde NODE_NAME e ip desde NODE_IP; coordinador en el Compose del Nodo A con puertos solo en la IP de Tailscale; imagen Python 3.13; pruebas de configuración y heartbeat; prueba de aceptación; guía de 679 a 421 líneas y contrato actualizado |
| Validado / corregido / descartado | Aceptado tras las correcciones de la fila de errores. Kenni corrigió la topología, confirmó los añadidos del arquitecto y aprobó cada fase. US-38 y RNF-01 no se dan por cumplidos: nada se ejecutó sobre nodos reales |
| Cómo se validó | pytest -q -m 'not integration and not acceptance': 682 passed, 3 skipped, 1 deselected. python -m scripts.conformidad repo: 0 problemas. Lectura de diffs contra el SPEC y contraste con el código. Mutantes de QA y dos del orquestador en copia temporal. Aceptación reproducida con datos sintéticos. Sin comprobar: Docker, Compose, imagen, Tailscale desde WSL2, CLIENT LIST y run_load real |
| Error de la IA | (1) La lógica de aceptación contaba como procesa a un nodo con todas sus sub-tareas fallidas, por usar metrics.subtasks_per_host; lo detectó el orquestador y se corrigió a contar solo completed y a fallar con timed_out. (2) 19 de 50 mutantes sobrevivían a las pruebas de la fase tests, incluidos worker sin env_file e imagen sin COPY scripts; lo detectó QA y añadió 73 líneas de pruebas. (3) El primer SPEC presentaba el proyecto como continuación del I Proyecto y retiraba la cuarta máquina; lo corrigió Kenni. (4) El encargo al arquitecto decía que AD-22 proponía Python 3.12; el arquitecto comprobó que ya decía 3.13. (5) El arquitecto añadió por su cuenta puertos solo en Tailscale y el rango 100.64.0.0/10; el orquestador no los dio por aprobados y Kenni los confirmó |

## 2026-11-05 · Kenni Rodriguez · F-38, despliegue en tres nodos, Parte 1: revisión (`feat/F-38-1-despliegue-en-tres-nodos`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes revisor y documentador |
| Componente | F-38, despliegue en tres nodos, Parte 1: revisión |
| Propósito | Comparar el diff contra el SPEC y corregir los desajustes de documentos antes de abrir la PR |
| Consulta resumida | Revisar el diff de la Parte 1 contra el SPEC, con contexto nuevo, y aplicar los hallazgos en la documentación |
| Resultado obtenido | Primera ronda DEVUELTO con 6 hallazgos de documentos; corregidos en 97219bd; segunda ronda APROBADO. La guía queda en 444 líneas, no en las 421 de la entrada anterior |
| Validado / corregido / descartado | Kenni aprobó la fase. Sin cambios en código ni configuración ejecutable |
| Cómo se validó | Confirmé los hallazgos con sed y grep y leí el delta. pytest -q -m 'not integration and not acceptance': 682 passed, 3 skipped, 1 deselected. conformidad repo: 0 problemas. Sin comprobar: Docker, Compose, imagen, PowerShell, Tailscale y run_load real |
| Error de la IA | El revisor detectó 6 desajustes en la documentación generada por IA: el SPEC decía que el archivo GPU no cambiaba y sus comentarios sí cambiaron; DECISIONES_DISENO seguía con coordinador nativo y Tailscale como plan B; faltaba la lista de comprobación que pedía el SPEC; notepad no bloquea PowerShell y la normalización del .env podía correr antes de editar; el filtro NODE_* daba falsa alarma; faltaban apt-get update y la nota de Python 3.13. Los corrigió el documentador |

## 2026-11-07 · José Andrés Loría Herrera · F-07, worker de texto, Parte 1: análisis por lotes y reglas de severidad (`feat/F-07-1-worker-de-texto`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes arquitecto, developer (4 rondas), QA tester y documentador |
| Componente | F-07, worker de texto, Parte 1: análisis por lotes y reglas de severidad |
| Propósito | Implementar sin modelos reales el analizador de texto por lotes que produce las cuatro salidas de US-07, con severidad por reglas en configuración |
| Consulta resumida | Diseñar el SPEC de F-07 con plan de 3 partes y aplicar en la parte 1 el ciclo de seis fases: pruebas en rojo; dominio, aplicación, adaptador TextAnalyzer y config/texto.toml con parser y modelos falsos; verificación por QA |
| Resultado obtenido | SPEC con AD-26 y plan de 3 partes; pruebas en rojo; text_analysis.py y severity.py en dominio, analyze_text.py en aplicación, TextAnalyzer y config/texto.toml (265 líneas fuera de tests y docs); comprobar_analyzer en tests/contratos.py; suite 744 passed. PR aparte #27, fusionada, con el arreglo de rutas de Windows en tests/test_contract.py, que destrabó la aprobación en Windows |
| Validado / corregido / descartado | Aceptado tras las correcciones de la fila de errores. José Andrés aprobó cada fase. Se pospusieron O2, O4, O5 y O7 a la parte 2. US-07 no se da por cumplida: faltan modelos reales (parte 2) y tabla de aciertos (parte 3) |
| Cómo se validó | py -m pytest -q -m 'not integration and not acceptance': 744 passed. py -m scripts.conformidad repo: 0 problemas. Rojo comprobado contra el código anterior: 21 failed. 12 mutaciones de QA, todas detectadas. Lectura de diffs contra el SPEC. Sin comprobar: modelos reales (parte 2), tabla de aciertos (parte 3) y lint (ruff no instalado) |
| Error de la IA | (1) El orquestador escribió el carácter de puntos suspensivos en su resumen de verificación del plan y flujo.py aprobar lo tomó como campo sin completar; se corrigió la fila (70f4adb) y se reverificó. (2) QA detectó H1: zip en analyze_text.py truncaba en silencio si el modelo devolvía otra cantidad de análisis y podía perder una amenaza de severidad alta; prueba en 1321474, corregido en 09d9cda. (3) La mutación de max a min en la confianza de ofensivo sobrevivía a las pruebas; QA agregó la prueba. (4) QA reportó 7 observaciones; José Andrés decidió corregir en esta parte O6 (tildes y mayúsculas en tema), O1 (config sin regla de amenaza degradaba a baja) y O3 (umbrales fuera de rango) (f2d9c15..d7c5cd9) y posponer O2, O4, O5 y O7 a la parte 2. (5) Al pedir fusionar la PR #27, el orquestador no aclaró antes que tests/test_contract.py era de Kenni; José Andrés lo cuestionó y luego autorizó la fusión |

## 2026-11-07 · José Andrés Loría Herrera · F-07, worker de texto, Parte 2: inferir con spaCy y HuggingFace (`feat/F-07-2-inferir-con-spacy-y-huggingface`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes arquitecto (fase plan compartida), developer (pruebas, implementación y correcciones de QA), QA tester y documentador |
| Componente | F-07, worker de texto, Parte 2: inferir con spaCy y HuggingFace |
| Propósito | Conectar modelos reales ya entrenados al analizador de texto y validar la configuración pospuesta de la parte 1 (O2, O4, O5, O7 y puntajes en [0, 1]) |
| Consulta resumida | Aplicar el ciclo de seis fases a la parte 2: pruebas en rojo con dobles; adaptador SpacyHfTextModels con importación diferida; modelos, revisiones y patrones de amenaza en config/texto.toml; requirements-texto.txt aparte para que CI no instale torch; verificación por QA; documentación y citas de licencias |
| Resultado obtenido | Adaptador src/adapters/spacy_hf_text_models.py (spaCy es_core_news_sm 3.8.0 GPL-3.0; pysentimiento/robertuito-sentiment-analysis y robertuito-hate-speech con revisión fijada, datasets de uso no comercial); config/texto.toml con [modelos.*] y patrón vas_a_ver; requirements-texto.txt con torch 2.15.0 CPU, spacy 3.8.18, transformers 5.22.2 y el wheel del modelo; validaciones O2, O4, O5, O7 y puntajes; 237 líneas fuera de tests y docs; suite 884 passed, 1 skipped. Citas en el código, README y ARQUITECTURA (R11, R12) |
| Validado / corregido / descartado | Aceptado tras las correcciones de la fila de errores. José Andrés aprobó cada fase. QA sin hallazgos H; las observaciones restantes quedan en el SPEC como pendientes para la parte 3. US-07 no se da por cumplida: la prueba de integración nunca se ha ejecutado y falta la tabla de aciertos (parte 3) |
| Cómo se validó | py -m pytest -q -m 'not integration and not acceptance': 884 passed, 1 skipped. py -m scripts.conformidad repo: 0 problemas. Rojo comprobado en fase tests: 68 failed y 1 error de colección, todos de F-07. Lectura de diffs contra el SPEC. Etiquetas hateful/targeted/aggressive contrastadas con config.json de HuggingFace. Sin comprobar: modelos reales (spaCy no instalado; la prueba de integración se salta) y mediciones de SO (no aplican) |
| Error de la IA | (1) El patrón inicial vas_a_ver de config/texto.toml usaba LEMMA = ir, que podía fallar con «Vas» en mayúscula al inicio de un mensaje; lo detectó QA, prueba en a4a67c2 y se corrigió con LOWER en c889c73. (2) _clasificar del adaptador lanzaba un TypeError incomprensible ante una salida mal formada del pipeline; lo detectó QA, prueba en a4a67c2 y se corrigió con ValueError en decf849. QA señaló además que faltaba la prueba del camino feliz de from_config (a27bd4f) |

## 2026-11-07 · José Andrés Loría Herrera · F-07, worker de texto, Parte 3: medir aciertos contra verdad de referencia (`feat/F-07-3-worker-de-texto`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes developer (pruebas, implementación y correcciones de QA), QA tester y documentador |
| Componente | F-07, worker de texto, Parte 3: medir aciertos contra verdad de referencia |
| Propósito | Medir de punta a punta el analizador de texto con los modelos reales contra una conversación etiquetada y registrar la tabla de aciertos de US-07 |
| Consulta resumida | Aplicar el ciclo de seis fases a la parte 3 con alcance mínimo: script aciertos_texto, prueba de aceptación, conversación sintética etiquetada y evidencia; ejecución real de integración y aceptación; verificación por QA; documentación de límites |
| Resultado obtenido | scripts/aciertos_texto.py (exigir_entero_positivo pasa a público en analyze_text.py), 267 líneas fuera de tests y docs; tests/datos/aciertos_texto_conversacion.json (40 mensajes ficticios redactados con IA y revisados por José Andrés) y aciertos_texto_etiquetas.json (4 lotes de 10); evidencia docs/evidencia/F-07_aciertos_2026-11-07.md: tema 4/4, sentimiento 4/4, amenaza 1/1, ofensivo 1/1, sin_ofensa 2/2, con sección Límites; patrón vas_a_ver reducido a vas y van; suite 913 passed, 1 skipped |
| Validado / corregido / descartado | Aceptado tras las correcciones de la fila de errores. José Andrés aprobó cada fase y revisó la conversación sintética. La tabla prueba el funcionamiento de punta a punta, no la precisión; los umbrales siguen provisionales porque la muestra no permite calibrarlos. Las observaciones menores de QA y los pendientes de la parte 2 quedan sin corregir en el SPEC por decisión de alcance mínimo |
| Cómo se validó | Primera ejecución real el 2026-11-07 en Windows, venv aparte con torch 2.15.0+cpu, spacy 3.8.18, transformers 5.22.2 y es_core_news_sm 3.8.0: integración 2 passed, aceptación 1 passed. py -m pytest -q -m not integration and not acceptance: 913 passed, 1 skipped. py -m scripts.conformidad repo: 0 problemas. Pruebas exploratorias de QA con los modelos reales: solo 2 de 10 insultos detectados, amenazas sin patrón no detectadas, puntajes de ofensa en 0.133 o menos y 0.981 o más. Sin comprobar: calidad sobre datos independientes (F-04) y mediciones de SO (no aplican) |
| Error de la IA | (1) En la parte 2 la IA amplió el patrón vas_a_ver a voy y vamos a ver, lo que produjo amenazas altas falsas (por ejemplo, Vamos a ver qué dice el profesor mañana); lo detectó QA con los modelos reales y se corrigió en la parte 3, con prueba en c019213 y corrección en 2a935a2. (2) El developer escribió caracteres de retroceso (x08) en vez de la secuencia de borde de palabra en una regex de una prueba; él mismo lo detectó y lo corrigió antes de entregar. (3) La conversación sintética redactada por IA conocía el léxico de temas y los patrones de amenaza, así que la tabla 4/4 sobreestima la calidad; lo señaló QA (H1) y la evidencia ahora lo declara en su sección Límites (2a935a2) |

## 2026-11-08 · José Andrés Loría Herrera · F-08 (`feat/F-08-1-worker-de-imagen`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes arquitecto, developer, QA tester y documentador |
| Componente | F-08 |
| Propósito | Convertir detecciones de imagen en hallazgos con categoría, confianza, severidad por reglas (SUP-07) y la caja como posición de la evidencia (RF-14), con un detector falso y sin modelo real |
| Consulta resumida | Escribir el SPEC con su plan de tres PR. Hacer las pruebas en rojo de la parte 1 y luego implementar el dominio, el caso de uso y el adaptador. Reutilizar SeverityRules de F-07 con la categoría obligatoria como parámetro y extraer el SHA-256 a un módulo común |
| Resultado obtenido | Detection con validaciones; sensitive_findings da un hallazgo por categoría con la confianza más alta; ImageAnalyzer.from_config exige la regla de arma; SeverityRules valida la lista de reglas, los campos y los duplicados, lo que también afecta a F-07; config/imagen.toml; 191 líneas en src y config. US-08 aún no está cumplida: faltan el modelo real (parte 2) y la tabla de aciertos (parte 3) |
| Validado / corregido / descartado | Aceptado tras corregir los cinco errores de la fila de errores. José Andrés aprobó cada fase. Las observaciones menores de QA quedan como pendientes para la parte 2 en el SPEC |
| Cómo se validó | El orquestador leyó los diffs y revisó cada fase sobre su commit exacto. QA reprodujo los defectos con py -c. py -m pytest -q -m 'not integration and not acceptance': 792 passed. Conformidad del repositorio: 0 problemas. Sin comprobar: lint (ruff no instalado) |
| Error de la IA | (1) D1: una configuración mal formada daba AttributeError, KeyError o TypeError en vez de ValueError; lo detectó QA, pruebas en fd6f3b6 y corrección en 1beeb6c. (2) D2: una regla duplicada de arma reemplazaba a la anterior y bajaba la severidad de alta a baja sin avisar, en código compartido con F-07; mismas pruebas y corrección. (3) R1: una categoría con espacios al borde pasaba la validación y quedaba en baja; corregido en 1beeb6c con prueba nueva. (4) Las pruebas no detectaban que se quitara el desempate por caja ni que se aceptaran coordenadas booleanas; QA agregó las pruebas. (5) El orquestador escribió el carácter de campo pendiente en su resumen de verificación del plan y flujo.py aprobar lo rechazó; se revirtió el registro (19b2add) y se volvió a verificar |

## 2026-11-08 · José Andrés Loría Herrera · F-08 (`feat/F-08-2-worker-de-imagen`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes developer, QA tester y documentador |
| Componente | F-08 |
| Propósito | Conectar YOLO11n preentrenado como ObjectDetector real en CPU, fijar los pesos con su SHA-256 y las versiones de las dependencias, y resolver los pendientes de QA de la parte 1 |
| Consulta resumida | Escribir pruebas en rojo de YoloDetector con un modelo falso. Implementar el adaptador y fijar torch CPU y ultralytics. Rechazar cajas invertidas y etiquetas vacías, copiar el mapa y exigir [clases] y umbral_minimo |
| Resultado obtenido | YoloDetector con detect en CPU y tipos nativos, y from_config, que comprueba el SHA-256 antes de cargar. Hash de yolo11n.pt (release v8.4.0, 5613764 bytes) en config/imagen.toml. torch==2.15.0 y ultralytics==8.4.208 en requirements-imagen.txt, y *.pt en .gitignore. Prueba de integración que se salta sin ultralytics. README, AD-27, R13, CONTRATOS y SPEC actualizados. US-08 aún no está cumplida: falta la tabla de aciertos (parte 3) |
| Validado / corregido / descartado | Aceptado, con la prueba agregada en 080eddb. José Andrés aprobó cada fase y autorizó la descarga de los pesos. R1, R2, R3 y O1 quedan como pendientes de la parte 3 en el SPEC. El YOLO real no se ejecutó |
| Cómo se validó | py -m pytest -q -m 'not integration and not acceptance': 822 passed, 1 skipped. QA probó 19 mutaciones: 14 detectadas, 4 equivalentes y 1 detectada desde 080eddb. El orquestador calculó el SHA-256 de los pesos con sha256sum y coincide con el digest de GitHub; QA lo recalculó. ultralytics 8.4.208 confirmado con pip index versions. Conformidad del repositorio: 0 problemas. Sin comprobar: YOLO real, wheels para Python 3.13 y lint (ruff no instalado) |
| Error de la IA | (1) No había prueba de que una lista de resultados vacía se rechazara: la mutación que quitaba ese rechazo pasaba las pruebas; QA agregó la prueba en 080eddb. (2) El developer describió de memoria, sin comprobarlo, cómo reacciona ultralytics ante una imagen corrupta; queda como riesgo R1 para la parte 3. (3) El mensaje de error de pesos dice nombre de archivo, pero se aceptan rutas con dos puntos de directorio padre (O1, lo señaló QA) |

## 2026-11-09 · José Andrés Loría Herrera · F-08 (`feat/F-08-3-worker-de-imagen`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes developer, QA tester y documentador |
| Componente | F-08 |
| Propósito | Medir los aciertos del analizador de imagen con YOLO11n real sobre una muestra propia, resolver los pendientes de QA de la parte 2 y cerrar US-08 |
| Consulta resumida | Pruebas en rojo y script de la tabla de aciertos, con validación de etiquetas, configuración y salida. Resolver R1 a R3 y O1 en el detector. Verificar con YOLO real y documentar los límites medidos |
| Resultado obtenido | Con umbral 0.25: arma VP 4, FP 0, FN 6, VN 10 sobre 20 fotos propias de José Andrés (CC BY 4.0, 480x640), en docs/evidencia/F-08_aciertos_2026-11-09.md. R1 medido con el modelo real: una imagen ilegible da lista vacía con aviso y un archivo inexistente da FileNotFoundError; los dos se convierten en ValueError. Análisis de fallos con las detecciones crudas: un solo cuchillo, confusión con tie en vertical, knife 0.15 bajo el umbral, cuchillo_05 en severidad baja, manos del autor detectadas como person, ejecución en Python 3.14 |
| Validado / corregido / descartado | Aceptado tras corregir los errores de la fila de errores. José Andrés aprobó cada fase, aportó las fotos y decidió mantener el umbral en 0.25 (SUP-17). AD-27 sigue provisional: falta medir con datos independientes y más de un cuchillo, y la huella de F-17 |
| Cómo se validó | Unitarias: 876 passed, 1 skipped. Integración y aceptación con YOLO real (venv con Python 3.14, torch 2.15.0+cpu, ultralytics 8.4.208): 3 passed. QA reprodujo la tabla idéntica y la recalculó a mano. De 26 mutaciones de QA, 22 detectadas, 2 equivalentes y 2 cubiertas después. El documentador reprodujo las detecciones crudas y la severidad. Conformidad: 0 problemas. Sin comprobar: Python 3.13 y lint (ruff no instalado) |
| Error de la IA | (1) El developer escribió dos comentarios sobre cómo reacciona ultralytics ante una imagen ilegible que contradecían lo medido; el orquestador lo detectó al correr el modelo real y se corrigieron en 342e706. (2) QA detectó D1 (etiquetas con estructura inesperada daban AttributeError) y D2 (salida no escribible sin manejar y detectada después de analizar la muestra), con pruebas en bb50ef0, corregidos en fbdcdd8 junto con R-a (config inexistente o rota). (3) Las pruebas no detectaban dos mutaciones (categorias_de fijo y pesos C:yolo11n.pt); se agregaron en fbdcdd8. (4) La sección de límites que genera el script omitía límites medidos; lo señaló QA y se agregó el análisis en faed202. (5) El orquestador corrió primero la integración con cuchillo_01, donde YOLO no detecta el cuchillo, y falló; se repitió con cuchillo_02 y quedó documentado |

## 2026-11-09 · José Andrés Loría Herrera · F-09 (`feat/F-09-1-worker-de-audio`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes arquitecto, developer, QA tester y documentador |
| Componente | F-09 |
| Propósito | Analizar notas de voz como texto con timestamps: un hallazgo de transcripción por segmento y los segmentos pasados como mensajes por el análisis de texto de F-07 (RF-06, RF-14), con un transcriptor falso y sin faster-whisper real |
| Consulta resumida | Escribir el SPEC con su plan de tres PR. Hacer las pruebas en rojo de la parte 1 y luego implementar el dominio, el caso de uso y el adaptador. Reutilizar analyze_conversation de F-07 con un parámetro de formato de posiciones, extraer la carga de ajustes de texto y agregar FakeTextModels a los dobles |
| Resultado obtenido | TranscriptSegment valida tiempos finitos con 0 <= inicio <= fin y confianza en [0, 1]; analyze_audio da un hallazgo transcripcion de severidad baja por segmento no vacío, renumera los segmentos tras descartar los vacíos y reutiliza el análisis de F-07 con posiciones segmento i t=a-bs, segmentos i-j y lista segmentos i,j; una nota sin voz da lista vacía; AudioAnalyzer.from_config calcula el SHA-256 antes de transcribir. Refactor de F-07 a PositionFormat y MessagePositions sin cambiar su salida, y cargar_ajustes_de_texto. US-09 aún no está cumplida: faltan el modelo real (parte 2) y la comparación de transcripción (parte 3) |
| Validado / corregido / descartado | Aceptado tras corregir los errores de la fila de errores. José Andrés aprobó cada fase y devolvió la verificación a implementación por los tiempos infinitos. Aprobó el plan sin modificar las 8 preguntas abiertas, que quedaron con las recomendaciones del SPEC. Las observaciones menores de QA quedan como pendientes para la parte 2 en el SPEC. Riesgo: el código de las partes 2 y 3 de F-07 y F-08 no está en main |
| Cómo se validó | El orquestador leyó los diffs y revisó cada fase sobre su commit exacto. QA hizo 2 rondas, probó 17 mutaciones (las pruebas detectaron 16) y agregó 7 pruebas. py -3 -m pytest -q -m 'not integration and not acceptance': 832 passed. tests/unit/test_conformidad.py: 28 passed. Sin comprobar: lint (ruff no instalado) y el modelo real (parte 2) |
| Error de la IA | (1) El developer dejó que TranscriptSegment aceptara tiempos infinitos, porque 0 <= inicio <= fin es verdadero con inf; QA lo detectó con una prueba roja en 63f9d3c, José Andrés devolvió la fase y se corrigió en f0ce6dc con math.isfinite. (2) El orquestador escribió el carácter de campo pendiente en su resumen de verificación del plan y flujo.py aprobar lo rechazó; se corrigió en ff2b22e y se volvió a verificar. (3) La prueba de mutación mostró que ninguna prueba original exigía calcular el SHA-256 antes de transcribir; QA lo cubrió con test_archivo_inexistente_falla_antes_de_transcribir (63f9d3c) |

## 2026-11-09 · José Andrés Loría Herrera · F-09 (`feat/F-09-2-worker-de-audio`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5: orquestador y subagentes developer, QA tester y documentador |
| Componente | F-09 |
| Propósito | Conectar faster-whisper base preentrenado como Transcriber real en CPU, fijar la revisión de los pesos y la versión de la dependencia, y resolver los pendientes de QA de la parte 1 |
| Consulta resumida | Escribir pruebas en rojo de WhisperTranscriber y de la carga de config/audio.toml con un modelo falso. Implementar el adaptador con importación diferida, fijar faster-whisper y la revisión de Systran/faster-whisper-base. Rechazar tiempos bool y fuera de rango en TranscriptSegment, convertir a tipos nativos y ordenar los segmentos |
| Resultado obtenido | WhisperTranscriber transcribe en CPU, carga el modelo una vez por instancia, devuelve tipos nativos, calcula la confianza como exp(min(0, avg_logprob)) y rechaza NaN, ordena los segmentos por inicio y da ValueError con la ruta ante un audio ilegible (OSError, ValueError, IndexError y av.error.FFmpegError). config/audio.toml fija la revisión ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 (40 hex) y compute_type solo int8 o float32; hilos 0 delega en CTranslate2. faster-whisper==1.2.1 en requirements-audio.txt, que incluye requirements-texto.txt. TranscriptSegment rechaza bool y tiempos mayores que TIEMPO_MAXIMO_S (388af7d). La prueba de integración se salta sin faster-whisper. README, AD-28, R14, CONTRATOS y SPEC actualizados (5e58d31). US-09 aún no está cumplida: falta la comparación de transcripción (parte 3) |
| Validado / corregido / descartado | Aceptado tras corregir los errores de la fila de errores. José Andrés aprobó cada fase, devolvió la implementación por H1 y H2 (cde59b5) y pidió omitir la re-verificación del QA tester. La excepción real de PyAV, BugError, los segmentos solapados, Python 3.13 y las claves extra de audio.toml quedan como pendientes de la parte 3 en el SPEC. faster-whisper real no se ejecutó |
| Cómo se validó | El orquestador comprobó el sha de la revisión en la API de Hugging Face y la versión 1.2.1 en PyPI. QA contrastó supuestos con el código fuente de PyAV 19.0.2 y faster-whisper 1.2.1 sin instalar nada. QA probó 16 mutaciones: 3 sobrevivían y se cubrieron con pruebas nuevas en 4f1dc5f, y 1 era equivalente. La re-verificación tras la corrección la hizo el orquestador sin subagente, no independiente, a pedido de José Andrés: detectó las 2 mutaciones de las correcciones. py -3 -m pytest -q -m 'not integration and not acceptance': 1148 passed, 3 skipped. Integración: 1 skipped sin faster-whisper. tests/unit/test_conformidad.py: 28 passed. Sin comprobar: faster-whisper y PyAV reales (parte 3), Python 3.13 y lint (ruff no instalado) |
| Error de la IA | (1) H1: el developer calculaba la confianza con exp(min(0, avg_logprob)), que con NaN da 1.0; QA lo detectó con prueba roja en 4f1dc5f, José Andrés devolvió la fase y se corrigió en b1ec7d7. (2) H2: el developer solo capturaba OSError y ValueError; un archivo sin pista de audio da IndexError en PyAV y otros FFmpegError no heredan de esas clases; QA lo detectó leyendo el código fuente de PyAV 19.0.2, misma prueba y corrección. (3) El developer escribió un comentario que afirmaba sin comprobarlo que PyAV lanza InvalidDataError; el orquestador lo señaló y se reemplazó en b1ec7d7 por lo comprobado en el código fuente. (4) Las pruebas de configuración no detectaban revisión en mayúsculas, match en vez de fullmatch ni float16; QA agregó los casos en 4f1dc5f |

## 2026-11-10 · José Andrés Loría Herrera · F-09 (`feat/F-09-2-worker-de-audio`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 y Sonnet 5.5: orquestador y subagentes developer, QA tester, documentador y revisor. La sesión cambió a Sonnet 5.5 durante esta ronda y esos commits llevan ese pie |
| Componente | F-09 |
| Propósito | Corregir en la parte 2 los hallazgos del revisor sobre WhisperTranscriber: validar el idioma de config/audio.toml al cargar y dejar de reportar como audio ilegible los errores transitorios de PyAV |
| Consulta resumida | Escribir pruebas en rojo del idioma inválido, de los errores transitorios de av y de la rama de FFmpegError. Validar el idioma contra los códigos de Whisper y propagar los errores transitorios. Corregir el comentario sobre cuándo corre decode_audio |
| Resultado obtenido | config/audio.toml exige un idioma de IDIOMAS_DE_WHISPER, 100 códigos copiados de _LANGUAGE_CODES de faster-whisper v1.2.1, sin espacios ni mayúsculas; un valor que no es texto da ValueError. MemoryError, TimeoutError, BlockingIOError, InterruptedError y PermissionError, incluidos los de av.error que también heredan de FFmpegError, se propagan para que F-12 y F-18 puedan reintentar. FileNotFoundError y otros OSError (ConnectionError, BrokenPipeError, IsADirectoryError) siguen dando ValueError con la ruta. El comentario aclara que decode_audio corre al llamar a transcribe() y que lo perezoso es la inferencia. AD-28, README y SPEC actualizados (01f58b0). US-09 aún no está cumplida: falta la comparación de transcripción (parte 3) |
| Validado / corregido / descartado | Aceptado tras corregir los errores de la fila de errores. José Andrés devolvió la fase a implementación (b14fb1e) para corregir ahora en vez de pasar los hallazgos a la parte 3. Quedan como pendientes de la parte 3 en el SPEC: BugError reportado como audio ilegible, ConnectionError y BrokenPipeError como audio ilegible, la copia estática de los 100 códigos y lo que ya había. PyAV y faster-whisper reales no se ejecutaron |
| Cómo se validó | El revisor dio APROBADO con 2 hallazgos importantes y 3 menores. QA re-verificó con 11 mutaciones, todas detectadas, comparó los 100 códigos con faster-whisper v1.2.1 y agregó 5 pruebas en d0c3846. py -3 -m pytest -q -m 'not integration and not acceptance': 1188 passed, 3 skipped. tests/unit/test_conformidad.py: 28 passed. Sin comprobar: PyAV y faster-whisper reales (parte 3), Python 3.13 y lint (ruff no instalado) |
| Error de la IA | (1) El developer aceptaba cualquier texto como idioma y un código inválido se reportaba como audio ilegible. Lo detectó el revisor leyendo tokenizer.py de faster-whisper v1.2.1; se corrigió en f8b866d con pruebas en 324c2d2. (2) El developer capturaba FFmpegError y OSError, y por eso errores transitorios (ENOMEM, ETIMEDOUT, EAGAIN, EACCES) se reportaban como audio ilegible. Lo detectó el revisor leyendo av/error.py de PyAV 19.0.2; mismo commit. (3) El orquestador afirmó en su verificación anterior que MemoryError genéricos siguen escapando, sin distinguir el MemoryError de PyAV. Lo señaló el revisor. (4) La corrección (1) introdujo una regresión: TypeError en vez de ValueError con idioma = [es]. La detectó el orquestador al leer el diff y se corrigió en 06df373, con prueba roja en b21d671. (5) No había prueba de la rama de FFmpegError; QA y el developer la agregaron en 324c2d2 y d0c3846 cubrió otros OSError de entrada y MemoryError sin av |

## 2026-11-10 · Kenni Rodriguez · Plan del dataset sintético (F-03 parte 1) (`feat/F-03-1-dataset-sintetico`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Sonnet 5.5; orquestador y subagentes por rol (arquitecto, developer, QA tester, documentador) |
| Componente | Plan del dataset sintético (F-03 parte 1) |
| Propósito | Planear de forma determinista el dataset sintético de B.3 (casos, conteos de mensajes, imágenes, audios, proporción positiva, heterogéneos livianos y pesados) y validar sus mínimos, como dominio puro. |
| Consulta resumida | Escribir el SPEC de F-03; escribir las pruebas rojas; implementar plan_dataset(seed, params) y check_minimums(plan); verificar con QA. |
| Resultado obtenido | src/domain/dataset_plan.py (117 líneas), tests/unit/test_dataset_plan.py y docs/specs/F-03/SPEC.md. El SPEC pasó a generación totalmente sintética y a un generador nuevo (AD-25 pendiente en la parte 6). |
| Validado / corregido / descartado | Aceptado con tres observaciones de QA, abiertas y marcadas xfail estricto, y una desviación del SPEC: el developer eligió check_minimums(plan) en vez de validar un manifiesto; la validación del manifiesto queda para la parte 5. Cada fase con verificación de IA y aprobación humana explícita. |
| Cómo se validó | Fase tests: pruebas rojas sin código. Implementación: pruebas en verde. Verificación: QA añadió bordes, totales exactos y determinismo (ed9ed39). Verificación de cada fase sobre el commit exacto, con pytest unitario sin red ni reloj. |
| Error de la IA | QA halló tres defectos reales en el código del developer, abiertos y marcados xfail: cases nunca recorta; los totales se pierden en silencio si ningún caso admite el tipo; los parámetros negativos no se validan. |

## 2026-11-10 · José Andrés Loría Herrera · F-09 (`feat/F-09-3-worker-de-audio`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 y Sonnet 5.5: orquestador y subagentes developer, QA tester y documentador |
| Componente | F-09 |
| Propósito | Comparar la transcripción de notas de voz con la esperada mediante la tasa de error por palabra (WER), con una muestra propia de 5 notas y el script de evidencia, sin que el modelo real se haya ejecutado todavía |
| Consulta resumida | Escribir pruebas del WER, la normalización y la lectura de esperadas, y luego implementar scripts/comparar_transcripcion.py con generación de la tabla en Markdown. Agregar la prueba de aceptación, la de errores de PyAV reales y la muestra de 5 notas con transcripciones.json. Tratar los errores de entorno como error: con código 1 |
| Resultado obtenido | scripts/comparar_transcripcion.py calcula el WER tras normalizar mayúsculas, tildes y puntuación (con NFC y la ñ conservada), lo registra sin umbral y escribe la tabla en docs/evidencia/ con una sección de límites de texto fijo. Los errores de entorno, incluida la falta de faster-whisper, spacy o transformers, salen como error: con código 1. La muestra son 5 notas Opus (2 de amenaza y 3 neutras) con voz propia de José Andrés leyendo guiones sintéticos redactados con IA, CC BY 4.0, en tests/datos/audio/ (687daa8). README, AD-28, CONTRATOS y SPEC actualizados (9e9317e). El modelo real nunca se ejecutó: no existe docs/evidencia/F-09_transcripcion_<fecha>.md, no hay WER medido y US-09 no está cumplida |
| Validado / corregido / descartado | Aceptado tras corregir los errores de la fila de errores. José Andrés devolvió la fase dos veces y aprobó cada fase; la aprobación de tests requirió --excepcion porque el script ya existía. Quedan pendientes en el SPEC: ejecutar integración, aceptación y script con el modelo real, confirmar la asignación de guiones a las 3 notas neutras, la duración de las notas (4 de 5 duran 4,26 a 4,94 s, menos de los 5 s del SPEC), la falta de normalización numérica, la sección de límites fija, que un fallo en una nota pierde toda la corrida, Python 3.13 y la copia estática de los 100 códigos de idioma. La licencia CC BY 4.0 la propuso la IA y José Andrés no la confirmó explícitamente |
| Cómo se validó | QA en 2 rondas. La primera la devolvió por H1 (ñ descompuesta) y H2 (ImportError y PackageNotFoundError con traceback, y versiones resueltas después de transcribir), con 23 mutaciones del script y 1 superviviente cubierto. La segunda dio APROBADO con 9 mutaciones, 4 supervivientes cubiertos con 4 pruebas nuevas (6dadc88). El orquestador encontró el mismo defecto de H2 con spacy y transformers ausentes, corregido con prueba roja en 3bf4115 y corrección en 102c0e1. py -3 -m pytest -q -m 'not integration and not acceptance': 1259 passed, 4 skipped. tests/unit/test_conformidad.py: 28 passed. Sin comprobar: el modelo real, PyAV real, Python 3.13 y lint (ruff no instalado) |
| Error de la IA | (1) El developer escribió test_wer_normaliza_antes_de_comparar con una expectativa incorrecta: 1/8 donde el WER era 0.0, porque la normalización quita las tildes. El orquestador no lo detectó al verificar la fase de tests, porque el archivo fallaba al importar y ninguna prueba se ejecutaba. Lo detectó el developer al implementar, se devolvió la fase y se corrigió en 3127c0f. (2) El script solo capturaba ValueError y OSError (H2). (3) normalizar perdía la tilde de la ñ descompuesta (H1). (4) El mismo defecto de H2 con spacy y transformers ausentes lo encontró el orquestador, no QA. (5) El orquestador escribió en transcripciones.json, antes de leer los nombres nuevos, un mapeo por nombres viejos que quedó inválido cuando José Andrés renombró los archivos. Además, las tres notas neutras se asignaron a su guion por orden de grabación sin poder oír el audio: supuesto aceptado por José Andrés y sin confirmar con el modelo |

## 2026-11-10 · Kenni Rodriguez · Generador de exportaciones de chat sintéticas (F-03 parte 2) (`feat/F-03-2-dataset-sintetico`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Sonnet 5.5; orquestador y subagentes por rol (developer, QA tester, documentador) |
| Componente | Generador de exportaciones de chat sintéticas (F-03 parte 2) |
| Propósito | Escribir las pruebas rojas y la implementación del generador de chats sintéticos (WhatsApp y Telegram) para el dataset de B.3 sin datos reales. |
| Consulta resumida | Pedir al developer las pruebas rojas del generador y su implementación mínima; pedir al QA que intentara romperlo. La API del generador, el parser local en pruebas y la estructura JSON de Telegram los aprobó la persona. |
| Resultado obtenido | src/adapters/chat_export_generator.py (132 líneas) y tests/unit/test_chat_export_generator.py. La IA redactó las plantillas de mensajes y las frases de amenaza ficticias. |
| Validado / corregido / descartado | Verificado por el orquestador y el QA, con aprobación humana de cada fase; cada verificación registrada sobre su commit. |
| Cómo se validó | Pruebas rojas (aa33e8c), implementación (648b23a), pruebas adicionales de QA (5ea6468). El QA comprobó que el ajuste de la regex no debilita la detección de datos reales. Quedan 2 defectos menores abiertos en xfail estricto: los renderizadores no convierten a UTC un mensaje con otra zona, y export_plan_chats no valida case.name. |
| Error de la IA | La prueba roja test_los_archivos_exportados_son_utf8_validos_sin_datos_reales (aa33e8c) era inconsistente con date_unixtime de Telegram: exigía int() y a la vez prohibía 7 o más dígitos. El developer la corrigió en 648b23a ajustando la regex con FECHA_UNIX; el QA confirmó que la detección no se debilita. |

## 2026-11-10 · José Andrés Loría Herrera · F-09 (`feat/F-09-3-worker-de-audio`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Opus 5.5 y Sonnet 5.5: orquestador y subagentes developer, QA tester, documentador y revisor |
| Componente | F-09 |
| Propósito | Ejecutar por primera vez el modelo real de faster-whisper sobre la muestra, corregir lo que la corrida reveló y generar la evidencia de transcripción de US-09 |
| Consulta resumida | Corregir la prueba de aceptación y la de integración para que funcionen con el modelo real, completar las versiones que pasa generar_markdown, fijar av en requirements-audio.txt, ejecutar scripts.comparar_transcripcion con faster-whisper 1.2.1, av 18.1.0, ctranslate2 4.9.0, torch 2.15.0+cpu, spaCy 3.8.18, transformers 5.22.2 y los pesos base fijados, y documentar lo medido |
| Resultado obtenido | WER por nota de 15.4, 9.1, 36.4, 27.3 y 0.0 % (media simple 17.6 %, calculada a mano) sobre 5 notas propias y sintéticas, en docs/evidencia/F-09_transcripcion_2026-11-10.md. amenaza_01 no produce hallazgo amenaza (Whisper base oyó más a ver en vez de vas a ver): falso negativo real; amenaza_02 sí da amenaza alta. 5 frente a cinco cuenta como error. Cada nota da un solo segmento, con tiempos redondeados de forma gruesa. Un tono de 440 Hz de 35 s produce un segmento inventado de puntos repetidos que el adaptador acepta; silencio y ruido blanco dan lista vacía. Una nota de 165.5 s tarda 23.3 s en 20 segmentos y las transcripciones son deterministas. faster-whisper 1.2.1 falla con av 19.0.2, así que requirements-audio.txt fija av==18.1.0 (bc24008). Un archivo no audio, uno vacío y un mp4 sin audio dan ValueError con PyAV real. US-09 queda demostrada solo con esa muestra, sin representatividad |
| Validado / corregido / descartado | José Andrés autorizó instalar faster-whisper y luego torch, spaCy y transformers, aprobó cada fase y devolvió la fase a tests tras la revisión (d55073c). Quedan pendientes en el SPEC: Python 3.13, duración de las notas (4 de 5 duran 4,26 a 4,94 s), normalización numérica, límites de texto fijo, que un fallo en una nota pierde la corrida, la copia estática de los 100 códigos de idioma, descartar segmentos sin letras, la licencia CC BY 4.0 propuesta por la IA y no confirmada, y renombrar las notas WhatsApp Ptt |
| Cómo se validó | El revisor devolvió la parte 3 con 1 bloqueante, 4 importantes y 4 menores, y el orquestador reprodujo el bloqueante. La corrida real con el entorno confirmó 6 pruebas de integración y aceptación, de las cuales 4 antes se saltaban. QA recalculó a mano los 5 WER y probó casos reales con audio sintético de ffmpeg. py -3 -m pytest -q -m 'not integration and not acceptance': 1261 passed, 4 skipped. tests/unit/test_conformidad.py: 28 passed. Sin comprobar: Python 3.13, lint (ruff no instalado) y la licencia |
| Error de la IA | (1) La prueba de aceptación pasaba solo la versión de faster-whisper a generar_markdown y lanzaba KeyError con el modelo real. Lo detectó el revisor leyendo el código, porque la prueba se saltaba sin faster-whisper, y lo reprodujo el orquestador. (2) La prueba de integración exigía una holgura de duración de 0.1 s que el modelo real incumple (fin de 5.00 s para 4.86 s de audio). Se detectó en la primera corrida real. (3) requirements-audio.txt dejaba av sin tope y faster-whisper 1.2.1 falla con av 19. Ninguna prueba con dobles podía detectarlo; se encontró en la primera corrida real. (4) El orquestador y el developer afirmaron antes, sin medir, que cierta asignación de guiones y la procedencia de la transcripción real eran correctas. La corrida real lo confirmó, pero se escribió antes de medir. (5) generar_markdown lanzaba KeyError si faltaba una versión. Se corrigió con prueba roja en 0b4bec3 y corrección en 089815b |

## 2026-11-10 · José Andrés Loría Herrera · F-16 (`feat/F-16-1-limites-por-worker`)

| Campo | Contenido |
|---|---|
| Herramienta | Codex, orquestador y subagente arquitecto |
| Componente | F-16 |
| Propósito | Delimitar la lectura de cgroups y el presupuesto de arranque sin invadir admisión, OOM ni despliegue ajeno |
| Consulta resumida | Diseñar F-16 contra los puertos existentes y dividir implementación pura y cableado Docker/WSL2 en PR pequeñas |
| Resultado obtenido | SPEC con dos partes, criterios y protocolo de medición; AD-29 y SUP-23 |
| Validado / corregido / descartado | Plan aprobado por José Andrés. Corregidas la afirmación de un comprobador inexistente y la omisión inicial del registro ADD/SUP. Descartado dar por existente el comprobador; se planificó agregarlo |
| Cómo se validó | Orquestador contrastó SPEC con US-16, RF-24, B.5 M1, AD-05 y contratos; inspeccionó `tests/contratos.py` y ejecutó `git diff origin/main...HEAD --check`. Evidencia en aprobaciones del SPEC sobre `94fc871` |
| Error de la IA | El plan afirmaba que existía `comprobar_resource_reader` cuando no estaba en `tests/contratos.py`. La inspección independiente del orquestador detectó el error; el diseño se corrigió para incorporarlo / El diseño introducía decisiones sin su registro ADD/SUP. El orquestador detectó la omisión y se agregaron AD-29 y SUP-23 antes de aprobar el plan |

## 2026-11-10 · José Andrés Loría Herrera · F-16 (`feat/F-16-1-limites-por-worker`)

| Campo | Contenido |
|---|---|
| Herramienta | Codex, orquestador y subagentes developer |
| Componente | F-16 |
| Propósito | Probar primero presupuesto y lectura estricta; implementar lo necesario conservando puertos |
| Consulta resumida | Cubrir suma, reserva, réplicas, configuración inválida y cgroups temporales; luego lograr verde sin modificar las pruebas aprobadas |
| Resultado obtenido | Pruebas unitarias y comprobador de contrato; `node_budget.py` y `cgroup_resources.py`, 52 líneas de producto |
| Validado / corregido / descartado | Fases tests e implementación aprobadas por José Andrés. No se agregaron CLI de arranque, cambios de workers ni Compose; pertenecen a parte 2 |
| Cómo se validó | `py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short`: 50 fallos esperados por módulos ausentes y 3 pruebas del doble aprobadas en rojo. `py -m pytest -q tests/unit/test_contratos.py`: 9 aprobadas. Tras implementar, `py -m pytest -q -m "not integration and not acceptance"`: 1138 aprobadas, 2 omitidas y 3 deseleccionadas. Diff de tests desde aprobación vacío y `git diff --check` correcto; evidencia en SPEC, producto `c19dc26` Incidencia: Un comando de aprobación del flujo en Windows falló por codificación de salida. Se resolvió usando `PYTHONIOENCODING`; no implicó corregir el producto ni se presenta como fallo de lógica encontrado por QA |

## 2026-11-10 · José Andrés Loría Herrera · F-16 (`feat/F-16-1-limites-por-worker`)

| Campo | Contenido |
|---|---|
| Herramienta | Codex, orquestador, subagente QA y subagente documentador |
| Componente | F-16 |
| Propósito | Intentar romper las garantías y documentar resultados reales con límites explícitos de evidencia |
| Consulta resumida | Revisar aceptación y sensibilidad de pruebas; preparar ficha de cinco elementos y bitácora sin atribuir datos sintéticos al SO |
| Resultado obtenido | `QA-parte-1.md`, ficha `docs/modulo-M1-memoria.md`, actualización de AD-29/SUP-23 con aprobación de diseño ya registrada y este borrador |
| Validado / corregido / descartado | QA no encontró fallos reproducibles de producción en parte 1; fase verificación aprobada por José Andrés. Documentación entregada para verificación del orquestador y aprobación humana. Mediciones Docker/WSL2, integración y aceptación de arranque permanecen pendientes para parte 2 |
| Cómo se validó | QA ejecutó la suite: 1138 aprobadas, 2 omitidas y 3 deseleccionadas; detectó seis mutaciones y comprobó nueve bordes exploratorios. Orquestador reprodujo 57 pruebas de presupuesto, lector y arquitectura y una mutación que permite todo presupuesto, detectada. Documentador contrastó ficha y borrador con implementación, SPEC, QA y anexos 2/3; `git diff --check`. Evidencia detallada en `QA-parte-1.md` y aprobaciones del SPEC |

## 2026-11-10 · Kenni Rodriguez · Generador de imágenes y audio sintéticos (F-03 parte 3) (`feat/F-03-3-dataset-sintetico`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code con Claude Sonnet 5.5; orquestador y subagentes por rol (developer, QA tester, documentador) |
| Componente | Generador de imágenes y audio sintéticos (F-03 parte 3) |
| Propósito | Generar con ffmpeg las 300 imágenes y 150 audios sintéticos del dataset de B.3, con etiqueta de verdad asignada por el generador, origen sintetico y reproducibles por semilla. |
| Consulta resumida | Pedir pruebas rojas e implementación de media_generator a partir de DatasetPlan, con etiquetas positivo o neutro en imágenes y tono o ruido en audio; pedir al QA que intentara romperlo con ffmpeg real. |
| Resultado obtenido | src/adapters/media_generator.py y sus pruebas (tests/unit/test_media_generator*.py, tests/integration/test_media_generator_ffmpeg.py). La IA generó el código y la lógica de etiquetas y colores. Plan completo medido por QA con carga en paralelo: 450 archivos, 720 MB en 166,8 s. |
| Validado / corregido / descartado | Verificación IA de cada fase y aprobación humana explícita. Pruebas unitarias 788 passed, 3 skipped, 10 xfailed sin XPASS; integración con ffmpeg real 2 passed. |
| Cómo se validó | El QA ejecutó ffmpeg real y comparó hashes entre corridas con distinto PYTHONHASHSEED: 450 sha256 idénticos con la misma semilla. Con ffmpeg real: 160 de 160 png y 140 de 140 jpg únicos. El orquestador reejecutó pytest en cada fase. Quedan 2 xfail abiertos de media_generator: un archivo previo oculta un ejecutor que no produjo nada, y el reparto de formatos se reinicia por caso. Decisiones de la persona: licencia provisional 'generado por el equipo, uso academico' (el repo no tiene LICENSE) y ampliar la variación de color; ajuste del SPEC a etiqueta neutro en vez de negativo (555c21d). |
| Error de la IA | QA: las imágenes colisionaban (160 png daban 102 hashes únicos y 140 jpg daban 92) por color en rango pequeño; corregido en b846164 a petición de la persona, y una línea de una prueba de QA pasó de gris puro a dispersión de canales <= 16. |

## 2026-11-10 · José Andrés Loría Herrera · M1, F-16 parte 2: presupuesto, Compose y arranque (`feat/F-16-2-limites-por-worker`)

| Campo | Contenido |
|---|---|
| Herramienta | Codex (orquestador y developer) |
| Componente | M1, F-16 parte 2: presupuesto, Compose y arranque |
| Propósito | Aplicar el presupuesto al arranque sin inventar límites por worker ni confundir pruebas con mediciones de SO |
| Consulta resumida | Implementar preflight y wrapper CPU/GPU, validar hostname, dirección IP, límites configurados y reserva derivada de memoria WSL2 antes de compose up |
| Resultado obtenido | scripts/preflight.py y scripts/start_worker.py; WORKER_MEM_LIMIT obligatorio como mem_limit y memswap_limit; SUP-24 provisional; suite informada: 1149 passed, 2 skipped, 3 deselected |
| Validado / corregido / descartado | QA halló que NODE_IP aceptaba texto no IP; se corrigió con ipaddress.ip_address y pruebas IPv4/IPv6. WORKER_MEM_LIMIT queda pendiente de medición por nodo. No se ejecutó Docker/Compose real ni se midieron nodos; no hubo reutilización del I Proyecto. |
| Cómo se validó | QA-parte-2.md documenta cobertura estática y que su intento de suite no inició; el orquestador informó 11 pruebas focalizadas y suite completa 1149/2/3. No se afirma medición de SO ni ejecución Compose. |
| Error de la IA | La implementación inicial aceptaba NODE_IP con cualquier texto no vacío. QA detectó el error; se corrigió validando IPv4/IPv6 con ipaddress.ip_address y agregando pruebas de IPv6 válido y texto inválido. |

## 2026-11-10 · José Andrés Loría Herrera · M1, F-16 parte 2: verificación y documentación (`feat/F-16-2-limites-por-worker`)

| Campo | Contenido |
|---|---|
| Herramienta | Codex (orquestador, QA y documentador) |
| Componente | M1, F-16 parte 2: verificación y documentación |
| Propósito | Registrar los resultados de QA y separar evidencia de software de mediciones reales |
| Consulta resumida | Intentar romper configuración y preflight; documentar ficha M1, instrucciones de arranque y limitaciones de medición |
| Resultado obtenido | QA-parte-2.md, ficha M1 actualizada, README y borrador de bitácora revisados |
| Validado / corregido / descartado | La documentación coincide con scripts, Compose y QA; WORKER_MEM_LIMIT y datos B/C/D siguen pendientes. No se ejecutaron Docker/Compose ni cgroups reales. |
| Cómo se validó | Se contrastó el diff con SPEC, scripts y QA-parte-2.md. Los conteos 1149/2/3 están atribuidos al orquestador/informe de QA. Mediciones memory.max y memory.swap.max tres veces por nodo siguen pendientes. |
| Error de la IA | QA detectó el error real de validación de NODE_IP descrito en la entrada anterior; quedó corregido con pruebas. |

## 2026-11-10 · José Andrés Loría Herrera · F-17 (`feat/F-17-1-control-de-admision`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude Code (Sonnet 5.5) |
| Componente | F-17 |
| Propósito | Plan, pruebas, implementación, QA y documentación de F-17 (control de admisión por huella de memoria) |
| Consulta resumida | Diseño de admits, tabla de huellas, compuerta antes de blpop en poll_once y AD-30 |
| Resultado obtenido | admits, FootprintTable, load_admission_config, compuerta en el worker, AD-30 y ficha M1 con medición pendiente |
| Validado / corregido / descartado | 69 pruebas en verde, revisión humana de cada fase; la medición M1 no se hizo (sin nodos WSL2 ni F-16 parte 2) |
| Cómo se validó | TDD con pruebas rojas primero; QA intentó romper valores bool, negativos y no ASCII |
| Error de la IA | En QA, CgroupResourceReader lanza ValueError con memory.max=max y el worker nunca admite; detectado y reportado, no corregido por estar fuera de alcance (F-16) |

## 2026-11-10 · Melany Vindas · F-22 (`feat/F-22-1-chunks-verificados`)

| Campo | Contenido |
|---|---|
| Herramienta | Claude (Opus 5.5) en claude.ai: orquestador y subagentes arquitecto, developer, QA tester y documentador, en una sesion que leia el repositorio. La sesion no tenia permiso de escritura: Melany aplico cada cambio con parches git am e hizo el push |
| Componente | F-22 |
| Propósito | Transferir archivos grandes en chunks verificados por SHA-256 (RF-31, AD-10): dominio, puerto ChunkStaging, caso de uso y staging en disco, sin rutas HTTP ni mediciones |
| Consulta resumida | Escribir el SPEC de F-22 con su plan de tres PR y registrar AD-28. Hacer las pruebas en rojo de la parte 1 y luego implementar UploadManifest y verify_chunk, el puerto ChunkStaging con su doble y su conformidad, ChunkedUpload y DiskChunkStaging; verificar por QA |
| Resultado obtenido | src/domain/chunks.py, ChunkStaging en ports.py, src/application/chunked_upload.py con reensamblado por flujo verificado y chunk maximo de 64 MiB, src/adapters/disk_chunk_staging.py con escritura atomica, FakeChunkStaging y comprobar_chunk_staging; test_chunks 44/44. AD-28 provisional y CONTRATOS actualizados. US-22 aun no esta cumplida: faltan rutas, cliente e integracion (parte 2) y la ficha M3 con datos medidos (parte 3) |
| Validado / corregido / descartado | Aceptado tras corregir H1. Melany Vindas aprobo cada fase con flujo.py aprobar. Riesgo 8 aceptado: ObjectStore no debe confirmar el objeto si la lectura lanza; pendiente llevarlo al contrato en una PR aparte. H2 (carrera entre receive y discard) queda para la parte 2 |
| Cómo se validó | pytest -q -m 'not integration and not acceptance': test_chunks 44/44 y suite 1086 passed. QA ataco el flujo con 14 lectores, chunks alterados en disco y concurrencia con hilos, sin ningun objeto con contenido distinto a su clave. Conformidad del repositorio: 0 problemas. Sin comprobar: subida real entre nodos y throughput, de las partes 2 y 3 |
| Error de la IA | (1) H1: la primera implementacion del developer calculaba el SHA-256 total en una pasada y releia el staging para put; un chunk cambiado entre las dos pasadas llegaba a ObjectStore con un SHA-256 ajeno. Lo detecto QA con una prueba en rojo; se devolvio a implementacion y se corrigio en 9e5b2b4 calculando el hash sobre el mismo flujo que lee put. (2) La primera verificacion de implementacion no fue independiente (el orquestador hizo el rol sin subagente) y no detecto H1. (3) Las pruebas iniciales del developer dejaban 5 mutantes vivos; QA las reforzo y en la segunda verificacion agrego pruebas que detectaron 3 mutantes mas. (4) La verificacion de la fase 4 se registro antes de aplicar las 12 pruebas de QA (cd0d180) porque un git am quedo a medias: el resumen decia 44/44 y la rama tenia 32. Se corrigio aplicando el parche despues |
