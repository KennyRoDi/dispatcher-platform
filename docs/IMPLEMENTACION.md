**Resumen:** Plan FDD con 42 funcionalidades por hito y responsable, ciclo TDD para la lógica y fichas de evidencia con comandos reproducibles para las mediciones de SO.

# Plan de implementación

Requisitos en `REQUERIMIENTOS.md`, decisiones en `ARQUITECTURA.md`, historias en `docs/backlog/`. Cada `F-XX` corresponde a la historia `US-XX`.

## 1. Calendario

### 1.1 Hitos del documento [Parte I §2]

| Hito | Contenido exigido para la Alternativa B | Fecha nominal | Fecha real |
|---|---|---|---|
| H1 | Reutilización, arquitectura, dataset sintético, pipeline base con texto, imagen y audio, matriz | Fin de semana 1 | 28/oct/26 (SUP-02) |
| H2 | M1, M2 y M3 con mediciones preliminares; estados, reintentos y cancelación | Fin de semana 2 | 04/nov/26 (SUP-02) |
| H3 | M4, M5, pruebas de carga, informe, demo y defensa | Entrega final | 10/nov/26 (SUP-03) |

### 1.2 Orden de trabajo

La entrega real es el 10/nov/26 (SUP-03). Se conserva el orden de dependencias de los hitos:

| Bloque | Hito | Salida verificable |
|---|---|---|
| B1 | H1 | Pipeline de los tres tipos sobre 3 nodos; dataset; matriz; reutilización |
| B2 | H2 | M1, M2, M3 con primera medición; estados, reintentos, cancelación |
| B3 | H3 | M4, M5, escenarios B.6 |
| B4 | H3 | Fichas, informe, README, ensayo de la demo y de la defensa |

**Regla de integridad del historial.** Los commits llevan su fecha real. No se usa `GIT_COMMITTER_DATE`, `--date` ni rebase para simular avance [Parte I §3, §9]. Si existe trabajo real en otras copias, debe integrarse conservando sus fechas.

### 1.3 Recorte si falta tiempo

Todo es obligatorio [B.10], así que recortar afecta la nota. Este orden minimiza el daño: un módulo sin ficha medida queda con máximo 2 [Parte I §5], y cada módulo vale 8 % [B.9].

| Orden | Se reduce | Consecuencia | Se conserva |
|---|---|---|---|
| 1 | Dashboard: solo agregar panel de recursos a las vistas existentes | Menor profundidad en un sub-punto del 15 % | Tiempo real |
| 2 | Alertas: solo registro en Stream y vista en el dashboard | Sin efecto si son asíncronas | RF-15, RF-16 |
| 3 | M5: una sola carga, Whisper, sin YOLO | Permitido: «al menos una carga» [B.5 M5] | Tabla y routing |
| 4 | Texto: palabras clave y un solo modelo preentrenado | Menor calidad del análisis, que no es el foco [B.1] | Las cuatro salidas |

**No se recorta:** las cinco fichas con datos, los tres nodos reales, la bitácora con errores reales y los cinco escenarios. Si un dato no se llega a medir, se declara así. **Nunca se inventa.**

## 2. Funcionalidades

**Responsables, aceptados por el equipo.** Matriz en [responsabilidades.md](responsabilidades.md).

| Integrante | Módulos como responsable principal | Áreas |
|---|---|---|
| Nahúm Murillo (N) | M2 | Coordinador, cola, estados, reutilización |
| José Andrés Loría Herrera (J) | M1, M5 | Workers, cancelación, modelos |
| Kenni Rodriguez (K) | M4 | Dataset, reporte, alertas, seguridad, informe |
| Melany Vindas (V) | M3 | E/S, almacenamiento, dashboard |

Tipo: **Reu**tilizar, **Mod**ificar, **Nue**vo. Este campo alimenta `docs/reutilizacion.md`.

