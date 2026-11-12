# F-41 · Lista de aceptación de fichas

**Corte inicial:** 2026-11-12, fase tests documental. Esta lista define qué comprobar; no registra experimentos nuevos. F-41 está exenta de TDD de lógica (`IMPLEMENTACION.md`, sección de pruebas); no se crean pruebas rojas artificiales para documentos o nodos ausentes.

**Estados:** cumple = evidencia suficiente para el producto y entorno indicados; parcial = existe evidencia limitada o falta validación; pendiente = no existe el registro exigido. Una feature de origen cerrada no acredita automáticamente su producto de evidencia. Una fila parcial o pendiente impide declarar aceptación completa de F-41.

## Lista RNF-09 a RNF-14

Rutas relativas a `docs/`. Los enlaces apuntan a material existente; la columna de aceptación indica el trabajo posterior necesario.

| Requisito / producto | Estado inicial | Evidencia existente / límite | Comprobación de aceptación |
|---|---|---|---|
| RNF-09: huella por modelo usado | parcial | [M1](../../modulo-M1-memoria.md), [F-19 comparación](../../evidencia/F-19/comparacion/run-20261111T050340678173Z.json); Whisper CPU, no todos los modelos | Tabla RSS/PSS por modelo y entorno, con cinco repeticiones según protocolo original y crudos por PID. No usar huellas sintéticas de operaciones como huellas medidas. |
| RNF-09: memoria por worker durante ráfaga | pendiente | M1 la declara pendiente; F-37 mide otro escenario | Gráfico con tiempo, unidad, worker y muestras crudas; distinguir saturación B.6 de ráfaga por worker. |
| RNF-09: OOM provocado y recuperación | parcial | [F-18 rep1](../../evidencia/mediciones-f18/F-18_corrida_rep1_2026-11-11.json), rep2/rep3 en el mismo directorio; arnés local sin WorkerNode/Redis | Verificar delta oom_kill, salida del hijo, política, reencolado y supervisor vivo. Conservar límites del arnés; falta evidencia del worker desplegado. |
| RNF-09: comparación de estrategias | parcial | F-19 comparación: N=1/N=2, cinco repeticiones por variante, Whisper CPU | Recalcular medias PSS/memory.current desde JSON; mismo modelo/carga/configuración, supervisor incluido. Acreditar solo la carga medida y explicar AD-07. |
| RNF-10: dos políticas bajo altas sostenidas | parcial | [F-21 CSV](../../evidencia/F-21_comparacion_politicas_2026-11-11.csv), [M2](../../modulo-M2-planificacion.md), FIFO/aging; simulación con reloj virtual | Identificar simulación y condiciones; no llamarla medición del SO o clúster. Revisar si el experimento satisface el requisito sin extrapolar al despliegue. |
| RNF-10: espera, turnaround y throughput por nivel | parcial | CSV F-21 solo baja/alta, semillas 42/43/44 | Recalcular agregados y unidades; explicitar los niveles no experimentados y obtener la evidencia del responsable necesaria para cubrirlos. |
| RNF-10: ausencia de inanición con datos | parcial | F-21 despacha casos bajos en escenario finito | No tratar promedio de 245.789 ms como máximo individual ni bono de 400 ms como cota universal de espera; demostrar afirmación con datos adecuados. FIFO no deja adelantar un caso ya en cola por llegadas posteriores. Corregir M2 y aclarar AD-04. |
| RNF-11: MB/s frente a tres tamaños de chunk | pendiente | [M3](../../modulo-M3-es-almacenamiento.md) declara pendiente F-22 entre nodos | Tres tamaños, comandos resueltos, tamaño de archivo, tiempos y crudos; distinguir MB/s de MiB/s y transferencia de complete. |
| RNF-11: tasa de deduplicación | parcial | [F-23 método](../../evidencia/F-23_deduplicacion_2026-11-11.md), [CSV](../../evidencia/m3_dedup_2026-11-11.csv), tres pasadas locales | Recalcular bytes ahorrados/lógicos y 66.936897%; conservar contexto del bucket inicial y las tres pasadas. Recálculo documental ejecutado: 66.9368965988105%, coincide a seis decimales; ver registro F-41. |
| RNF-11: profundidad y latencia con/sin backpressure | parcial | [CSV](../../evidencia/m3_backpressure_2026-11-11.csv), [gráfico](../../evidencia/m3_backpressure_2026-11-11.png); local sin workers | Verificar ambas condiciones, repeticiones, códigos, unidades y muestras faltantes; no presentar máximo muestreado como máximo real continuo. |
| RNF-12: manipulación detectada | parcial | [F-29](../../evidencia/F-29_prueba_A_local_sintetica_2026-11-11.md), datos sintéticos locales | Verificar cadena íntegra exit 0 y alterada exit 1, posición y comandos exactos; delimitar prueba local frente a demo/nodos. |
| RNF-12: accesos denegados por rol | parcial | [M4](../../modulo-M4-seguridad.md) tabla de códigos HTTP, demo local sin TLS, una petición por celda | Contrastar cada permiso con matriz; 409 de cancelación autorizada no significa denegación por rol. Conservar entorno y limitaciones de la ejecución. |
| RNF-12: captura de tráfico cifrado | pendiente | [F-27](../../evidencia/F-27_servidores_tls_local_2026-11-11.md) solo prueba local de servidores | Captura real entre nodos y comandos de análisis; handshake local no sustituye captura ni prueba ausencia de texto claro entre nodos. No publicar llaves ni tokens. |
| RNF-12: workers sin root | parcial | M4: UID 10001, raíz de solo lectura, cap_drop y no-new-privileges en una demo local | Salida de verificaciones efectivas por worker/nodo desplegado, ID y entorno; configuración declarada no sustituye ejecución. |
| RNF-13: latencia, throughput y memoria por configuración | parcial | [F-31 JSON](../../evidencia/F-31_m5_bench_2026-11-11.json), [método](../../evidencia/F-31_m5_bench_2026-11-11.md), CPU float32/int8, 1/2/4 hilos, cinco repeticiones | Recalcular tabla y unidades; confirmar condición de alternativa CPU si ningún integrante tiene GPU. No exigir GPU adicional si se cumple B.5 M5. |
| RNF-13: routing justificado por resultados | pendiente | [M5](../../modulo-M5-computo.md) y routing CPU/GPU declarados provisionales | Cada decisión de routing debe citar datos comparables; no inferir comparación GPU de un benchmark solo CPU ni convertir valores provisionales en medidos. |
| RNF-13: conexión Unidad 1 | parcial | Conceptos en M5, interpretación de hilos/cuantización | Explicar CPU/GPU/NPU y decisiones observadas sin atribuir aceleración no medida; enlazar bibliografía. |
| RNF-14: cinco fichas con cinco elementos | cumple (estructura) | M1, M2, M3, M4 y M5 existen y pasan revisar_ficha según verificación del orquestador | Mantener qué se implementó, concepto, método, resultados e interpretación; la estructura no acredita suficiencia semántica. |
| RNF-14: referencias y capítulos | parcial | Bibliografía presente en varias fichas; M2 sin referencia explícita | Autor, obra, edición y capítulo por concepto; SUP-16 mantiene edición del curso por confirmar. No inventar fuentes consultadas. |
| RNF-14: comandos y trazabilidad | parcial | Métodos y evidencias enlazados, con texto histórico obsoleto en M1 y pendientes explícitos | Revisar existencia de rutas, correspondencia con CLI vigente, condiciones/repeticiones y datos; consolidar F-19 futuro frente a resultados reales. |
| US-41: repetir un comando por ficha en otra máquina | pendiente | No hay cinco registros de reproducción independiente | Completar los cinco registros de la sección siguiente. Reejecutar en la misma máquina no satisface el criterio. |

