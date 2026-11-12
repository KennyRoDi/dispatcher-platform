# Revisión F-16, parte 1

**Resultado: APROBADO por el revisor de IA.** Requiere la verificación del orquestador y la aprobación humana; este informe no las registra.

Fecha: 2026-11-10. Rama: `feat/F-16-1-limites-por-worker`.
HEAD revisado: `5f1b331372e7485b0e65ebc8131aa0018c01aa50`.
Base remota actualizada con `git fetch origin main`: `691846cf1892e62e692716c21d0c3d90336ee748`.
Ancestro común del diff de la PR: `a96bbe29dce79932a0acde86120dbf464c82e184`.

## Evaluación independiente

Se leyeron AGENTS.md, el rol revisor, CONTRIBUTING.md, el SPEC, US-16, B.5 M1 y los contratos existentes. Se inspeccionó el diff completo `git diff origin/main...HEAD`, incluyendo documentos y pruebas. La conclusión se fundamenta en el código y las comprobaciones propias; los informes anteriores se contrastaron como documentación, sin sustituir la inspección.

No se encontraron hallazgos reproducibles que requieran corrección en el alcance aprobado de parte 1.

| Aspecto | Resultado |
|---|---|
| Presupuesto | Suma cada límite recibido y la reserva; acepta igualdad y reserva cero explícita. Rechaza RAM/límites no positivos, valores ausentes, tipos incorrectos y exceso. Los enteros de Python evitan desbordamiento de la suma. La enumeración de réplicas desde Compose queda para parte 2 |
| Lector | Relee ambos archivos, exige decimal ASCII y límite positivo, rechaza `max` y propaga errores de archivo, permisos y UTF-8. El uso cero o superior al límite conserva la semántica existente de disponibilidad acotada a cero |
| Contrato y capas | `ResourceReader.read()` y `ResourceUsage` permanecen intactos. Comprobador compartido aplicado al doble y lector temporal. Dominio sin E/S; lectura de cgroup en infraestructura. Pruebas de arquitectura aprobadas |
| Alcance y recursos | Solo presupuesto puro y lector; sin CLI, Compose, workers ni cambios de F-09. Archivos gestionados por `Path.read_text`, sin procesos, concurrencia o recursos persistentes añadidos |
| Restricciones | Entradas sintéticas y archivos temporales; sin datos reales de terceros ni secretos observados en el diff. No se añaden comentarios redundantes. AD-29 y SUP-23 registran la decisión y sus límites |
| Tamaño y commits | 52 líneas de producto agregadas, 0 eliminadas: cumple el máximo de 400. Commits inspeccionados con ámbito F-16, descripción en español y hasta 72 caracteres; autor José Andrés Loría Herrera |
| Documentación | Ficha distingue pruebas de software de mediciones pendientes. El borrador está identificado como tal; la referencia local `origin/estado` contiene entradas de la rama en la bitácora publicada |

## Comprobaciones propias

```powershell
git fetch origin main
git diff origin/main...HEAD --check
git diff origin/main...HEAD --numstat
git log --format='%h %an <%ae> %s' origin/main..HEAD
py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py tests/unit/test_arquitectura.py tests/unit/test_contratos.py
```

Resultados: fetch correcto; diff sin errores de espacios; tamaño y commits conformes a la inspección indicada; **66 passed in 0.24s**, código 0. El lanzador Python y el fetch requirieron ejecución fuera del sandbox por ubicación de Python y metadatos Git; los primeros intentos restringidos no pudieron ejecutarse. No se repitió la suite completa porque no cambió producto desde las fases previas y esta revisión focalizada comprueba cálculo, lector, contratos y capas.

El árbol estaba limpio al iniciar. Solo se agrega este informe; no se modificaron código ni pruebas, ni se ejecutaron comandos de aprobación/verificación del flujo, cierre o fusión.

## Limitaciones

Esta aprobación corresponde exclusivamente a parte 1. No demuestra el límite aplicado por el kernel, swap deshabilitado, RAM efectiva WSL2, expansión real de réplicas ni detención del arranque antes de Compose. CLI, despliegue coordinado con Kenni, integración, aceptación y mediciones B/C/D pertenecen a parte 2. No se ejecutaron Docker ni mediciones de SO. No se repitieron mutaciones de QA ni la suite completa; los resultados históricos permanecen atribuidos a sus informes originales. La bitácora se comprobó mediante la referencia local de `origin/estado`, sin actualizarla en esta revisión.
