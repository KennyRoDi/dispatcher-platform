from importlib import import_module

import pytest


def configuracion(estrategia, procesos):
    return import_module("src.domain.model_loading").LoadingConfig(
        strategy=estrategia, processes=procesos
    )


@pytest.mark.parametrize("estrategia", ["por_proceso", "fork_compartido"])
@pytest.mark.parametrize("procesos", [1, 2, 7])
def test_configuracion_elige_estrategia(estrategia, procesos):
    config = configuracion(estrategia, procesos)

    assert config.strategy == estrategia
    assert config.processes == procesos


@pytest.mark.parametrize(
    "estrategia",
    [None, "", "spawn", "mmap", "POR_PROCESO", " por_proceso", "fork_compartido ", 1, True, []],
)
def test_estrategia_invalida_se_rechaza_sin_elegir_otra(estrategia):
    with pytest.raises(ValueError):
        configuracion(estrategia, 2)


@pytest.mark.parametrize("procesos", [None, 0, -1, 1.0, 1.5, "2", True, False, []])
@pytest.mark.parametrize("estrategia", ["por_proceso", "fork_compartido"])
def test_numero_de_procesos_debe_ser_entero_positivo(estrategia, procesos):
    with pytest.raises(ValueError):
        configuracion(estrategia, procesos)
