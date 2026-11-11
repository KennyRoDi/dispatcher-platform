import copy
from pathlib import Path

import pytest
import yaml

from scripts.verificar_workers import (
    incumplimientos_compose,
    incumplimientos_dockerfile,
    main,
)
from tests.unit.test_despliegue_compose import _ejecuta_worker

RAIZ = Path(__file__).resolve().parents[2]
COMPOSES = ["deploy/docker-compose.worker.yml", "deploy/docker-compose.local.yml"]

DOCKERFILE_OK = """FROM python:3.13-slim
RUN useradd --uid 10001 --create-home appuser && mkdir -p /scratch && chown appuser /scratch
USER 10001
ENV WORK_DIR=/scratch
CMD ["python", "-m", "src.workers.worker_node"]
"""

WORKER_OK = {
    "build": {"context": "..", "dockerfile": "Dockerfile.worker"},
    "user": "10001:10001",
    "read_only": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
    "volumes": ["scratch:/scratch"],
    "tmpfs": ["/tmp:size=64m,mode=1777"],
    "environment": {"WORK_DIR": "/scratch"},
}


def _compose_ok() -> dict:
    return {
        "services": {
            "worker": copy.deepcopy(WORKER_OK),
            "redis": {"image": "redis:7-alpine"},
            "minio": {"image": "minio"},
        },
        "volumes": {"scratch": {}},
    }


def _sin(clave: str) -> dict:
    compose = _compose_ok()
    del compose["services"]["worker"][clave]
    return compose


def _con(**cambios) -> dict:
    compose = _compose_ok()
    compose["services"]["worker"].update(cambios)
    return compose


def _compose_real(ruta: str) -> dict:
    return yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))


def test_compose_ejemplo_cumplidor_no_tiene_incumplimientos():
    assert incumplimientos_compose(_compose_ok()) == []


@pytest.mark.parametrize(
    ("compose", "clave"),
    [
        (_sin("user"), "user"),
        (_con(user="0"), "user"),
        (_con(user="root"), "user"),
        (_con(user="appuser"), "user"),
        (_con(user="0:0"), "user"),
        (_sin("read_only"), "read_only"),
        (_con(read_only=False), "read_only"),
        (_sin("cap_drop"), "cap_drop"),
        (_con(cap_drop=["NET_RAW"]), "cap_drop"),
        (_con(cap_add=["NET_ADMIN"]), "cap_add"),
        (_sin("security_opt"), "no-new-privileges"),
        (_con(security_opt=["no-new-privileges:false"]), "no-new-privileges"),
        (_sin("volumes"), "/scratch"),
        (_con(volumes=["scratch:/data"]), "/scratch"),
        (_sin("tmpfs"), "/tmp"),
        (_con(tmpfs=["/tmp"]), "/tmp"),
        (_con(tmpfs=["/scratch:size=64m"]), "/tmp"),
        (_sin("environment"), "WORK_DIR"),
        (_con(environment={"WORK_DIR": "/tmp/mm-worker"}), "WORK_DIR"),
    ],
)
def test_cada_clave_faltante_o_incorrecta_da_un_mensaje_que_la_nombra(compose, clave):
    mensajes = incumplimientos_compose(compose)

    assert len(mensajes) == 1, mensajes
    assert "worker" in mensajes[0] and clave in mensajes[0]


def test_varias_claves_faltantes_dan_un_mensaje_por_incumplimiento():
    compose = _sin("user")
    del compose["services"]["worker"]["read_only"]
    del compose["services"]["worker"]["cap_drop"]

    assert len(incumplimientos_compose(compose)) == 3


def test_cap_drop_all_en_minusculas_o_junto_a_otras_se_acepta():
    compose = _con(cap_drop=["NET_RAW", "ALL"])

    assert incumplimientos_compose(compose) == []


def test_user_numerico_sin_grupo_se_acepta():
    assert incumplimientos_compose(_con(user="10001")) == []


def test_work_dir_en_lista_de_environment_se_lee():
    compose = _con(environment=["WORK_DIR=/scratch", "OTRA=1"])

    assert incumplimientos_compose(compose) == []


def test_servicios_que_no_son_worker_no_se_exigen():
    compose = _compose_ok()
    compose["services"]["coordinator"] = {
        "build": {"dockerfile": "Dockerfile.worker"},
        "command": ["python", "-m", "uvicorn", "src.coordinator.main:app"],
    }
    compose["services"]["reaper"] = {
        "build": {"dockerfile": "Dockerfile.worker"},
        "command": ["python", "-m", "scripts.reaper"],
    }

    assert incumplimientos_compose(compose) == []


def test_un_servicio_worker_sin_comando_con_la_imagen_del_worker_se_exige():
    compose = _compose_ok()
    compose["services"]["extra"] = {"build": {"dockerfile": "Dockerfile.worker"}}

    mensajes = incumplimientos_compose(compose)

    assert mensajes and all("extra" in mensaje for mensaje in mensajes)


