import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "deploy" / "tls" / "generar_certs.sh"
NODE_IP = "100.64.0.7"
NODE_NAME = "nodo-a-demo"
ARCHIVOS = ["ca.pem", "ca.key", "server.pem", "server.key", "minio/public.crt", "minio/private.key"]
LLAVES = ["ca.key", "server.key", "minio/private.key"]

necesita_openssl = pytest.mark.skipif(
    shutil.which("openssl") is None or os.name == "nt",
    reason="requiere openssl y un bash POSIX; en Windows bash es el lanzador de WSL",
)


def _texto() -> str:
    assert SCRIPT.is_file(), f"falta {SCRIPT.relative_to(RAIZ)}"
    return SCRIPT.read_text(encoding="utf-8")


def _ejecutar(entorno: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    base = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(SCRIPT)], env={**base, **entorno}, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=60
    )


def _openssl(*argumentos: str) -> str:
    resultado = subprocess.run(["openssl", *argumentos], capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def _dias_de_validez(certificado: Path) -> int:
    fechas = dict(linea.split("=", 1) for linea in _openssl("x509", "-in", str(certificado), "-noout", "-dates").splitlines())
    formato = "%b %d %H:%M:%S %Y %Z"
    inicio = datetime.strptime(fechas["notBefore"], formato).replace(tzinfo=timezone.utc)
    fin = datetime.strptime(fechas["notAfter"], formato).replace(tzinfo=timezone.utc)
    return round((fin - inicio).total_seconds() / 86400)


def _estado_del_repo() -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="module")
def certificados(tmp_path_factory) -> Path:
    if shutil.which("openssl") is None or os.name == "nt":
        pytest.skip("requiere openssl y un bash POSIX")
    tmp_path = tmp_path_factory.mktemp("certs")
    destino = tmp_path / "salida"
    antes = _estado_del_repo()
    resultado = _ejecutar({"CERTS_DIR": str(destino), "NODE_IP": NODE_IP, "NODE_NAME": NODE_NAME}, tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert _estado_del_repo() == antes, "el script modificó el repositorio"
    return destino


@pytest.mark.skipif(os.name == "nt", reason="el bit de ejecución no existe")
def test_el_script_existe_y_es_ejecutable():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR, "falta el bit de ejecución"


def test_el_script_falla_ante_errores():
    assert re.search(r"^set -euo pipefail$", _texto(), re.MULTILINE)


def test_el_directorio_por_defecto_esta_fuera_del_repo():
    texto = _texto()
    assert re.search(r"CERTS_DIR:-\$\{?HOME\}?/\.ms-certs", texto), "el valor por defecto debe ser $HOME/.ms-certs"
    assert not re.search(r"CERTS_DIR[:=-]+[^\n]*(\$\(pwd\)|\$PWD|\.\./|\./)", texto), "CERTS_DIR no debe apuntar al repo"


def test_el_script_usa_ec_p256_y_las_vigencias_de_sup_33():
    texto = _texto()
    assert re.search(r"prime256v1|P-256", texto)
    assert re.search(r"-days\s+(365|\$\{?CA_DAYS\}?)", texto)
    assert re.search(r"-days\s+(90|\$\{?CERT_DAYS\}?)", texto)
    assert "umask 077" in texto or "chmod 600" in texto


def test_sin_node_ip_el_script_falla_y_no_escribe(tmp_path):
    _texto()
    destino = tmp_path / "salida"
    resultado = _ejecutar({"CERTS_DIR": str(destino), "NODE_NAME": NODE_NAME}, tmp_path)
    assert resultado.returncode != 0
    assert not (destino / "server.key").exists()


@necesita_openssl
def test_con_certs_dir_crea_todos_los_archivos(certificados):
    for relativo in ARCHIVOS:
        assert (certificados / relativo).is_file(), f"falta {relativo}"


@necesita_openssl
def test_sin_certs_dir_escribe_en_home_ms_certs_y_no_en_el_repo(tmp_path):
    antes = _estado_del_repo()
    resultado = _ejecutar({"NODE_IP": NODE_IP, "NODE_NAME": NODE_NAME}, tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert (tmp_path / "home" / ".ms-certs" / "ca.pem").is_file()
    assert _estado_del_repo() == antes
    assert not list(tmp_path.glob("*.pem")) and not list(tmp_path.glob("*.key")), "escribió en el directorio actual"


@necesita_openssl
@pytest.mark.parametrize("llave", LLAVES)
def test_las_llaves_son_ec_p256_y_no_son_legibles_por_otros(certificados, llave):
    ruta = certificados / llave
    assert "prime256v1" in _openssl("ec", "-in", str(ruta), "-noout", "-text")
    modo = stat.S_IMODE(ruta.stat().st_mode)
    # 0600 de la CA; las llaves de servidor pueden abrirse al grupo (0640) para el UID de cada imagen.
    assert modo & 0o400 and modo & 0o007 == 0 and modo & 0o020 == 0, oct(modo)


@necesita_openssl
def test_la_llave_de_la_ca_tiene_modo_0600(certificados):
    assert stat.S_IMODE((certificados / "ca.key").stat().st_mode) == 0o600


@necesita_openssl
def test_el_certificado_del_servidor_se_valida_contra_la_ca(certificados):
    salida = _openssl("verify", "-CAfile", str(certificados / "ca.pem"), str(certificados / "server.pem"))
    assert "OK" in salida


@necesita_openssl
def test_el_certificado_de_minio_se_valida_contra_la_ca(certificados):
    salida = _openssl("verify", "-CAfile", str(certificados / "ca.pem"), str(certificados / "minio" / "public.crt"))
    assert "OK" in salida


@necesita_openssl
def test_el_certificado_trae_los_san_de_los_servicios(certificados):
    san = _openssl("x509", "-in", str(certificados / "server.pem"), "-noout", "-ext", "subjectAltName")
    for esperado in (f"IP Address:{NODE_IP}", f"DNS:{NODE_NAME}", "DNS:redis", "DNS:minio", "DNS:coordinator"):
        assert esperado in san, f"falta {esperado} en {san}"


@necesita_openssl
def test_el_certificado_no_es_de_ca_y_sirve_para_servidor(certificados):
    texto = _openssl("x509", "-in", str(certificados / "server.pem"), "-noout", "-text")
    assert "CA:FALSE" in texto
    assert "TLS Web Server Authentication" in texto


@necesita_openssl
def test_vigencias_ca_365_dias_y_servidor_90(certificados):
    assert _dias_de_validez(certificados / "ca.pem") == 365
    assert _dias_de_validez(certificados / "server.pem") == 90


@necesita_openssl
def test_ca_pem_no_contiene_llaves(certificados):
    assert "PRIVATE KEY" not in (certificados / "ca.pem").read_text(encoding="utf-8")


@necesita_openssl
def test_ejecutarlo_dos_veces_no_rompe_la_cadena(tmp_path):
    entorno = {"CERTS_DIR": str(tmp_path / "salida"), "NODE_IP": NODE_IP, "NODE_NAME": NODE_NAME}
    for _ in range(2):
        resultado = _ejecutar(entorno, tmp_path)
        assert resultado.returncode == 0, resultado.stderr
    certificados = Path(entorno["CERTS_DIR"])
    salida = _openssl("verify", "-CAfile", str(certificados / "ca.pem"), str(certificados / "server.pem"))
    assert "OK" in salida
