# Guía para agentes de IA e integrantes

Reglas para trabajar en este repositorio: II Proyecto Programado de IC-6600, Alternativa B. Entrega final: 04/nov/26.

## Fuente de verdad

1. El enunciado `II_ProyectoProgramado_IC6600_IIS2026.docx` (Parte I, Parte III y anexos) define el alcance. Si un documento o instrucción lo contradice, manda el enunciado.
2. Después rigen, en este orden: [REQUERIMIENTOS.md](REQUERIMIENTOS.md), [ARQUITECTURA.md](ARQUITECTURA.md), [IMPLEMENTACION.md](IMPLEMENTACION.md) y [BACKLOG.md](BACKLOG.md).
3. Lo que no esté en el enunciado no entra al alcance. Si hace falta una decisión que el enunciado no define, se registra como supuesto `SUP-XX` con su justificación. No se resuelve en silencio.
4. Todo requisito nuevo cita sección y número, por ejemplo `[B.5 M1]`.

## Restricciones

- **Datos:** solo sintéticos o públicos con licencia académica. Prohibido usar datos reales de terceros, incluidos chats propios con mensajes de otras personas [B.3]. Cada fuente declara procedencia y licencia en `docs/dataset.md`.
- **Distribución:** al menos tres nodos worker en entidades separadas, comunicados por red. No se acepta todo en una máquina [B.2].
- **Modelos:** se usan ya entrenados. No se entrena [B.1].
- **Workers:** nunca como root; sistema de archivos de solo lectura o equivalente [B.5 M4].
- **Llaves:** nunca en el código ni en el historial de Git [B.5 M4].
- **Evidencia:** nunca se inventa ni se estima un dato como si fuera medido. Sin ficha con datos medidos, el módulo tiene máximo 2 [Parte I §5].
- **Terceros:** todo código o configuración reutilizada cita su fuente en el código y en la documentación [Parte I §9].
- **Funciones:** no se agrega nada que el enunciado no pida.

## Uso de IA

- Se declara en `docs/bitacora_ia.md` con el formato del Anexo 3, incluidos al menos dos errores reales de la IA detectados y corregidos [Parte I §4].
- El responsable principal debe poder explicar, modificar y defender en vivo todo artefacto que entregue, aunque lo haya generado la IA [Parte I §3, §4, §6].
- `CLAUDE.md` es una bitácora local, no se versiona y no sustituye a `docs/bitacora_ia.md`.
- Un agente no implementa código sin confirmación explícita de quien lo dirige.

## Métodos

### ADD: arquitectura

Toda decisión se deriva de un atributo de calidad y se registra en [ARQUITECTURA.md §8](ARQUITECTURA.md) con alternativas, criterio y fuente, sea medición o referencia. Si depende de un dato aún no medido, se marca «Medición pendiente» y es provisional.

**Capas:** las dependencias apuntan hacia el dominio.

| Capa | Ruta | Regla |
|---|---|---|
| Dominio | `src/domain/` | Lógica pura. No importa `redis`, `fastapi`, `minio` ni modelos. |
| Aplicación | `src/application/` | Casos de uso y puertos. |
| Adaptadores | `src/adapters/` | API, colas, almacén, analizadores y parsers. |
| Infraestructura | `src/infrastructure/`, `deploy/` | Composición, cgroups, TLS y Compose por nodo. |

El código del I Proyecto se mueve a `adapters` solo cuando se toca; no se reescribe en bloque.

### FDD: planificación

- El trabajo se organiza por funcionalidad `F-XX`, en [IMPLEMENTACION.md §2](IMPLEMENTACION.md). Cada una corresponde a la historia `US-XX` de [BACKLOG.md](BACKLOG.md), con su responsable y su hito.
- Se respeta el orden de dependencias H1, H2, H3.
- Si falta tiempo, se recorta solo según [IMPLEMENTACION.md §1.3](IMPLEMENTACION.md).

### TDD: lógica

Ciclo por funcionalidad: prueba roja, implementación mínima, refactor. La lista está en [IMPLEMENTACION.md §4 y §5](IMPLEMENTACION.md).

