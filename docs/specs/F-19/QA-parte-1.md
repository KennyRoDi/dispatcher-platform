# QA F-19, parte 1

**Resultado:** APROBADO para el alcance de la parte 1; suite general bloqueada por un fallo preexistente. No acredita la feature completa. Fecha: 2026-11-10. Producto revisado: `aa73b49e8914439957e396d18915e40140394246`; fase vigente al revisar: `581f50f`.

## Criterios y evidencia

| Criterio del SPEC | Resultado de esta parte |
|---|---|
| Dado el parámetro de estrategia | `LoadingConfig` conserva ambas estrategias y N=1/2/7; rechaza nombres desconocidos, espacios, tipos inválidos y bool |
| Cuando se inicia con N procesos por variante | El doble registra N inicios con `fork` explícito antes de recoger resultados. Carga por hijo en `por_proceso`; precarga única en supervisor para `fork_compartido`. No son procesos del SO |
| Ambas producen el mismo resultado | Cada doble devuelve listas completas de `TranscriptSegment`, incluida confianza y tiempos, para la misma entrada. Igualdad real con Whisper y detección de divergencia entre variantes: pendientes en partes 2/3 |
| Memoria total, supervisor incluido | Fuera de la parte 1. No hay lector ni medición de PSS/RSS/cgroup. Pendiente parte 3 |
| Error, timeout o diferencia impide declarar equivalencia | Propagación de errores de precarga, carga en hijo, inferencia e inicio parcial comprobada. Timeout, SIGTERM, comparación real y ausencia real de zombies: pendientes parte 2 |
| Recolección ante fallos | Se intenta terminate/join de los handles iniciados. Seis casos QA adicionales comprueban que un error de limpieza no oculta el primario ni impide intentar la recolección de los demás; un error de join tras éxito se propaga |
| Capas y tamaño | Dominio puro e infraestructura consumiendo Transcriber existente; contratos compartidos intactos. 83 líneas de producto frente al máximo de 150 de esta parte |

No se encontró un fallo nuevo del producto. No se corrigió código de implementación ni se modificaron las pruebas de la fase tests. Las seis pruebas QA nuevas cubren fallos de limpieza no ejercitados previamente.

## Comandos ejecutados

Desde la raíz del worktree F-19, Windows, Python 3.14 y pytest 9.1.1. En PowerShell se usó `$env:PYTHONUTF8='1'` y el intérprete `C:/Users/Usuario/AppData/Local/Python/pythoncore-3.14-64/python.exe` en lugar del alias `python`:

```sh
python -m pytest -q tests/unit/test_model_loading.py tests/unit/test_model_loader.py tests/unit/test_model_loader_qa.py tests/unit/test_arquitectura.py
python docs/specs/F-19/mutaciones_parte1.py
python -m pytest -q -m "not integration and not acceptance" --tb=line
python -m scripts.conformidad repo
git diff --check
```

Resultados observados:

- Focal y arquitectura: `56 passed in 0.26s` (52 F-19, 4 arquitectura).
- Mutaciones: 6 de 6 detectadas. El script ejecuta primero cada prueba sobre el módulo original; después compila una copia temporal modificada, sin escribir sobre `src/`. Admite solamente fallos de aserción o de expectativa de pytest como detección; otros errores abortan.
- Suite general: error de colección en `test_dataset_sintetico_qa2.py:46`, `os.geteuid` ausente en Windows; `4 skipped, 8 deselected, 1 warning, 1 error in 5.26s`. No se declara verde. La excepción de implementación no constituye autorización para exceptuar esta fase.
- Conformidad: `0 problema(s)`; diff sin errores de whitespace.

Salida cruda del experimento de mutaciones:

```text
DETECTADA: aceptar bool como N (Failed)
DETECTADA: aceptar estrategia desconocida (Failed)
DETECTADA: usar spawn (AssertionError)
DETECTADA: omitir join (AssertionError)
DETECTADA: cargar por hijo en variante compartida (AssertionError)
DETECTADA: ocultar error de inferencia (Failed)
6 de 6 mutaciones detectadas
```

La primera ejecución del script en el sandbox falló por permisos de su directorio temporal antes de completar mutaciones. La ejecución fuera del sandbox terminó con la salida anterior; no se cuenta el problema de entorno como mutación detectada.

La suite complementaria de la fase anterior, sin el archivo de `geteuid`, registró 1611 aprobadas, 2 fallidas, 4 omitidas, 13 xfailed y 8 deseleccionadas. Los dos fallos (`/etc/passwd` y XPASS estricto del nombre malicioso) fueron reproducidos sobre `887f2c7` antes de implementar F-19. Es evidencia heredada de implementación, no una nueva ejecución completa de QA. No se repitió esa suite larga: no hubo cambios de producto y las nuevas pruebas se ejecutaron directamente.

## Límites

Las operaciones inyectadas verifican decisiones y el protocolo; no prueban fork nativo, CoW, inferencia, hilos nativos, aislamiento, señales ni recursos reales. No hay datos de SO que recalcular. Las mediciones del SPEC corresponden a la parte 3 y la puerta de compatibilidad real a la parte 2. No se ejecutaron sus comandos futuros ni se actualizaron resultados de la ficha M1. Sin esos pasos no se elige una estrategia definitiva ni se acredita M1 completo.
