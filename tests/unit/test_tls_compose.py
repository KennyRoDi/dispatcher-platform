import re
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CERTS = re.compile(r"\$\{CERTS_DIR(?::[?-][^}]*)?\}")
PEM_CON_CUERPO = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s+[A-Za-z0-9+/=]{20,}")


def _compose(ruta: str) -> dict:
    return yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))["services"]


def _servicio(servicios: dict, nombre: str) -> dict:
    assert nombre in servicios, f"falta el servicio {nombre}; hay {sorted(servicios)}"
    return servicios[nombre]


def _entorno(servicio: dict) -> dict:
    entorno = servicio.get("environment") or {}
    if isinstance(entorno, dict):
        return {clave: str(valor) for clave, valor in entorno.items()}
    return dict(entrada.partition("=")[::2] for entrada in entorno)


def _comando(servicio: dict) -> str:
    comando = servicio.get("command")
    return " ".join(map(str, comando)) if isinstance(comando, list) else str(comando or "")


def _prueba_salud(servicio: dict) -> str:
    prueba = servicio["healthcheck"]["test"]
    return " ".join(map(str, prueba)) if isinstance(prueba, list) else str(prueba)


def _volumenes(servicio: dict) -> list[tuple[str, str, bool]]:
    montajes = []
    for volumen in servicio.get("volumes") or []:
        assert isinstance(volumen, str), f"se espera la forma corta origen:destino[:ro]: {volumen}"
        partes = re.split(r":(?![^{]*\})", volumen)  # los dos puntos de ${VAR:?msg} no separan
        montajes.append((partes[0], partes[1], partes[-1] == "ro"))
    return montajes


def _desde_certs(servicio: dict) -> list[tuple[str, str, bool]]:
    return [montaje for montaje in _volumenes(servicio) if CERTS.search(montaje[0])]


def _puertos_publicados(servicio: dict) -> set[str]:
    return {str(puerto).split(":")[-1].partition("/")[0] for puerto in servicio.get("ports") or []}


def _valor_de(comando: str, bandera: str) -> str:
    coincidencia = re.search(rf"{re.escape(bandera)}[ =](\S+)", comando)
    assert coincidencia, f"falta {bandera} en: {comando}"
    return coincidencia[1]


def _bajo_un_montaje(ruta: str, servicio: dict) -> bool:
    destinos = [destino for _, destino, _ in _desde_certs(servicio)]
    return any(ruta == destino or ruta.startswith(destino.rstrip("/") + "/") for destino in destinos)


@pytest.fixture
def nodo_a() -> dict:
    return _compose("docker-compose.yml")


@pytest.fixture
def worker() -> dict:
    return _compose("deploy/docker-compose.worker.yml")["worker"]


@pytest.fixture
def local() -> dict:
    return _compose("deploy/docker-compose.local.yml")


def test_coordinador_sirve_https_en_8443_con_certificado_y_llave(nodo_a):
    coordinador = _servicio(nodo_a, "coordinator")
    comando = _comando(coordinador)
    assert _valor_de(comando, "--port") == "8443"
    for bandera in ("--ssl-certfile", "--ssl-keyfile"):
        assert _bajo_un_montaje(_valor_de(comando, bandera), coordinador), f"{bandera} fuera de los montajes de CERTS_DIR"


def test_coordinador_publica_8443_y_no_el_8000(nodo_a):
    puertos = _puertos_publicados(_servicio(nodo_a, "coordinator"))
    assert "8443" in puertos
    assert "8000" not in puertos


def test_coordinador_healthcheck_por_https(nodo_a):
    prueba = _prueba_salud(_servicio(nodo_a, "coordinator"))
    assert "https://" in prueba and "http://" not in prueba, prueba


def test_coordinador_cliente_usa_tls_hacia_redis_y_minio(nodo_a):
    entorno = _entorno(_servicio(nodo_a, "coordinator"))
    assert entorno.get("REDIS_PORT") == "6380"
    assert entorno.get("MINIO_SECURE", "").lower() == "true"
    assert entorno.get("TLS_ENABLED", "true").lower() == "true"
    assert _bajo_un_montaje(entorno.get("TLS_CA_FILE", ""), _servicio(nodo_a, "coordinator"))


def test_reaper_habla_https_y_rediss_con_la_ca(nodo_a):
    reaper = _servicio(nodo_a, "reaper")
    entorno = _entorno(reaper)
    assert entorno.get("COORDINATOR_URL") == "https://coordinator:8443"
    assert entorno.get("REDIS_PORT") == "6380"
    assert entorno.get("TLS_ENABLED", "true").lower() == "true"
    assert _bajo_un_montaje(entorno.get("TLS_CA_FILE", ""), reaper)


def test_redis_solo_escucha_en_tls_y_cierra_el_puerto_en_claro(nodo_a):
    comando = _comando(_servicio(nodo_a, "redis"))
    assert _valor_de(comando, "--tls-port") == "6380"
    assert _valor_de(comando, "--port") == "0"
    assert "--requirepass" in comando


