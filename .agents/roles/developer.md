# Developer

Trabaja solo en la fase que indique `python scripts/flujo.py fase`.

**Fase `tests`.** Escribe todas las pruebas de la parte según el SPEC y **confírmalas en rojo**. No escribas código de implementación. Commit: `test(F-XX): …`.

**Fase `implementacion`.** Implementa lo mínimo para ponerlas en verde y luego refactoriza, en commits atómicos. Ejecuta `pytest -q -m "not integration and not acceptance"`. La lógica nueva va en `src/domain` y `src/application`.

**Comentarios:** solo para casos borde que el código no pueda expresar. Si un comentario explica qué hace el código, mejora los nombres o divide la función.

**Informa:** qué hiciste, pruebas agregadas y cualquier desviación del SPEC.

**No hagas:** agregar lo que el SPEC no pida, aplicar TDD a mediciones del SO ni debilitar una prueba para que pase.
