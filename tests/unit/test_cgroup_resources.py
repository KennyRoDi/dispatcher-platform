from importlib import import_module
from pathlib import Path

import pytest

from src.domain.resources import ResourceUsage
from tests.contratos import comprobar_resource_reader
from tests.dobles import FakeResourceReader


def crear_lector(ruta, worker_id="worker-sintetico"):
    return import_module("src.infrastructure.cgroup_resources").CgroupResourceReader(
        cgroup_path=ruta, worker_id=worker_id
    )


def escribir_memoria(ruta, actual="123\n", limite="1024\n"):
    (ruta / "memory.current").write_text(actual, encoding="utf-8")
    (ruta / "memory.max").write_text(limite, encoding="utf-8")


def test_lector_devuelve_identidad_y_memoria_en_bytes(tmp_path):
    escribir_memoria(tmp_path, actual="123456789\n", limite="4294967296\n")
    uso = crear_lector(tmp_path, worker_id="worker-gpu-2").read()
    assert uso == ResourceUsage("worker-gpu-2", 123456789, 4294967296)
    assert uso.memory_available == 4171510507


def test_lector_relee_los_archivos_en_cada_consulta(tmp_path):
    escribir_memoria(tmp_path)
    lector = crear_lector(tmp_path)
    assert lector.read().memory_current == 123
    escribir_memoria(tmp_path, actual="456\n", limite="2048\n")
    assert lector.read() == ResourceUsage("worker-sintetico", 456, 2048)


@pytest.mark.parametrize("actual", ["0\n", "2048\n"])
def test_uso_cero_o_transitoriamente_superior_al_limite_es_legible(tmp_path, actual):
    escribir_memoria(tmp_path, actual=actual)
    uso = crear_lector(tmp_path).read()
    assert uso == ResourceUsage("worker-sintetico", int(actual), 1024)
    assert uso.memory_available == max(1024 - int(actual), 0)


@pytest.mark.parametrize("limite", ["max\n", "", "0\n", "-1\n", "1.5\n", "abc\n"])
def test_limite_ilimitado_no_positivo_o_invalido_es_error(tmp_path, limite):
    escribir_memoria(tmp_path, limite=limite)
    with pytest.raises(ValueError):
        crear_lector(tmp_path).read()


@pytest.mark.parametrize("actual", ["", "max\n", "-1\n", "1.5\n", "abc\n"])
def test_uso_de_memoria_invalido_es_error(tmp_path, actual):
    escribir_memoria(tmp_path, actual=actual)
    with pytest.raises(ValueError):
        crear_lector(tmp_path).read()


@pytest.mark.parametrize("archivo", ["memory.current", "memory.max"])
def test_archivo_de_cgroup_ausente_es_error_explicito(tmp_path, archivo):
    escribir_memoria(tmp_path)
    (tmp_path / archivo).unlink()
    with pytest.raises(OSError):
        crear_lector(tmp_path).read()


def test_cgroup_v2_ausente_no_devuelve_capacidad_ilimitada(tmp_path):
    with pytest.raises(OSError):
        crear_lector(tmp_path / "cgroup-inexistente").read()


@pytest.mark.parametrize("archivo", ["memory.current", "memory.max"])
def test_error_de_permisos_de_lectura_no_se_oculta(tmp_path, monkeypatch, archivo):
    escribir_memoria(tmp_path)
    lectura_original = Path.open

    def abrir(ruta, *args, **kwargs):
        if ruta == tmp_path / archivo:
            raise PermissionError("lectura sintética denegada")
        return lectura_original(ruta, *args, **kwargs)

    monkeypatch.setattr(Path, "open", abrir)
    with pytest.raises(OSError):
        crear_lector(tmp_path).read()


@pytest.mark.parametrize("actual, limite", [(0, 1024), (123, 1024), (2048, 1024)])
@pytest.mark.parametrize("adaptador", ["doble", "cgroup"])
def test_resource_reader_cumple_contrato_compartido(tmp_path, actual, limite, adaptador):
    esperado = ResourceUsage("worker-contrato", actual, limite)
    if adaptador == "doble":
        lector = FakeResourceReader(esperado)
    else:
        escribir_memoria(tmp_path, actual=str(actual), limite=str(limite))
        lector = crear_lector(tmp_path, worker_id=esperado.worker_id)
    comprobar_resource_reader(lector, esperado)
