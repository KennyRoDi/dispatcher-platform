# Borrador de bitácora IA: F-16, parte 1

**Rama:** `feat/F-16-1-limites-por-worker`. **Estado:** borrador para revisión humana de documentación. El orquestador lo publicará con `scripts/flujo.py bitacora` solo después de esa aprobación; este archivo no es la bitácora publicada. La revisión final de la parte todavía está pendiente.

## Consulta: plan de límites y presupuesto

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador y subagente arquitecto |
| Componente | M1, F-16, plan de las dos partes |
| Propósito | Delimitar la lectura de cgroups y el presupuesto de arranque sin invadir admisión, OOM ni despliegue ajeno |
| Consulta resumida | Diseñar F-16 contra los puertos existentes y dividir implementación pura y cableado Docker/WSL2 en PR pequeñas |
| Resultado obtenido | SPEC con dos partes, criterios y protocolo de medición; AD-29 y SUP-23 |
| Validado / corregido / descartado | Plan aprobado por José Andrés. Corregidas la afirmación de un comprobador inexistente y la omisión inicial del registro ADD/SUP. Descartado dar por existente el comprobador; se planificó agregarlo |
| Cómo se validó | Orquestador contrastó SPEC con US-16, RF-24, B.5 M1, AD-05 y contratos; inspeccionó `tests/contratos.py` y ejecutó `git diff origin/main...HEAD --check`. Evidencia en aprobaciones del SPEC sobre `94fc871` |
| Error de la IA | El plan afirmaba que existía `comprobar_resource_reader` cuando no estaba en `tests/contratos.py`. La inspección independiente del orquestador detectó el error; el diseño se corrigió para incorporarlo |
| Error de la IA | El diseño introducía decisiones sin su registro ADD/SUP. El orquestador detectó la omisión y se agregaron AD-29 y SUP-23 antes de aprobar el plan |

## Consulta: pruebas rojas e implementación mínima

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador y subagentes developer |
| Componente | M1, F-16 parte 1: dominio, infraestructura y contratos de prueba |
| Propósito | Probar primero presupuesto y lectura estricta; implementar lo necesario conservando puertos |
| Consulta resumida | Cubrir suma, reserva, réplicas, configuración inválida y cgroups temporales; luego lograr verde sin modificar las pruebas aprobadas |
| Resultado obtenido | Pruebas unitarias y comprobador de contrato; `node_budget.py` y `cgroup_resources.py`, 52 líneas de producto |
| Validado / corregido / descartado | Fases tests e implementación aprobadas por José Andrés. No se agregaron CLI de arranque, cambios de workers ni Compose; pertenecen a parte 2 |
| Cómo se validó | `py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=short`: 50 fallos esperados por módulos ausentes y 3 pruebas del doble aprobadas en rojo. `py -m pytest -q tests/unit/test_contratos.py`: 9 aprobadas. Tras implementar, `py -m pytest -q -m "not integration and not acceptance"`: 1138 aprobadas, 2 omitidas y 3 deseleccionadas. Diff de tests desde aprobación vacío y `git diff --check` correcto; evidencia en SPEC, producto `c19dc26` |
| Incidencia de herramienta | Un comando de aprobación del flujo en Windows falló por codificación de salida. Se resolvió usando `PYTHONIOENCODING`; no implicó corregir el producto ni se presenta como fallo de lógica encontrado por QA |

## Consulta: QA independiente y documentación

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador, subagente QA y subagente documentador |
| Componente | M1, F-16 parte 1: verificación, ficha y documentación |
| Propósito | Intentar romper las garantías y documentar resultados reales con límites explícitos de evidencia |
| Consulta resumida | Revisar aceptación y sensibilidad de pruebas; preparar ficha de cinco elementos y bitácora sin atribuir datos sintéticos al SO |
| Resultado obtenido | `QA-parte-1.md`, ficha `docs/modulo-M1-memoria.md`, actualización de AD-29/SUP-23 con aprobación de diseño ya registrada y este borrador |
| Validado / corregido / descartado | QA no encontró fallos reproducibles de producción en parte 1; fase verificación aprobada por José Andrés. Documentación entregada para verificación del orquestador y aprobación humana. Mediciones Docker/WSL2, integración y aceptación de arranque permanecen pendientes para parte 2 |
| Cómo se validó | QA ejecutó la suite: 1138 aprobadas, 2 omitidas y 3 deseleccionadas; detectó seis mutaciones y comprobó nueve bordes exploratorios. Orquestador reprodujo 57 pruebas de presupuesto, lector y arquitectura y una mutación que permite todo presupuesto, detectada. Documentador contrastó ficha y borrador con implementación, SPEC, QA y anexos 2/3; `git diff --check`. Evidencia detallada en `QA-parte-1.md` y aprobaciones del SPEC |

No se inventa un error de producción para completar la bitácora: los dos errores de IA detectados en el plan están descritos arriba. No hubo mediciones de SO en esta parte. No se usaron datos reales de terceros.