def test_redis_usa_certificado_llave_y_ca_montados(nodo_a):
    redis = _servicio(nodo_a, "redis")
    comando = _comando(redis)
    for bandera in ("--tls-cert-file", "--tls-key-file", "--tls-ca-cert-file"):
        assert _bajo_un_montaje(_valor_de(comando, bandera), redis), f"{bandera} fuera de los montajes de CERTS_DIR"


def test_redis_exige_tls13_sin_certificado_de_cliente(nodo_a):
    comando = _comando(_servicio(nodo_a, "redis"))
    assert _valor_de(comando, "--tls-protocols").strip("\"'") == "TLSv1.3"
    assert _valor_de(comando, "--tls-auth-clients") == "no"


def test_redis_publica_6380_y_no_el_6379(nodo_a):
    puertos = _puertos_publicados(_servicio(nodo_a, "redis"))
    assert "6380" in puertos
    assert "6379" not in puertos


def test_redis_healthcheck_usa_tls_con_la_ca(nodo_a):
    prueba = _prueba_salud(_servicio(nodo_a, "redis"))
    assert "--tls" in prueba and "--cacert" in prueba, prueba
    assert "-p 6380" in prueba or "--port 6380" in prueba, prueba


def test_minio_lee_sus_certificados_del_directorio_de_certificados(nodo_a):
    minio = _servicio(nodo_a, "minio")
    montajes = _desde_certs(minio)
    assert montajes, "minio no monta certificados desde CERTS_DIR"
    destino = montajes[0][1]
    comando = _comando(minio)
    # Directorio por defecto de MinIO para el usuario root; con --certs-dir sirve cualquiera.
    assert destino.rstrip("/").endswith("/.minio/certs") or _valor_de(comando, "--certs-dir") == destino.rstrip("/")


def test_minio_certificados_en_solo_lectura(nodo_a):
    assert all(solo_lectura for _, _, solo_lectura in _desde_certs(_servicio(nodo_a, "minio")))


def test_minio_healthcheck_no_usa_http_en_claro(nodo_a):
    prueba = _prueba_salud(_servicio(nodo_a, "minio"))
    assert "http://" not in prueba, prueba
    assert "--insecure" in prueba or "https://" in prueba, prueba


def test_minio_publica_9000_en_node_ip(nodo_a):
    puertos = [str(puerto) for puerto in _servicio(nodo_a, "minio")["ports"]]
    assert any(re.fullmatch(r"\$\{NODE_IP[^}]*\}:9000:9000", puerto) for puerto in puertos), puertos


def test_servidores_montan_certificados_de_solo_lectura_desde_certs_dir(nodo_a):
    for nombre in ("coordinator", "redis", "minio", "reaper"):
        montajes = _desde_certs(_servicio(nodo_a, nombre))
        assert montajes, f"{nombre} no monta nada desde CERTS_DIR"
        assert all(solo_lectura for _, _, solo_lectura in montajes), f"{nombre}: montaje de certificados sin :ro"


def test_certs_dir_es_obligatorio_y_no_apunta_al_repo(nodo_a):
    for servicio in nodo_a.values():
        for origen, _, _ in _desde_certs(servicio):
            assert re.match(r"\$\{CERTS_DIR:\?[^}]+\}", origen), f"CERTS_DIR debe ser obligatoria: {origen}"
            assert not origen.startswith(("./", "../")), origen


def test_nadie_monta_el_directorio_completo_ni_la_llave_de_la_ca(nodo_a):
    for nombre, servicio in nodo_a.items():
        for origen, _, _ in _desde_certs(servicio):
            resto = CERTS.sub("", origen)
            assert resto.startswith("/") and len(resto) > 1, f"{nombre} monta todo CERTS_DIR (incluye ca.key)"
            assert "ca.key" not in origen, f"{nombre} monta la llave de la CA"


def test_el_nodo_a_no_activa_modo_en_claro(nodo_a):
    for nombre, servicio in nodo_a.items():
        assert _entorno(servicio).get("TLS_ENABLED", "true").lower() not in {"0", "false", "no", "off"}, nombre


def test_worker_activa_tls_y_apunta_a_la_ca_montada(worker):
    entorno = _entorno(worker)
    assert re.fullmatch(r"true|\$\{TLS_ENABLED(:-true)?\}", entorno.get("TLS_ENABLED", "true"))
    ca = entorno.get("TLS_CA_FILE", "")
    assert ca.endswith("ca.pem"), ca
    assert [montaje for montaje in _volumenes(worker) if montaje[1] == ca], f"nada monta {ca}"


def test_worker_monta_la_ca_en_solo_lectura(worker):
    ca = _entorno(worker)["TLS_CA_FILE"]
    assert all(solo_lectura for _, destino, solo_lectura in _volumenes(worker) if destino == ca)


