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