| ID | Área | Funcionalidad | Requisitos | Resp. | Hito | Bloque | Tipo |
|---|---|---|---|---|---|---|---|
| F-01 | Recepción | Crear caso multifuente y registrar carga | RF-01, RF-03 | N | H1 | B1 | Mod |
| F-02 | Recepción | Validar formatos y normalizar exportaciones | RF-02 | N | H1 | B1 | Nue |
| F-03 | Dataset | Generar dataset sintético | RF-18 a RF-22, RNF-04, RNF-05 | K | H1 | B1 | Mod |
| F-04 | Dataset | Verdad de referencia y `docs/dataset.md` | RF-23, RNF-06 | K | H1 | B1 | Nue |
| F-05 | Cola | Descomponer y enrutar por tipo de contenido | RF-04, RF-05 | N | H1 | B1 | Mod |
| F-06 | Cola | Cola confiable con `BLMOVE` | RNF-03, RF-44 | N | H1 | B1 | Mod |
| F-07 | Workers | Worker de texto | RF-06, RNF-25 | J | H1 | B1 | Nue |
| F-08 | Workers | Worker de imagen | RF-07, RNF-25 | J | H1 | B1 | Nue |
| F-09 | Workers | Worker de audio | RF-08, RNF-25 | J | H1 | B1 | Nue |
| F-10 | Estados | Máquina de estados y barrier/join | RF-09, RF-10 | N | H2 | B2 | Mod |
| F-11 | Estados | Reintentos con backoff | RF-11 | N | H2 | B2 | Mod |
| F-12 | Estados | Cancelación real y Clean Shutdown | RF-12 | J | H2 | B2 | Nue |
| F-13 | Reportes | Reporte consolidado con evidencias | RF-13, RF-14 | K | H2 | B2 | Mod |
| F-14 | Alertas | Alertas asíncronas | RF-15, RF-16 | K | H3 | B3 | Nue |
| F-15 | Dashboard | Monitoreo y recursos por nodo | RF-17 | V | H3 | B3 | Mod |
| F-16 | M1 | Límites cgroups v2 por worker | RF-24 | J | H2 | B2 | Nue |
| F-17 | M1 | Control de admisión | RF-25 | J | H2 | B2 | Nue |
| F-18 | M1 | Detección de OOM y reencolado | RF-26 | J | H2 | B2 | Nue |
| F-19 | M1 | Dos estrategias de carga de modelos | RF-27 | J | H2 | B2 | Nue |
| F-20 | M2 | Scheduler con cuatro prioridades y aging | RF-28, RF-29 | N | H2 | B2 | Nue |
| F-21 | M2 | Política FIFO seleccionable | RF-30 | N | H2 | B2 | Nue |
| F-22 | M3 | Transferencia por chunks con hash | RF-31 | V | H2 | B2 | Nue |
| F-23 | M3 | Almacenamiento por contenido con dedup | RF-32 | V | H2 | B2 | Mod |
| F-24 | M3 | Backpressure | RF-33 | V | H2 | B2 | Nue |
| F-25 | M3 | Recepción no bloqueante | RF-34 | V | H2 | B2 | Nue |
| F-26 | M4 | Autenticación y roles | RF-35 | K | H3 | B3 | Nue |
| F-27 | M4 | TLS entre nodos | RF-36 | K | H3 | B3 | Nue |
| F-28 | M4 | Cifrado en reposo y llaves | RF-37, RNF-08 | K | H3 | B3 | Nue |
| F-29 | M4 | Cadena de custodia y verificador | RF-38, RF-39 | K | H3 | B3 | Nue |
| F-30 | M4 | Workers sin privilegios | RNF-07 | K | H3 | B3 | Mod |
| F-31 | M5 | Benchmark de inferencia | RF-40 | J | H3 | B3 | Mod |
| F-32 | M5 | Routing por tipo de nodo | RF-41 | J | H3 | B3 | Nue |
| F-33 | Carga | Escenario: ráfaga | RF-42 | K | H3 | B3 | Mod |
| F-34 | Carga | Escenario: caída de worker | RF-43 | N | H3 | B3 | Reu |
| F-35 | Carga | Escenario: reinicio del coordinador | RF-44 | N | H3 | B3 | Reu |
| F-36 | Carga | Escenario: cancelación en curso | RF-45 | J | H3 | B3 | Nue |
| F-37 | Carga | Escenario: saturación de memoria | RF-46 | J | H3 | B3 | Nue |
| F-38 | Entrega | Despliegue en 3 nodos | RNF-01, RNF-22 | K | H1 | B1 | Mod |
| F-39 | Entrega | Reutilización y correcciones | RNF-02, RNF-03, RNF-24 | N | H1 | B1 | Nue |
| F-40 | Entrega | Matriz, historial y bitácora | RNF-17 a RNF-20 | K | H1 | B1 | Nue |
| F-41 | Entrega | Cinco fichas de evidencia | RNF-09 a RNF-14 | Cada responsable | H3 | B4 | Nue |
| F-42 | Entrega | Informe, README, demo y defensa | RNF-15, RNF-16, RNF-21 a RNF-23 | Todos, coordina K | H3 | B4 | Nue |
| F-43 | Integración | Workers tipados de texto, imagen y audio conectados al pipeline | RF-04 a RF-08, RF-09 a RF-12 | K | H2 | B2 | Nue |

