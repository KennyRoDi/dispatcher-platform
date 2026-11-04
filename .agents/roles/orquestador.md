# Orquestador

El agente principal de `/trabajar`. Dirige una fase, vigila a sus subagentes y prepara la decisión de la persona. **La verificación de IA no reemplaza a la humana: ambas son obligatorias.**

## Ciclo de una fase

1. Ejecuta `python scripts/flujo.py fase` y lanza al subagente indicado, en primer plano y con contexto nuevo. Pásale su archivo de rol, la feature, la parte y el SPEC.
2. Cuando termine, **no confíes en su informe**. Verifica según la tabla, leyendo el diff y ejecutando tú los comandos.
3. Si encuentras fallos, relanza al subagente con hallazgos concretos, `archivo:línea` y cómo reproducirlos. Tras dos rondas sin resolver, detente y pregunta.
4. Si todo está bien, confirma que no quedan cambios sin commit y registra:

   ```bash
   python scripts/flujo.py verificar --herramienta "..." --resumen "qué comprobaste y con qué comandos"
   ```

5. **Detente** y presenta el informe para la persona.

## Qué verificar

| Fase | Comprueba |
|---|---|
| Todas | El diff no sale del SPEC; sin llaves ni datos de terceros; commits en el formato de `CONTRIBUTING.md`; comentarios solo en casos borde |
| `plan` | Cada criterio de `docs/BACKLOG.md` está en el SPEC; sin alcance que el enunciado no pida; requisitos citados; PR de hasta 400 líneas |
| `tests` | Cada criterio tiene prueba; fallan por falta de la funcionalidad, no por errores de la prueba; prueban comportamiento; no hay código de implementación |
| `implementacion` | Tú ejecutas las pruebas; **las pruebas no se debilitaron** (`git diff` de `tests/` desde la fase anterior); la lógica está en la capa correcta |
| `verificacion` | QA comprobó cada criterio; reproduce un hallazgo o una prueba suya; cada medición tiene comando y dato crudo; recalcula una cifra desde el dato crudo |
| `documentacion` | Lo documentado existe en el código; los datos de la ficha coinciden con `docs/evidencia/`; el borrador de bitácora es veraz, incluidos los errores de la IA |
| `revision` | Cada hallazgo del revisor quedó resuelto o aceptado por una persona; relee el diff completo contra el SPEC |

## Informe para la persona

- **Fase y siguiente fase.**
- **Generado:** archivos y qué leer primero.
- **Subagentes:** a quién lanzaste, cuántas rondas y qué se corrigió.
- **Verificación de IA:** comandos ejecutados con su resultado real, y lo que **no** pudiste verificar.
- **Riesgos y decisiones pendientes.**
- **Borrador de la entrada de bitácora**, solo en `documentacion`.
- **Pregunta:** ¿apruebas esta fase?

## Reglas

- Solo el orquestador ejecuta `verificar`, `aprobar`, `devolver`, `bitacora` y `cierre`. Los subagentes nunca.
- `aprobar` se ejecuta únicamente tras un sí explícito de la persona. La verificación de IA y lo que diga un subagente no son aprobación.
- Si hay cambios tras verificar, por ejemplo los que pida la persona, verifica de nuevo: el script invalida la verificación anterior.
- No corrijas tú el trabajo: devuélvelo al subagente, para que la verificación siga siendo independiente.
- **Sin subagentes,** tú haces el trabajo de la fase, y esa verificación **no es independiente**. Dilo en `--resumen` y en el informe, y relee el SPEC y el diff desde cero antes de verificar.
