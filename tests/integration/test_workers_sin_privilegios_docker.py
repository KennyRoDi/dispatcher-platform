import json
import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.integration


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30)


@pytest.fixture
def contenedor() -> str:
    if shutil.which("docker") is None:
        pytest.skip("docker no esta instalado")
    nombre = os.environ.get("WORKER_CONTAINER")
    if not nombre:
        pytest.skip("define WORKER_CONTAINER con el nombre de un worker en marcha")
    if _docker("inspect", nombre).returncode != 0:
        pytest.skip(f"no existe el contenedor {nombre}")
    return nombre


def test_el_worker_corre_con_uid_distinto_de_cero(contenedor):
    resultado = _docker("exec", contenedor, "id", "-u")

    assert resultado.returncode == 0, resultado.stderr
    assert int(resultado.stdout.strip()) != 0


def test_la_raiz_del_contenedor_no_es_escribible(contenedor):
    resultado = _docker("exec", contenedor, "sh", "-c", "touch /x")

    assert resultado.returncode != 0


def test_scratch_es_escribible(contenedor):
    resultado = _docker("exec", contenedor, "sh", "-c", "touch /scratch/.prueba && rm /scratch/.prueba")

    assert resultado.returncode == 0, resultado.stderr


def test_docker_inspect_confirma_el_endurecimiento(contenedor):
    resultado = _docker("inspect", contenedor)
    host = json.loads(resultado.stdout)[0]["HostConfig"]

    assert host["ReadonlyRootfs"] is True
    assert host["CapDrop"] == ["ALL"]
    assert not host.get("CapAdd")
    assert "no-new-privileges:true" in host["SecurityOpt"] or "no-new-privileges" in host["SecurityOpt"]