## 3. Cobertura de la rúbrica [B.9]

| Rubro | Peso | Funcionalidades |
|---|---|---|
| Pipeline y análisis multimedia | 15 % | F-01 a F-15, F-38 |
| M1 a M5 | 40 % | F-16 a F-32, F-41 |
| Pruebas de carga y fallos | 10 % | F-33 a F-37, F-42 |
| Documentación y repositorio | 10 % | F-39, F-40, F-42 |
| Defensa oral | 15 % | F-42 |
| Bitácora de IA | 10 % | F-40 |

## 4. Ciclo TDD por funcionalidad

**Clean Tests (F.I.R.S.T.):** las pruebas unitarias no usan red, `sleep` ni reloj real. Se inyecta `Clock` y se usa `fakeredis`, ya presente en el I Proyecto. Cada una prepara sus datos. Los marcadores `integration` y `acceptance` separan lo que necesita servicios. `pytest -q -m "not integration and not acceptance"` debe ejecutarse en segundos.

Las F-33 a F-37 y F-38 a F-42 no siguen TDD: son escenarios y entregables, y su verificación está en `docs/backlog/`.

| ID | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| F-01 | `test_crear_caso_con_varias_fuentes_las_registra` | Entidad `Case` y caso de uso `create_case` | Separar el repositorio Redis |
| F-02 | `test_parser_whatsapp_normaliza_timestamp_y_remitente`, `test_formato_no_admitido_se_rechaza` | Parser y validador por extensión y contenido | Interfaz común de parsers |
| F-03 | `test_generador_cumple_minimos_de_b3` | Generador determinista con semilla | Parámetros por configuración |
| F-04 | `test_comparador_reporta_aciertos_y_errores`, `test_fuente_sin_licencia_falla_validacion` | Comparador y validador del manifiesto | Reutilizar el modelo de manifiesto |
| F-05 | `test_video_genera_subtareas_de_audio_e_imagen`, `test_tipo_enruta_a_su_cola` | Función de descomposición y mapa de colas | Pasar el mapa a configuración |
| F-06 | `test_muerte_tras_blmove_deja_subtarea_en_inflight` | `BLMOVE` a `inflight:{worker}` | Retirar `WATCH/MULTI` |
| F-07 | `test_texto_con_amenaza_produce_categoria_y_severidad` | Adaptador con analizador falso y puerto `Analyzer` | Reglas de severidad en configuración |
| F-08 | `test_imagen_produce_categoria_y_confianza` | Adaptador con detector falso | Formato común de hallazgos |
| F-09 | `test_transcripcion_pasa_por_analisis_de_texto` | Composición transcriptor + analizador de texto | Compartir segmentos con timestamp |
| F-10 | `test_transicion_invalida_se_rechaza`, `test_barrier_no_cuenta_dos_veces`, `test_estado_final_por_combinacion` | `CaseState` en dominio y uso de `SADD` | Prueba de frontera de `import` del dominio |
| F-11 | `test_backoff_crece_y_respeta_maximo`, `test_agota_intentos_y_falla` | `next_delay(attempt, base, jitter)` con aleatoriedad inyectada | Unificar con `recovery.py` |
| F-12 | `test_cancelar_envia_sigterm_y_luego_sigkill`, `test_temporal_se_borra_tras_sigkill`, `test_no_quedan_zombies` | Supervisor con subproceso real de prueba (`sleep`) y grupo propio | Extraer `ProcessSupervisor` |
| F-13 | `test_reporte_tiene_cuatro_secciones`, `test_evidencia_resuelve_a_fuente`, `test_linea_temporal_ordenada` | `build_report` | Separar serialización |
| F-14 | `test_incidencia_alta_publica_alerta`, `test_fallo_de_alerta_no_afecta_pipeline` | Puerto `AlertPublisher` y Stream | Reutilizar reglas de severidad |
| F-15 | `test_heartbeat_incluye_memoria_de_cgroup` | Lector de cgroup con ruta inyectada | Separar formato de vistas |
| F-16 | `test_preflight_rechaza_suma_de_limites_mayor_a_ram` | Script `check_node_budget` | Compartir el lector de cgroup |
| F-17 a F-32 | Ver §5 | Ver §5 | Ver §5 |

## 5. M1 a M5: lógica con TDD frente a medición con ficha

TDD prueba que la lógica decide bien. **No demuestra el comportamiento del sistema operativo.** Eso lo demuestran las mediciones, que no se automatizan como prueba roja o verde: se ejecutan, se registran y se interpretan en la ficha [Anexo 2]. Los scripts `scripts/measure/*` están por crear.