def test_dos_servicios_worker_incumplidores_se_reportan_por_separado():
    compose = _compose_ok()
    compose["services"]["worker-gpu"] = {"build": {"dockerfile": "Dockerfile.worker"}}

    mensajes = incumplimientos_compose(compose)

    assert mensajes and all("worker-gpu" in mensaje for mensaje in mensajes)


def test_compose_sin_servicios_worker_se_reporta():
    compose = {"services": {"redis": {"image": "redis:7-alpine"}}}

    assert incumplimientos_compose(compose) != []


@pytest.mark.parametrize("ruta", COMPOSES)
def test_los_compose_del_repo_no_tienen_incumplimientos(ruta):
    assert incumplimientos_compose(_compose_real(ruta)) == []


@pytest.mark.parametrize("ruta", COMPOSES)
def test_todo_servicio_worker_del_repo_monta_scratch_y_endurece(ruta):
    servicios = _compose_real(ruta)["services"]
    workers = {n: s for n, s in servicios.items() if _ejecuta_worker(n, s)}

    assert workers, f"{ruta} no tiene workers"
    for nombre, servicio in workers.items():
        assert servicio.get("read_only") is True, nombre
        assert "ALL" in servicio.get("cap_drop", []), nombre
        assert "cap_add" not in servicio, nombre


def test_el_compose_local_no_endurece_redis_ni_minio():
    servicios = _compose_real("deploy/docker-compose.local.yml")["services"]

    for nombre in ("redis", "minio"):
        assert "read_only" not in servicios[nombre]


def test_dockerfile_cumplidor_no_tiene_incumplimientos():
    assert incumplimientos_dockerfile(DOCKERFILE_OK) == []


def test_dockerfile_del_repo_no_tiene_incumplimientos():
    texto = (RAIZ / "Dockerfile.worker").read_text(encoding="utf-8")

    assert incumplimientos_dockerfile(texto) == []


@pytest.mark.parametrize(
    ("texto", "clave"),
    [
        (DOCKERFILE_OK.replace("USER 10001\n", ""), "USER"),
        (DOCKERFILE_OK.replace("USER 10001", "USER root"), "USER"),
        (DOCKERFILE_OK.replace("USER 10001", "USER 0"), "USER"),
        (DOCKERFILE_OK.replace("USER 10001", "USER appuser"), "USER"),
        (DOCKERFILE_OK.replace("USER 10001", "USER 10002"), "10001"),
        (DOCKERFILE_OK.replace("--uid 10001 ", ""), "10001"),
        (DOCKERFILE_OK.replace("ENV WORK_DIR=/scratch\n", ""), "WORK_DIR"),
        (DOCKERFILE_OK.replace("WORK_DIR=/scratch", "WORK_DIR=/tmp/mm-worker"), "WORK_DIR"),
    ],
)
def test_dockerfile_incumplidor_nombra_la_instruccion(texto, clave):
    mensajes = incumplimientos_dockerfile(texto)

    assert mensajes and any(clave in mensaje for mensaje in mensajes)


def test_dockerfile_usa_la_ultima_instruccion_user():
    texto = DOCKERFILE_OK.replace("USER 10001", "USER 10001\nUSER root")

    assert incumplimientos_dockerfile(texto) != []


def test_cli_sin_incumplimientos_devuelve_cero(tmp_path, capsys):
    compose = tmp_path / "compose.yml"
    compose.write_text(yaml.safe_dump(_compose_ok()), encoding="utf-8")
    dockerfile = tmp_path / "Dockerfile.worker"
    dockerfile.write_text(DOCKERFILE_OK, encoding="utf-8")

    codigo = main(["--compose", str(compose), "--dockerfile", str(dockerfile)])

    assert codigo == 0
    assert capsys.readouterr().err == ""


def test_cli_con_incumplimientos_devuelve_uno_y_los_imprime(tmp_path, capsys):
    compose = tmp_path / "compose.yml"
    compose.write_text(yaml.safe_dump(_sin("read_only")), encoding="utf-8")
    dockerfile = tmp_path / "Dockerfile.worker"
    dockerfile.write_text(DOCKERFILE_OK, encoding="utf-8")

    codigo = main(["--compose", str(compose), "--dockerfile", str(dockerfile)])

    salida = capsys.readouterr()
    assert codigo == 1
    assert "read_only" in salida.out + salida.err


def test_cli_sin_argumentos_verifica_los_archivos_del_repo():
    assert main([]) == 0


def test_cli_con_archivo_inexistente_devuelve_uno(tmp_path):
    assert main(["--compose", str(tmp_path / "no-existe.yml")]) == 1
