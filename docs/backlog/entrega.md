# Área: entrega y proceso

### US-38 · Despliegue en tres nodos (F-38) · P1 · H1
- **Responsable:** K · **Depende de:** —
Como equipo, queremos desplegar en tres máquinas para cumplir la distribución real.
- **Dado** tres máquinas en red con Docker
- **Cuando** se siguen las instrucciones y se levanta el Compose de cada nodo
- **Entonces** tres `hostname` distintos aparecen como workers activos y procesan sub-tareas
- **Pruebas:** I `scripts/check_connectivity.py` existente. A corrida con reparto por nodo.
- **Demuestra:** tabla de sub-tareas por `hostname`. **Evidencia:** log de `GET /workers` e IP por nodo.

### US-39 · Reutilización y correcciones (F-39) · P1 · H1
- **Responsable:** N · **Depende de:** —
Como evaluador, quiero saber qué es reutilizado y qué es nuevo para evaluar lo nuevo.
- **Dado** el repositorio del I Proyecto
- **Cuando** se revisa `docs/reutilizacion.md`
- **Entonces** cada componente aparece como reutilizado, modificado o nuevo, con ruta, y cada deficiencia tiene corrección enlazada
- **Pruebas:** A revisión contra `ARQUITECTURA.md` §1.
- **Demuestra:** el documento. **Evidencia:** `docs/reutilizacion.md`.

### US-40 · Matriz, historial y bitácora (F-40) · P1 · H1
- **Responsable:** K · **Depende de:** —
Como evaluador, quiero ver responsabilidades, proceso y uso de IA para valorar la contribución individual.
- **Dado** el repositorio
- **Cuando** se revisan la matriz, el historial y la bitácora
- **Entonces** cada módulo tiene responsable, cada integrante tiene al menos un módulo y commits propios, hay entradas por módulo y ≥ 2 errores reales de la IA documentados
- **Pruebas:** A `git shortlog -sn --all`; revisión contra Anexos 1 y 3.
- **Demuestra:** comandos y documentos. **Evidencia:** `docs/responsabilidades.md`, `docs/BITACORA_IA.md`.

### US-41 · Fichas de evidencia (F-41) · P2 · H3
- **Responsable:** Cada responsable · **Depende de:** F-19, F-21, F-25, F-29, F-30, F-32
Como evaluador, quiero fichas con datos medidos para calificar cada módulo.
- **Dado** los cinco módulos
- **Cuando** se revisa cada ficha
- **Entonces** tiene los cinco elementos, con comandos exactos, resultados, interpretación y referencia bibliográfica
- **Pruebas:** A lista de comprobación contra RNF-09 a RNF-14; repetir un comando por ficha en otra máquina.
- **Demuestra:** comprobación. **Evidencia:** `docs/modulo-M1-memoria.md`, `docs/modulo-M2-planificacion.md`, `docs/modulo-M3-es-almacenamiento.md`, `docs/modulo-M4-seguridad.md`, `docs/modulo-M5-computo.md`.

### US-42 · Informe, README, demo y defensa (F-42) · P1 · H3
- **Responsable:** Todos · **Depende de:** F-33, F-34, F-35, F-36, F-37, F-41
Como evaluador, quiero el informe y una demo real para verificar el sistema y la comprensión de cada integrante.
- **Dado** el sistema en los tres nodos
- **Cuando** se presenta
- **Entonces** `docs/BITACORA_IA.md` de `main` está al día con la rama `estado` (`git checkout origin/estado -- docs/BITACORA_IA.md` por PR); el PDF tiene ≤ 20 páginas sin anexos e integra B.6; la demo es en vivo; cada responsable explica y modifica su componente
- **Pruebas:** A ensayo completo de la demo y simulacro cruzado de preguntas.
- **Demuestra:** ensayo. **Evidencia:** informe PDF y README con mapa del repositorio.
