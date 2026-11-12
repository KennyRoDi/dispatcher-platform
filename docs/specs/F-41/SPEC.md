# SPEC F-41: Fichas de evidencia

**Fase:** verificacion
**Base:** main
**Verificación IA:** verificacion ed090432
**Historia:** US-41 · **Requisitos:** RNF-09 a RNF-14 · **Responsable:** Cada responsable

## Objetivo

Entregar al evaluador las cinco fichas M1–M5 con trazabilidad entre componente, concepto de SO, método reproducible, datos e interpretación, conforme a Parte I §5, B.5, B.8 y Anexo 2 de `docs/ENUNCIADO.md`. Una estructura completa no acredita por sí sola un módulo medido; no se declarará cumplido un requisito cuya evidencia falte.

## Alcance

**Incluye:** revisar y consolidar las cinco fichas existentes, corregir texto obsoleto o conclusiones que excedan los datos, asociar cada producto RNF-09 a RNF-13 con su evidencia cruda y fuente bibliográfica, y registrar una lista de comprobación y la reproducción de un comando por ficha en otra máquina. Conservar fecha, entorno, versiones, unidades, condiciones y repeticiones de cada ejecución real.

**No incluye:** desarrollar funcionalidades de F-16 a F-32, cambiar contratos, entrenar modelos, reemplazar mediciones faltantes por simulaciones, ni ampliar los escenarios B.6. Los experimentos se reutilizan de las features de origen; si falta una capacidad o acceso a nodos se informa al responsable y se detiene su acreditación. No se exige GPU si el equipo cumple la alternativa CPU de B.5 M5.

## Criterios de aceptación

- **Dado** los cinco módulos, **cuando** se revisa cada ficha, **entonces** tiene los cinco elementos, con comandos exactos, resultados, interpretación y referencia bibliográfica (US-41).
- **Dadas** las fichas, **cuando** se aplica la lista contra RNF-09 a RNF-14, **entonces** cada producto exigido tiene una referencia a datos crudos y su condición de cumplimiento comprobable; un pendiente impide declarar satisfecha la lista.
- **Dado** un comando documentado por ficha, **cuando** otra persona lo repite en otra máquina con los prerrequisitos indicados, **entonces** quedan registrados comando resuelto, entorno y salida real, con interpretación de diferencias; no se exige igualdad numérica entre máquinas.
- **Dada** una conclusión cuantitativa, **cuando** se recalcula desde el crudo, **entonces** coinciden fórmula, unidad, población y redondeo y se explicitan las limitaciones del experimento.

## Diseño

Cambio documental, sin dependencias nuevas entre capas. Reutiliza `scripts/measure/*`, `scripts/preflight.py`, `scripts/verificar_workers.py`, `scripts/verify_custody.py` y evidencias de las features de origen, sin modificar sus interfaces. El validador existente `scripts/conformidad.py:revisar_ficha` solo comprueba secciones: no sustituye la revisión de contenido o la reproducción.

Archivos de entrega: `docs/modulo-M1-memoria.md`, `docs/modulo-M2-planificacion.md`, `docs/modulo-M3-es-almacenamiento.md`, `docs/modulo-M4-seguridad.md`, `docs/modulo-M5-computo.md` y `docs/specs/F-41/COMPROBACION.md`; aclaración mínima de AD-04 en `docs/ARQUITECTURA.md` para distinguir ventana de adelantamiento de tiempo de espera, sin cambiar el algoritmo ni introducir una decisión nueva. Salidas nuevas y registros reproducidos, si se obtienen realmente, en `docs/evidencia/F-41/`, sin llaves, tokens ni datos privados. La comprobación tendrá una fila por producto RNF, enlace al crudo, comando, entorno y veredicto con motivo. La bitácora se publica exclusivamente con `flujo.py bitacora` durante documentación.

`docs/CONTRATOS.md` conserva todos los puertos y dueños: J, M1/M5; N, M2; V, M3; K, M4. Revisar transversalmente no transfiere autoría ni permite alterar sus componentes. No hay código del I Proyecto que implementar en esta feature. Se aplican AD-02 (nodos separados), AD-04 (planificación), AD-05 a AD-07 (memoria), AD-10 a AD-13 (E/S), AD-18 y AD-32 (routing) y las decisiones vigentes de seguridad, sin introducir otra decisión arquitectónica. Si surge una, se registra primero con alternativas, criterio y fuente en ARQUITECTURA §8; los supuestos se identifican como SUP, nunca se resuelven en silencio.

### Revisión inicial y trabajo requerido

