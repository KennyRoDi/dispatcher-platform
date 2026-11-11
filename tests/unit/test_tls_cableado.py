import argparse
import ssl
from pathlib import Path

import pytest
import redis
import requests
import trustme
import urllib3
from requests.adapters import HTTPAdapter

import minio

import scripts.check_connectivity as check_connectivity
import scripts.run_load as run_load
import scripts.submit_case as submit_case
from src.coordinator import conexion
from src.infrastructure.tls import TlsConfigError, TlsSettings
from src.workers.config import Settings, make_redis
from src.workers.reporter import Reporter
from src.workers.storage import Storage


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


class FakeRedis:
    llamadas = []

    def __init__(self, *args, **kwargs):
        type(self).llamadas.append((args, kwargs))

    @classmethod
    def from_url(cls, *args, **kwargs):
        raise AssertionError("con TLS no se usa Redis.from_url: ssl duplicado")


@pytest.fixture
def redis_falso(monkeypatch):
    FakeRedis.llamadas = []
    monkeypatch.setattr(redis, "Redis", FakeRedis)
    return FakeRedis


class FakeMinio:
    llamadas = []

    def __init__(self, *args, **kwargs):
        type(self).llamadas.append((args, kwargs))


@pytest.fixture
def minio_falso(monkeypatch):
    FakeMinio.llamadas = []
    monkeypatch.setattr(minio, "Minio", FakeMinio)
    return FakeMinio


@pytest.fixture
def envios(monkeypatch):
    registro = []

    def send(self, request, **kwargs):
        registro.append((request.url, kwargs))
        respuesta = requests.Response()
        respuesta.status_code = 200
        respuesta._content = b'{"case_id": "c1", "status": "completed"}'
        respuesta.url = request.url
        respuesta.request = request
        return respuesta

    monkeypatch.setattr(HTTPAdapter, "send", send)
    return registro


def settings_con(**env) -> Settings:
    return Settings.from_env(env)


def claves_ssl(kwargs: dict) -> list[str]:
    return [clave for clave in kwargs if clave.startswith("ssl")]


# make_redis (workers, reaper, check_connectivity, run_load)

@pytest.mark.parametrize("explicito", [False, True])
def test_make_redis_con_tls_usa_host_port_y_ssl(tls_activo, redis_falso, explicito):
    settings = settings_con(REDIS_HOST="nodo-a", REDIS_PORT="6380", REDIS_PASSWORD="clave")

    make_redis(settings, tls_activo) if explicito else make_redis(settings)

    (args, kwargs), = redis_falso.llamadas
    assert args == ()
    assert kwargs["host"] == "nodo-a"
    assert kwargs["port"] == 6380
    assert kwargs["password"] == "clave"
    assert kwargs["decode_responses"] is True
    assert kwargs["ssl"] is True
    assert kwargs["ssl_ca_certs"] == str(tls_activo.ca_file)
    assert kwargs["ssl_cert_reqs"] == "required"
    assert kwargs["ssl_check_hostname"] is True
    assert kwargs["ssl_min_version"] == ssl.TLSVersion.TLSv1_3
    assert "url" not in kwargs and "connection_pool" not in kwargs


def test_make_redis_sin_tls_conserva_los_argumentos_de_siempre(redis_falso):
    settings = settings_con(REDIS_HOST="nodo-a", REDIS_PORT="6379")

    make_redis(settings)

    (args, kwargs), = redis_falso.llamadas
    assert claves_ssl(kwargs) == []
    assert kwargs == {
        "host": "nodo-a",
        "port": 6379,
        "password": None,
        "decode_responses": True,
        "socket_keepalive": True,
        "health_check_interval": 30,
    }


def test_make_redis_con_tls_sin_ca_no_arranca(tls_sin_ca, redis_falso):
    with pytest.raises(TlsConfigError):
        make_redis(settings_con())

    assert redis_falso.llamadas == []


# Reporter (workers y reaper hacia la API)

def test_reporter_con_tls_usa_sesion_con_la_ca(tls_activo):
    reporter = Reporter(settings_con(COORDINATOR_URL="https://nodo-a:8443"), object())

    assert isinstance(reporter.session, requests.Session)
    assert reporter.session.verify == str(tls_activo.ca_file)
    assert reporter.session.trust_env is False


@pytest.mark.parametrize("url", ["http://nodo-a:8000", "HTTP://nodo-a:8000"])
def test_reporter_con_tls_rechaza_coordinador_en_claro(tls_activo, url):
    with pytest.raises(TlsConfigError):
        Reporter(settings_con(COORDINATOR_URL=url), object())


