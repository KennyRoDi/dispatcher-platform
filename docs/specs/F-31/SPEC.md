# SPEC F-31: Benchmark de inferencia

**Fase:** verificacion
**Base:** main
**Verificación IA:** verificacion 1a0036a
**Historia:** US-31 · **Requisitos:** RF-40 (B.5 M5) · **Responsable:** J

## Objetivo

Medir una misma carga de inferencia (transcripción con Whisper) en varias configuraciones de cómputo y producir latencia, throughput y memoria por configuración, con repeticiones. El enunciado (B.5 M5) pide comparar CPU frente a GPU o, sin GPU, CPU con distinto número de hilos y modelo cuantizado frente a no cuantizado. Esos datos alimentan F-32 (routing por tipo de nodo) y la ficha M5 con su conexión con la Unidad 1.

## Alcance

**Incluye:** función pura de agregación de corridas; script de medición `scripts/measure/m5_bench.py` que reutiliza `WhisperTranscriber`; salida en CSV/JSON con una fila por configuración; prueba de integración corta en CPU.

**No incluye:** la política de routing (F-32); la ficha M5 final (F-41); entrenar o cambiar modelos; correr en GPU dentro de CI.

## Criterios de aceptación

- **Dado** el mismo conjunto de audio
- **Cuando** corre en al menos dos configuraciones
- **Entonces** se obtienen latencia, throughput y memoria, con repeticiones

Pruebas: U agregación. I corrida corta en CPU. Evidencia: ficha M5, tabla por configuración y conexión con Unidad 1.

## Diseño

- **Dominio** (`src/domain/benchmark.py`, nuevo, puro): `Corrida(config, repeticion, segundos, audio_segundos, memoria_pico_mb)`, `ResumenConfig(config, latencia_media_s, latencia_p95_s, throughput_x_realtime, memoria_pico_mb, repeticiones)` y `resumir(corridas)`. Throughput = segundos de audio / segundos de pared (factor de tiempo real). Latencia p95 por rango más cercano. Sin red, reloj ni E/S.
- **Script** (`scripts/measure/m5_bench.py`, infraestructura): recibe `--model --compute --threads --reps --audio` según IMPLEMENTACION §5; construye un `WhisperTranscriber` por configuración (`ConfigWhisper.compute_type` ∈ `int8|float32`, `hilos`), descarta una corrida de calentamiento, mide latencia con `time.perf_counter` y memoria pico del proceso con `psutil` (RSS, muestreado); imprime tabla y escribe JSON. El reloj y el transcriptor se inyectan para poder probarlo.
- **Contratos:** usa el puerto de transcripción existente sin modificarlo; no toca `docs/CONTRATOS.md`.
- **GPU:** `COMPUTE_TYPES` hoy solo admite `int8` y `float32`; `float16`/GPU requiere ampliarlo y un nodo con GPU. Se deja fuera de esta feature y se anota como «Medición pendiente».
- **Decisiones:** AD nueva no requerida; si se agrega `psutil` a `requirements-dev.txt`, se registra en la ficha.
- **Datos:** audio sintético ya generable con `src/adapters/media_generator.py` (sin datos de terceros).

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_resumen_calcula_latencia_y_throughput` | Agregación pura correcta |
| Unitaria | `test_resumen_agrupa_por_configuracion_y_exige_repeticiones` | Una fila por configuración; rechaza lista vacía |
| Unitaria | `test_p95_con_pocas_repeticiones` | Caso borde con 1–2 corridas |
| Integración | `test_bench_corto_en_cpu_dos_configuraciones` (marca `integration`) | Corrida real con audio corto, 2 configuraciones, salida completa |
| Aceptación | No aplica | La evidencia es la medición |

## Mediciones

Comando (IMPLEMENTACION §5): `python scripts/measure/m5_bench.py --model whisper-base --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio benchmark_set/`. Con GPU: añadir `gpu-float16` y registrar `nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv -l 1` durante la corrida. Destino: `docs/modulo-M5-computo.md`.
**Medición pendiente:** los valores reales los toma la persona en su máquina o en nodos; esta fase no los inventa. La variante GPU queda pendiente hasta tener GPU/Colab/Kaggle.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-31): benchmark de inferencia con agregación y script de medición` | `domain/benchmark.py`, `scripts/measure/m5_bench.py`, pruebas unitaria e integración, documentación y bitácora |

## Riesgos y preguntas abiertas

- ¿Hay GPU disponible (local, Colab o Kaggle)? Si no, se compara hilos y int8 frente a float32, permitido por B.5 M5.
- La memoria pico por RSS incluye el modelo cargado; se reporta por configuración, no por corrida.
- Medición pendiente: ejecutar en la máquina de José y, si F-38 lo permite, en los nodos.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | SPEC F-31 completo sin campos …, plan de 1 PR, medición pendiente anotada (45f017b) |
| plan | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de tests | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | 3 archivos de prueba nuevos, sin código; unitarias fallan por módulos ausentes (rojo) (b9209c2) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | domain/benchmark.py y scripts/measure/m5_bench.py; 15 unitarias en verde; integración omitida (faster_whisper no instalado local) (43efd15) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de verificacion | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | 15 unitarias en verde, arquitectura ok, bordes (vacía, tiempo 0) rechazados; 167 líneas de código; integración omitida (faster_whisper ausente); medición real pendiente (1a0036a) |