| Módulo / requisito | Evidencia existente | Brecha que debe resolver o declarar la entrega |
|---|---|---|
| M1 / RNF-09 | F-19 compara estrategias con crudos JSON; F-18 registra OOM local; F-37 registra saturación | Separar experimentos locales de workers desplegados. Revisar texto que todavía describe F-19 como futuro; comprobar huella de cada modelo usado, gráfico por worker, OOM y recuperación. No atribuir la comparación Whisper a texto o imagen ni confundir ráfaga B.6 con todo M1. |
| M2 / RNF-10 | CSV y gráfico F-21, FIFO y aging, semillas 42/43/44, reloj virtual | Añadir referencia con autor y capítulo. Distinguir tiempos simulados de medición del SO; no inferir una cota universal de espera de 400 ms del bono de prioridades. FIFO no permite que llegadas posteriores adelanten un caso ya en cola. El CSV contiene promedios por semilla: no presentar 245.789 ms como máximo individual. Verificar métricas por los niveles exigidos: el CSV actual solo cubre baja/alta; la cobertura restante y la ausencia de inanición requieren evidencia adecuada del responsable. |
| M3 / RNF-11 | Deduplicación F-23; CSV y gráficos F-24/F-25 locales | Throughput para al menos tres tamaños de chunk entre nodos sigue pendiente. Verificar MB/s frente a MiB/s, fórmulas de deduplicación y población de profundidad/latencia. Conservar las limitaciones de S3 simulado y ausencia de workers de ciertos experimentos. |
| M4 / RNF-12 | Pruebas locales F-27/F-28/F-29 y salidas de worker sin privilegios | Captura real de tráfico entre nodos pendiente; revisar accesos denegados por rol, manipulación y permisos efectivos. Separar controles escritos de controles aplicados. No publicar material criptográfico ni alegar tres nodos a partir de una demo local. |
| M5 / RNF-13 | Benchmark CPU con float32/int8, 1/2/4 hilos, cinco repeticiones | B.5 permite esta alternativa solo si ningún integrante tiene GPU: confirmar la condición. Justificar routing con datos comparables; la tabla actual CPU/GPU es provisional y el benchmark de un host no acredita por sí solo clases distintas. Explicar Unidad 1 sin presentar GPU como obligación adicional. |
| Todos / RNF-14 | Existen cinco fichas con secciones | Uniformar cinco elementos, bibliografía y enlaces; repetir un comando por ficha en otra máquina. No hay registro de esa reproducción en esta fase. |

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | No aplica a esta parte documental: no se agrega lógica de producto ni un validador nuevo | No se confunden mediciones con TDD |
| Integración | No aplica como prueba nueva; reutilizar verificadores y experimentos de origen con sus prerrequisitos | F-41 no reemplaza implementación de otros módulos |
| Aceptación | Lista manual RNF-09 a RNF-14; cinco elementos por ficha, enlaces existentes y recalcular al menos una cifra por módulo con datos cuantitativos | Trazabilidad y corrección de resultados, sin inventar lo ausente |
| Reproducibilidad | Ejecutar un comando por ficha en otra máquina y guardar los cinco registros | Criterio explícito de US-41 |
| Conformidad | Ejecutar el comprobador existente de secciones sobre las cinco fichas y revisar el diff | Estructura y alcance documental; no acredita experimentos |

Las fases tests/implementacion de esta parte son documentales: antes de aprobarlas se requiere autorización humana específica de `aprobar --excepcion` si las comprobaciones del script exigen pruebas nuevas en rojo o código. No se fabricarán pruebas que fallen por datos físicos inexistentes.

## Mediciones

No se ejecutan mediciones durante plan. No se introduce un protocolo experimental diferente de los aprobados en las features originales. Antes de una ejecución se copia el comando exacto de la ficha o evidencia original, con parámetros reales y prerrequisitos resueltos; se registra salida íntegra, fecha UTC, máquina, versiones y repeticiones en `docs/evidencia/F-41/`.

| Destino | Protocolo que se reutiliza | Repeticiones / verificación |
|---|---|---|
| M1 | IMPLEMENTACION §5 M1 y crudos de F-19/F-18; lectura de `memory.max`, `memory.current`, `smaps_rollup` y `memory.events` | Cinco para huella/estrategias según protocolo de origen; documentar cada OOM y recuperación. Reproducir al menos un comando en otra máquina. |
| M2 | `SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate 100 --low 5 --seed 42 --out m2_fifo_42.csv` y variante aging | Semillas 42, 43 y 44; marcar simulación. No afirmar cobertura de prioridades que el runner no genera. |
| M3 | Comandos de `m3_chunks.py`, `m3_dedup.py`, `m3_backpressure.py` y `m3_no_bloqueo.py` ya documentados | Al menos tres tamaños de chunk; repeticiones del protocolo de origen, tres donde ya se fijan; preservar crudos por condición. |
| M4 | `python -m scripts.verificar_workers`; prueba A con verificador de custodia y protocolos de rol/TLS de la ficha | Registrar cada caso positivo/negativo y una captura real entre nodos; nunca reemplazarla por handshake local. |
| M5 | `python scripts/measure/m5_bench.py --audio <audio_publico_o_sintetico> --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --salida <resultado.json>` | Cinco tras calentamiento conforme F-31; GPU solo si corresponde; no lanzar con marcadores literales. |

