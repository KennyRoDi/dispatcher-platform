# QA F-19, parte 3: medición M1

**Estado:** PENDIENTE; no se declara medición ni se aprueba verificación. Rama `feat/F-19-3-estrategias-de-carga`.

## Verificación local

- `tests/unit/test_model_memory.py`: 8 passed.
- `tests/unit/test_comparar_carga.py` y `tests/unit/test_model_memory.py`: 16 passed.
- `tests/unit/test_whisper_transcriber.py`: 42 passed.
- `tests/integration/test_comparar_carga.py`: 3 skipped en Windows; requieren POSIX.
- `git diff --check`: limpio.

Estas pruebas cubren parseo de RSS/PSS, validación cgroup, CLI, equivalencia y agregación. No demuestran memoria real ni ejecución del runtime de medición en Linux.

## Bloqueo de entorno

No se ejecutaron el preflight ni las repeticiones M1. `docker info` no encuentra `npipe:////./pipe/dockerDesktopLinuxEngine`; WSL devuelve `Wsl/E_ACCESSDENIED`. No hay nodo Linux worker accesible ni lecturas válidas de `/proc/<pid>/smaps_rollup` y cgroup v2 limitado.

## Pendiente para cerrar

En un nodo Linux worker accesible, con cgroup v2 finito y `memory.swap.max=0`, pesos disponibles y sin otros trabajos en el cgroup:

```bash
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 2 --estrategias por_proceso workers_compartidos --repeticiones 1 --timeout 120 --solo-validar --salida docs/evidencia/F-19/compatibilidad
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 1 2 --estrategias por_proceso workers_compartidos --repeticiones 5 --timeout 120 --cgroup /sys/fs/cgroup --salida docs/evidencia/F-19/comparacion
```

Conservar los JSON crudos y registrar nodo, kernel, límite y lecturas. Docker por sí solo no se presenta como medición de worker real. AD-07 permanece provisional hasta obtener la tabla M1 con PSS y `memory.current` válidos.
