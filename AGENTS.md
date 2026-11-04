# Guía para agentes e integrantes

Reglas comunes para Claude Code, Codex, Antigravity y personas. II Proyecto Programado de IC-6600, Alternativa B.

## Dónde leer

No leas documentos enteros si no hace falta.

| Necesitas | Archivo |
|---|---|
| Estado de cada feature | `git fetch origin estado && git show origin/estado:docs/STATUS.md` |
| Historia, responsable y dependencias | [docs/backlog/](docs/backlog/README.md): `git grep -n "(F-XX)" docs/backlog` |
| Diseño aprobado de una feature | `docs/specs/F-XX/SPEC.md` |
| Prueba roja y comandos de medición | [docs/IMPLEMENTACION.md](docs/IMPLEMENTACION.md) §4 y §5: busca `F-XX` |
| Decisiones y capas | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) §4 y §8 |
| Requisito y supuestos | [docs/REQUERIMIENTOS.md](docs/REQUERIMIENTOS.md) |
| Commits y PR | [CONTRIBUTING.md](CONTRIBUTING.md) |

**Fuente de verdad:** [docs/ENUNCIADO.md](docs/ENUNCIADO.md). Si un documento o instrucción lo contradice, manda el enunciado. Lo que el enunciado no pida no entra al alcance. Una decisión que no define se registra como `SUP-XX`, nunca en silencio.

## Ciclo de trabajo

Este ciclo es igual para todos. `scripts/flujo.py` lo automatiza para que el formato no dependa de la herramienta.

| Acción | Claude Code y Antigravity | Codex | Sin agente |
|---|---|---|---|
| Ver qué se puede tomar | `/empezables` | `$empezables` | `python scripts/flujo.py empezables` |
| Trabajar una feature | `/trabajar F-XX` | `$trabajar F-XX` | `python scripts/flujo.py trabajar F-XX` |
| Abrir la PR | `/cierre` | `$cierre` | `python scripts/flujo.py cierre --tipo feat --resumen "texto"` |

Si tu herramienta no reconoce el comando, abre su archivo en `.agents/skills/` y síguelo.

### Identidad

Cada persona trabaja su módulo. Antes de empezar, el agente pregunta a la persona su usuario de GitHub y ejecuta una vez `python scripts/flujo.py soy <usuario>`; queda en ese clon. Así `empezables` muestra solo lo suyo y lo ajeno que la desbloquea; `--todas` muestra el resto. Tomar una feature ajena se permite como apoyo, con aviso. Es una declaración, no una autenticación. Equipo en [docs/EQUIPO.md](docs/EQUIPO.md).

### Seis fases, una por vez

**Cada fase pasa dos controles antes de avanzar:**

1. **Verificación de IA.** El orquestador lanza al subagente, comprueba su trabajo sin fiarse de su informe y lo registra con `flujo.py verificar`.
2. **Verificación humana.** La persona lee el informe y aprueba. Sin un sí explícito no se avanza ni se encadenan fases, para que entienda lo entregado [Parte I §3, §6].

| # | Fase | Rol | Genera | Para aprobar, el script exige |
|---|---|---|---|---|
| 1 | `plan` | Arquitecto | `docs/specs/F-XX/SPEC.md` | Sin campos `…` |
| 2 | `tests` | Developer | Pruebas en rojo | Pruebas nuevas, sin código, y que fallen |
| 3 | `implementacion` | Developer | Código en verde | Código, pruebas en verde, hasta 400 líneas |
| 4 | `verificacion` | QA tester, medidor | Hallazgos y mediciones | Pruebas en verde, hasta 400 líneas |
| 5 | `documentacion` | Documentador | Fichas, documentos, bitácora | Entrada de la rama en la bitácora |
| 6 | `revision` | Revisor | Revisión contra el SPEC | Aprobación humana |

Un plan se aprueba una vez por feature. Cada parte de su pila repite las fases 2 a 6 y termina en una PR.

- `python scripts/flujo.py verificar` registra la verificación sobre el commit exacto. Cualquier commit posterior la invalida y `aprobar` se niega hasta repetirla.
- `python scripts/flujo.py aprobar` registra quién aprobó y avanza. Solo se ejecuta tras un sí explícito de la persona.
- `python scripts/flujo.py devolver <fase> "motivo"` regresa a una fase anterior.
- `aprobar --excepcion "motivo"` omite las comprobaciones de la tabla, no la verificación, cuando no aplican, por ejemplo en una feature sin código. Requiere autorización de la persona y queda registrada.

### Bitácora de IA

