import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]

_PUERTO_CORTO = re.compile(
    r"(?:(?P<ip>\$\{[^}]*\}|\d+\.\d+\.\d+\.\d+|\[[^\]]*\]):)?"
    r"(?:[^:]+:)?"
    r"(?P<destino>[^:/]+)(?:/\w+)?"
)


def _servicios(ruta: str) -> dict:
    return yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))["services"]


@pytest.fixture
def worker() -> dict:
    return _servicios("deploy/docker-compose.worker.yml")["worker"]


@pytest.fixture
def nodo_a() -> dict:
    return _servicios("docker-compose.yml")


def _servicio(servicios: dict, nombre: str) -> dict:
    assert nombre in servicios, f"falta el servicio {nombre}; hay {sorted(servicios)}"
    return servicios[nombre]


def _entorno(servicio: dict) -> dict:
    entorno = servicio.get("environment") or {}
    if isinstance(entorno, dict):
        return entorno
    return dict(entrada.partition("=")[::2] for entrada in entorno)


def _es_obligatoria(valor, variable: str) -> bool:
    return re.fullmatch(rf"\$\{{{variable}:\?[^}}]*\}}", str(valor)) is not None


def _publicaciones(servicio: dict) -> list[tuple[str | None, str]]:
    publicaciones = []
    for puerto in servicio.get("ports") or []:
        if isinstance(puerto, dict):
            publicaciones.append((puerto.get("host_ip"), str(puerto["target"])))
            continue
        corto = _PUERTO_CORTO.fullmatch(str(puerto))
        assert corto, f"puerto no reconocido: {puerto}"
        publicaciones.append((corto["ip"], corto["destino"]))
    return publicaciones


def _ejecuta_worker(nombre: str, servicio: dict) -> bool:
    comando = servicio.get("command")
    texto = " ".join(comando) if isinstance(comando, list) else str(comando or "")
    # Dockerfile.worker arranca el worker por defecto: sin `command` el servicio es un worker.
    hereda_cmd = "Dockerfile.worker" in str(servicio.get("build")) and not comando
    return "worker" in nombre.lower() or "worker_node" in texto or hereda_cmd


def _instrucciones(nombre: str) -> list[str]:
    dockerfile = (RAIZ / "Dockerfile.worker").read_text(encoding="utf-8")
    return re.findall(rf"^\s*{nombre}\s+(\S+)", dockerfile, re.MULTILINE | re.IGNORECASE)


def test_worker_exige_hostname_desde_node_name(worker):
    assert _es_obligatoria(worker.get("hostname"), "NODE_NAME"), worker.get("hostname")


def test_worker_exige_node_ip(worker):
    node_ip = _entorno(worker).get("NODE_IP")
    assert _es_obligatoria(node_ip, "NODE_IP"), node_ip


@pytest.mark.parametrize("nombre", ["coordinator", "redis", "minio", "reaper"])
def test_nodo_a_levanta_el_servicio(nodo_a, nombre):
    _servicio(nodo_a, nombre)


def test_nodo_a_no_ejecuta_workers(nodo_a):
    workers = [nombre for nombre, servicio in nodo_a.items() if _ejecuta_worker(nombre, servicio)]
    assert workers == []


def test_reaper_apunta_al_coordinador_del_compose(nodo_a):
    assert _entorno(_servicio(nodo_a, "reaper")).get("COORDINATOR_URL") == "http://coordinator:8000"


@pytest.mark.parametrize("variable, valor", [
    ("REDIS_HOST", "redis"),
    ("MINIO_ENDPOINT", "minio:9000"),
])
def test_coordinador_usa_los_servicios_del_compose(nodo_a, variable, valor):
    assert _entorno(_servicio(nodo_a, "coordinator")).get(variable) == valor


@pytest.mark.parametrize("nombre, destino", [
    ("coordinator", "8000"),
    ("redis", "6379"),
    ("minio", "9000"),
])
def test_nodo_a_publica_el_puerto_en_node_ip(nodo_a, nombre, destino):
    publicaciones = _publicaciones(_servicio(nodo_a, nombre))
    interfaces = [ip for ip, puerto in publicaciones if puerto == destino]
    assert interfaces, f"{nombre} no publica {destino}: {publicaciones}"
    assert all(_es_obligatoria(ip, "NODE_IP") for ip in interfaces), interfaces


def test_nodo_a_no_publica_nada_fuera_de_node_ip(nodo_a):
    expuestos = [
        (nombre, puerto)
        for nombre, servicio in nodo_a.items()
        for ip, puerto in _publicaciones(servicio)
        if not _es_obligatoria(ip, "NODE_IP")
    ]
    assert expuestos == []


def test_imagen_usa_python_313():
    imagen = _instrucciones("FROM")[-1]
    assert re.fullmatch(r"python:3\.13(?:[.-].*)?", imagen), imagen


def test_imagen_no_corre_como_root():
    usuarios = _instrucciones("USER")
    assert usuarios, "Dockerfile.worker no declara USER"
    assert usuarios[-1].partition(":")[0] not in {"root", "0"}


@pytest.mark.parametrize("variable", ["NODE_IP", "NODE_NAME"])
def test_env_example_define_la_identidad_del_nodo(variable):
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^{variable}=", ejemplo, re.MULTILINE), f"{variable} sin definir"
