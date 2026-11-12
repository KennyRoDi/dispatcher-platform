# Módulo M5: cómputo y benchmark de inferencia

**Responsable:** José Andrés Loría Herrera (`joselhcr`).

Estado: implementado y con pruebas unitarias en verde. Medido en CPU el 2026-11-11 en un único host Docker Desktop (sección 4). **Pendiente:** justificar routing (F-32) con datos comparables y reproducción en otra máquina. GPU solo corresponde si no aplica la alternativa CPU de B.5 M5 (ningún integrante con acceso a GPU).

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

Comando realmente registrado en la evidencia F-31 (rutas del contenedor original):

```bash
python scripts/measure/m5_bench.py --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio /bench --config /audio_en.toml --salida /bench/m5_bench.json
```

Preparar `/bench` con el WAV público descrito en la evidencia y `/audio_en.toml` con su idioma; en otra máquina resolver esas rutas. La CLI no admite `--model` ni `--out`: usa `--config` y `--salida`. El runner actual solo admite CPU. Si el equipo requiere comparar GPU, esa capacidad pertenece a la feature de origen; no añadir `gpu-float16` a este comando como si funcionara. Para un futuro experimento GPU, el monitor sería:

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

**Medido el 2026-11-11** en un único host (Windows 11, Docker Desktop 29.7.2, contenedor `python:3.13`, 16 CPU lógicas Ryzen 7 5700X, ~16 GB), no en nodos separados. faster-whisper 1.2.1, CTranslate2 4.9.0, PyAV 18.1.0, modelo `base`, un clip público de 11.372 s (jfk.flac, repo MIT de faster-whisper, idioma `en`), 5 repeticiones tras calentamiento. Comando exacto, salida cruda y limitaciones en [F-31_m5_bench_2026-11-11.md](evidencia/F-31_m5_bench_2026-11-11.md). El experimento no representa nodos separados ni audios largos. GPU es condicional según B.5 M5; no constituye un faltante obligatorio si el equipo cumple la alternativa CPU.

| Configuración | Latencia media (s) | Latencia p95 (s) | Throughput (x tiempo real) | RSS máximo muestreado (MiB) | Repeticiones |
|---|---|---|---|---|---|
| cpu-float32-h1 | 2.310 | 2.505 | 4.922 | 488 | 5 |
| cpu-float32-h2 | 1.611 | 1.653 | 7.057 | 470 | 5 |
| cpu-float32-h4 | 1.321 | 1.367 | 8.612 | 519 | 5 |
| cpu-int8-h1 | 1.954 | 2.233 | 5.821 | 317 | 5 |
| cpu-int8-h2 | 1.049 | 1.187 | 10.841 | 343 | 5 |
| cpu-int8-h4 | 0.828 | 0.947 | 13.727 | 345 | 5 |

## 5. Interpretación

Lectura de la medición del 2026-11-11 (un host, un clip de 11 s; no generalizar a los nodos):

- Hilos: de 1 a 2 hilos la latencia media baja ~30 % en float32 (2.310 a 1.611 s) y ~46 % en int8 (1.954 a 1.049 s); de 2 a 4 baja menos (float32 1.611 a 1.321 s; int8 1.049 a 0.828 s). No se midió más allá de 4 hilos, así que no se sabe dónde se estanca.
- int8 frente a float32: RSS máximo muestreado 317-345 MiB frente a 470-519 MiB, y throughput 1.2 a 1.6 veces mayor con el mismo número de hilos.
- Todas las configuraciones superan el tiempo real (throughput > 4.9).

Las preguntas que el benchmark debe seguir respondiendo con nodos reales son:

- ¿Mejora la latencia al pasar de 1 a 2 y de 2 a 4 hilos, o el beneficio se estanca? Si se estanca, el exceso de hilos compite por los núcleos disponibles.
- ¿Cuánta memoria se ahorra con `int8` frente a `float32`, y cuánto cambia el throughput?
- ¿Qué configuración conviene en cada tipo de nodo? Este punto alimenta el enrutamiento de F-32.

Las cifras de F-32 (routing por tipo de nodo) y F-41 (fichas de evidencia) dependen de esta medición. Las afirmaciones sobre hilos y memoria valen solo para la medición de la sección 4; para otros nodos siguen siendo hipótesis.

## 6. Routing por tipo de nodo (F-32)

**Justificación.** B.5 M5 pide dirigir cada tipo de sub-tarea a la clase de nodo que la ejecuta mejor. La política es una tabla estática tipo → clases en `config/routing.toml` (`[rutas]`), implementada por `RoutingTable` (`src/domain/routing.py`) y validada al arranque. Decisión registrada en AD-32 de `docs/ARQUITECTURA.md`.

**Valores provisionales.** Medición pendiente: F-31 midió solo CPU en un único host, así que no hay datos por clase de nodo (`gpu` frente a `cpu`) con los que cambiar la tabla. Audio prefiere `gpu` y cae a `cpu`; texto e imagen van a `cpu`. Ningún valor sale de datos medidos. La referencia de cada uno está en `[evidencia]` de `config/routing.toml`.

**Medición que los sustituye.** F-31: `python scripts/measure/m5_bench.py --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio /bench --config /audio_en.toml --salida /bench/m5_bench.json`. Sus resultados (sección 4) comparan configuraciones CPU, no fijan un orden entre CPU y GPU.

**Pendiente.** La medición de la sección 4 no compara clases CPU/GPU, por lo que no justifica esa preferencia y `config/routing.toml` no se modificó. Si se aplica la alternativa CPU autorizada por B.5 M5, se deben justificar las configuraciones/rutas disponibles con sus datos, sin exigir GPU adicional ni inventar una comparación entre clases.

**Unidad 1 y bibliografía.** CPU, GPU y NPU tienen organizaciones y grados de paralelismo distintos; este experimento solo compara CPU con hilos y cuantización. No mide aceleración GPU/NPU. R2 de ARQUITECTURA: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed., capítulos 1 (organización del sistema), 4 (hilos) y 5 (planificación); edición del curso por confirmar según SUP-16. Se reutiliza la referencia existente, sin atribuirle resultados del benchmark. El campo histórico `memoria_pico_mb` divide RSS por 1024²: la unidad es MiB y el máximo es entre muestras tras repeticiones, no un pico continuo.