### M1 · Memoria (`docs/modulo-M1-memoria.md`, responsable J)

| Lógica con TDD | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| Decisión de admisión (F-17) | `test_rechaza_si_no_cabe_huella_con_margen` | Función pura `admits(current, max, footprint, margin)` | Tabla de huellas en configuración |
| Lectura de cgroup (F-16, F-18) | `test_parsea_memory_events_oom_kill` con archivo temporal | `read_memory_events(path)` | Usar en heartbeat |
| Política OOM (F-18) | `test_oom_aumenta_reserva_y_no_gasta_intentos`, `test_oom_agotado_falla_con_causa_oom` | `OomPolicy` | Unificar con reintentos |
| Clasificar salida (F-18) | `test_codigo_menos_9_con_oom_kill_es_oom` | `classify_exit(code, oom_delta)` | — |
| Selección de estrategia (F-19) | `test_configuracion_elige_estrategia` | `ModelLoader` con dos variantes | — |

| Medición de SO | Comando reproducible | Producto |
|---|---|---|
| Límite aplicado | `docker exec <w> cat /sys/fs/cgroup/memory.max` | Valor por worker |
| Huella por modelo | `grep -E '^(Rss\|Pss):' /proc/<pid>/smaps_rollup` tras cargar y tras inferir, 5 repeticiones | Tabla RSS y PSS |
| Memoria en el tiempo | Bucle a 1 Hz de `docker exec <w> cat /sys/fs/cgroup/memory.current`, escrito a CSV, durante una ráfaga | Gráfico por worker |
| OOM provocado | Reducir `mem_limit` y lanzar audio largo; `docker exec <w> cat /sys/fs/cgroup/memory.events`; `docker inspect -f '{{.State.OOMKilled}}' <w>` | `oom_kill` y recuperación |
| Estrategias de carga | N procesos con cada estrategia; suma de PSS de `smaps_rollup` y `memory.current` | Comparación de memoria total |

### M2 · Planificación (`docs/modulo-M2-planificacion.md`, responsable N)

| Lógica con TDD | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| Orden con aging (F-20) | `test_alta_gana_a_baja_si_entran_juntas`, `test_baja_antigua_gana_a_alta_reciente` | `AgingPolicy.score(enqueued_at, priority)` | Bonos en configuración |
| Sin inanición (F-20) | `test_baja_se_despacha_bajo_flujo_alto_continuo`, con reloj simulado | Simulador en memoria con `Clock` | Reutilizar en el experimento |
| Prioridad inválida (F-20) | `test_prioridad_desconocida_se_rechaza` | Enum `Priority` | — |
| Cambio de política (F-21) | `test_fifo_ignora_prioridad`, `test_politica_se_elige_por_configuracion` | `FifoPolicy` con interfaz `SchedulingPolicy` | — |

| Medición de SO | Comando reproducible | Producto |
|---|---|---|
| Comparación de políticas | `SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate R --low N --seed 42 --out m2_fifo.csv`, luego `SCHED_POLICY=aging`, 3 repeticiones, 3 nodos | Espera, turnaround y throughput por nivel |
| Ausencia de inanición | Con los mismos CSV: `python scripts/measure/m2_plot.py m2_*.csv` | Espera máxima de la prioridad baja por política |

### M3 · E/S y almacenamiento (`docs/modulo-M3-es-almacenamiento.md`, responsable V)

| Lógica con TDD | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| Reensamblado (F-22) | `test_reensamblado_coincide_con_sha256`, `test_chunk_alterado_se_rechaza`, `test_chunk_fuera_de_orden_se_ordena` | `ChunkAssembler` | Puerto de almacenamiento temporal |
| Dedup (F-23) | `test_mismo_contenido_guarda_un_objeto`, `test_clave_es_sha256_del_contenido` | `ContentStore` sobre puerto | Referencias por fuente |
| Cola acotada (F-24) | `test_cola_llena_rechaza_productor`, `test_scheduler_no_mueve_si_cola_llena`, `test_limite_desactivable` | Lua con `LLEN`, probado con `fakeredis[lua]` | Límites en configuración |
| No bloqueo (F-25) | `test_subida_lenta_no_bloquea_otra_peticion` con `httpx.AsyncClient` | Handler `async` con escritura en hilo | — |

| Medición de SO | Comando reproducible | Producto |
|---|---|---|
| Throughput | `python scripts/measure/m3_chunks.py --file case_h1.mp4 --chunk 256K,1M,4M,16M --reps 5 --remote nodo-a` | MB/s por chunk entre nodos |
| Deduplicación | `python scripts/measure/m3_dedup.py` sobre el dataset completo | `1 − bytes_guardados / bytes_lógicos` |
| Backpressure | `BACKPRESSURE=on\|off python scripts/run_load.py ...` con muestreo de `LLEN` a 1 Hz | Gráfico de profundidad y respuesta con y sin límite |

