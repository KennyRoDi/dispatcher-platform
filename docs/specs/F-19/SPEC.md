# SPEC F-19: Estrategias de carga

**Fase:** revision
**Base:** feat/F-19-1-estrategias-de-carga
**Verificación IA:** documentacion 10d4b01
**Historia:** US-19 · **Requisitos:** RF-27, RNF-09 (comparación), RNF-14 · **Responsable:** J

## Objetivo

Permitir al responsable de M1 ejecutar un modelo por proceso y un modelo con workers concurrentes de CTranslate2 que comparten pesos, comprobar resultados y comparar memoria total para justificar AD-07 con datos [B.5 M1]. La comparación inicial usa Whisper CPU de F-09; no demuestra todavía la huella ni la conveniencia para texto o imagen.

## Alcance

**Incluye:** selección explícita de estrategia y N trabajos, carga e inferencia con el transcriptor de F-09, validación Linux de igualdad y terminación, instrumentación RSS/PSS y `memory.current`, tabla comparativa y conclusión trazable en la ficha M1.

**No incluye:** entrenamiento; cambio de pesos, precisión o hilos intra-op entre variantes; admisión (F-17), OOM (F-18), cancelación del pipeline (F-12), routing/benchmark de cómputo (F-31/F-32), despliegue ajeno ni afirmar que los procesos independientes comparten memoria. Las huellas de otros modelos quedan pendientes y no se atribuyen a esta comparación.

## Criterios de aceptación

- **Dado** el parámetro de estrategia.
- **Cuando** se inicia con N ejecuciones concurrentes en cada variante.
- **Entonces** ambas producen el mismo resultado y se obtiene su memoria total.
- La selección distingue `por_proceso` y `workers_compartidos`; rechaza otras estrategias y N no entero positivo, incluido `bool`. No degrada silenciosamente a otra variante.
- Todos los trabajos procesan la misma entrada con pesos y parámetros idénticos. Se comparan todos los campos de `TranscriptSegment`, incluidos confianza y tiempos. Un error, timeout o diferencia impide declarar equivalencia.
- Se registra PSS total del supervisor y todos sus hijos vivos, RSS por PID y `memory.current` del mismo cgroup. La suma de RSS no se presenta como memoria física exclusiva.

## Diseño

Se aplica AD-07 y se propone SUP-25: comenzar con Whisper CPU de F-09, por su dependencia explícita y muestra disponible. La aprobación del plan decide ese alcance; no se elige estrategia definitiva antes de medir.

`src/domain/model_loading.py` contiene selección y validación puras. `src/infrastructure/model_loader.py` implementa `ModelLoader` con fábrica inyectada: `por_proceso` carga una instancia dentro de cada proceso hijo; `workers_compartidos` crea una instancia Whisper con `num_workers=N` y ejecuta N llamadas desde hilos en un solo proceso hijo. faster-whisper pasa `num_workers` a CTranslate2 como `inter_threads`, que comparte los pesos entre workers. Un proceso supervisor externo aplica timeout y contabiliza sus procesos. No se hace fork después de cargar el modelo.

Se reutiliza `WhisperTranscriber.from_config` y el contrato `Transcriber.transcribe(Path) -> list[TranscriptSegment]` de `src/application/analyze_audio.py`. El dominio no importa adaptadores ni multiprocessing. Se conservan pesos/revisión, idioma, precisión y beam size de `config/audio.toml`; el experimento fija el mismo número de hilos en ambas variantes y registra el valor sin alterar la configuración productiva. No se modifican `Analyzer`, `WorkQueue`, `ResourceReader` ni otros puertos compartidos; se inyectan dobles locales en las pruebas de F-19.

La estrategia anterior `fork_compartido` se bloqueó en Linux con Whisper real, incluso con un hilo. `workers_compartidos` carga CTranslate2 dentro del hijo y emplea su paralelismo documentado. La parte 2 exige prueba Linux con el modelo real. Un proceso externo impone timeout configurable y recolecta el hijo ante error o SIGTERM sin zombies.

`scripts/measure/comparar_carga.py` será la entrada independiente del experimento y `src/infrastructure/model_memory.py` leerá smaps/cgroup. Barreras IPC mantienen vivos supervisor e hijos tras carga y tras inferencia hasta leerlos; no se leen PIDs ya terminados. Se registran PID, parentesco, UTC, configuración, versiones, hash de entrada, salidas y errores. Una lectura ausente o inválida invalida la repetición. La CLI ofrece validación de igualdad sin atribuir mediciones de SO y medición con datos crudos.

