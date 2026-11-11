import re
import subprocess
import sys
from pathlib import Path

import pytest
import requests
import trustme
from requests.adapters import HTTPAdapter

import minio

import scripts.check_connectivity as check_connectivity
import scripts.fetch_results as fetch_results
import scripts.submit_case as submit_case
from src.infrastructure.tls import TlsConfigError, TlsSettings
from src.workers.config import Settings
from src.workers.storage import Storage

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def ca_pem(tmp_path):
    path = tmp_path / "ca.pem"
    trustme.CA().cert_pem.write_to_path(path)
    return path


@pytest.fixture
def tls_activo(monkeypatch, ca_pem):
    monkeypatch.setenv("TLS_ENABLED", "true")
    monkeypatch.setenv("TLS_CA_FILE", str(ca_pem))
    return TlsSettings(enabled=True, ca_file=ca_pem)


@pytest.fixture
def tls_sin_ca(monkeypatch):
    monkeypatch.delenv("TLS_ENABLED", raising=False)
    monkeypatch.delenv("TLS_CA_FILE", raising=False)


@pytest.fixture
def envios(monkeypatch):
    registro = []

    def send(self, request, **kwargs):
        registro.append(request.url)
        respuesta = requests.Response()
        respuesta.status_code = 200
        respuesta._content = b'{"case_id": "c1", "status": "completed", "subtasks": []}'
        respuesta.url = request.url
        respuesta.request = request
        return respuesta

    monkeypatch.setattr(HTTPAdapter, "send", send)
    return registro


def settings_con(**env) -> Settings:
    return Settings.from_env(env)


# (1) Funciones de biblioteca de submit_case: solo main() exige cifrado; llamadas directas viajan en claro

@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (media): las funciones publicas de submit_case no llaman a exigir_cifrado; con TLS activo envian a http:// en claro")
@pytest.mark.parametrize("operacion", ["submit_case", "cancel_case", "fetch_report", "poll_case"])
def test_con_tls_las_funciones_de_submit_case_no_envian_a_http(tls_activo, envios, operacion):
    url = "http://nodo-a:8000"
    llamadas = {
        "submit_case": lambda: submit_case.submit_case(url, [("k", "auto")]),
        "cancel_case": lambda: submit_case.cancel_case(url, "c1"),
        "fetch_report": lambda: submit_case.fetch_report(url, "c1"),
        "poll_case": lambda: submit_case.poll_case(url, "c1", 0.0, 0.0, sleep=lambda _: None),
    }

    try:
        llamadas[operacion]()
    except (TlsConfigError, requests.RequestException):
        pass

    assert [u for u in envios if u.startswith("http://")] == []


# (1) Scripts y modulos que siguen fuera de tls.py (requests plano)

@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (media): fetch_results.main usa el modulo requests plano; ignora la CA y acepta http:// con TLS activo")
def test_fetch_results_no_usa_el_modulo_requests_como_sesion_por_defecto():
    import inspect

    por_defecto = inspect.signature(fetch_results.main).parameters["session"].default

    assert por_defecto is not requests


PLANOS = {
    "scripts/demo_feeder.py": r"run\(settings, requests,",
    "scripts/generate_dataset.py": r"requests\.Session\(\)",
}


@pytest.mark.parametrize("archivo", sorted(PLANOS))
@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (media): script con cliente HTTP plano; no pasa por tls.py y acepta http:// con TLS activo")
def test_script_no_crea_clientes_http_planos(archivo):
    assert re.search(PLANOS[archivo], (RAIZ / archivo).read_text(encoding="utf-8")) is None


# (2) Los diagnosticos deben informar, no morir con traza

def test_check_redis_con_tls_sin_ca_informa_en_vez_de_lanzar(tls_sin_ca):
    ok, mensaje = check_connectivity.check_redis(settings_con())

    assert ok is False
    assert "TLS" in mensaje


@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (baja): check_minio no atrapa TlsConfigError con MINIO_SECURE=false y TLS activo")
def test_check_minio_con_tls_y_minio_inseguro_informa_en_vez_de_lanzar(tls_activo):
    ok, mensaje = check_connectivity.check_minio(settings_con(MINIO_SECURE="false"))

    assert ok is False


@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (baja): submit_case.main construye Storage fuera del try; TlsConfigError sale como traza")
def test_submit_case_main_con_minio_inseguro_sale_con_error_limpio(tls_activo, monkeypatch, tmp_path, capsys):
    (tmp_path / "a.mp4").write_bytes(b"x")
    monkeypatch.setenv("COORDINATOR_URL", "https://nodo-a:8443")
    monkeypatch.setenv("MINIO_SECURE", "false")

    codigo = submit_case.main(["--dir", str(tmp_path)])

    assert codigo == 1
    assert "MINIO" in capsys.readouterr().out.upper()


# (4) Cliente inyectado

@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (baja, limite declarado): Storage con cliente inyectado no pasa por exigir_cifrado")
def test_storage_con_cliente_inyectado_y_minio_inseguro_se_rechaza(tls_activo):
    inyectado = minio.Minio("nodo-a:9000", access_key="a", secret_key="b", secure=False)

    with pytest.raises(TlsConfigError):
        Storage(settings_con(MINIO_SECURE="false"), client=inyectado)


# (5) conexion.py al importar

def _importar_conexion(env_extra: dict):
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("TLS_")}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import src.coordinator.conexion"],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=60,
    )


def test_importar_conexion_con_tls_activo_sin_ca_falla_con_mensaje_claro():
    resultado = _importar_conexion({})

    assert resultado.returncode != 0
    assert "TLS_CA_FILE" in resultado.stderr