def test_reporter_con_tls_sin_ca_no_arranca(tls_sin_ca):
    with pytest.raises(TlsConfigError):
        Reporter(settings_con(COORDINATOR_URL="https://nodo-a:8443"), object())


def test_reporter_sin_tls_usa_la_sesion_de_siempre():
    reporter = Reporter(settings_con(COORDINATOR_URL="http://nodo-a:8000"), object())

    assert type(reporter.session) is requests.Session
    assert reporter.session.verify is True


def test_reporter_respeta_la_sesion_inyectada(tls_activo):
    propia = requests.Session()

    reporter = Reporter(settings_con(COORDINATOR_URL="https://nodo-a:8443"), object(), session=propia)

    assert reporter.session is propia


# Storage (workers y coordinador hacia MinIO)

def test_storage_con_tls_pasa_secure_y_cliente_http_con_la_ca(tls_activo, minio_falso):
    Storage(settings_con(MINIO_ENDPOINT="nodo-a:9000", MINIO_SECURE="true"))

    (args, kwargs), = minio_falso.llamadas
    assert args == ("nodo-a:9000",)
    assert kwargs["secure"] is True
    http_client = kwargs["http_client"]
    assert isinstance(http_client, urllib3.PoolManager)
    contexto = http_client.connection_pool_kw["ssl_context"]
    assert contexto.minimum_version == ssl.TLSVersion.TLSv1_3
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


@pytest.mark.parametrize("valor", ["false", "0", "no", "off"])
def test_storage_con_tls_rechaza_minio_secure_apagado(tls_activo, minio_falso, valor):
    with pytest.raises(TlsConfigError):
        Storage(settings_con(MINIO_SECURE=valor))

    assert minio_falso.llamadas == []


def test_storage_con_tls_sin_ca_no_arranca(tls_sin_ca, minio_falso):
    with pytest.raises(TlsConfigError):
        Storage(settings_con(MINIO_SECURE="true"))

    assert minio_falso.llamadas == []


def test_storage_sin_tls_conserva_los_argumentos_de_siempre(minio_falso):
    Storage(settings_con(MINIO_ENDPOINT="nodo-a:9000", MINIO_SECURE="false"))

    (args, kwargs), = minio_falso.llamadas
    assert kwargs["secure"] is False
    assert kwargs.get("http_client") is None


def test_storage_respeta_el_cliente_inyectado(tls_activo, minio_falso):
    propio = object()

    assert Storage(settings_con(MINIO_SECURE="true"), client=propio).client is propio
    assert minio_falso.llamadas == []


# Coordinador (src/coordinator/conexion.py)

def test_cliente_redis_del_coordinador_con_tls(tls_activo, redis_falso, monkeypatch):
    monkeypatch.setattr(conexion, "REDIS_HOST", "nodo-a")
    monkeypatch.setattr(conexion, "REDIS_PORT", 6380)

    conexion.make_redis_client()

    (args, kwargs), = redis_falso.llamadas
    assert args == ()
    assert kwargs["host"] == "nodo-a"
    assert kwargs["port"] == 6380
    assert kwargs["ssl"] is True
    assert kwargs["ssl_ca_certs"] == str(tls_activo.ca_file)
    assert kwargs["ssl_check_hostname"] is True
    assert kwargs["ssl_min_version"] == ssl.TLSVersion.TLSv1_3
    assert kwargs["decode_responses"] is True


def test_cliente_redis_del_coordinador_sin_tls(redis_falso, monkeypatch):
    monkeypatch.setattr(conexion, "REDIS_HOST", "nodo-a")
    monkeypatch.setattr(conexion, "REDIS_PORT", 6379)

    conexion.make_redis_client()

    (args, kwargs), = redis_falso.llamadas
    assert claves_ssl(kwargs) == []
    assert kwargs["host"] == "nodo-a"
    assert kwargs["port"] == 6379


def test_cliente_redis_del_coordinador_con_tls_sin_ca_no_arranca(tls_sin_ca, redis_falso):
    with pytest.raises(TlsConfigError):
        conexion.make_redis_client()

    assert redis_falso.llamadas == []


# scripts/check_connectivity.py

def test_check_coordinator_con_tls_verifica_con_la_ca(tls_activo, envios):
    ok, _ = check_connectivity.check_coordinator(settings_con(COORDINATOR_URL="https://nodo-a:8443"))

    assert ok is True
    (url, kwargs), = envios
    assert url == "https://nodo-a:8443/openapi.json"
    assert kwargs["verify"] == str(tls_activo.ca_file)


def test_check_coordinator_con_tls_no_envia_nada_a_una_url_en_claro(tls_activo, envios):
    try:
        ok, _ = check_connectivity.check_coordinator(settings_con(COORDINATOR_URL="http://nodo-a:8000"))
    except TlsConfigError:
        ok = False

    assert ok is False
    assert envios == []