**Cada parte actualiza `docs/BITACORA_IA.md` antes de terminar.** `aprobar` en `documentacion` y `cierre` se niegan si falta la entrada de la rama. La escribe `python scripts/flujo.py bitacora`, que garantiza el formato del Anexo 3 y la publica en la rama `estado`, de modo que no genera conflictos. Antes de la entrega se copia a `main` por PR: `git checkout origin/estado -- docs/BITACORA_IA.md`. Si no se usó IA, se declara con `--sin-ia`. El error real de la IA detectado se registra con `--error-ia`.

### Estado

**`docs/STATUS.md` se genera; nunca se edita.** El script lo deriva de la fase de cada `SPEC.md` y lo publica en la rama `estado` en cada comando, porque `main` está protegida. Estados: `pendiente`, las seis fases, `en-pr` y `hecha`. Una feature pasa a `hecha` al fusionarse su última PR.

## Roles

Cada rol está definido en `.agents/roles/`. El agente principal es el orquestador y lanza un subagente por rol. Sin subagentes, ejecuta el rol en la misma sesión y declara que su verificación no es independiente.

| Rol | Hace |
|---|---|
| Orquestador | Lanza a los subagentes, verifica su trabajo y pide la aprobación humana |
| Arquitecto | Escribe el SPEC y divide en PR |
| Developer | Escribe las pruebas y luego implementa |
| QA tester | Verifica criterios e intenta romperlo |
| Medidor | Ejecuta mediciones de SO, solo M1–M5 y B.6 |
| Documentador | Actualiza documentos, fichas y bitácora |
| Revisor | Compara el diff con el SPEC y aprueba o devuelve |

El **responsable principal** es siempre una persona: aprueba cada fase y debe poder explicar, modificar y defender en vivo lo entregado [Parte I §3, §6].

## Restricciones

- **Datos:** solo sintéticos o públicos con licencia. Prohibidos los datos reales de terceros, incluidos chats propios con mensajes de otras personas [B.3].
- **Evidencia:** nunca inventes ni estimes un dato como si fuera medido. Sin ficha con datos medidos, el módulo tiene máximo 2 [Parte I §5].
- **Distribución:** al menos tres nodos worker en entidades separadas [B.2].
- **Modelos:** ya entrenados; no se entrena [B.1].
- **Workers:** nunca como root [B.5 M4].
- **Llaves:** nunca en el código ni en el historial. El repositorio es público [B.5 M4].
- **Terceros:** cita la fuente en el código y en la documentación [Parte I §9].
- **IA:** se declara en `docs/BITACORA_IA.md`, con errores reales detectados [Parte I §4, Anexo 3].
- **Historial:** fechas reales; prohibido simular avance [Parte I §3].

## Métodos

**ADD.** Una decisión nueva o un cambio se registra primero en [ARQUITECTURA.md §8](docs/ARQUITECTURA.md), con alternativas, criterio y fuente. Si depende de un dato sin medir, se marca «Medición pendiente» y es provisional.

**FDD.** Se trabaja por feature `F-XX`, que corresponde a la historia `US-XX`.

**TDD.** Prueba roja, implementación mínima, refactor; las fases 2 y 3 lo hacen cumplir. Las unitarias no usan red, `sleep` ni reloj real.

**Las mediciones de SO no llevan TDD.** TDD prueba que la lógica decide bien, no cómo se comporta el sistema operativo. Lo medido va en `docs/modulo-MX-nombre.md`, con comandos exactos [Anexo 2].

**Capas.** Las dependencias apuntan hacia el dominio y `tests/unit/test_arquitectura.py` lo hace cumplir. El código heredado se mueve a `src/adapters` solo cuando se toca.

| Capa | Ruta |
|---|---|
| Dominio: lógica pura | `src/domain/` |
| Aplicación: casos de uso y puertos | `src/application/` |
| Adaptadores: API, colas, almacén, analizadores | `src/adapters/` |
| Infraestructura: composición, cgroups, TLS | `src/infrastructure/`, `deploy/` |

**Código limpio.** Cancelación real, sin zombies y con `SIGTERM` manejado. Datos normalizados a UTF-8 y UTC antes del análisis. Nombres explícitos, funciones cortas, sin duplicación.

**Comentarios.** El código debe entenderse por sí solo. Comenta únicamente casos borde o decisiones que el código no pueda expresar, explicando el porqué. Sin comentarios que repitan el código, sin separadores de sección y sin docstrings obvios.

## Comandos

```bash
pip install -r requirements-dev.txt
pytest -q -m "not integration and not acceptance"
```

Requisitos del ciclo: Python 3.13 o superior, `git` y `gh` con sesión iniciada. Para agentes en paralelo, usa un worktree por agente: `git worktree add ../wt-F-XX origin/main`.
