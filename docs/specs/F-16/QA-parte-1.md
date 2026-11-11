# QA F-16, parte 1

**Resultado: APROBADO por QA de IA.** No sustituye la aprobación humana de la fase.

Fecha: 2026-11-10. Rama: `feat/F-16-1-limites-por-worker`.
Producto revisado: `c19dc26`; estado del SPEC y aprobaciones al comenzar: `9ddba23`.
Revisión independiente del developer, realizada por el subagente QA de Codex.

## Alcance y criterios

Se revisó el diff contra `origin/main`, el SPEC, el rol QA, los puertos y el modelo de recursos existentes. Esta parte agrega 52 líneas de producto: lector de archivos cgroup en infraestructura y presupuesto puro en dominio. No cambia workers, despliegue ni contratos públicos.

| Criterio aplicable a parte 1 | Evidencia y resultado |
|---|---|
| Rechazar suma superior a RAM | `test_preflight_rechaza_suma_de_limites_mayor_a_ram`: pasa; comparación directa de bytes enteros, sin reloj ni servicios |
| Aceptar igualdad y presupuesto menor | `test_presupuesto_igual_o_menor_a_ram_es_valido`: ambos casos pasan |
| Considerar reserva y cada réplica | `test_reserva_se_suma_antes_de_comparar_con_ram`, `test_cada_replica_consume_su_limite_aunque_sean_iguales` y reserva cero explícita: pasan |
| Rechazar configuración ausente/no positiva/inválida | Parametrizaciones de RAM, límites y reserva: pasan; `None`, cadenas, flotantes y booleanos se rechazan. Reserva cero es válida según su semántica; RAM y límites deben ser positivos |
| Leer bytes e identidad con ruta inyectada | `test_lector_devuelve_identidad_y_memoria_en_bytes`: pasa, incluidos valores superiores a 32 bits |
| Consultar de nuevo el estado | `test_lector_relee_los_archivos_en_cada_consulta`: pasa; no conserva una lectura anterior |
| Rechazar `max`, contenido inválido, archivo ausente y lectura denegada | Parametrizaciones del lector y errores de archivos/permisos: pasan; los errores se propagan explícitamente |
| Conservar `ResourceReader` y `ResourceUsage` | Contrato compartido aplicado al doble y al lector temporal para uso cero, normal y superior al límite: pasa; disponibilidad acotada a cero |
| Separación de capas y ausencia de mutación del presupuesto | Prueba de arquitectura incluida en suite; `test_presupuesto_no_modifica_los_limites_del_operador`: pasa |

El criterio de arranque Compose, `mem_limit == memswap_limit`, expansión de configuración efectiva y réplicas, rechazo antes de `compose up`, así como `memory.max` aplicado por el kernel, corresponden a la **parte 2** aprobada en el plan. Aquí se verifica que el cálculo cuenta cada límite recibido; no se demuestra todavía que Compose entregue todos los contenedores.

## Ejecución independiente

Comando desde la raíz del repositorio, con el lanzador Python instalado de Windows fuera del sandbox:

```powershell
py -m pytest -q -m "not integration and not acceptance"
git diff origin/main...HEAD --check
```

Resultado: **1138 passed, 2 skipped, 3 deselected**, 42.36 s. Una advertencia de deprecación de Starlette/httpx ya observada en implementación. `git diff --check` sin errores. La suite incluye las 53 pruebas de presupuesto/lector y la prueba de arquitectura.

## Sensibilidad a regresiones

Se crearon seis copias temporales independientes de los archivos Python de `src/` y `tests/`, junto con `pytest.ini`, dentro de `.qa-f16-mutations/<mutación>/`. En cada copia se aplicó exclusivamente la sustitución indicada y se ejecutó, desde esa carpeta:

```powershell
py -m pytest -q tests/unit/test_node_budget.py tests/unit/test_cgroup_resources.py --tb=no
```

Cada ejecución terminó con código 1 por aserciones fallidas, sin errores de colección. Las copias se eliminaron tras comprobar sus rutas dentro del workspace; los archivos aprobados permanecieron intactos.

| Mutación | Sustitución exacta | Resultado |
|---|---|---|
| Ignorar reserva | `required_memory = reserve` → `required_memory = 0` | 1 failed, 52 passed |
| Rechazar igualdad | `required_memory > node_memory` → `required_memory >= node_memory` | 3 failed, 50 passed |
| Omitir réplicas iguales | `for limit in worker_limits:` → `for limit in set(worker_limits):` | 1 failed, 52 passed |
| Permitir límite cero | `_validate_bytes(limit, "worker_limit", 1)` → `_validate_bytes(limit, "worker_limit", 0)` | 1 failed, 52 passed |
| Leer archivo incorrecto para uso actual | `memory_current=self._read_bytes("memory.current", 0)` → `memory_current=self._read_bytes("memory.max", 0)` | 14 failed, 39 passed |
| Aceptar capacidad ilimitada | Insertar `if content == "max": return 999999999999999` antes de validar el contenido | 2 failed, 51 passed |

Esto demuestra sensibilidad a estas seis regresiones concretas; no es una medición exhaustiva de cobertura de mutaciones.

## Exploración adicional de bordes

Se ejecutó el siguiente programa mediante un here-string de PowerShell enviado a `py -`. Terminó con código 0 y `9 comprobaciones exploratorias correctas`. No generó pruebas persistentes ni modificó producción.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from src.domain.node_budget import validate_node_budget
from src.infrastructure.cgroup_resources import CgroupResourceReader

validate_node_budget(worker_limits=(n for n in [400, 500]), node_memory=1000, reserve=100)
with TemporaryDirectory() as folder:
    path = Path(folder)
    (path / "memory.current").write_text("1", encoding="utf-8")
    for invalid in ["١٠٢٤", "+1024", "1_024", "1024\x00", "1024 2048", "1e3"]:
        (path / "memory.max").write_text(invalid, encoding="utf-8")
        try:
            CgroupResourceReader(cgroup_path=path, worker_id="qa").read()
        except ValueError:
            pass
        else:
            raise AssertionError(repr(invalid))
    (path / "memory.max").write_bytes(bytes([255]))
    try:
        CgroupResourceReader(cgroup_path=path, worker_id="qa").read()
    except UnicodeDecodeError:
        pass
    else:
        raise AssertionError("UTF-8 ilegible aceptado")
    (path / "memory.max").unlink()
    (path / "memory.max").mkdir()
    try:
        CgroupResourceReader(cgroup_path=path, worker_id="qa").read()
    except OSError:
        pass
    else:
        raise AssertionError("Directorio aceptado como archivo")
print("9 comprobaciones exploratorias correctas")
```

## Hallazgos y limitaciones

No se encontraron fallos reproducibles del alcance de parte 1 ni se agregaron correcciones o pruebas de producción. Los archivos temporales simulan lecturas; no son evidencia del kernel. No se ejecutaron Docker, WSL2, mediciones de RAM, límites reales ni pruebas de integración/aceptación. La coordinación con Kenni, el preflight de arranque y las mediciones de los nodos B/C/D siguen pendientes para parte 2 y no constituyen fallos de esta parte. No se ejecutaron comandos de aprobación, verificación del flujo ni bitácora.
