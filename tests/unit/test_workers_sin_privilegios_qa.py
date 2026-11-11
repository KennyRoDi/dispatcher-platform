import copy
from pathlib import Path

import pytest
import yaml

from scripts.verificar_workers import (
    incumplimientos_compose,
    incumplimientos_dockerfile,
    main,
)

RAIZ = Path(__file__).resolve().parents[2]

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


def _compose(**cambios) -> dict:
    worker = copy.deepcopy(WORKER_OK)
    worker.update(cambios)
    return {"services": {"worker": worker}, "volumes": {"scratch": {}}}


def _dockerfile(env: str = "ENV WORK_DIR=/scratch", usuario: str = "USER 10001") -> str:
    return f"FROM python:3.13-slim\nRUN useradd --uid 10001 appuser\n{usuario}\n{env}\n"


def _ejecuta_main(tmp_path, contenido: bytes, capsys) -> tuple[int, str]:
    ruta = tmp_path / "compose.yml"
    ruta.write_bytes(contenido)
    codigo = main(["--compose", str(ruta)])
    return codigo, capsys.readouterr().err


def test_compose_con_raiz_lista_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"- 1\n", capsys)

    assert codigo == 1
    assert "Traceback" not in error


def test_servicio_nulo_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"services:\n  worker:\n", capsys)

    assert codigo == 1
    assert "Traceback" not in error


def test_archivo_no_utf8_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"\xff\xfe", capsys)

    assert codigo == 1
    assert "Traceback" not in error


def test_privileged_se_detecta():
    assert incumplimientos_compose(_compose(privileged=True)) != []


def test_gid_root_se_detecta():
    assert incumplimientos_compose(_compose(user="10001:0")) != []


def test_security_opt_como_cadena_se_detecta():
    assert incumplimientos_compose(_compose(security_opt="no-new-privileges:true")) != []


def test_destino_de_scratch_con_barra_final_se_acepta():
    assert incumplimientos_compose(_compose(volumes=["scratch:/scratch/"])) == []


def test_dockerfile_con_work_dir_entre_comillas_se_acepta():
    assert incumplimientos_dockerfile(_dockerfile('ENV WORK_DIR="/scratch"')) == []


def test_dockerfile_con_work_dir_en_linea_de_continuacion_se_acepta():
    env = "ENV PYTHONUNBUFFERED=1 \\\n    WORK_DIR=/scratch"

    assert incumplimientos_dockerfile(_dockerfile(env)) == []


def test_dockerfile_con_env_sin_igual_se_acepta():
    assert incumplimientos_dockerfile(_dockerfile("ENV WORK_DIR /scratch")) == []


def test_dockerfile_con_work_dir_redefinido_se_detecta():
    env = "ENV WORK_DIR=/scratch\nENV WORK_DIR=/tmp"

    assert incumplimientos_dockerfile(_dockerfile(env)) != []


def test_dockerfile_multietapa_con_etapa_final_sin_user_se_detecta():
    texto = _dockerfile() + "FROM python:3.13-slim\nCOPY --from=0 /app /app\n"

    assert incumplimientos_dockerfile(texto) != []


def test_useradd_solo_en_comentario_se_detecta():
    texto = "FROM x\n# RUN useradd --uid 10001 appuser\nUSER 10001\nENV WORK_DIR=/scratch\n"

    assert incumplimientos_dockerfile(texto) != []


def test_user_con_arg_resuelto_a_10001_se_acepta():
    texto = _dockerfile(usuario="USER ${APP_UID}").replace("FROM", "ARG APP_UID=10001\nFROM", 1)

    assert incumplimientos_dockerfile(texto) == []


def _replicas(servicio: dict) -> int:
    return int((servicio.get("deploy") or {}).get("replicas", 1))


def test_replicas_no_comparten_el_mismo_scratch():
    compose = yaml.safe_load((RAIZ / "deploy/docker-compose.local.yml").read_text(encoding="utf-8"))
    for nombre, servicio in compose["services"].items():
        if _replicas(servicio) <= 1:
            continue
        origenes = [str(v).split(":")[0] for v in servicio.get("volumes") or [] if str(v).split(":")[1] == "/scratch"]
        assert origenes == [], f"{nombre}: {_replicas(servicio)} replicas comparten el volumen {origenes}"
