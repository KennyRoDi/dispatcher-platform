# SPEC F-32: Routing por tipo de nodo

**Fase:** revision
**Base:** main
**Verificación IA:** revision e712255
**Historia:** US-32 · **Requisitos:** RF-41 (B.5 M5, Conexión con Unidad 1) · **Responsable:** J

## Objetivo

Dirigir cada sub-tarea a la clase de nodo que la ejecuta mejor según una tabla de routing, y a una clase alternativa si la preferida no tiene nodos activos. El enunciado (B.5 M5) pide una política de routing por tipo de nodo definida con los resultados medidos en F-31; la tabla cita esa medición. Mientras no haya mediciones en nodos reales, los valores son provisionales y se marcan como tales.

## Alcance

**Incluye:** `RoutingTable` en el dominio, que implementa el puerto `RoutingPolicy`; carga y validación de la tabla desde `config/routing.toml`; asignación de `Subtask.node_class` con el resultado; prueba de integración con dos clases de worker usando dobles; ficha M5 con la justificación y referencia a la medición.

**No incluye:** el benchmark (F-31, ya fusionada); el despliegue de los nodos (F-38, de Kenni); que el coordinador llame a `route` en su cola (código de Nahúm, M2, que consume el puerto); GPU real; generar la tabla desde CSV (refactor opcional, fuera de alcance).

## Criterios de aceptación

- **Dado** la tabla de routing y clases de nodo activas
- **Cuando** llega una sub-tarea, o el nodo preferido no está activo
- **Entonces** se dirige a la clase indicada, o a la alternativa

Pruebas: U clase, alternativa y tabla inválida. I dos clases de worker. Evidencia: ficha M5, justificación con referencia a la medición.

## Diseño

- **Contrato:** implementa `RoutingPolicy.route(subtask, live_classes) -> str` de `docs/CONTRATOS.md` sin cambiarlo; lo consume el Scheduler (M2). Usa `Subtask.kind` (`ContentKind`) y `Subtask.node_class`. `docs/CONTRATOS.md` no cambia.
- **Dominio** (`src/domain/routing.py`, archivo de J, puro): `RoutingTable(reglas: Mapping[ContentKind, tuple[str, ...]])`; cada tipo de contenido tiene una lista ordenada de clases (preferida primero, luego alternativas). `route` devuelve la primera clase de la lista presente en `live_classes`; sin ninguna activa lanza `NoLiveNodeClass(ValueError)` con el tipo y las clases pedidas, para que el coordinador decida (esperar o reencolar) en vez de perder la sub-tarea. No muta la sub-tarea. Valida en el constructor: tabla no vacía, lista no vacía por tipo, sin clases vacías ni duplicadas, sin tipos desconocidos; todo error es `ValueError`.
- **Configuración** (`config/routing.toml`, `src/adapters/routing_config.py`): sección `[rutas]` de tipo → lista de clases y sección `[evidencia]` con la referencia a la medición que justifica cada valor. Un tipo de contenido sin ruta o una tabla inválida hace fallar el arranque con `ValueError` (`test_tabla_invalida_falla_al_arrancar`). Los nombres de clase salen de la configuración, no del código (p. ej. `cpu`, `gpu`), alineados con el `node_class` del worker.
- **Valores iniciales:** provisionales, con «Medición pendiente»: audio prefiere la clase con más hilos o GPU si existe; texto e imagen en `cpu`. Se reemplazan por la medición de F-31 en nodos reales; no se inventan cifras.
- **Decisión nueva (AD-32, propuesta):** la política es una tabla ordenada tipo → clases por defecto estática y validada al arranque, no una heurística dinámica por carga. Alternativas: elegir por carga instantánea del nodo (acopla con M1 y no es reproducible); hard-code en el coordinador (no cita la medición). Se registra en `docs/ARQUITECTURA.md` §8 en la fase de documentación, con «Medición pendiente».
- **Capas:** dominio sin E/S; el adaptador lee TOML con `tomllib`; `tests/unit/test_arquitectura.py` debe seguir en verde. No reutiliza código del I Proyecto.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_tabla_elige_clase_de_nodo` | La clase preferida activa se elige por tipo |
| Unitaria | `test_sin_nodo_preferido_usa_alternativa` | Sin la preferida activa se usa la siguiente de la lista |
| Unitaria | `test_sin_ninguna_clase_activa_falla_explicito` | Error claro, sin perder la sub-tarea |
| Unitaria | `test_tabla_invalida_falla_al_arrancar` | Tabla vacía, lista vacía, duplicados o tipo desconocido dan `ValueError` |
| Unitaria | `test_routing_table_cumple_el_puerto` | Conformidad con `RoutingPolicy` |
| Integración | `test_routing_con_dos_clases_de_worker` | Con dos clases activas, cada tipo llega a su clase y, al caer una, pasa a la otra |
| Aceptación | No aplica | La evidencia es la justificación en la ficha |

## Mediciones

No aplica TDD. La tabla se justifica con la medición de F-31: `python scripts/measure/m5_bench.py --model whisper-base --compute cpu-float32,cpu-int8 --threads 1,2,4 --reps 5 --audio benchmark_set/`. Destino: `docs/modulo-M5-computo.md`, con la referencia en `[evidencia]` de `config/routing.toml`.
**Medición pendiente:** valores en nodos WSL2 reales (dependen de F-38); la variante GPU queda pendiente hasta tener GPU. Los valores iniciales son provisionales.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-32): routing por tipo de nodo con tabla validada y alternativa` | `domain/routing.py`, `adapters/routing_config.py`, `config/routing.toml`, pruebas unitaria e integración, ficha M5, AD-32 y bitácora |

## Riesgos y preguntas abiertas

- El coordinador (M2, Nahúm) debe invocar `route`; esta feature entrega la política y su prueba contra dobles, no el cableado en su código. Hay que avisarle.
- ¿Qué hace el coordinador ante `NoLiveNodeClass` (esperar o reencolar)? Se propone esperar; lo decide M2.
- Valores de la tabla provisionales hasta medir en nodos (F-38).
- Se aprueba AD-32 con este plan.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | SPEC F-32 completo sin campos pendientes, plan de 1 PR, medición pendiente anotada (8d1fabe) |
| verificación IA de plan | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | SPEC F-32 completo, plan de 1 PR, medición pendiente anotada (8fe6903) |
| plan | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de tests | Claude Code (Sonnet 5.5), no independiente | 2026-11-10 | Pruebas nuevas en rojo (ModuleNotFoundError routing y routing_config), sin código de producción (deb3e93) |
| tests | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de implementacion | Claude Code (misma sesion, no independiente) | 2026-11-10 | 22 pruebas en verde (routing, integracion, arquitectura); 3 archivos de codigo ~50 lineas (81647ef) |
| implementacion | José Andrés Loría Herrera | 2026-11-10 |  |
| verificación IA de verificacion | claude-code | 2026-11-10 | QA: 22 pruebas verdes. Hallazgo: ruta como str se expandia a letras; ahora ValueError con prueba. Tipo desconocido, sin clase viva y orden de clases verificados. (453baf4) |
| verificacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de documentacion | claude-code | 2026-11-10 | Documentacion: AD-32 y seccion M5 (2 archivos, 11 lineas), bitacora con error-ia publicada. Verificacion no independiente (2b0ba2c) (2b0ba2c) |
| documentacion | José Andrés Loría Herrera | 2026-11-10 | aprobación delegada por José en el chat |
| verificación IA de revision | claude-code | 2026-11-10 | Revision: diff cumple SPEC (RoutingTable, config, AD-32, ficha M5); 23 pruebas verdes (e712255) |
