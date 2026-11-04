# Cómo contribuir

Estas reglas aplican a personas y agentes. El ciclo completo está en [AGENTS.md](AGENTS.md). `scripts/flujo.py` rechaza los commits y títulos que no las cumplan.

## Commits y títulos de PR

Ambos siguen [Conventional Commits 1.0.0](https://www.conventionalcommits.org/es/v1.0.0/):

```text
<tipo>(F-XX): <descripción>
```

- Descripción en español, en imperativo, en minúscula, sin punto final y de hasta 72 caracteres en total.
- El ámbito es la feature. Sin feature, se omite: `docs: actualizar readme`.
- Un cambio incompatible lleva `!`: `feat(F-06)!: cambiar formato de la cola`.

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un error |
| `test` | Pruebas sin cambiar el comportamiento |
| `refactor` | Cambio interno sin cambiar el comportamiento |
| `perf` | Mejora de rendimiento |
| `docs` | Documentación, SPEC, fichas y bitácora |
| `build` | Dependencias e imágenes |
| `ci` | Integración continua |
| `chore` | Mantenimiento |
| `style` | Formato sin cambiar la lógica |
| `revert` | Revertir un commit anterior |

Ejemplos:

```text
test(F-20): agregar prueba de inanicion con reloj simulado
feat(F-20): ordenar sub-tareas con aging implicito
docs(F-20): agregar spec
```

- **Título de PR:** usa el mismo formato y describe el resultado de toda la PR.
- **Commits atómicos:** un paso coherente por commit, con su prueba.
- **Autoría:** cada persona usa su propia identidad de Git. El autor debe coincidir con la matriz de responsabilidades [Parte I §3].
- **Fechas:** siempre reales. Prohibido usar `GIT_COMMITTER_DATE` o `--date` para simular avance.
- `chore(status): regenerar` y `docs(F-XX): aprobar fase …` los genera solo `scripts/flujo.py`.
- `docs/STATUS.md` nunca se edita a mano.

## Ramas

`feat/F-XX-<parte>-<descripcion>`, por ejemplo `feat/F-20-2-scheduler-redis`. La crea `flujo.py trabajar`, de modo que el número de parte y la base siempre sean correctos. La base queda registrada en el SPEC.

## PR pequeñas y apiladas

Cada PR hace una sola cosa y tiene **hasta 400 líneas, sin contar `tests/` ni `docs/`**. Si crece más, se divide en otra parte de la pila. El SPEC define esa división de antemano.

```text
main
 └─ feat/F-20-1-politica-aging        PR 1: base main
     └─ feat/F-20-2-scheduler-redis   PR 2: base la rama de la PR 1
         └─ feat/F-21-1-fifo          PR 3: otra feature apilada sobre la anterior
```

- **Crear:** con las fases de una parte aprobadas, `flujo.py trabajar F-20 "scheduler redis"` crea la siguiente encima.
- **Apilar otra feature:** `flujo.py empezables` indica cuándo su única dependencia pendiente está en curso, y `trabajar` usa esa rama como base.
- **Última parte:** `flujo.py cierre --final` marca el SPEC como cerrado. Al fusionar esa PR, la feature pasa a `hecha`.
- **Revisar:** cada PR se revisa por sí sola, de abajo hacia arriba.
- **Fusionar:** de abajo hacia arriba, **con merge commit, nunca squash ni rebase**. Así se conserva la autoría que exige [Parte I §3] y las ramas superiores no necesitan reescribirse.
- **Después de fusionar:** borra la rama. GitHub cambia la base de la PR siguiente automáticamente.
- **Si cambia una PR intermedia:** corrige en su rama y propaga con merge a las superiores, o desde la rama superior con `git rebase --update-refs <base>` y `git push --force-with-lease` si la pila es tuya. Nunca fuerces el push de una rama compartida.

## Comprobaciones automáticas

`flujo.py aprobar` comprueba cada fase (ver [AGENTS.md](AGENTS.md)). `flujo.py cierre` exige todas las fases aprobadas, sin cambios pendientes, y comprueba commits, título, tamaño y `pytest -q -m "not integration and not acceptance"`.

Superar el límite de tamaño no tiene excepción: se divide la PR. Quien revisa sigue siendo responsable de comprobar los criterios de `docs/BACKLOG.md`.

## Configuración del repositorio

Una vez, quien administre el repositorio:

```bash
gh repo edit --enable-squash-merge=false --enable-rebase-merge=false --delete-branch-on-merge
```

`main` debe aceptar los commits `chore(status): regenerar` del script. Si se protege, hay que permitirlos o `docs/STATUS.md` dejará de actualizarse.
