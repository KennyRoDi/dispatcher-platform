# QA F-19, parte 2: compatibilidad de carga con Whisper

**Resultado inicial:** `fork_compartido` falló. Se registró ADD delegada y se cambió a `workers_compartidos`. Fecha: 2026-11-10. Rama `feat/F-19-2-estrategias-de-carga`.

## Entorno reproducible

Docker Desktop 29.7.2, motor Linux, cgroups v2; imagen `python:3.13-slim`, Python 3.13.18; faster-whisper 1.2.1, PyAV 18.1.0 y CTranslate2 4.9.0. Pesos `Systran/faster-whisper-base`, revisión de `config/audio.toml`; entrada sintética `tests/datos/audio/amenaza_01.ogg`. El caché HF del host se montó en el contenedor. Sin GPU.

Comando usado para la puerta inicial (la estrategia fallida):

```sh
pip install pytest faster-whisper==1.2.1 av==18.1.0 ctranslate2==4.9.0
python -m pytest -q tests/integration/test_fork_runtime.py --tb=short
```

Resultado: `TimeoutError: el proceso excedió el tiempo límite` con el timeout prescrito de 120 s. Python emitió `DeprecationWarning: This process is multi-threaded, use of fork() may lead to deadlocks in the child.` El segundo intento con caché persistente también expiró (124.95 s). Con `hilos=1`, N=1 también agotó el timeout diagnóstico de 30 s.

## Diagnóstico aislado

Se ejecutó cada variante en un contenedor/proceso limpio, con timeout diagnóstico de 30 s; no se reutilizó un padre después de inferencia:

| Variante | N | Resultado | Duración |
|---|---:|---|---:|
| `por_proceso` | 1 | 1 salida | 2.3 s |
| `por_proceso` | 2 | 2 salidas | 2.5 s |
| `fork_compartido` | 1 | timeout | 31.3 s |
| `fork_compartido` | 2 | timeout | 31.3 s |

Control de carga del modelo: proceso recién iniciado tenía 16 hilos tras importar el stack; al cargar Whisper tenía 20. Una prueba diagnóstica independiente reportó 1 antes de cargar y 21 después; su resultado no se usó para la tabla por haber ejecutado inferencia directa antes de probar estrategias. La advertencia de Python y el crecimiento de hilos son observaciones; no prueban por sí solos cuál hilo queda bloqueado. Los procesos hijos se terminaron y recolectaron al vencer el timeout.

Las pruebas del runtime Linux para retorno, rechazo de `spawn`, excepción del hijo y timeout/limpieza: 4 passed en Docker. Las regresiones parte 1 y arquitectura: 56 passed en Windows; 4 skipped en ese host porque requiere POSIX. Conformidad: 0 problemas.

## Resultado de la estrategia soportada

Se eligió `workers_compartidos`: faster-whisper 1.2.1 pasa `num_workers` a CTranslate2 como `inter_threads`; CTranslate2 documenta concurrencia desde hilos y pesos compartidos. La SPEC y AD-07 se actualizaron antes de continuar.

Repetición real Linux: `python -m pytest tests/integration/test_fork_runtime.py -q` → **5 passed en 5.87 s**. Incluye retorno, rechazo de `spawn`, error del hijo, timeout/limpieza y Whisper real N=2 comparando los segmentos completos entre `por_proceso` y `workers_compartidos`. Entorno y versiones indicados arriba; caché montado; sin GPU.

## Control adicional solicitado: hilos=1

En un contenedor limpio se creó un `audio.toml` temporal cambiando solo `hilos = 0` por `hilos = 1`; se usó `OMP_NUM_THREADS=1`, modelo/revisión originales y N=1. Resultado: `por_proceso` produjo una salida en 6.22 s; `fork_compartido` excedió 30 s en 31.37 s. El padre tenía 1 hilo antes de cargar Python/modelos y 3 tras la precarga compartida. La advertencia de Python sobre fork de procesos multihilo apareció en la prueba pytest anterior; el control adicional confirmó el timeout con hilos limitados. El archivo productivo `config/audio.toml` no se modificó.

Conclusión acotada: fijar hilos no vuelve compatible el fork del modelo en este entorno. `workers_compartidos` sí pasó igualdad real en Linux; esto no constituye medición de memoria ni justifica todavía una estrategia definitiva.

## Verificación posterior en Windows

`pytest tests/integration/test_fork_runtime.py -q` → **5 skipped en 0.15 s**. El runtime es POSIX y está marcado correctamente para omitir estos casos en Windows; esta omisión no cambia el resultado Linux de 5 passed ni el fallo de `fork_compartido`.
