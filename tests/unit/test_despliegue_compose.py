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
    assert _entorno(_servicio(nodo_a, "reaper")).get("COORDINATOR_URL") == "https://coordinator:8443"


@pytest.mark.parametrize("variable, valor", [
    ("REDIS_HOST", "redis"),
    ("MINIO_ENDPOINT", "minio:9000"),
])
def test_coordinador_usa_los_servicios_del_compose(nodo_a, variable, valor):
    assert _entorno(_servicio(nodo_a, "coordinator")).get(variable) == valor


@pytest.mark.parametrize("nombre, destino", [
    ("coordinator", "8443"),
    ("redis", "6380"),
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


def _archivos_de_entorno(servicio: dict) -> list:
    archivos = servicio.get("env_file") or []
    return [archivos] if isinstance(archivos, str) else archivos


def test_worker_lee_el_env_de_la_raiz(worker):
    assert _archivos_de_entorno(worker) == ["../.env"]


def test_worker_no_escala_ni_usa_la_red_del_host(worker):
    assert "network_mode" not in worker
    assert "replicas" not in (worker.get("deploy") or {})
    assert "scale" not in worker


def test_worker_no_fija_worker_id(worker):
    assert "WORKER_ID" not in _entorno(worker)


def test_nodo_a_no_usa_la_red_del_host(nodo_a):
    assert [nombre for nombre, servicio in nodo_a.items() if "network_mode" in servicio] == []


def test_coordinador_exige_la_clave_de_redis(nodo_a):
    clave = _entorno(_servicio(nodo_a, "coordinator")).get("REDIS_PASSWORD")
    assert _es_obligatoria(clave, "REDIS_PASSWORD"), clave


def test_coordinador_arranca_la_app_en_todas_las_interfaces_del_contenedor(nodo_a):
    comando = _servicio(nodo_a, "coordinator")["command"]
    assert "src.coordinator.main:app" in comando
    assert (RAIZ / "src/coordinator/main.py").is_file()
    assert comando[comando.index("--host") + 1] == "0.0.0.0"
    assert comando[comando.index("--port") + 1] == "8443"


def test_reaper_usa_el_redis_del_compose_con_su_clave(nodo_a):
    reaper = _servicio(nodo_a, "reaper")
    assert _entorno(reaper).get("REDIS_HOST") == "redis"
    assert _archivos_de_entorno(reaper) == [".env"] or "REDIS_PASSWORD" in _entorno(reaper)


@pytest.mark.parametrize("carpeta", ["src", "scripts"])
def test_imagen_copia_el_codigo(carpeta):
    dockerfile = (RAIZ / "Dockerfile.worker").read_text(encoding="utf-8")
    assert re.search(rf"^COPY\s+{carpeta}\s", dockerfile, re.MULTILINE), f"la imagen no copia {carpeta}"


def test_imagen_arranca_el_worker_por_defecto():
    dockerfile = (RAIZ / "Dockerfile.worker").read_text(encoding="utf-8")
    assert re.search(r'^CMD\s+\[.*"src\.workers\.worker_node"\]', dockerfile, re.MULTILINE)


@pytest.mark.parametrize("variable, valor", [
    ("REDIS_HOST", "<IP_TAILSCALE_NODO_A>"),
    ("COORDINATOR_URL", "https://<IP_TAILSCALE_NODO_A>:8443"),
    ("MINIO_ENDPOINT", "<IP_TAILSCALE_NODO_A>:9000"),
])
def test_env_example_apunta_al_nodo_a_por_tailscale(variable, valor):
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^{variable}={re.escape(valor)}$", ejemplo, re.MULTILINE), f"{variable} no usa el marcador"