## Reproducción requerida en otra máquina

Seleccionar un comando representativo ya documentado por ficha. La segunda máquina debe identificarse sin datos privados; registrar por qué es distinta del host original. Antes de ejecutar, resolver parámetros, dependencias y archivos públicos/sintéticos. Ninguna fila es una ejecución realizada.

| Ficha | Comando candidato / protocolo existente | Prerrequisitos y salida esperada de la comprobación | Estado |
|---|---|---|---|
| M1 | Protocolo de `scripts/measure/comparar_carga.py` en [QA F-19 parte 3](../F-19/QA-parte-3.md) | Linux con cgroup v2 limitado, modelo/audio del protocolo; JSON con RSS/PSS/memory.current y cinco repeticiones por variante | pendiente |
| M2 | `SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate 100 --low 5 --seed 42 --out m2_fifo_42.csv` | Python y dependencias; ejecutar desde raíz; CSV de simulación. No acredita medición del SO | pendiente |
| M3 | Protocolo `scripts/measure/m3_dedup.py` de [F-23](../../evidencia/F-23_deduplicacion_2026-11-11.md) | Dataset sintético con procedencia, coordinador/MinIO aislados y bucket inicial vacío; CSV de tres pasadas | pendiente |
| M4 | Protocolo `python -m scripts.verify_custody` de [F-29](../../evidencia/F-29_prueba_A_local_sintetica_2026-11-11.md) | Log/objetos sintéticos y llave efímera fuera del repositorio; salida íntegra exit 0 y alteración exit 1 | pendiente |
| M5 | Protocolo `scripts/measure/m5_bench.py` de [F-31](../../evidencia/F-31_m5_bench_2026-11-11.md) | Audio público/licenciado, modelo y configuración registrados; float32/int8, 1/2/4 hilos, cinco repeticiones tras calentamiento; JSON | pendiente |

