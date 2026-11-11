"""QA de la parte 3 de F-27: intentos de romper generar_certs.sh y los Compose con TLS.

Los xfail(strict=True) fijaron defectos reproducidos; ya corregidos, sus marcas se quitaron.
Los demás son guardas de lo que no se logró romper.
"""

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "deploy" / "tls" / "generar_certs.sh"
COMPOSES = ["docker-compose.yml", "deploy/docker-compose.worker.yml", "deploy/docker-compose.local.yml", "deploy/docker-compose.demo.yml"]

necesita_openssl = pytest.mark.skipif(
    shutil.which("openssl") is None or os.name == "nt",
    reason="requiere openssl y un bash POSIX; en Windows bash es el lanzador de WSL",
)


def _generar(entorno: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    (tmp_path / "home").mkdir(exist_ok=True)
    base = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home")}
    return subprocess.run(
        ["bash", str(SCRIPT)], env={**base, **entorno}, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=60
    )


def _openssl(*argumentos: str) -> str:
    resultado = subprocess.run(["openssl", *argumentos], capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def _fin(certificado: Path) -> datetime:
    linea = _openssl("x509", "-in", str(certificado), "-noout", "-enddate").strip().split("=", 1)[1]
    return datetime.strptime(linea, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def _clave_publica(ruta: Path, certificado: bool) -> str:
    if certificado:
        return _openssl("x509", "-in", str(ruta), "-noout", "-pubkey")
    return _openssl("pkey", "-in", str(ruta), "-pubout")


def _servicios(ruta: str) -> dict:
    return yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))["services"]


# --- generar_certs.sh ---------------------------------------------------------------------------


@necesita_openssl
@pytest.mark.parametrize("ip", ["10.0.0.1; touch pwn", "1.2.3.4\nDNS:evil.com", "", "1.2.3.4 5.6.7.8", "$(id)"])
def test_node_ip_con_inyeccion_o_basura_se_rechaza_sin_crear_nada(tmp_path, ip):
    destino = tmp_path / "certs"
    resultado = _generar({"NODE_IP": ip, "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path)
    assert resultado.returncode != 0
    assert not destino.exists()
    assert not (tmp_path / "pwn").exists()


@necesita_openssl
@pytest.mark.parametrize("nombre", ["a b", "a;b", "a\nDNS:evil", "$(id)", "a_b", "ñ"])
def test_node_name_con_caracteres_raros_se_rechaza_sin_crear_nada(tmp_path, nombre):
    destino = tmp_path / "certs"
    resultado = _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": nombre, "CERTS_DIR": str(destino)}, tmp_path)
    assert resultado.returncode != 0
    assert not destino.exists()


@necesita_openssl
def test_ipv6_valida_se_acepta_y_entra_en_el_san(tmp_path):
    destino = tmp_path / "certs"
    resultado = _generar({"NODE_IP": "fd7a:115c::1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert "FD7A:115C:0:0:0:0:0:1" in _openssl("x509", "-in", str(destino / "server.pem"), "-noout", "-ext", "subjectAltName")


@necesita_openssl
def test_el_script_funciona_con_certs_dir_con_espacios_y_umask_laxa(tmp_path):
    destino = tmp_path / "con espacios"
    anterior = os.umask(0o000)
    try:
        resultado = _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path)
    finally:
        os.umask(anterior)
    assert resultado.returncode == 0, resultado.stderr
    for relativo in ["ca.key", "server.key", "minio/private.key", "ca.srl"]:
        assert (destino / relativo).stat().st_mode & 0o077 == 0, relativo
    assert destino.stat().st_mode & 0o077 == 0


@necesita_openssl
def test_el_certificado_de_servidor_no_es_de_ca_y_tiene_eku_y_vigencia(tmp_path):
    destino = tmp_path / "certs"
    assert _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path).returncode == 0
    ext = _openssl("x509", "-in", str(destino / "server.pem"), "-noout", "-ext", "extendedKeyUsage,basicConstraints")
    assert "TLS Web Server Authentication" in ext and "CA:FALSE" in ext
    assert "TLS Web Client Authentication" not in ext
    assert _fin(destino / "server.pem") <= _fin(destino / "ca.pem")


@necesita_openssl
def test_segunda_ejecucion_reutiliza_la_ca_y_cambia_la_llave_del_servidor(tmp_path):
    destino = tmp_path / "certs"
    entorno = {"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}
    assert _generar(entorno, tmp_path).returncode == 0
    ca = (destino / "ca.pem").read_bytes(), (destino / "ca.key").read_bytes()
    assert _generar({**entorno, "NODE_IP": "10.0.0.2"}, tmp_path).returncode == 0
    assert ((destino / "ca.pem").read_bytes(), (destino / "ca.key").read_bytes()) == ca
    assert "10.0.0.2" in _openssl("x509", "-in", str(destino / "server.pem"), "-noout", "-ext", "subjectAltName")
    _openssl("verify", "-CAfile", str(destino / "ca.pem"), str(destino / "server.pem"))


@necesita_openssl
def test_un_fallo_a_mitad_no_deja_llave_y_certificado_desparejados(tmp_path):
    destino = tmp_path / "certs"
    entorno = {"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}
    assert _generar(entorno, tmp_path).returncode == 0
    assert _generar({**entorno, "NODE_IP": "deadbeef"}, tmp_path).returncode != 0
    assert _clave_publica(destino / "server.pem", True) == _clave_publica(destino / "server.key", False)
    assert not (destino / "server.csr").exists()


@necesita_openssl
@pytest.mark.parametrize("ip", ["deadbeef", "...", "1.2.3", "::::", "1.2.3.4.5"])
def test_ip_invalida_se_rechaza_antes_de_crear_nada(tmp_path, ip):
    destino = tmp_path / "certs"
    resultado = _generar({"NODE_IP": ip, "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path)
    assert resultado.returncode != 0
    assert not destino.exists()


@necesita_openssl
def test_la_ca_no_puede_firmar_otras_ca(tmp_path):
    destino = tmp_path / "certs"
    assert _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path).returncode == 0
    restricciones = _openssl("x509", "-in", str(destino / "ca.pem"), "-noout", "-ext", "basicConstraints")
    assert re.search(r"pathlen:\s*0", restricciones, re.IGNORECASE), restricciones


@necesita_openssl
def test_una_ca_por_vencer_no_deja_un_certificado_que_la_sobrevive(tmp_path):
    destino = tmp_path / "certs"
    (destino / "minio").mkdir(parents=True)
    _openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", str(destino / "ca.key"))
    _openssl("req", "-x509", "-new", "-key", str(destino / "ca.key"), "-sha256", "-days", "10", "-subj", "/CN=vieja",
             "-out", str(destino / "ca.pem"), "-addext", "basicConstraints=critical,CA:TRUE")
    assert _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path).returncode == 0
    assert _fin(destino / "server.pem") <= _fin(destino / "ca.pem")


@necesita_openssl
@pytest.mark.parametrize("nombre", [".", "..", "-x"])
def test_node_name_que_no_es_un_nombre_de_host_se_rechaza(tmp_path, nombre):
    destino = tmp_path / "certs"
    resultado = _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": nombre, "CERTS_DIR": str(destino)}, tmp_path)
    assert resultado.returncode != 0


@necesita_openssl
def test_certs_dir_dentro_del_repo_se_rechaza(tmp_path):
    destino = RAIZ / "zz_qa_certs_tmp"
    try:
        resultado = _generar({"NODE_IP": "10.0.0.1", "NODE_NAME": "nodo", "CERTS_DIR": str(destino)}, tmp_path)
        assert resultado.returncode != 0
        assert not destino.exists()
    finally:
        shutil.rmtree(destino, ignore_errors=True)


# --- Compose ------------------------------------------------------------------------------------


def _montajes(servicio: dict) -> list[str]:
    return [str(volumen) for volumen in servicio.get("volumes") or []]


@pytest.mark.parametrize("ruta", COMPOSES)
def test_ningun_compose_monta_la_llave_de_la_ca(ruta):
    for nombre, servicio in _servicios(ruta).items():
        assert not any("ca.key" in montaje for montaje in _montajes(servicio)), f"{ruta}:{nombre}"


def test_el_nodo_a_publica_solo_en_node_ip_y_nunca_en_claro():
    for nombre, servicio in _servicios("docker-compose.yml").items():
        for puerto in servicio.get("ports") or []:
            texto = str(puerto)
            assert texto.startswith("${NODE_IP:?"), f"{nombre} publica {texto} fuera de NODE_IP"
            assert texto.rsplit(":", 1)[-1] not in {"6379", "8000"}, f"{nombre} publica {texto} en claro"


def test_los_workers_montan_solo_la_ca_en_solo_lectura():
    montajes = [m for m in _montajes(_servicios("deploy/docker-compose.worker.yml")["worker"]) if not m.startswith("scratch:")]
    assert len(montajes) == 1 and montajes[0].endswith(":/certs/ca.pem:ro")
    assert not any(".key" in montaje or "CERTS_DIR" in montaje for montaje in montajes)


def test_todo_montaje_de_certificados_del_nodo_a_es_de_solo_lectura():
    for nombre, servicio in _servicios("docker-compose.yml").items():
        for montaje in _montajes(servicio):
            if "CERTS_DIR" in montaje:
                assert montaje.endswith(":ro"), f"{nombre}: {montaje}"


def test_insecure_solo_aparece_en_el_healthcheck_de_minio_hacia_localhost():
    for nombre, servicio in _servicios("docker-compose.yml").items():
        texto = yaml.safe_dump(servicio)
        if "--insecure" in texto or "verify=False" in texto or "CERT_NONE" in texto:
            assert nombre == "minio"
            prueba = " ".join(map(str, servicio["healthcheck"]["test"]))
            assert "--insecure" in prueba
            assert " ready local " in prueba and "https://localhost:9000" in prueba


def test_env_example_no_trae_secretos_ni_certificados():
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert "BEGIN" not in texto and "PRIVATE KEY" not in texto
    assert re.search(r"^REDIS_PASSWORD=$", texto, re.MULTILINE)
    assert re.search(r"^# CERTS_DIR=", texto, re.MULTILINE)


@pytest.mark.parametrize("ruta", ["ca.key", "server.key", "ca.pem", "x/minio/private.key", "x/minio/public.crt", "ca.srl", ".ms-certs/a", "certs/ca.pem"])
def test_gitignore_ignora_los_artefactos_de_certificados(ruta):
    resultado = subprocess.run(["git", "check-ignore", "-q", ruta], cwd=RAIZ, check=False)
    assert resultado.returncode == 0, ruta


@pytest.mark.parametrize("servicio", ["redis", "minio", "coordinator"])
def test_los_servidores_pueden_leer_la_llave_montada(servicio):
    definicion = _servicios("docker-compose.yml")[servicio]
    assert "user" in definicion, f"{servicio} monta una llave 0600 sin fijar el UID"


def test_el_feeder_de_la_demo_apaga_tls_como_el_resto_del_compose_local():
    entorno = _servicios("deploy/docker-compose.demo.yml")["feeder"]["environment"]
    assert str(entorno.get("TLS_ENABLED")).lower() == "false"


def test_env_demo_apaga_tls():
    assert re.search(r"^TLS_ENABLED=false$", (RAIZ / ".env.demo").read_text(encoding="utf-8"), re.MULTILINE)