Los workers heredados del I Proyecto procesan multimedia con hilos y carecen de un cargador reutilizable. Se reutilizan transcriptor y muestra sintética de F-09 y se agrega composición aislada para M1, sin cambiar al consumidor heredado. Este comando ejecuta realmente ambas estrategias; no se limita a declarar una configuración.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_configuracion_elige_estrategia`, estrategias y N inválidos | Selección pura sin red, sleep ni reloj real |
| Unitaria | Fábrica/operaciones de proceso inyectadas: orden cargar/fork, carga por hijo, error y recolección | Protocolo de las variantes; no demuestra seguridad nativa |
| Unitaria | Archivos temporales RSS/PSS, unidades, lecturas ausentes y suma incluyendo supervisor | Cálculo y validación sin medir el SO |
| Integración | Linux con transcriptor determinista: N=1/N=2, igualdad, error, timeout y SIGTERM | Ciclo real de procesos e IPC; marcador `integration` |
| Integración | Linux, Whisper real de F-09, N=2, ambas variantes, `amenaza_01.ogg`, timeout externo 120 s | Igualdad exacta de segmentos y compatibilidad en ese entorno; puerta obligatoria antes de declarar listo el cargador |
| Contrato | Mismo protocolo `Transcriber` para doble y transcriptor real de ambas variantes | Tipos y contenido de segmentos sin cambiar puertos compartidos |
| Aceptación | CLI selecciona variantes, registra N salidas y rechaza divergencia o lecturas ausentes | US-19 de extremo a extremo en el experimento M1 |

## Mediciones

Solo M1 [B.5 M1], sin TDD de cifras físicas. Los siguientes comandos son la interfaz propuesta de un script por implementar; **no se han ejecutado ni hay mediciones en este plan**. Ejecutarlos desde la raíz del repositorio dentro de un contenedor Linux no root de un nodo worker real, VM WSL2 según ARQUITECTURA §6, con cgroup v2 limitado y pesos previamente disponibles. Registrar nodo, kernel, Python, dependencias, revisión de pesos, límite, swap y comandos resueltos. El límite debe estar configurado y documentado, no estimado. Escribir la lógica no depende de implementar F-16/F-17.

Puerta de compatibilidad previa:

```bash
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 2 --estrategias por_proceso workers_compartidos --repeticiones 1 --timeout 120 --solo-validar --salida docs/evidencia/F-19/compatibilidad
```

Después de pasarla, cinco ejecuciones nuevas por variante y por N=1/N=2, con supervisor e hijos nuevos en cada ejecución:

```bash
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 1 2 --estrategias por_proceso workers_compartidos --repeticiones 5 --timeout 120 --cgroup /sys/fs/cgroup --salida docs/evidencia/F-19/comparacion
```

Registrar baseline de `memory.current` antes de cargar e instantáneas tras carga y tras consumir toda la inferencia. Conservar el texto crudo de `/proc/<pid>/smaps_rollup` para supervisor y cada hijo y de `/sys/fs/cgroup/memory.current`, `memory.max` y `memory.swap.max`. Extraer `Rss:`/`Pss:` en KiB; sumar PSS y convertir a bytes por 1024 al cotejar unidades. La tabla incluye cada repetición, media y rango, memoria absoluta y diferencia frente al baseline. `memory.current` incluye otros cargos y no equivale a PSS. No hay otros trabajos simultáneos en ese cgroup; las lecturas son secuenciales con los procesos en la barrera, no una instantánea atómica. No se vacía la caché del host ni se exige root.

Destino: `docs/evidencia/F-19/` para crudos y metadatos; `docs/modulo-M1-memoria.md` para tabla, comandos, interpretación y límites; AD-07 para conclusión sustentada por esas rutas. No se exige un ahorro predeterminado: una variante puede no ahorrar. Sin nodo, compatibilidad real o lecturas válidas, la verificación de la parte queda pendiente y se solicita decisión humana; no se sustituye por Windows, dobles ni estimaciones.

## Resultados de parte 2

En Docker Linux 29.7.2, Python 3.13.18, faster-whisper 1.2.1, PyAV 18.1.0 y CTranslate2 4.9.0, `fork_compartido` agotó el timeout de 120 s; con `hilos=1`, también agotó el timeout diagnóstico de 30 s. `workers_compartidos` pasó la prueba Linux con Whisper real N=2 y comparación completa de segmentos. Las 5 integraciones pasaron en 5.87 s; las 51 pruebas unitarias focales pasaron en Windows. Detalle y límites en [QA-parte-2.md](QA-parte-2.md). Esto acredita compatibilidad en ese entorno, no una medición de memoria ni una elección definitiva para M1.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-19): seleccionar estrategia de carga de modelos` | Selección pura y protocolo de carga con operaciones inyectadas; unitarias y límite documentado. Hasta 150 líneas de producto. No acredita procesos ni memoria reales |
| 2 | `feat(F-19): ejecutar carga por proceso y compartida con fork` | Supervisor Linux, ciclo de procesos y composición Whisper; prueba real obligatoria de igualdad/compatibilidad, fallos y recolección. Hasta 400 líneas de producto; base parte 1 |
| 3 | `feat(F-19): medir memoria y comparar estrategias de carga` | Lector RSS/PSS, CLI de validación/medición, crudos, ficha M1 y conclusión AD-07. Hasta 400 líneas de producto; base parte 2. Dividir antes de cerrar si excede el límite |