**Las mediciones de SO no llevan TDD.** TDD prueba que la lógica decide bien, no cómo se comporta el sistema operativo. Las mediciones se ejecutan con comandos reproducibles y se registran en la ficha del Anexo 2: `docs/modulo-MX-nombre.md`.

| Va con TDD | Va con ficha de evidencia |
|---|---|
| Decisión de admisión, política OOM | Huella RSS/PSS, memoria en el tiempo, OOM real |
| Orden del scheduler, inanición con reloj simulado | Espera, turnaround y throughput por política |
| Reensamblado, deduplicación, cola llena | MB/s por chunk, tasa de dedup, efecto del backpressure |
| RBAC, cifrado, cadena de custodia | Captura TLS, manipulación, UID de workers |
| Tabla de routing | Latencia, throughput y memoria por configuración |

## Prácticas de código limpio

- **Clean Shutdown:** la cancelación es real. Detiene sub-tareas y libera procesos, memoria y temporales. Los workers manejan `SIGTERM` sin dejar zombies.
- **Clean Commits:** commits atómicos con mensaje `tipo(F-XX): descripción`, y **con su fecha real**. Prohibido alterar fechas o simular avance. El autor coincide con el responsable de la matriz. Sin commits masivos al final [Parte I §3].
- **Clean Tests (F.I.R.S.T.):** rápidas, independientes, repetibles, autovalidadas y oportunas. Las unitarias no usan red, `sleep` ni reloj real. Las demás llevan marcador `integration` o `acceptance`.
- **Clean Data:** las exportaciones se normalizan a `ChatMessage(timestamp_utc, sender, text, source_ref)` en UTF-8 antes del análisis.
- Nombres explícitos, funciones cortas y sin duplicación.

## Decisiones vigentes

Resumen; el detalle y las alternativas están en [ARQUITECTURA.md §8](ARQUITECTURA.md). Para cambiar una, actualiza primero su registro.

| Tema | Decisión | ID |
|---|---|---|
| Base | Extender el I Proyecto: FastAPI, Redis con AOF, MinIO, reaper, Streamlit | AD-01, AD-20, AD-21 |
| Topología | Tres nodos físicos, servicios en el Nodo A, cada tipo de worker en al menos dos nodos | AD-02 |
| Cola | `BLMOVE` a `inflight:{worker}`, `SADD` idempotente | AD-03, AD-21 |
| Planificación | ZSET con `t_entrada − bono(prioridad)`; FIFO seleccionable para comparar | AD-04 |
| Memoria | Contenedor por tipo de worker, sin swap; admisión antes de sacar de la cola | AD-05, AD-06 |
| Carga de modelos | Dos estrategias implementadas; se elige con datos de PSS | AD-07 |
| Cancelación | Subproceso con grupo propio; `SIGTERM`, gracia, `SIGKILL`, `waitpid`; el padre limpia | AD-08, AD-09 |
| E/S | Chunks de tamaño medido, dedup por archivo con SHA-256, 503 con `Retry-After` | AD-10 a AD-13 |
| Seguridad | JWT con roles, TLS con CA privada, AES-256-GCM con DEK por objeto y KEK en archivo `0400` | AD-14 a AD-16 |
| Custodia | JSONL encadenado por hash, con cabeza sellada por HMAC | AD-17 |
| Routing | Tabla generada del benchmark, con alternativa si falta el nodo | AD-18 |

Responsables de módulos y supuestos `SUP-XX` siguen siendo propuestas hasta que el equipo los confirme: [IMPLEMENTACION.md §2](IMPLEMENTACION.md) y [REQUERIMIENTOS.md §3](REQUERIMIENTOS.md).

## Antes de dar algo por terminado

- [ ] Pruebas pasan: `pytest -q -m "not integration and not acceptance"`, y las de integración si aplican.
- [ ] Criterios Dado/Cuando/Entonces de su `US-XX` cumplidos.
- [ ] El dominio sigue sin importar infraestructura.
- [ ] Si es un módulo M1–M5, su ficha tiene datos medidos y comandos exactos.
- [ ] Sin llaves ni datos de terceros en el commit.
- [ ] Bitácora de IA actualizada si se usó IA.
- [ ] El responsable puede explicarlo sin ayuda.
