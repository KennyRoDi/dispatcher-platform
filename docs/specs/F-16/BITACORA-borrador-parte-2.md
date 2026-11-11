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

## Consulta: compatibilidad Windows, Compose real y evidencia local

| Campo | Contenido |
|---|---|
| Fecha · integrante | 2026-11-10 · José Andrés Loría Herrera |
| Herramienta | Codex, orquestador, developer y QA tester |
| Componente | M1, F-16 parte 2: lectura de RAM, límites Compose y cgroups |
| Propósito | Verificar en el entorno de despliegue que preflight lee el daemon WSL2 y que Compose aplica el límite de memoria sin swap |
| Consulta resumida | Corregir hallazgos QA en Windows/Compose y ejecutar una comprobación local efímera sin levantar un worker productivo |
| Resultado obtenido | `docker info --format '{{.MemTotal}}'` desde Windows; parser de límites normalizados por Compose; preflight aprobado con configuración sintética; tres contenedores efímeros con `memory.max=1073741824`, `memory.swap.max=0` y UID 1000. QA actualizada en `docs/specs/F-16/QA-parte-2.md`. |
| Validado / corregido / descartado | QA halló que `_node_memory_bytes` intentaba abrir `/proc/meminfo` desde Python en Windows, donde no existe; se cambió a `docker info` del daemon Linux. Después, Compose v5.5.1 mostró límites JSON como cadenas decimales de bytes y `validate_config` los rechazaba; se añadió parseo estricto a entero positivo. La comprobación local usó `.env` sintético, host `DESKTOP-796L2A2` no confirmado como B/C/D y contenedores `run --rm`; no se inició worker de larga duración ni carga B.3. No se reutilizó código del I Proyecto. |
| Cómo se validó | Tests focalizados: 76 passed; suite completa informada y reproducida por el orquestador: 1161 passed, 2 skipped, 3 deselected, 1 warning preexistente de Starlette. `docker info` local reportó 16728616960 bytes. `py scripts/preflight.py` aprobó y tres ejecuciones Compose CPU leyeron `memory.max=1073741824`, `memory.swap.max=0`, `uid=1000(appuser)`. Compose config CPU/GPU resolvió ambos límites a 4294967296 con `WORKER_MEM_LIMIT=4g` sintético; el runtime GPU no se ejecutó. El diff no presenta la lectura local como evidencia de B/C/D. |
| Error de la IA | QA detectó dos errores reales: (1) asumir que Python en Windows podía leer `/proc/meminfo`; se corrigió consultando `docker info --format '{{.MemTotal}}'`. (2) asumir límites JSON como enteros JSON, cuando Compose los entrega como cadenas decimales; se corrigió normalizando enteros/cadenas decimales ASCII positivos y rechazando entradas inválidas. |

Las mediciones calibradas de `WORKER_MEM_LIMIT`, tres arranques en cada B/C/D y la aplicación runtime del override GPU siguen pendientes por falta de canal de administración remota a los equipos de compañeros. El usuario autorizó continuar dejando esta evidencia pendiente por ahora. La reserva SUP-24 sigue siendo supuesto provisional. No se usaron datos reales de terceros.
