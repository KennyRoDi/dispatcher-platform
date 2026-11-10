# Contratos entre módulos

Cada módulo se desarrolla de principio a fin sin esperar a otro. Los módulos solo se tocan a través de estos contratos.

## Cómo se trabaja

1. Programa contra el puerto de `src/application/ports.py`, nunca contra el adaptador de otro módulo.
2. En tus pruebas, usa los dobles de `tests/dobles.py`.
3. Si entregas un adaptador, pásalo por `tests/contratos.py`. Esa misma prueba valida al doble, de modo que lo probado con él vale con el real.
4. Registra tus piezas donde indica la tabla de archivos.

## Quién implementa y quién usa

| Contrato | Lo implementa | Lo usa |
|---|---|---|
| `Subtask`, `ContentKind`, `QueueFull` | Compartido | M2 y workers |
| `Priority` | Compartido | Coordinador, M2 |
| `Finding`, `EvidenceRef`, `Severity` | Compartido | Workers (produce), reporte y alertas (consume) |
| `ChatMessage` | Compartido | F-02 (produce), F-07 (consume) |
| `ConversationParser` | Nahúm, F-02 | José Andrés, F-07 |
| `Analyzer` | José Andrés, F-07 a F-09; conformidad: `comprobar_analyzer` en `tests/contratos.py` | Workers |
| `WorkQueue` | Nahúm, F-06; Melany agrega el límite, F-24 | M2, M1 (reencolar), workers |
| `ObjectStore` | Melany, F-23; Kenni lo envuelve con cifrado, F-28 | Coordinador, workers |
| `FindingStore` | Kenni, F-13 | Workers (escribe), reporte (lee) |
| `CustodyLog` | Kenni, F-29 | Recepción (M3), workers |
| `RoutingPolicy` | José Andrés, F-32 | Scheduler (M2) |
| `ResourceReader`, `ResourceUsage` | José Andrés, F-16 | Admisión (M1), dashboard (F-15) |
| `AlertPublisher` | Kenni, F-14 | Coordinador, workers |
| `Clock` | Infraestructura de quien lo necesite | Todos |

## Quién toca qué

Cada módulo crea archivos propios, para que dos PR no choquen.

| Dueño | Archivos |
|---|---|
| Nahúm: coordinador, M2 | `src/coordinator/rutas_casos.py`, `rutas_subtareas.py`, `src/domain/scheduling.py`, `case_state.py`, `retry.py` |
| José Andrés: workers, M1, M5 | `src/workers/`, `src/domain/admission.py`, `oom_policy.py`, `routing.py`, `text_analysis.py`, `image_detection.py`, `transcription.py`, `severity.py` (F-14 de Kenni lo reutiliza: avisar al cambiarlo), `src/application/analyze_text.py`, `analyze_image.py`, `analyze_audio.py`, `src/adapters/*_analyzer.py`, `hashing.py`, `config/texto.toml`, `imagen.toml` |
| Melany: M3, dashboard | `src/coordinator/rutas_archivos.py` (nuevo), `src/domain/chunks.py`, `src/adapters/minio_object_store.py`, `dashboard/` |
| Kenni: M4, reporte, alertas, despliegue | `src/domain/rbac.py`, `custody_chain.py`, `src/coordinator/seguridad.py` (nuevo), `src/application/build_report.py`, `deploy/` |

**Archivos compartidos.** Cambios de una línea, sin reordenar: `src/coordinator/main.py` (un `include_router` por módulo), `requirements.txt` (una dependencia por línea), `src/application/ports.py`.

**Autenticación sin tocar rutas ajenas.** F-26 la aplica en `main.py` con `include_router(..., dependencies=[...])`.

## Cambiar un contrato

Es lo único que obliga a coordinarse. Abre una PR solo con ese cambio, actualiza `tests/contratos.py` y `tests/dobles.py`, y avisa a quienes aparecen en la tabla. Mientras se pueda, agrega en vez de modificar.

## Qué no cubre

Las features F-33 a F-37, F-41 y F-42 son de **integración**: comprueban el sistema completo en los tres nodos y solo pueden cerrarse al final. Los contratos reducen el ajuste de integración, pero no lo eliminan: no detectan problemas de rendimiento, memoria real ni red. Por eso conviene integrar temprano lo que ya esté en `main`.
