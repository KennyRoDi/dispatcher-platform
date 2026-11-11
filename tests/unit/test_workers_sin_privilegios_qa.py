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


@pytest.mark.xfail(strict=True, reason="main solo atrapa OSError y YAMLError: un YAML cuya raiz es una lista da AttributeError con traza")
def test_compose_con_raiz_lista_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"- 1\n", capsys)

    assert codigo == 1
    assert "Traceback" not in error


@pytest.mark.xfail(strict=True, reason="un servicio vacio (`worker:` sin valor) da AttributeError en _es_worker con traza")
def test_servicio_nulo_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"services:\n  worker:\n", capsys)

    assert codigo == 1
    assert "Traceback" not in error


@pytest.mark.xfail(strict=True, reason="UnicodeDecodeError es ValueError, no OSError: un archivo no UTF-8 sale con traza")
def test_archivo_no_utf8_da_un_mensaje_y_codigo_1(tmp_path, capsys):
    codigo, error = _ejecuta_main(tmp_path, b"\xff\xfe", capsys)

    assert codigo == 1
    assert "Traceback" not in error


@pytest.mark.xfail(strict=True, reason="privileged: true anula cap_drop y read_only y el verificador no lo mira")
def test_privileged_se_detecta():
    assert incumplimientos_compose(_compose(privileged=True)) != []


@pytest.mark.xfail(strict=True, reason="user 10001:0 pasa: el GID 0 deja al proceso en el grupo root")
def test_gid_root_se_detecta():
    assert incumplimientos_compose(_compose(user="10001:0")) != []


@pytest.mark.xfail(strict=True, reason="falso negativo: security_opt como str se acepta por subcadena, Compose lo rechaza (debe ser lista)")
def test_security_opt_como_cadena_se_detecta():
    assert incumplimientos_compose(_compose(security_opt="no-new-privileges:true")) != []


@pytest.mark.xfail(strict=True, reason="falso positivo: el destino '/scratch/' con barra final no se reconoce como /scratch")
def test_destino_de_scratch_con_barra_final_se_acepta():
    assert incumplimientos_compose(_compose(volumes=["scratch:/scratch/"])) == []


@pytest.mark.xfail(strict=True, reason="falso positivo: ENV WORK_DIR=\"/scratch\" (comillas validas) se rechaza")
def test_dockerfile_con_work_dir_entre_comillas_se_acepta():
    assert incumplimientos_dockerfile(_dockerfile('ENV WORK_DIR="/scratch"')) == []


@pytest.mark.xfail(strict=True, reason="falso positivo: ENV con WORK_DIR en una linea de continuacion (como PYTHONUNBUFFERED hoy) se rechaza")
def test_dockerfile_con_work_dir_en_linea_de_continuacion_se_acepta():
    env = "ENV PYTHONUNBUFFERED=1 \\\n    WORK_DIR=/scratch"

    assert incumplimientos_dockerfile(_dockerfile(env)) == []


@pytest.mark.xfail(strict=True, reason="falso positivo: la forma antigua `ENV WORK_DIR /scratch` se rechaza")
def test_dockerfile_con_env_sin_igual_se_acepta():
    assert incumplimientos_dockerfile(_dockerfile("ENV WORK_DIR /scratch")) == []


@pytest.mark.xfail(strict=True, reason="falso negativo: un segundo ENV WORK_DIR=/tmp posterior sigue pasando")
def test_dockerfile_con_work_dir_redefinido_se_detecta():
    env = "ENV WORK_DIR=/scratch\nENV WORK_DIR=/tmp"

    assert incumplimientos_dockerfile(_dockerfile(env)) != []


@pytest.mark.xfail(strict=True, reason="falso negativo: una etapa final sin USER corre como root y se mira el USER de una etapa anterior")
def test_dockerfile_multietapa_con_etapa_final_sin_user_se_detecta():
    texto = _dockerfile() + "FROM python:3.13-slim\nCOPY --from=0 /app /app\n"

    assert incumplimientos_dockerfile(texto) != []


@pytest.mark.xfail(strict=True, reason="falso negativo: `useradd --uid 10001` en un comentario cuenta como fijar el UID")
def test_useradd_solo_en_comentario_se_detecta():
    texto = "FROM x\n# RUN useradd --uid 10001 appuser\nUSER 10001\nENV WORK_DIR=/scratch\n"

    assert incumplimientos_dockerfile(texto) != []


@pytest.mark.xfail(strict=True, reason="falso positivo: USER ${UID} con ARG se rechaza aunque resuelva a 10001")
def test_user_con_arg_resuelto_a_10001_se_acepta():
    texto = _dockerfile(usuario="USER ${APP_UID}").replace("FROM", "ARG APP_UID=10001\nFROM", 1)

    assert incumplimientos_dockerfile(texto) == []


def _replicas(servicio: dict) -> int:
    return int((servicio.get("deploy") or {}).get("replicas", 1))


@pytest.mark.xfail(strict=True, reason=(
    "docker-compose.local.yml: 3 replicas montan el mismo volumen scratch en /scratch y "
    "WorkerNode._borrar_temporales_huerfanos (worker_node.py:125-128) borra TODO WORK_DIR al arrancar: "
    "una replica que reinicia destruye los in/out de las subtareas en curso de las otras"
))
def test_replicas_no_comparten_el_mismo_scratch():
    compose = yaml.safe_load((RAIZ / "deploy/docker-compose.local.yml").read_text(encoding="utf-8"))
    for nombre, servicio in compose["services"].items():
        if _replicas(servicio) <= 1:
            continue
        origenes = [str(v).split(":")[0] for v in servicio.get("volumes") or [] if str(v).split(":")[1] == "/scratch"]
        assert origenes == [], f"{nombre}: {_replicas(servicio)} replicas comparten el volumen {origenes}"
