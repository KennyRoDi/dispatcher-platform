# SPEC F-19: Estrategias de carga

**Fase:** implementacion
**Base:** main
**Verificación IA:** tests 54912ab
**Historia:** US-19 · **Requisitos:** RF-27, RNF-09 (comparación), RNF-14 · **Responsable:** J

## Objetivo

Permitir al responsable de M1 ejecutar un modelo por proceso y un modelo precargado compartido tras `fork`, comprobar sus resultados y comparar memoria total para justificar AD-07 con datos [B.5 M1]. La comparación inicial usa Whisper CPU de F-09; no demuestra todavía la huella ni la conveniencia de esa estrategia para texto o imagen.

## Alcance

**Incluye:** selección explícita de estrategia y N procesos, carga e inferencia con el transcriptor de F-09, validación Linux de igualdad y terminación, instrumentación RSS/PSS y `memory.current`, tabla comparativa y conclusión trazable en la ficha M1.

**No incluye:** entrenamiento; cambio de pesos, precisión o hilos entre variantes; admisión (F-17), OOM (F-18), cancelación del pipeline (F-12), routing/benchmark de cómputo (F-31/F-32), despliegue ajeno ni sustitución silenciosa de `fork` por `spawn` o `mmap`. Las huellas de otros modelos quedan pendientes y no se atribuyen a esta comparación.

## Criterios de aceptación

- **Dado** el parámetro de estrategia.
- **Cuando** se inicia con N procesos en cada variante.
- **Entonces** ambas producen el mismo resultado y se obtiene su memoria total.
- La selección distingue `por_proceso` y `fork_compartido`; rechaza otras estrategias y N no entero positivo, incluido `bool`. No degrada silenciosamente a otra variante.
- Todos los hijos procesan la misma entrada con pesos y parámetros idénticos. Se comparan todos los campos de `TranscriptSegment`, incluidos confianza y tiempos. Un error, timeout o diferencia impide declarar equivalencia.
- Se registra PSS total del supervisor y todos sus hijos vivos, RSS por PID y `memory.current` del mismo cgroup. La suma de RSS no se presenta como memoria física exclusiva.

## Diseño

Se aplica AD-07 y se propone SUP-25: comenzar con Whisper CPU de F-09, por su dependencia explícita y muestra disponible. La aprobación del plan decide ese alcance; no se elige estrategia definitiva antes de medir.

`src/domain/model_loading.py` contiene selección y validación puras. `src/infrastructure/model_loader.py` implementa `ModelLoader` con fábrica inyectada: `por_proceso` carga una instancia dentro de cada hijo; `fork_compartido` carga una instancia en un supervisor nuevo y la heredan sus N hijos. El supervisor permanece vivo durante la medición y se contabiliza. Se solicita `fork` explícitamente, sin depender del método predeterminado de Python 3.14. No se hace fork desde `worker_node.py`, que ya usa hilos, ni después de arrancar heartbeat, consumidores o clientes de red.

Se reutiliza `WhisperTranscriber.from_config` y el contrato `Transcriber.transcribe(Path) -> list[TranscriptSegment]` de `src/application/analyze_audio.py`. El dominio no importa adaptadores ni multiprocessing. Se conservan pesos/revisión, idioma, precisión y beam size de `config/audio.toml`; el experimento fija el mismo número de hilos en ambas variantes y registra el valor sin alterar la configuración productiva. No se modifican `Analyzer`, `WorkQueue`, `ResourceReader` ni otros puertos compartidos; se inyectan dobles locales en las pruebas de F-19.

Precargar antes de los hilos Python no garantiza ausencia de hilos nativos de CTranslate2, OpenMP o el tokenizador. La parte 2 exige prueba Linux con el modelo real antes de declarar listo el cargador. Un proceso externo impone timeout configurable explícito; un error termina y recolecta supervisor e hijos, también ante SIGTERM, sin zombies. No se hace inferencia de calentamiento en el padre antes de fork. Bloqueos, señales, salidas incompletas o diferencias detienen la comparación y requieren decisión humana antes de cambiar backend o estrategia.

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
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 2 --estrategias por_proceso fork_compartido --repeticiones 1 --timeout 120 --solo-validar --salida docs/evidencia/F-19/compatibilidad
```

Después de pasarla, cinco ejecuciones nuevas por variante y por N=1/N=2, con supervisor e hijos nuevos en cada ejecución:

```bash
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 1 2 --estrategias por_proceso fork_compartido --repeticiones 5 --timeout 120 --cgroup /sys/fs/cgroup --salida docs/evidencia/F-19/comparacion
```

Registrar baseline de `memory.current` antes de cargar e instantáneas tras carga y tras consumir toda la inferencia. Conservar el texto crudo de `/proc/<pid>/smaps_rollup` para supervisor y cada hijo y de `/sys/fs/cgroup/memory.current`, `memory.max` y `memory.swap.max`. Extraer `Rss:`/`Pss:` en KiB; sumar PSS y convertir a bytes por 1024 al cotejar unidades. La tabla incluye cada repetición, media y rango, memoria absoluta y diferencia frente al baseline. `memory.current` incluye otros cargos y no equivale a PSS. No hay otros trabajos simultáneos en ese cgroup; las lecturas son secuenciales con los procesos en la barrera, no una instantánea atómica. No se vacía la caché del host ni se exige root.

Destino: `docs/evidencia/F-19/` para crudos y metadatos; `docs/modulo-M1-memoria.md` para tabla, comandos, interpretación y límites; AD-07 para conclusión sustentada por esas rutas. No se exige un ahorro predeterminado: una variante puede no ahorrar. Sin nodo, compatibilidad real o lecturas válidas, la verificación de la parte queda pendiente y se solicita decisión humana; no se sustituye por Windows, dobles ni estimaciones.

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
