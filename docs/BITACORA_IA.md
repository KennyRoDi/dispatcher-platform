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
