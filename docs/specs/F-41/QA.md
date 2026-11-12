# F-41 · Revisión independiente de evidencia

**Fecha:** 2026-11-12. **Revisión:** `b7e9e3f6`. **Rol:** QA tester/revisor, distinto del autor de las correcciones documentales.

**APROBADA la corrección documental. DEVUELTA la aceptación total de F-41.** No se encontraron defectos nuevos en las correcciones revisadas. Los productos experimentales pendientes y las cinco reproducciones en otra máquina impiden declarar la feature satisfecha.

## Criterios del SPEC

| Criterio | Resultado | Evidencia y límite |
|---|---|---|
| Cinco fichas con los cinco elementos, comandos, interpretación y bibliografía | Estructura comprobada; evidencia parcial | Se revisaron M1–M5 y sus cambios. M2 corrige media frente a máximo, FIFO y ventana de adelantamiento; M5 corrige CLI, MiB y muestreo. No se completan experimentalmente los productos pendientes por corregir su documentación. |
| Lista contra RNF-09 a RNF-14 | Lista completa; aceptación devuelta | [COMPROBACION](COMPROBACION.md) distingue evidencia local, simulación, productos parciales y pendientes sin acreditarlos como clúster. |
| Repetir un comando por ficha en otra máquina | Pendiente | No hay cinco registros reales de reproducción independiente. La comprobación local o el recálculo de datos históricos no cumplen este criterio. |
| Recalcular conclusiones cuantitativas desde datos existentes | Comprobado con límites | [Recálculos](../../evidencia/F-41/recalculos.md) coinciden con datos M1/M2/M3/M5. M4 registra resultados categóricos. M5 conserva agregados: no permite reconstruir el p95 desde observaciones individuales. |

## Verificación ejecutada

- Lectura del SPEC, `git diff origin/main...HEAD` de los nueve documentos de F-41 y el diff de trabajo, sin cambios de código de producto.
- `git diff --check origin/main...HEAD`: sin errores; `git status --short`: vacío al revisar.
- Comprobación con Python 3.14, `pathlib` y expresión de enlaces Markdown: todos los destinos locales de los nueve documentos existen. No se comprobaron enlaces externos ni anclas HTML.
- Recálculo independiente con `json`, `csv` y `statistics`: medias PSS de snapshots `inferred` de F-19; medias por política/nivel del CSV F-21; tasa de deduplicación de F-23; reducciones de latencia con agregados de F-31. Coinciden con los redondeos documentados.
- Revisión de tablas locales RBAC y salidas de custodia: 409 de cancelación corresponde a conflicto tras autorización, no denegación por rol; custodia íntegra exit 0, manipulaciones exit 1 y errores de llave exit 2.
- Lectura de `scripts/measure/m5_bench.py`: RSS se divide por 1024² y se consulta tras cada repetición. La ficha distingue MiB y máximo entre muestras de un pico continuo.

No se ejecutaron mediciones de nodos ni una segunda suite desde este rol. El orquestador informó 28 pruebas de conformidad aprobadas y reprodujo el código exacto de `recalculos.md` con salida idéntica; las cinco fichas devolvieron `[]` en `revisar_ficha` y el diff pasó `git diff --check`.

**Unitarias ejecutadas por el orquestador:** 3030 passed, 82 skipped, 5 deselected, 37 xfailed y 5 warnings, en 131.56 s, exit 0. Comando PowerShell:

```powershell
Remove-Item Env:REQUESTS_CA_BUNDLE -ErrorAction SilentlyContinue
Remove-Item Env:CURL_CA_BUNDLE -ErrorAction SilentlyContinue
& C:\Users\Usuario\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q tests/unit -m 'not integration and not acceptance' --maxfail=1 -o faulthandler_timeout=30
```

La eliminación de variables se limitó al proceso de prueba; no cambió el entorno del sistema. Un intento previo falló en `test_tls_cableado.py:294` porque `REQUESTS_CA_BUNDLE` heredada apuntaba a una CA de PostgreSQL en vez del valor esperado. También hubo impedimentos iniciales de permisos temporales y falta de `lupa`, dependencia requerida que se instaló. La suite global no tiene resultado verde: se interrumpió tras observar esperas reales del reporter. El éxito de las unitarias no acredita toda la suite ni las pruebas distribuidas pendientes.

## Bloqueos de aceptación

- M1: huellas de todos los modelos usados, memoria por worker durante ráfaga y validación del worker desplegado.
- M2: evidencia adecuada por los niveles exigidos y ausencia de inanición; el CSV actual solo contiene baja/alta y medias por semilla.
- M3: throughput entre nodos para al menos tres tamaños de chunk.
- M4: captura TLS entre nodos y controles efectivos de los workers desplegados.
- M5: routing respaldado por datos comparables; confirmar la condición de alternativa CPU de B.5 M5. GPU no es obligatoria si esa alternativa aplica.
- US-41: cinco reproducciones en otra máquina, con comandos resueltos, entorno y salida real.

No se declara ninguna ejecución remota ni cumplimiento a partir del estado cerrado de las features de origen. La falta de servicios locales Docker/Tailscale no describe el estado de los nodos remotos. No hay hallazgos nuevos que requieran corregir las fichas revisadas; los bloqueos impiden aprobar la aceptación total.

## Base de comparación

`origin/main` avanzó con F-34 durante esta revisión. La comparación de PR usa tres puntos (`origin/main...HEAD`); comparar directamente las puntas puede mostrar como eliminaciones aparentes archivos F-34 posteriores a la base de F-41. El diff revisado de F-41 contiene únicamente los nueve documentos previstos.