Cada registro real en `docs/evidencia/F-41/` incluirá: módulo, ejecutor, fecha UTC, commit, máquina/entorno/versiones, procedencia de entrada, comando exacto resuelto, condiciones/repeticiones, salida cruda, código de retorno, comparación e interpretación de diferencias. Nunca guardar secretos ni modificar retrospectivamente el crudo original. La variación entre máquinas no es por sí sola un fallo; sí lo son una salida ausente, un comando que no corresponde o una conclusión sin apoyo.

## Cierre de aceptación

Correcciones documentales y recálculos ejecutados según la sección siguiente. Pendiente: completar los productos RNF parciales, incorporar únicamente ejecuciones reales y repetir los cinco comandos en otra máquina. Registrar resultados finales por fila y distinguir bloqueos externos. No cerrar F-41 como satisfecha mientras falten productos RNF o reproducción. Las excepciones documentales del flujo omiten rojo/código, no estos criterios.

## Resultado de implementación documental (2026-11-12)

Se corrigieron las cinco fichas y AD-04: M1 consolida el método F-19 ya ejecutado; M2 distingue medias, ventana de adelantamiento y simulación; M3 separa unidades y muestreo; M4 reconoce datos locales sin atribuirlos al clúster; M5 usa flags vigentes y MiB, con GPU condicional. Se añadieron responsables y bibliografía M2/M5 reutilizando R2.

[Recálculos ejecutados y comando exacto](../../evidencia/F-41/recalculos.md): M1 medias PSS, M2 agregados, M3 deduplicación y M5 transcripción de agregados coinciden con el redondeo documentado. Los cinco comprobadores estructurales devuelven lista vacía. Esto corrige documentación, no cambia a cumplidos los productos experimentales parciales o pendientes de arriba. M2/M5 ya incorporan referencias; SUP-16 sigue abierto.

Impedimento temporal comprobado por el orquestador en este host: Docker CLI instalado pero daemon Linux inaccesible (pipe dockerDesktopLinuxEngine inexistente), y Tailscale CLI instalado pero servicio tailscaled sin conexión. No describe el estado de máquinas remotas ni acredita una ejecución distribuida. Las cinco reproducciones en otra máquina siguen pendientes.

## Decisión de entrega documental (2026-11-12)

La persona responsable decidió subir las fichas en su estado actual y cerrar el trabajo documental aceptando los pendientes. Los estados parciales y pendientes de esta lista se mantienen: no se declaran RNF completos ni reproducciones realizadas. No se logró cerrar formalmente F-41.

Deuda: completar huellas/ráfaga/validación desplegada M1; niveles e inanición M2; throughput distribuido por tamaños M3; TLS y controles desplegados M4; routing y condición de alternativa CPU M5; y las cinco reproducciones US-41 en otra máquina. Esta decisión no modifica los datos existentes ni sustituye la evidencia faltante.