La tasa de deduplicación depende de los duplicados que tenga el dataset. Su origen se declara en `docs/dataset.md`: los adjuntos reenviados entre casos son parte del diseño, no un resultado espontáneo.

### M4 · Seguridad (`docs/modulo-M4-seguridad.md`, responsable K)

| Lógica con TDD | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| Permisos (F-26) | Prueba paramétrica `test_matriz_rol_accion`, `test_sin_token_es_401`, `test_token_expirado_es_401` | `rbac.can(role, action)` y dependencia FastAPI | Matriz en un único sitio |
| Cifrado (F-28) | `test_ida_y_vuelta_aes_gcm`, `test_chunk_alterado_falla_autenticacion`, `test_nonce_no_se_repite`, `test_falla_si_falta_kek` | `EnvelopeCipher` | Puerto de llaves |
| Cadena (F-29) | `test_cada_entrada_enlaza_a_la_anterior`, `test_alterar_entrada_detecta_posicion`, `test_truncar_log_se_detecta`, `test_alterar_evidencia_se_detecta` | `CustodyChain` y `verify` | CLI `verify_custody` |

F-27 (TLS) y F-30 (sin privilegios) son configuración de despliegue, sin lógica propia que justifique TDD. Se verifican con las mediciones siguientes y con la prueba de integración de `docs/backlog/`.

| Medición de SO | Comando reproducible | Producto |
|---|---|---|
| Manipulación | Alterar un byte con `printf 'X' \| dd of=chain.jsonl bs=1 seek=<n> conv=notrunc`, luego `python -m src.adapters.cli.verify_custody` | Salida con posición detectada |
| Denegación | `curl --cacert ca.pem -i -H "Authorization: Bearer $TOKEN_ANALISTA" -X DELETE https://nodo-a:8443/users/<id>` | Códigos 401 y 403 por rol |
| TLS (F-27) | `sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'`; `tshark -r m4.pcap -Y tls.handshake.type==1`; `strings m4.pcap \| grep -c <marcador_sintetico>` | Handshake TLS y 0 coincidencias del marcador |
| Sin root (F-30) | `docker exec <w> id -u`; `docker inspect -f '{{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}}' <w>` | UID distinto de 0, solo lectura y capacidades |
| Llaves (F-28) | `git log -p --all \| grep -nE 'BEGIN .*PRIVATE KEY\|MINIO_SECRET_KEY=.+'`, y `gitleaks detect` si está disponible | Sin coincidencias |

### M5 · Cómputo heterogéneo (`docs/modulo-M5-computo.md`, responsable J)

| Lógica con TDD | Prueba roja | Implementación mínima | Refactor |
|---|---|---|---|
| Decisión de routing (F-32) | `test_tabla_elige_clase_de_nodo`, `test_sin_nodo_preferido_usa_alternativa`, `test_tabla_invalida_falla_al_arrancar` | `RoutingTable.route(task, live_classes)` | Generar la tabla desde CSV |
| Agregación (F-31) | `test_resumen_calcula_latencia_y_throughput` | Función pura sobre resultados | — |

| Medición de SO | Comando reproducible | Producto |
|---|---|---|
| Inferencia (F-31) | `python scripts/measure/m5_bench.py --model whisper-base --compute cpu-float32,cpu-int8,gpu-float16 --threads 1,2,4 --reps 5 --audio benchmark_set/` | Latencia, throughput y memoria por configuración |
| GPU (F-31) | `nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv -l 1` durante la corrida | Memoria y uso de GPU |
| Sin GPU local | Mismo script en Colab o Kaggle; si nadie tiene GPU, solo hilos y `int8` [B.5 M5] | Se declara la diferencia de entorno |

## 6. Clean Commits y PR

Las reglas de commits, títulos de PR y pilas están en [CONTRIBUTING.md](../CONTRIBUTING.md). El estado está en `docs/STATUS.md` de la rama `estado` y las dependencias de cada funcionalidad, en [backlog/](backlog/README.md). Los resultados de medición se versionan en `docs/evidencia/` con el script y el commit que los produjo.

## 7. Riesgo de orden

**F-27 (TLS) y F-26 (auth) tocan todas las conexiones.** Si van tarde, pueden romper mediciones ya hechas. Las mediciones de M1 a M3 se repiten si TLS altera sus resultados, al menos el throughput de M3, y esa diferencia se reporta.
