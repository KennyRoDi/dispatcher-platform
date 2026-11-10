# Borrador de bitácora IA: F-16, parte 2

**Rama:** `feat/F-16-2-limites-por-worker`. **Estado:** borrador para revisión humana de documentación. El orquestador lo publicará con `scripts/flujo.py bitacora` solo después de esa aprobación; este archivo no es la bitácora publicada. La revisión final de la parte todavía está pendiente.

## Consulta: implementación de preflight y arranque

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador y subagente developer |
| Componente | M1, F-16 parte 2: presupuesto, Compose y arranque |
| Propósito | Aplicar el presupuesto al arranque sin inventar límites por worker ni confundir pruebas con mediciones de SO |
| Consulta resumida | Implementar preflight y wrapper CPU/GPU, validar hostname, dirección IP, límites configurados y reserva derivada de memoria WSL2 antes de `compose up` |
| Resultado obtenido | `scripts/preflight.py`, `scripts/start_worker.py`, configuración Compose con `WORKER_MEM_LIMIT` obligatorio como límite de memoria y swap, reserva SUP-24; suite final informada con 1149 aprobadas, 2 omitidas y 3 deseleccionadas |
| Validado / corregido / descartado | Implementación aprobada tras resolver el hallazgo de QA sobre `NODE_IP`. El valor de `WORKER_MEM_LIMIT` permanece vacío hasta medirlo en cada nodo. No se afirma ejecución de Compose ni medición de nodos. No se reutilizó código del I Proyecto en esta parte. |
| Cómo se validó | El informe QA `docs/specs/F-16/QA-parte-2.md` registra revisión estática, pruebas de dirección IP y suma, e intento de suite que no pudo iniciar en el entorno QA. El orquestador informó 11 pruebas focalizadas y suite `py -m pytest -q -m "not integration and not acceptance"`: 1149 passed, 2 skipped, 3 deselected. No se ejecutó Docker/Compose real. |

## Consulta: QA independiente y documentación

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador, subagente QA y subagente documentador |
| Componente | M1, F-16 parte 2: verificación, ficha, manual y documentación |
| Propósito | Verificar criterios y registrar el límite entre evidencia de software y medición real |
| Consulta resumida | Intentar romper configuración y preflight; actualizar ficha M1 y uso de despliegue; preparar bitácora conforme al Anexo 3 |
| Resultado obtenido | QA `docs/specs/F-16/QA-parte-2.md`; ficha M1 al corte parte 2; instrucciones mínimas de arranque en README; este borrador |
| Validado / corregido / descartado | QA encontró que `validate_config` aceptaba cualquier `NODE_IP` no vacío. Se corrigió con `ipaddress.ip_address` y pruebas para IPv6 válida y texto inválido. Los hallazgos restantes de arranque real no son conclusiones de QA: Docker, Compose y nodos B/C/D no se ejecutaron. Revisión final de la parte pendiente. |
| Cómo se validó | Se contrastaron SPEC, scripts, Compose, `.env.example`, ficha y QA; `NODE_IP` inválida se rechaza y las pruebas de software finales reportadas fueron 1149 passed, 2 skipped y 3 deselected. El informe limita explícitamente la ejecución Compose a cobertura estática de YAML y deja pendiente verificar `memory.max` y `memory.swap.max` tres veces en cada nodo B/C/D. |
| Error de la IA | QA detectó que la implementación aceptaba `NODE_IP` con cualquier texto no vacío, aunque el contrato exige una dirección válida. La corrección usa `ipaddress.ip_address` y añade pruebas de IPv6 válida y `not-an-ip` rechazado. |

No hay mediciones de SO ni valor medido para `WORKER_MEM_LIMIT` en esta parte. La reserva SUP-24 es supuesto provisional. La implementación no reutilizó código del I Proyecto. No se usaron datos reales de terceros.