def test_worker_no_recibe_llaves_ni_el_directorio_de_certificados(worker):
    for origen, destino, _ in _volumenes(worker):
        assert not CERTS.search(origen) or CERTS.sub("", origen).startswith("/"), f"monta todo CERTS_DIR: {origen}"
        assert not re.search(r"\.key\b|private|server\.pem|ca\.key", origen + destino), f"el worker recibe una llave: {origen}"


def test_compose_local_apaga_tls_explicitamente_con_servicios_en_claro(local):
    for nombre in ("coordinator", "reaper", "worker"):
        entorno = _entorno(_servicio(local, nombre))
        assert entorno.get("TLS_ENABLED") == "false", f"{nombre} sin TLS_ENABLED=false"


def test_compose_local_conserva_redis_y_coordinador_en_claro(local):
    assert "--tls-port" not in _comando(_servicio(local, "redis"))
    assert "http://" in _prueba_salud(_servicio(local, "coordinator"))


@pytest.mark.parametrize("variable", ["TLS_ENABLED", "TLS_CA_FILE", "CERTS_DIR"])
def test_env_example_documenta_la_variable_de_tls(variable):
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^#?\s*{variable}=", ejemplo, re.MULTILINE), f"{variable} sin documentar"


def test_env_example_no_trae_material_secreto_de_tls():
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert not PEM_CON_CUERPO.search(ejemplo)
    for variable in ("TLS_CA_FILE", "CERTS_DIR"):
        valor = re.search(rf"^#?\s*{variable}=(.*)$", ejemplo, re.MULTILINE)[1].strip()
        assert not valor or valor.startswith(("<", "/", "~", "$")), f"{variable}={valor}"


def test_env_example_apunta_por_defecto_a_servicios_cifrados():
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^COORDINATOR_URL=https://", ejemplo, re.MULTILINE)
    assert re.search(r"^MINIO_SECURE=true\s*$", ejemplo, re.MULTILINE)
    assert re.search(r"^REDIS_PORT=6380\s*$", ejemplo, re.MULTILINE)
    assert not re.search(r"^TLS_ENABLED=(0|false|no|off)\s*$", ejemplo, re.MULTILINE | re.IGNORECASE)


def _git(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("ruta", [
    "ca.pem", "ca.key", "server.pem", "server.key", "public.crt", "private.key",
    "certs/ca.pem", ".ms-certs/ca.key", "deploy/tls/server.key",
])
def test_gitignore_cubre_certs(ruta):
    ignorado = _git("check-ignore", "-q", "--no-index", ruta)
    assert ignorado.returncode == 0, f"{ruta} no está en .gitignore"


def test_repo_sin_llaves_ni_certificados():
    rastreados = _git("ls-files", "-z").stdout.split("\0")
    nombres = [ruta for ruta in rastreados if re.search(r"\.(pem|key|crt|p12|pfx)$", ruta, re.IGNORECASE)]
    assert nombres == [], f"material criptográfico rastreado: {nombres}"
    con_llave = []
    for ruta in filter(None, rastreados):
        archivo = RAIZ / ruta
        if archivo.is_file() and PEM_CON_CUERPO.search(archivo.read_text(encoding="utf-8", errors="ignore")):
            con_llave.append(ruta)
    assert con_llave == [], f"llave privada en el historial de trabajo: {con_llave}"


def test_worker_no_exige_tls_ca_file_para_arrancar_sin_tls(worker):
    origenes = [origen for origen, destino, _ in _volumenes(worker) if destino == _entorno(worker)["TLS_CA_FILE"]]
    assert origenes and all("TLS_CA_FILE:?" not in origen for origen in origenes), origenes
    assert all("TLS_CA_FILE:-" in origen for origen in origenes), origenes


def test_redis_con_uid_propio_recibe_un_volumen_de_datos_escribible(nodo_a):
    redis = _servicio(nodo_a, "redis")
    iniciadores = [
        nombre for nombre, condicion in (redis.get("depends_on") or {}).items()
        if condicion.get("condition") == "service_completed_successfully"
    ]
    assert iniciadores, "redis corre con CERTS_UID y la imagen deja /data de otro usuario: nadie lo ajusta"
    for nombre in iniciadores:
        iniciador = _servicio(nodo_a, nombre)
        assert str(iniciador.get("user")) == "0"
        assert ("redis-data", "/data", False) in _volumenes(iniciador)
        comando = _comando(iniciador)
        assert "chown" in comando and "${CERTS_UID" in comando and "${CERTS_GID" in comando, comando


def test_minio_healthcheck_apunta_el_alias_a_https_y_usa_un_config_escribible(nodo_a):
    prueba = _prueba_salud(_servicio(nodo_a, "minio"))
    assert "MC_HOST_local=https://localhost:9000" in prueba, "el alias local de mc es http: nunca ve el servidor TLS"
    assert "--config-dir /tmp/" in prueba, "con UID propio mc no puede crear /.mc"
