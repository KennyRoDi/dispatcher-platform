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

**Fase de planificación.** Este repositorio contiene los documentos de diseño; todavía no hay código ni mediciones. La implementación extenderá la plataforma del I Proyecto Programado.

## Mapa del repositorio

| Ruta | Contenido |
|---|---|
| [docs/REQUERIMIENTOS.md](docs/REQUERIMIENTOS.md) | Requisitos con cita al enunciado, supuestos y trazabilidad |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Escenarios de calidad, capas, diagramas y decisiones |
| [docs/IMPLEMENTACION.md](docs/IMPLEMENTACION.md) | Funcionalidades, calendario, responsables y comandos de medición |
| [docs/BACKLOG.md](docs/BACKLOG.md) | Historias de usuario con criterios de aceptación y pruebas |

Conviene leerlos en ese orden, porque cada uno depende del anterior.

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