def test_check_coordinator_sin_tls_conserva_la_verificacion_de_siempre(envios):
    ok, _ = check_connectivity.check_coordinator(settings_con(COORDINATOR_URL="http://nodo-a:8000"))

    assert ok is True
    (url, kwargs), = envios
    assert url == "http://nodo-a:8000/openapi.json"
    assert kwargs["verify"] is True


def test_check_minio_con_tls_y_minio_secure_apagado_informa_el_rechazo(tls_activo, minio_falso):
    ok, mensaje = check_connectivity.check_minio(settings_con(MINIO_SECURE="false"))

    assert ok is False
    assert minio_falso.llamadas == []


# scripts/submit_case.py

def test_submit_case_y_fetch_report_con_tls_usan_la_ca_por_defecto(tls_activo, envios):
    submit_case.submit_case("https://nodo-a:8443", [("k", "convert_audio")])
    submit_case.fetch_report("https://nodo-a:8443", "c1")

    assert len(envios) == 2
    assert all(kwargs["verify"] == str(tls_activo.ca_file) for _, kwargs in envios)


def test_fetch_report_sin_tls_conserva_la_verificacion_de_siempre(envios):
    submit_case.fetch_report("http://nodo-a:8000", "c1")

    (url, kwargs), = envios
    assert kwargs["verify"] is True


def test_submit_case_main_con_tls_rechaza_coordinador_en_claro_al_arrancar(tls_activo, envios, monkeypatch, tmp_path):
    monkeypatch.setenv("COORDINATOR_URL", "http://nodo-a:8000")
    (tmp_path / "a.mp3").write_bytes(b"x")

    try:
        code = submit_case.main(["--dir", str(tmp_path), "--no-upload", "--timeout", "0", "--poll", "0"])
    except TlsConfigError:
        code = 1

    assert code != 0
    assert envios == []


# scripts/run_load.py

def test_run_load_main_con_tls_rechaza_coordinador_en_claro_antes_de_cargar(tls_activo, monkeypatch, tmp_path):
    monkeypatch.setenv("COORDINATOR_URL", "http://nodo-a:8000")

    def no_debe_llegar(*args, **kwargs):
        raise AssertionError("se cargó el dataset antes de rechazar la comunicación en claro")

    monkeypatch.setattr(run_load, "load_dataset", no_debe_llegar)

    with pytest.raises(TlsConfigError):
        run_load.main(["--dataset", str(tmp_path), "--out", str(tmp_path / "out")])


def args_de_carga(tmp_path) -> argparse.Namespace:
    return argparse.Namespace(
        dataset=tmp_path, upload=False, kinds=None, limit=None, concurrency=1, high_fraction=0.0,
        seed=1, poll=0.0, timeout=1.0, out=tmp_path / "out",
    )


@pytest.fixture
def carga_sin_red(monkeypatch):
    capturado = {}

    def submit_all(session, *args, **kwargs):
        capturado["session"] = session
        return []

    monkeypatch.setattr(run_load, "load_dataset", lambda dataset: ({}, {"cases": []}))
    monkeypatch.setattr(run_load, "select_cases", lambda *a, **k: [])
    monkeypatch.setattr(run_load, "index_manifest", lambda manifest: {})
    monkeypatch.setattr(run_load, "connect_redis", lambda *a, **k: None)
    monkeypatch.setattr(run_load, "submit_all", submit_all)
    monkeypatch.setattr(run_load, "monitor", lambda *a, **k: {"series": [], "timed_out": False})
    monkeypatch.setattr(run_load, "fetch_reports", lambda *a, **k: {})
    monkeypatch.setattr(run_load, "compute_metrics", lambda *a, **k: {})
    monkeypatch.setattr(run_load, "render_md", lambda *a, **k: "")
    return capturado


def test_run_load_con_tls_usa_una_sesion_con_la_ca_por_defecto(tls_activo, carga_sin_red, tmp_path):
    run_load.run_load(
        args_de_carga(tmp_path), settings_con(COORDINATOR_URL="https://nodo-a:8443"), stamp="t",
    )

    sesion = carga_sin_red["session"]
    assert isinstance(sesion, requests.Session)
    assert sesion.verify == str(tls_activo.ca_file)


def test_run_load_sin_tls_conserva_la_sesion_de_siempre(carga_sin_red, tmp_path):
    run_load.run_load(
        args_de_carga(tmp_path), settings_con(COORDINATOR_URL="http://nodo-a:8000"), stamp="t",
    )

    assert getattr(carga_sin_red["session"], "verify", True) is True
