# Área: M1 · Memoria

### US-16 · Límites por worker (F-16) · P2 · H2
- **Responsable:** J · **Depende de:** —
Como operador, quiero un límite por worker para que ninguno afecte al nodo.
- **Dado** el Compose de un nodo
- **Cuando** arranca
- **Entonces** `memory.max` tiene el límite configurado, y el preflight rechaza si la suma supera la RAM disponible
- **Pruebas:** U `test_preflight_rechaza_suma_de_limites_mayor_a_ram`. I lectura de `memory.max` en cada contenedor.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: valores por worker.

### US-17 · Control de admisión (F-17) · P2 · H2
- **Responsable:** J · **Depende de:** F-16
Como operador, quiero admitir solo lo que cabe en memoria para evitar terminaciones por OOM.
- **Dado** un worker sin memoria para otra sub-tarea según la huella medida
- **Cuando** hay trabajo en cola
- **Entonces** no la saca de la cola y otro nodo con capacidad puede tomarla
- **Pruebas:** U `test_rechaza_si_no_cabe_huella_con_margen`. I worker con límite bajo y dos sub-tareas. A US-37.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: tabla de huella y gráfico de memoria por worker.

### US-18 · Detección de OOM (F-18) · P2 · H2
- **Responsable:** J · **Depende de:** F-12, F-16
Como operador, quiero distinguir un OOM de otros fallos para aplicar la política correcta.
- **Dado** una sub-tarea que excede el límite
- **Cuando** el kernel termina el subproceso
- **Entonces** queda registrada con causa `oom` y se reencola con más reserva, hasta el máximo de la política; el supervisor sigue activo
- **Pruebas:** U `classify_exit`, `OomPolicy`. I OOM real con un asignador de memoria en contenedor.
- **Demuestra:** prueba I. **Evidencia:** ficha M1: `memory.events` y recuperación.

### US-19 · Estrategias de carga (F-19) · P2 · H2
- **Responsable:** J · **Depende de:** F-09
Como responsable de M1, quiero ejecutar ambas estrategias para justificar la elegida con datos.
- **Dado** el parámetro de estrategia
- **Cuando** se inicia con N procesos en cada variante
- **Entonces** ambas producen el mismo resultado y se obtiene su memoria total
- **Pruebas:** U selección. I igualdad de salidas en ambas variantes.
- **Demuestra:** comparación de PSS. **Evidencia:** ficha M1: tabla comparativa y decisión AD-07.
