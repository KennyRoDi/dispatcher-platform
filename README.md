# Plataforma distribuida de análisis de datos de mensajería

II Proyecto Programado de IC-6600 Principios de Sistemas Operativos, II Semestre 2026, Instituto Tecnológico de Costa Rica, Campus San Carlos. Alternativa B.

La plataforma recibe casos de análisis con conversaciones, notas de voz, imágenes, videos y documentos, los procesa en workers distribuidos y genera reportes consolidados con evidencias enlazadas a su fuente.

El análisis es la carga de trabajo, no el objetivo. El proyecto se centra en cómo el sistema administra recursos escasos y protege información sensible:

| Módulo | Tema |
|---|---|
| M1 | Gestión de memoria: límites con cgroups v2, control de admisión y recuperación de OOM |
| M2 | Planificación: cuatro niveles de prioridad, sin inanición |
| M3 | E/S y almacenamiento: chunks, almacenamiento por contenido y backpressure |
| M4 | Protección y seguridad: roles, TLS, cifrado en reposo y cadena de custodia |
| M5 | Cómputo heterogéneo: routing basado en mediciones |

Solo se usan datos sintéticos o públicos con licencia. Está prohibido incorporar conversaciones, audios o imágenes reales de terceros, incluidos chats propios con mensajes de otras personas.

## Estado

**En desarrollo.** El repositorio contiene el código del I Proyecto Programado, que sirve de base, y los documentos de diseño. Las funcionalidades del II Proyecto y sus mediciones aún no están implementadas. El avance está en `docs/STATUS.md` de la rama `estado`.

## Cómo trabajar

Personas y agentes (Claude Code, Codex y Antigravity) siguen el mismo ciclo: elegir una tarea y avanzar por seis fases, plan, tests, implementación, verificación, documentación y revisión, con aprobación humana en cada una, hasta abrir PR pequeñas y apiladas. Empieza por [AGENTS.md](AGENTS.md) y [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python scripts/flujo.py empezables
```

## Mapa del repositorio

| Ruta | Contenido |
|---|---|
| [AGENTS.md](AGENTS.md) | Reglas y ciclo de trabajo para agentes y personas |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Commits, títulos de PR y pilas |
| `docs/STATUS.md` de la rama `estado` | Estado de cada funcionalidad |
| [docs/backlog/](docs/backlog/README.md) | Historias, responsables, dependencias y criterios de aceptación |
| [docs/specs/](docs/specs/) | `SPEC.md` aprobado de cada funcionalidad |
| [docs/BITACORA_IA.md](docs/BITACORA_IA.md) | Bitácora de uso de IA |
| [docs/ENUNCIADO.md](docs/ENUNCIADO.md) | Enunciado del proyecto: fuente de verdad |
| [docs/REQUERIMIENTOS.md](docs/REQUERIMIENTOS.md) | Requisitos con cita al enunciado, supuestos y trazabilidad |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Escenarios de calidad, capas, diagramas y decisiones |
| [docs/IMPLEMENTACION.md](docs/IMPLEMENTACION.md) | Funcionalidades, responsables, TDD y comandos de medición |
| [docs/README_I_PROYECTO.md](docs/README_I_PROYECTO.md) | Manual de la plataforma heredada |
| `src/domain`, `src/application`, `src/adapters`, `src/infrastructure` | Capas nuevas |
| `src/coordinator`, `src/workers`, `dashboard`, `scripts`, `deploy` | Código heredado del I Proyecto |
| `tests/` | Pruebas heredadas y `unit`, `integration`, `acceptance` |
| `scripts/flujo.py` | Comandos del ciclo de trabajo |
| `.agents/` | Comandos y roles comunes a todos los agentes |

## Manual

*Pendiente: se completará cuando el sistema esté implementado.*

### Requisitos

*Pendiente.*

### Instalación y despliegue en tres nodos

*Pendiente.*

### Uso

*Pendiente.*

### Pruebas

*Pendiente.*
