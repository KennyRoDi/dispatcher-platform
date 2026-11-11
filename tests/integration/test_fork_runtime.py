from importlib import import_module
import multiprocessing
import os

import pytest


def devolver(valor):
    return valor


def fallar():
    raise ValueError("fallo hijo")


def bloquear(evento):
    evento.wait()


def runtime(timeout=2):
    return import_module("src.infrastructure.fork_runtime").ForkProcessRuntime(timeout=timeout)


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_runtime_linux_exige_fork_y_retorna_valor_del_hijo():
    worker = runtime()
    handle = worker.start(devolver, ([1, "ok"],), method="fork")
    try:
        assert worker.result(handle) == [1, "ok"]
        assert handle.exitcode == 0
    finally:
        worker.join(handle)


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_runtime_rechaza_metodo_spawn():
    with pytest.raises(ValueError):
        runtime().start(devolver, (1,), method="spawn")


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_runtime_propaga_error_del_hijo_y_lo_recolecta():
    worker = runtime()
    handle = worker.start(fallar, (), method="fork")
    with pytest.raises(RuntimeError, match="fallo hijo"):
        worker.result(handle)
    worker.join(handle)
    assert handle.exitcode != 0


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_runtime_timeout_termina_y_recolecta_hijo():
    evento = multiprocessing.get_context("fork").Event()
    worker = runtime(timeout=0.05)
    handle = worker.start(bloquear, (evento,), method="fork")
    with pytest.raises(TimeoutError):
        worker.result(handle)
    worker.terminate(handle)
    worker.join(handle)
    assert not handle.is_alive()
