**Resumen:** 42 historias de usuario, una por funcionalidad, divididas por área, con criterios, prioridad, pruebas y evidencia.

# Backlog

- [recepcion-dataset](recepcion-dataset.md)
- [cola-workers](cola-workers.md)
- [estados-reporte-dashboard](estados-reporte-dashboard.md)
- [m1-memoria](m1-memoria.md)
- [m2-planificacion](m2-planificacion.md)
- [m3-es-almacenamiento](m3-es-almacenamiento.md)
- [m4-seguridad](m4-seguridad.md)
- [m5-computo](m5-computo.md)
- [carga-fallos](carga-fallos.md)
- [entrega](entrega.md)

## Dependencias

Cada módulo se desarrolla de principio a fin sin esperar a otro. **Una feature de módulo solo puede depender de otra del mismo responsable;** el check `piezas y formato` lo exige. El contacto entre módulos ocurre por los contratos de [CONTRATOS.md](../CONTRATOS.md), con dobles y pruebas de conformidad.

Solo F-33 a F-37, F-41 y F-42 dependen de varios módulos: son la integración final sobre los tres nodos.

## Prioridad

Todos los requisitos son obligatorios [B.10], por lo que MoSCoW los dejaría a todos en «Must» y no ayudaría a decidir. Se usa una prioridad numérica, justificada por hito y dependencias.

| P | Criterio | Hito | Justificación |
|---|---|---|---|
| 1 | Sin esto no se puede medir ni demostrar nada | H1 | Los tres nodos, el dataset y los workers son prerrequisito de M1 a M5 y de B.6 |
| 2 | Módulo con 8 % de la nota, con tope de 2 si no tiene ficha medida [Parte I §5] | H2, H3 | M1 a M5 suman 40 % [B.9] |
| 3 | Pipeline y estados que exige la rúbrica | H2 | Parte del 15 % de pipeline; además los usa B.6 |
| 4 | Escenarios B.6 | H3 | 10 % [B.9]; dependen de P1 a P3 |
| 5 | Vistas sobre datos ya disponibles | H3 | Menor coste y menor peso individual |

Las historias de entrega (US-38 a US-42) toman P1 o P2 según lo que bloquean: los rubros comunes suman 35 % [Parte I §8].

Pruebas: **U** unitaria, **I** integración, **A** aceptación.

El estado de cada funcionalidad está en `docs/STATUS.md` de la rama `estado`. Responsables: [EQUIPO.md](../EQUIPO.md).

## Cobertura de hitos

| Hito | Historias |
|---|---|
| H1 | US-01 a US-09, US-38, US-39, US-40 |
| H2 | US-10 a US-13, US-16 a US-25 |
| H3 | US-14, US-15, US-26 a US-37, US-41, US-42 |
