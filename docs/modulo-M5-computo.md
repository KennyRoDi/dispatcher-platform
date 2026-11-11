# Módulo M5: cómputo y benchmark de inferencia

Estado: implementado y con pruebas unitarias en verde. **Medición pendiente**: no hay cifras medidas en este documento.

## 1. Qué se implementó

- **Función pura de agregación** (`src/domain/benchmark.py`): `resumir()` agrupa las corridas por configuración y calcula latencia media, p95, throughput (segundos de audio procesados por segundo de cómputo) y memoria pico.
- **Script de medición** (`scripts/measure/m5_bench.py`): construye un `WhisperTranscriber` por configuración (`cpu-float32` o `cpu-int8`, con 1, 2 o 4 hilos), descarta una corrida de calentamiento, mide cada repetición y escribe un JSON con una fila por configuración.
- **Inyección de dependencias**: el reloj, la memoria y el transcriptor se pasan como parámetros, de modo que las pruebas no usan reloj real ni modelo.
- **Pruebas**: 15 pruebas unitarias en verde.
- **Integración: omitida**. `faster_whisper` no está instalado en la máquina de desarrollo, así que la prueba de integración corta en CPU no se ejecutó.
- **GPU: fuera de alcance**. `COMPUTOS` solo admite `cpu-float32` y `cpu-int8`. La variante `gpu-float16` requiere ampliar el script y un nodo con GPU.

## 2. Concepto de Sistemas Operativos

- **Planificación y hilos frente a núcleos.** El planificador del SO reparte el tiempo de CPU entre los hilos del proceso. Con más hilos que núcleos libres, los hilos compiten por el mismo tiempo y aumentan los cambios de contexto; con menos, parte de la capacidad queda ociosa. El parámetro `--threads` controla cuántos hilos pide el modelo, por lo que el número óptimo depende del hardware y debe medirse.
- **Memoria.** El proceso mantiene en RAM los pesos del modelo y los buffers de audio y de inferencia. La cuantización a `int8` reduce el tamaño de los pesos frente a `float32`, lo que disminuye la huella de memoria a costa de precisión numérica. La huella se mide como RSS (memoria residente) del proceso.
- **Medición del tiempo.** La latencia se mide con `time.perf_counter`, un reloj monotónico de alta resolución. El calentamiento se descarta porque la primera ejecución incluye carga de páginas y otras inicializaciones que no representan el uso sostenido.

## 3. Método de medición

Comando (IMPLEMENTACION §5):

```bash
python scripts/measure/m5_bench.py --model whisper-base --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio benchmark_set/
```

Con GPU, añadir `gpu-float16` y registrar en paralelo la utilización y la memoria de la tarjeta:

```bash
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv -l 1
```

Definiciones de las columnas:

- **Latencia media**: promedio de los tiempos de las repeticiones, sin el calentamiento.
- **Latencia p95**: percentil 95 de las repeticiones (método del índice `ceil(0.95·n)`).
- **Throughput**: duración total del audio dividida entre el tiempo total de cómputo. Un valor mayor que 1 indica procesamiento más rápido que tiempo real.
- **Memoria pico**: RSS máximo muestreado tras cada repetición con `psutil`. Es una muestra, no un máximo continuo, por lo que puede subestimar un pico breve dentro de una transcripción.

Antes de dar por válido un resultado, la persona que mide debe confirmar que la máquina no está ejecutando otras cargas pesadas.

## 4. Resultados

**Medición pendiente.** Los valores los toma la persona en su máquina o en los nodos cuando F-38 lo permita. Esta fase no estima ni inventa cifras.

| Configuración | Latencia media (s) | Latencia p95 (s) | Throughput (x tiempo real) | Memoria pico (MB) | Repeticiones |
|---|---|---|---|---|---|
| cpu-float32-h1 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| cpu-float32-h2 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| cpu-float32-h4 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| cpu-int8-h1 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| cpu-int8-h2 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| cpu-int8-h4 | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente | Medición pendiente |
| gpu-float16 | Medición pendiente (requiere GPU) | Medición pendiente (requiere GPU) | Medición pendiente (requiere GPU) | Medición pendiente (requiere GPU) | Medición pendiente (requiere GPU) |

## 5. Interpretación

Sin mediciones no hay conclusiones. Las preguntas que el benchmark debe responder cuando existan datos son:

- ¿Mejora la latencia al pasar de 1 a 2 y de 2 a 4 hilos, o el beneficio se estanca? Si se estanca, el exceso de hilos compite por los núcleos disponibles.
- ¿Cuánta memoria se ahorra con `int8` frente a `float32`, y cuánto cambia el throughput?
- ¿Qué configuración conviene en cada tipo de nodo? Este punto alimenta el enrutamiento de F-32.

Las cifras de F-32 (routing por tipo de nodo) y F-41 (fichas de evidencia) dependen de esta medición. Hasta que exista, cualquier afirmación sobre el mejor número de hilos o el ahorro de memoria es una hipótesis y no un resultado.

## 6. Routing por tipo de nodo (F-32)

**Justificación.** B.5 M5 pide dirigir cada tipo de sub-tarea a la clase de nodo que la ejecuta mejor. La política es una tabla estática tipo → clases en `config/routing.toml` (`[rutas]`), implementada por `RoutingTable` (`src/domain/routing.py`) y validada al arranque. Decisión registrada en AD-32 de `docs/ARQUITECTURA.md`.

**Valores provisionales.** Medición pendiente. Audio prefiere `gpu` y cae a `cpu`; texto e imagen van a `cpu`. Ningún valor sale de datos medidos. La referencia de cada uno está en `[evidencia]` de `config/routing.toml`.

**Medición que los sustituye.** F-31: `python scripts/measure/m5_bench.py --model whisper-base --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio benchmark_set/`. Sus resultados (sección 4) fijan el orden de clases.

**Pendiente.** Valores en nodos WSL2 reales (depende de F-38) y variante GPU, que queda pendiente hasta tener GPU.
