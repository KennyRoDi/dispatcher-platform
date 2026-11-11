# QA F-19, parte 3: medición M1

**Estado:** medición completada en Docker Desktop Linux/WSL2, configuración controlada, no nodo worker de producción.

## Verificación

- `tests/unit/test_model_memory.py`: 8 passed; `tests/unit/test_comparar_carga.py`: 9 passed; `tests/unit/test_whisper_transcriber.py`: 42 passed.
- `tests/integration/test_comparar_carga_posix.py`: 3 skipped en Windows; requieren POSIX. Se renombró para evitar colisión de colección pytest con `tests/unit/test_comparar_carga.py`, ambos compartían basename.
- Preflight y 20 ejecuciones (dos estrategias × N=1/2 × 5 repeticiones) completados. JSON crudos en `docs/evidencia/F-19/{compatibilidad,comparacion}/`.
- Entorno: Docker Engine 29.7.2, kernel `6.18.33.2-microsoft-standard-WSL2`, Python 3.13.18, faster-whisper 1.2.1, CTranslate2 4.9.0, PyAV 18.1.0, cgroup v2 `memory.max=4294967296`, `memory.swap.max=0`; proceso no-root.

## Resultado (etapa inferred, promedio de 5)

| Estrategia | N | PSS medio (bytes) | `memory.current` medio (bytes) | delta medio sobre baseline (bytes) |
|---|---:|---:|---:|---:|
| `por_proceso` | 1 | 264806195 | 816900506 | 173993984 |
| `workers_compartidos` | 1 | 261983232 | 815903539 | 172160614 |
| `por_proceso` | 2 | 420311450 | 975574630 | 331178803 |
| `workers_compartidos` | 2 | 281929728 | 836598989 | 191442944 |

Con esta carga Whisper CPU y este entorno, `workers_compartidos` reduce las medias observadas frente a `por_proceso` en N=2. No se generaliza a otros modelos, nodos ni cargas. El contenedor de medición no es un worker real; la evidencia valida instrumentación y comportamiento en WSL2, no el despliegue de tres nodos.

## Incidencias

El primer preflight corrigió un anidamiento de resultados por proceso y detectó un `TypeError` en la serialización; arreglo en `8eecde5`. Una ejecución posterior falló al instalar dependencias porque `HOME` apuntaba a `/.local` no escribible; la repetición instaló en `/tmp` y completó. No se usaron datos estimados. El primer JSON fallido no produjo medición y no se incluye como evidencia válida.

## Comandos

```bash
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 2 --estrategias por_proceso workers_compartidos --repeticiones 1 --timeout 120 --solo-validar --salida docs/evidencia/F-19/compatibilidad
python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 1 2 --estrategias por_proceso workers_compartidos --repeticiones 5 --timeout 120 --cgroup /sys/fs/cgroup --salida docs/evidencia/F-19/comparacion
```
