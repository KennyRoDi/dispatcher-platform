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

Una dependencia significa un bloqueo real: sin ella no se puede probar la feature. La lógica que se apoya en `src/application/ports.py` se desarrolla con fakes, sin esperar a otro módulo.

Trabajar con fakes no termina la integración. Quien entrega una feature conecta su adaptador real si la otra parte ya está en `main`. Si no, lo indica en su SPEC como integración pendiente. Los escenarios F-33 a F-37 dependen de todo lo que integran y lo comprueban sobre los tres nodos.

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