Para los comandos de la tabla que contienen marcadores, el registro final debe enlazar el comando realmente resuelto; la tabla es un plan, no evidencia ejecutada. Se elige un comando representativo por ficha para la repetición en otra máquina. Cualquier requisito que necesite nodos no accesibles queda bloqueado de forma explícita y se solicita acceso/datos al responsable; no se estima el resultado.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `docs(F-41): consolidar las cinco fichas de evidencia` | Cinco fichas, lista de comprobación, referencias y registros reales de reproducción. Sin código de producto. No se cierra como cumplimiento total mientras exista un producto RNF o reproducción pendiente. |

## Riesgos y preguntas abiertas

- Se necesita otra máquina y acceso a los nodos para acreditar reproducción y las evidencias distribuidas pendientes. No se dispone de esa evidencia por el hecho de que las features dependientes estén cerradas.
- Confirmar con el equipo si ningún integrante tiene acceso a GPU para aplicar la alternativa CPU de B.5 M5. No cambia ni invalida los datos CPU ya medidos.
- Confirmar edición del libro del curso (SUP-16) antes de dar por definitivos los capítulos; citar con precisión la edición realmente consultada.
- Los errores conceptuales y textos obsoletos detectados se corrigen en las fichas y se declaran en la bitácora con su validación. No alterar crudos históricos para hacerlos coincidir con una conclusión.
- La lista puede quedar parcialmente bloqueada por evidencia de otros responsables. Se entrega el inventario verificable, pero no se declara F-41 cumplida hasta resolverlo. No se introducen umbrales de rendimiento ni repeticiones adicionales ajenos al enunciado o al protocolo aprobado.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Codex | 2026-11-12 | Revision independiente del arquitecto en una ronda: diff completo contra origin/main solo SPEC; criterios US-41 y RNF-09 a RNF-14 cotejados con enunciado y backlog; sin marcadores; git diff --check limpio; cinco fichas pasan revisar_ficha. Verificados flags CLI m5. Brechas y errores M1/M2/M5 registrados; sin ejecutar mediciones ni acreditar reproduccion en otra maquina. (3fec3cde) |
| plan | José Andrés Loría Herrera | 2026-11-12 |  |
| verificación IA de tests | Codex | 2026-11-12 | Revision independiente de COMPROBACION: cubre productos RNF09-14 y cinco reproducciones; estados parciales no se declaran cumplidos; diff solo documental y diff --check limpio. pytest tests/unit/test_conformidad.py: 28 passed. F41 no lleva TDD segun IMPLEMENTACION116; sin codigo ni pruebas rojas artificiales. (a649c769) |
| tests | José Andrés Loría Herrera | 2026-11-12 | Autonomia autorizada expresamente por joselhcr en el chat: F41 documental exenta de TDD segun IMPLEMENTACION116; lista de aceptacion revisada, no aplica prueba roja de codigo. No se omiten criterios de evidencia ni reproduccion. |
| verificación IA de implementacion | Codex | 2026-11-12 | Correccion documental revisada independientemente: diff completo solo docs, enlaces existentes, cinco revisar_ficha sin errores, diff --check limpio y codigo literal de recalculos reproducido. pytest tests/unit:3030 passed,82 skipped,37 xfailed; variables CA aisladas solo en proceso. Suite global interrumpida por esperas existentes Reporter; no verde global. QA documental aprobado, aceptacion total pendiente de nodos y cinco reproducciones. (89fe63fc) |
| implementacion | José Andrés Loría Herrera | 2026-11-12 | Autonomia autorizada por joselhcr: implementacion solo documental sin codigo, revisada independientemente. Unitarias 3030 passed; suite global sin verde por esperas previas de Reporter documentadas en QA. Se omite requisito de codigo y suite global para avanzar a verificacion, NO se aprueba aceptacion RNF ni reproducciones pendientes. |
| verificación IA de verificacion | Codex | 2026-11-12 | QA independiente reviso los cinco modulos y devolvio aceptacion total por mediciones y cinco reproducciones ausentes; documentacion y estado parcial veraces en QA y COMPROBACION. Usuario acepta expresamente subir y fusionar F41 con esta deuda. CI de PR142 verde salvo estado-feature. Verificacion de alcance y faltantes, no de cumplimiento completo. (ed090432) |
