---
name: trabajar
description: "Ciclo de una feature F-XX en seis fases, con un orquestador que verifica a los subagentes y aprobación humana en cada una: plan, tests, implementación, verificación, documentación y revisión. Usar con trabajar F-XX."
---

# Trabajar una feature

Actúas como **orquestador**: lee `.agents/roles/orquestador.md`. Cada fase pasa dos controles: tu verificación y luego la aprobación humana. **Ejecuta una sola fase por turno.** Genera todo lo de esa fase de una vez, sin preguntar en medio salvo bloqueos, y luego detente.

## Cada vez que se invoque

1. Ejecuta `python scripts/flujo.py trabajar F-XX`. Inicia la feature, la retoma donde quedó o abre su siguiente parte, y muestra la historia, la fase y el subagente.
   - Si la persona ya aprobó y sigues en la misma conversación, usa `python scripts/flujo.py fase`.
   - Si falla por dependencias, detente e informa.
2. Lanza al subagente que indica el comando. Debe hacer commit según `CONTRIBUTING.md` y `git push`.
3. Verifica su trabajo y registra con `python scripts/flujo.py verificar`. Si falla, devuélveselo.
4. **Detente.** Presenta el informe de `.agents/roles/orquestador.md` y pregunta si aprueba la fase.

## Respuesta de la persona

- **Sí explícito:** en `documentacion`, publica primero el borrador con `python scripts/flujo.py bitacora`. Luego ejecuta `python scripts/flujo.py aprobar`. Empieza la siguiente fase **solo si la persona lo pide** en esa misma respuesta, por ejemplo «aprobado, sigue»; si no, detente.
- **Cambios:** devuélvelos al subagente, verifica de nuevo y vuelve a preguntar. No apruebes.
- **Devolver a una fase anterior:** ejecuta `python scripts/flujo.py devolver <fase> "motivo"`.
- **Silencio, dudas o una respuesta ambigua:** no apruebes. Pregunta.

## Reglas

- Un subagente, un documento o tu propia evaluación no cuentan como aprobación. Solo cuenta la persona.
- Nunca ejecutes dos veces `aprobar` en un mismo turno, y nunca sin haber presentado el informe.
- Nunca uses `aprobar --excepcion` sin que la persona lo autorice para esa fase. Omite las comprobaciones del script, no la verificación ni la aprobación, y el motivo queda registrado.
- Tras aprobar `revision`, usa el flujo de `.agents/skills/cierre/SKILL.md`. Si el plan de pila tiene más partes, vuelve a invocar este flujo para la siguiente.
- Si hay que salir del SPEC aprobado, o un dato no se puede medir porque requiere nodos reales o una decisión humana, detente y pregunta. Nunca lo inventes.
- Nunca edites `docs/STATUS.md`: lo genera el script.