def test_importar_conexion_con_ca_invalida_falla_con_mensaje_claro(tmp_path):
    basura = tmp_path / "ca.pem"
    basura.write_text("no es un certificado")

    resultado = _importar_conexion({"TLS_CA_FILE": str(basura)})

    assert resultado.returncode != 0
    assert "PEM" in resultado.stderr


def test_importar_conexion_con_ca_valida_no_abre_conexion(ca_pem):
    resultado = _importar_conexion({"TLS_CA_FILE": str(ca_pem)})

    assert resultado.returncode == 0, resultado.stderr


# (7) Credenciales en mensajes

@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (baja): una URL con usuario:clave se imprime tal cual en config_summary y en check_coordinator")
def test_config_summary_no_imprime_credenciales_de_la_url():
    resumen = check_connectivity.config_summary(
        settings_con(COORDINATOR_URL="https://usuario:SECRETO@nodo-a:8443")
    )

    assert "SECRETO" not in resumen


@pytest.mark.xfail(strict=True, reason="QA F-27 p2 (baja): exigir_cifrado acepta una URL del coordinador con usuario:clave embebidos")
def test_exigir_cifrado_rechaza_credenciales_en_la_url_del_coordinador(tls_activo):
    from src.infrastructure.tls import exigir_cifrado

    with pytest.raises(TlsConfigError):
        exigir_cifrado(tls_activo, coordinator_url="https://usuario:SECRETO@nodo-a:8443")


# (3) make_redis contra un servidor TLS stub (sockets locales, sin Docker)

import socket
import ssl
import threading
from contextlib import contextmanager

from src.workers.config import make_redis

HOST = "127.0.0.1"


@contextmanager
def redis_stub(ca, identidades=(HOST,), max_version=None, con_tls=True):
    contexto = None
    if con_tls:
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ca.issue_cert(*identidades).configure_cert(contexto)
        if max_version is not None:
            contexto.maximum_version = max_version
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(5)
    escucha.settimeout(0.1)
    recibido = bytearray()
    detenido = threading.Event()

    def servir(conexion):
        conexion.settimeout(2)
        while True:
            datos = conexion.recv(4096)
            if not datos:
                return
            recibido.extend(datos)
            conexion.sendall(b"+PONG\r\n" if b"PING" in datos else b"+OK\r\n")

    def atender():
        while not detenido.is_set():
            try:
                conexion, _ = escucha.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            try:
                if contexto is not None:
                    conexion = contexto.wrap_socket(conexion, server_side=True)
                servir(conexion)
            except OSError:
                pass
            finally:
                conexion.close()

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    try:
        yield escucha.getsockname()[1], recibido
    finally:
        detenido.set()
        escucha.close()


def redis_activo(monkeypatch, tmp_path, ca, puerto, password="CLAVE-SECRETA"):
    ruta = tmp_path / "ca-cliente.pem"
    ca.cert_pem.write_to_path(ruta)
    monkeypatch.setenv("TLS_ENABLED", "true")
    monkeypatch.setenv("TLS_CA_FILE", str(ruta))
    return make_redis(settings_con(REDIS_HOST=HOST, REDIS_PORT=str(puerto), REDIS_PASSWORD=password))


@pytest.mark.integration
def test_make_redis_hace_handshake_tls13_y_ping_con_la_ca(monkeypatch, tmp_path):
    ca = trustme.CA()
    with redis_stub(ca) as (puerto, recibido):
        cliente = redis_activo(monkeypatch, tmp_path, ca, puerto)
        assert cliente.ping() is True
        assert b"CLAVE-SECRETA" in recibido


@pytest.mark.integration
def test_make_redis_rechaza_servidor_firmado_por_otra_ca(monkeypatch, tmp_path):
    with redis_stub(trustme.CA()) as (puerto, recibido):
        cliente = redis_activo(monkeypatch, tmp_path, trustme.CA(), puerto)
        with pytest.raises(Exception, match="(?i)certificate|ssl|verify"):
            cliente.ping()
        assert b"CLAVE-SECRETA" not in recibido


@pytest.mark.integration
def test_make_redis_verifica_el_hostname(monkeypatch, tmp_path):
    ca = trustme.CA()
    with redis_stub(ca, identidades=("otro-host.local",)) as (puerto, recibido):
        cliente = redis_activo(monkeypatch, tmp_path, ca, puerto)
        with pytest.raises(Exception, match="(?i)hostname|certificate|ssl"):
            cliente.ping()
        assert b"CLAVE-SECRETA" not in recibido


@pytest.mark.integration
def test_make_redis_rechaza_servidor_tls12(monkeypatch, tmp_path):
    ca = trustme.CA()
    with redis_stub(ca, max_version=ssl.TLSVersion.TLSv1_2) as (puerto, recibido):
        cliente = redis_activo(monkeypatch, tmp_path, ca, puerto)
        with pytest.raises(Exception, match="(?i)version|protocol|ssl|tls"):
            cliente.ping()
        assert b"CLAVE-SECRETA" not in recibido


@pytest.mark.integration
def test_make_redis_contra_servidor_en_claro_no_filtra_la_clave(monkeypatch, tmp_path):
    ca = trustme.CA()
    with redis_stub(ca, con_tls=False) as (puerto, recibido):
        cliente = redis_activo(monkeypatch, tmp_path, ca, puerto)
        with pytest.raises(Exception):
            cliente.ping()
        assert b"CLAVE-SECRETA" not in recibido