## Riesgos y preguntas abiertas

- Aprobar o ajustar SUP-25: comparación inicial de Whisper CPU, sin generalizar a texto/imagen ni dar por medida la tabla completa de huellas M1.
- Seguridad de fork con CTranslate2 no comprobada. Python advierte sobre hilos/fork ([os.fork](https://docs.python.org/3.14/library/os.html#os.fork)); faster-whisper expone paralelismo nativo ([fuente v1.2.1](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)). Fijar un hilo no demuestra ausencia de hilos nativos. Si falla la puerta real, detenerse y proponer decisión humana.
- Confirmar acceso al nodo Linux/WSL2 con smaps/cgroup legibles y memoria limitada antes de parte 2. No se modifica `deploy/` ni se presume que Windows demuestre CoW.
- N=1/N=2, cinco repeticiones, un hilo y timeout 120 s son parámetros propuestos, no capacidad medida ni política productiva. Registrar cualquier ajuste y pedir decisión si cambia el SPEC aprobado.
- CoW puede perder ahorro durante inferencia; el supervisor añade memoria y se incluye. Un modelo, entrada y nodo no justifican una elección universal.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Codex | 2026-11-10 | Revision independiente del diff f3b5abe contra US-19, RF-27 y B.5 M1; SPEC sin campos pendientes, contratos conservados y pila de hasta 400 lineas. git diff --check HEAD^ HEAD limpio; python -m scripts.conformidad repo: 0 problemas; arbol limpio y HEAD igual a upstream. Solo documentos; no se ejecutaron inferencias ni mediciones. Compatibilidad real de fork pendiente para parte 2. Corregida colision SUP-24 usando SUP-25. (f3b5abe) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Codex | 2026-11-10 | Revision independiente de 54912ab contra SPEC parte 1: solo dos archivos nuevos de pruebas, seleccion y validacion estrategia/N y protocolo con fabrica/runtime inyectados, sin implementacion. python -m pytest -q tests/unit/test_model_loading.py tests/unit/test_model_loader.py --tb=short: 46 failed por ModuleNotFoundError de src.domain.model_loading ausente; coleccion correcta sin skip ni xfail. git diff --check limpio; conformidad repo 0 problemas; arbol limpio y HEAD igual upstream. Suite general bloqueada por fallo preexistente Windows os.geteuid en test_dataset_sintetico_qa2.py:46. No procesos reales ni mediciones; pendientes partes 2 y 3. (54912ab) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Codex | 2026-11-10 | Revision independiente de aa73b49 contra SPEC parte 1: 83 lineas de producto en dominio e infraestructura, tests intactos desde 54912ab. Ejecucion propia pytest focal y arquitectura: 50 passed; conformidad repo 0 problemas; diff check limpio, arbol limpio y HEAD igual upstream. Suite general bloqueada por os.geteuid Windows preexistente. Subagente ejecuto complementaria sin ese archivo: 1611 passed, 2 failed, 4 skipped, 13 xfailed, 8 deselected. Reproduje independientemente ambos fallos en baseline 887f2c7: ruta /etc/passwd y XPASS strict nombre malicioso, 2 failed 2 passed. Sin regresiones nuevas detectadas; suite general no verde y aprobacion ordinaria bloqueada. No procesos reales ni mediciones; parte 2 pendiente. (aa73b49) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 | Autorizado por la persona: suite general bloqueada por os.geteuid en Windows y dos fallos preexistentes reproducidos en baseline 887f2c7; pruebas focales y arquitectura 50 passed, sin cambios en tests |
| verificación IA de verificacion | Codex | 2026-11-10 | Revision independiente QA parte1 commit 3c75908: criterios del SPEC trazados y limites partes2/3 explicitos. Ejecute pytest focal con seis nuevas pruebas QA y arquitectura: 56 passed. Reproduje script mutaciones: 6 de 6 detectadas; conteo coincide con seis casos y salida cruda. Conformidad 0 problemas; diff check limpio; src y pruebas originales intactos; arbol limpio y HEAD upstream coinciden. No mediciones SO aplicables a parte1. Suite general no verde por os.geteuid Windows y fallos preexistentes ya documentados; no se extiende excepcion sin autorizacion humana para esta fase. (3c75908) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 | Autorizado por la persona para verificacion: suite general bloqueada por os.geteuid Windows y fallos preexistentes documentados; 56 pruebas focales y arquitectura aprobadas y 6/6 mutaciones detectadas |
| verificación IA de documentacion | Codex | 2026-11-10 | Revision independiente de dc0b28c contra codigo, SPEC y QA parte1: ficha M1 describe LoadingConfig/ModelLoader existentes y distingue dobles de procesos/mediciones reales pendientes; AD07/SUP25 reflejan aprobacion de plan sin eleccion definitiva. Borrador bitacora veraz con campos del script y error real SUP24/SUP25; pendiente publicacion tras aprobacion humana. Solo cuatro documentos; sin cambios en src/tests/BITACORA_IA/STATUS. Conformidad repo 0 problemas y diff check limpio; arbol limpio y HEAD upstream coinciden. No mediciones nuevas ni repeticion innecesaria de suite para documentacion. (dc0b28c) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de revision | Codex | 2026-11-10 | Revision independiente de d9cd5b0 y diff completo contra SPEC: subagente revisor informa APROBADO sin hallazgos para parte1; inspeccione informe, capas, commits, limite 83/150 lineas y limites de evidencia. Conformidad repo 0 problemas; diff check limpio; arbol limpio y HEAD igual upstream. QA focal 56 passed y mutaciones 6/6 verificados antes. Sin mediciones SO, cuya ejecucion corresponde a partes 2/3. (d9cd5b0) |
| revision | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Codex | 2026-11-10 | Pruebas parte2 escritas y ejecutadas en Docker Linux python:3.13-slim: 4 failed exclusivamente por ModuleNotFoundError src.infrastructure.fork_runtime ausente; runtime aun no existe. Solo se agrego tests/integration/test_fork_runtime.py, sin implementacion. Casos POSIX de resultado, rechazo spawn, excepcion hija y timeout/terminacion/recoleccion. (17ed894) |
| tests | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat; tests rojos por implementación ausente |
| verificación IA de implementacion | Codex GPT-6 Luna | 2026-11-10 | 51 unitarias model_loading/model_loader y QA pasaron en Windows; 5 integraciones incl. Whisper real pasaron en Docker Linux Python 3.13, faster-whisper 1.2.1/CTranslate2 4.9.0; git diff --check limpio. Verificación en misma sesión, no independiente. ADD/SPEC actualizadas por fork incompatible. (b7b5b1d) |
| verificación IA de implementacion | Codex GPT-6 Luna | 2026-11-10 | 51 unitarias model_loading/model_loader y QA pasaron en Windows; 5 integraciones incl. Whisper real pasaron en Docker Linux Python 3.13, faster-whisper 1.2.1/CTranslate2 4.9.0; git diff --check limpio. Verificación en misma sesión, no independiente. ADD/SPEC actualizadas por fork incompatible. (3e97344) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de verificacion | Codex GPT-6 Luna | 2026-11-10 | QA parte 2: 51 unitarias y 5 integraciones ya aprobadas; caso Whisper real valida igualdad de 2 salidas entre ambas estrategias en Docker Linux. Fork precargado falla por timeout y se documenta sin ocultarlo. Verificación misma sesión, no independiente; sin repetir pruebas pasadas. (33f5121) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de documentacion | Codex | 2026-11-10 | Documentación parte 2: resumen y enlace al QA Linux en SPEC; QA-parte-2.md conserva timeout real de fork, prueba completa workers_compartidos y límites. Bitácora IA publicada por flujo.py; error real de edición en worktree incorrecto registrado y revertido. Sin pruebas repetidas; verificación documental según flujo y no independiente. (10d4b01) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
