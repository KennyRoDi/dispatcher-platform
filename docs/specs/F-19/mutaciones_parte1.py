import importlib
from pathlib import Path
import runpy
import sys
import tempfile
import types


RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
CONFIG = "src.domain.model_loading"
LOADER = "src.infrastructure.model_loader"
pruebas_config = runpy.run_path(str(RAIZ / "tests/unit/test_model_loading.py"))
pruebas_loader = runpy.run_path(str(RAIZ / "tests/unit/test_model_loader.py"))

CASOS = [
    ("aceptar bool como N", CONFIG, "type(self.processes) is not int", "not isinstance(self.processes, int)",
     pruebas_config["test_numero_de_procesos_debe_ser_entero_positivo"], ("por_proceso", True)),
    ("aceptar estrategia desconocida", CONFIG, 'raise ValueError("estrategia de carga inválida")', "pass",
     pruebas_config["test_estrategia_invalida_se_rechaza_sin_elegir_otra"], ("spawn",)),
    ("usar spawn", LOADER, 'method="fork"', 'method="spawn"',
     pruebas_loader["test_inicia_todos_los_hijos_con_fork_explicito_y_recolecta_cada_uno"], ("por_proceso",)),
    ("omitir join", LOADER, "self.runtime.join(handle)", "pass",
     pruebas_loader["test_inicia_todos_los_hijos_con_fork_explicito_y_recolecta_cada_uno"], ("fork_compartido",)),
    ("cargar por hijo en variante compartida", LOADER, 'self.config.strategy == "fork_compartido"', "False",
     pruebas_loader["test_fork_compartido_precarga_una_vez_y_los_hijos_usan_la_misma_instancia"], (2,)),
    ("ocultar error de inferencia", LOADER, "            raise\n        self._cleanup", "            return []\n        self._cleanup",
     pruebas_loader["test_error_de_inferencia_se_propaga_y_no_deja_hijos_sin_recolectar"], ("por_proceso",)),
]


def main():
    for nombre, modulo, original, mutacion, prueba, argumentos in CASOS:
        cargado = importlib.import_module(modulo)
        prueba(*argumentos)
        fuente = Path(cargado.__file__).read_text(encoding="utf-8")
        assert fuente.count(original) == 1, nombre
        with tempfile.TemporaryDirectory(prefix="F19-mutacion-") as temporal:
            copia = Path(temporal) / "mutado.py"
            copia.write_text(fuente.replace(original, mutacion), encoding="utf-8")
            mutado = types.ModuleType(modulo)
            sys.modules[modulo] = mutado
            try:
                exec(compile(copia.read_text(encoding="utf-8"), str(copia), "exec"), mutado.__dict__)
                try:
                    prueba(*argumentos)
                except BaseException as error:
                    if not isinstance(error, AssertionError) and type(error).__name__ != "Failed":
                        raise
                    print(f"DETECTADA: {nombre} ({type(error).__name__})")
                else:
                    raise AssertionError(f"mutación sobreviviente: {nombre}")
            finally:
                sys.modules[modulo] = cargado
    print(f"{len(CASOS)} de {len(CASOS)} mutaciones detectadas")


if __name__ == "__main__":
    main()
