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

## Acceso a posibles nodos (2026-11-12)

El orquestador comprobó el acceso con permisos elevados: `tailscale status` mostró `hp-nahum`, `krddebian-1` y `magdalena` conectados, y el ping de Tailscale a cada uno recibió pong mediante DERP. Esto actualiza el diagnóstico local inicial de Tailscale: no hay un bloqueo general de conectividad de la malla en esta comprobación. Los nombres son nodos potenciales; no se confirmó su correspondencia con los nodos A/B/C/D ni un despliegue del proyecto.

Los intentos SSH no abrieron una sesión: `hp-nahum` y `magdalena` agotaron el tiempo de conexión al puerto 22; `krddebian-1` devolvió `banner exchange: Connection refused`. Comandos de conexión informados por el orquestador, sin IP ni credenciales:

```powershell
tailscale status
tailscale ping hp-nahum
tailscale ping krddebian-1
tailscale ping magdalena
ssh -o BatchMode=yes -o ConnectTimeout=4 hp-nahum
ssh -o BatchMode=yes -o ConnectTimeout=4 krddebian-1
ssh -o BatchMode=yes -o ConnectTimeout=4 magdalena
```

No hubo acceso remoto ni mediciones. Un pong DERP acredita respuesta de Tailscale, no disponibilidad de SSH, autenticación, servicios de la aplicación ni nodos worker distintos. No se registran IP, usuarios de acceso, llaves o tokens. El bloqueo actual es la ausencia de una sesión ejecutable en otra máquina y de las salidas experimentales pendientes, no la mera instalación del cliente de red.

## Ejecución por responsables cuando haya acceso

Estos son protocolos pendientes, no comandos ejecutados durante QA. Ejecutar desde la raíz del checkout en la máquina confirmada, con sus prerrequisitos. Resolver cualquier marcador antes de ejecutar y guardar el comando resuelto. Cada registro debe incluir responsable, UTC, commit, identidad no privada del entorno, versiones, entradas públicas/sintéticas y su procedencia, salida íntegra, código de retorno e interpretación. Conservar originales y añadir resultados en `docs/evidencia/F-41/`; no publicar secretos ni la captura de tráfico cruda.

| Responsable | Comando o protocolo existente | Salida necesaria |
|---|---|---|
| José Andrés, M1 | [QA F-19 parte 3](../F-19/QA-parte-3.md): `python scripts/measure/comparar_carga.py --config config/audio.toml --hilos 1 --entrada tests/datos/audio/amenaza_01.ogg --procesos 1 2 --estrategias por_proceso workers_compartidos --repeticiones 5 --timeout 120 --cgroup /sys/fs/cgroup --salida docs/evidencia/F-41/m1` | Linux/cgroup v2 limitado y ejecución no root; JSON por variante con snapshots RSS/PSS/memory.current y cinco repeticiones. Completar además huellas de todos los modelos, ráfaga por worker y OOM desplegado con los protocolos de [M1](../../modulo-M1-memoria.md); esta comparación no los sustituye. |
| Nahúm, M2 | [M2](../../modulo-M2-planificacion.md): `SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate 100 --low 5 --seed 42 --out m2_fifo_42.csv`, repetir con aging y semillas 43/44 | CSV de simulación con parámetros y entorno. No acredita niveles media/crítica, máximos individuales ni comportamiento desplegado; esos productos siguen requiriendo evidencia adecuada del responsable. |
| Melany, M3 | [M3](../../modulo-M3-es-almacenamiento.md): `python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a` | Ejecutar desde otro nodo hacia el coordinador real; preparar archivo sintético de al menos 200 MiB y resolver `nodo-a` según despliegue. Guardar repeticiones, bytes, tiempo total/complete y unidad. Para reproducción representativa de deduplicación, seguir [F-23](../../evidencia/F-23_deduplicacion_2026-11-11.md), con dataset sintético y almacén aislado inicialmente vacío. |
| Kenni, M4 | [M4](../../modulo-M4-seguridad.md): `python -m scripts.verificar_workers`; custodia según [F-29](../../evidencia/F-29_prueba_A_local_sintetica_2026-11-11.md) | Salidas efectivas por worker confirmado; custodia íntegra exit 0 y alterada exit 1, con llave efímera fuera del repo. Completar matriz de roles y captura TLS entre nodos con el protocolo siguiente; un handshake local no basta. |
| José Andrés, M5 | [F-31](../../evidencia/F-31_m5_bench_2026-11-11.md): `python scripts/measure/m5_bench.py --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio /bench --config /audio_en.toml --salida /bench/m5_bench.json` | Preparar WAV público y configuración del protocolo y resolver rutas locales; JSON, cinco repeticiones tras calentamiento, versión/modelo/entrada y comparación con host original. Justificar routing con datos compatibles. GPU solo si no aplica la alternativa CPU de B.5 M5. |

Para TLS, Kenni debe aplicar el protocolo ya aprobado en M4 desde el nodo coordinador, sustituyendo interfaz y marcador sintético reales:

```bash
sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'
tshark -r m4.pcap -Y tls.handshake.type==1
strings m4.pcap | grep -c <marcador_sintetico>
```

Registrar intento y análisis, handshakes y ausencia del marcador en claro; el archivo `m4.pcap` queda fuera del repositorio como exige la ficha. Ningún resultado previsto se considera obtenido. La reproducción de un comando por ficha no elimina los demás productos RNF pendientes.

## Decisión de entrega documental (2026-11-12)

La persona responsable decidió subir las fichas tal como están y cerrar este trabajo documental aceptando la evidencia pendiente. Se entrega el estado parcial descrito en este informe; la decisión no acredita RNF completos, ejecuciones remotas ni las cinco reproducciones US-41. No se logró cerrar formalmente F-41.

Deuda conservada: M1, huellas de todos los modelos, ráfaga por worker y validación desplegada; M2, niveles y evidencia de inanición; M3, throughput entre nodos con al menos tres tamaños; M4, captura TLS y controles desplegados; M5, routing justificado y condición de alternativa CPU; todos los módulos, reproducción de un comando por ficha en otra máquina. Los datos y resultados anteriores permanecen sin cambios.
