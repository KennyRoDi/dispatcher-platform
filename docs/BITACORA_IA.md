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
