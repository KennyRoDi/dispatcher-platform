import datetime
import http.server
import ssl
import socket
import threading

import pytest
import redis
import requests
import trustme
import urllib3

from src.infrastructure.tls import (
    TlsSettings,
    client_context,
    minio_http_client,
    redis_kwargs,
    requests_session,
)
from tests.integration.test_tls_local import HOST, servidor_tls, settings_con

pytestmark = pytest.mark.integration


def _conectar(contexto, puerto):
    with socket.create_connection((HOST, puerto), timeout=5) as crudo:
        with contexto.wrap_socket(crudo, server_hostname=HOST) as seguro:
            return seguro.version()


@pytest.fixture
def ca_y_ajustes(tmp_path):
    ca = trustme.CA()
    return ca, settings_con(ca, tmp_path)


def test_certificado_expirado_es_rechazado(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    contexto = client_context(ajustes)
    ayer = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    contexto_srv = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert(HOST, not_before=ayer - datetime.timedelta(days=30), not_after=ayer).configure_cert(contexto_srv)
    with _servidor_con_contexto(contexto_srv) as puerto:
        with pytest.raises(ssl.SSLCertVerificationError, match="expired"):
            _conectar(contexto, puerto)


def test_certificado_de_ca_ajena_con_mismo_hostname_es_rechazado(ca_y_ajustes):
    _, ajustes = ca_y_ajustes
    with servidor_tls(trustme.CA()) as (puerto, _):
        with pytest.raises(ssl.SSLCertVerificationError):
            _conectar(client_context(ajustes), puerto)


def test_certificado_sin_san_es_rechazado(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    contexto_srv = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert(common_name=HOST).configure_cert(contexto_srv)
    with _servidor_con_contexto(contexto_srv) as puerto:
        with pytest.raises(ssl.SSLCertVerificationError):
            _conectar(client_context(ajustes), puerto)


def test_la_propia_ca_usada_como_servidor_con_hostname_ajeno_es_rechazada(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    contexto_srv = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto_srv.load_cert_chain(*_pem_de_ca(ca, ajustes))
    with _servidor_con_contexto(contexto_srv) as puerto:
        with pytest.raises(ssl.SSLError):
            _conectar(client_context(ajustes), puerto)


def test_ca_con_varios_certificados_valida_solo_los_de_sus_cas(tmp_path):
    ca_buena, ca_otra, ca_servidor = trustme.CA(), trustme.CA(), trustme.CA()
    ruta = tmp_path / "bundle.pem"
    ruta.write_bytes(ca_buena.cert_pem.bytes() + ca_otra.cert_pem.bytes())
    contexto = client_context(TlsSettings(enabled=True, ca_file=ruta))
    with servidor_tls(ca_otra) as (puerto, _):
        assert _conectar(contexto, puerto) == "TLSv1.3"
    with servidor_tls(ca_servidor) as (puerto, _):
        with pytest.raises(ssl.SSLCertVerificationError):
            _conectar(contexto, puerto)


def test_cliente_tls_contra_servidor_en_claro_falla():
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(1)
    escucha.settimeout(5)

    def atender():
        try:
            conexion, _ = escucha.accept()
            conexion.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            conexion.close()
        except OSError:
            pass

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    ca = trustme.CA()
    contexto = ssl.create_default_context()
    ca.configure_trust(contexto)
    with pytest.raises(ssl.SSLError):
        _conectar(contexto, escucha.getsockname()[1])
    escucha.close()


def test_redis_kwargs_rechaza_ca_ajena(ca_y_ajustes):
    _, ajustes = ca_y_ajustes
    with servidor_tls(trustme.CA()) as (puerto, _):
        cliente = redis.Redis(host=HOST, port=puerto, socket_timeout=5, **redis_kwargs(ajustes))
        with pytest.raises(redis.exceptions.ConnectionError, match="CERTIFICATE_VERIFY_FAILED"):
            cliente.ping()


def test_redis_kwargs_rechaza_hostname_ajeno(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    with servidor_tls(ca, identidades=("otro.example",)) as (puerto, _):
        cliente = redis.Redis(host=HOST, port=puerto, socket_timeout=5, **redis_kwargs(ajustes))
        with pytest.raises(redis.exceptions.ConnectionError, match="CERTIFICATE_VERIFY_FAILED"):
            cliente.ping()


def test_redis_kwargs_rechaza_servidor_tls12(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    with servidor_tls(ca, max_version=ssl.TLSVersion.TLSv1_2) as (puerto, _):
        cliente = redis.Redis(host=HOST, port=puerto, socket_timeout=5, **redis_kwargs(ajustes))
        with pytest.raises(redis.exceptions.ConnectionError, match="(?i)version|protocol"):
            cliente.ping()


def test_redis_kwargs_contra_servidor_en_claro_falla(ca_y_ajustes):
    _, ajustes = ca_y_ajustes
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(5)
    escucha.settimeout(0.1)
    detenido = threading.Event()

    def atender():
        while not detenido.is_set():
            try:
                conexion, _ = escucha.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            conexion.sendall(b"+PONG\r\n")
            conexion.close()

    threading.Thread(target=atender, daemon=True).start()
    cliente = redis.Redis(host=HOST, port=escucha.getsockname()[1], socket_timeout=2, **redis_kwargs(ajustes))
    try:
        with pytest.raises(redis.exceptions.RedisError):
            cliente.ping()
    finally:
        detenido.set()
        escucha.close()


@pytest.mark.xfail(strict=True, reason="redis_kwargs incluye ssl=True: con from_url('rediss://') redis-py lanza TypeError (ssl duplicado); parte 2 debe usar host/port o quitar 'ssl'")
def test_redis_kwargs_se_pueden_usar_con_from_url_rediss(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    with servidor_tls(trustme.CA()) as (puerto, _):
        cliente = redis.Redis.from_url(
            f"rediss://{HOST}:{puerto}/0", socket_timeout=5, **redis_kwargs(ajustes)
        )
        with pytest.raises(redis.exceptions.ConnectionError, match="CERTIFICATE_VERIFY_FAILED"):
            cliente.ping()


@pytest.mark.xfail(strict=True, reason="la query ?ssl_cert_reqs=none de la URL pisa los kwargs y acepta un servidor de otra CA; exigir_cifrado no la rechaza")
def test_redis_url_con_ssl_cert_reqs_none_no_desactiva_la_verificacion(ca_y_ajustes):
    _, ajustes = ca_y_ajustes
    sin_ssl = {k: v for k, v in redis_kwargs(ajustes).items() if k != "ssl"}
    with servidor_tls(trustme.CA()) as (puerto, _):
        cliente = redis.Redis.from_url(
            f"rediss://{HOST}:{puerto}/0?ssl_cert_reqs=none", socket_timeout=5, **sin_ssl
        )
        with pytest.raises(redis.exceptions.ConnectionError, match="CERTIFICATE_VERIFY_FAILED"):
            cliente.ping()


def test_minio_http_client_rechaza_ca_ajena_y_hostname(ca_y_ajustes):
    ca, ajustes = ca_y_ajustes
    pool = minio_http_client(ajustes)
    with servidor_tls(trustme.CA()) as (puerto, _):
        with pytest.raises(urllib3.exceptions.SSLError, match="CERTIFICATE_VERIFY_FAILED"):
            pool.request("GET", f"https://{HOST}:{puerto}/", retries=False, timeout=5)
    with servidor_tls(ca, identidades=("otro.example",)) as (puerto, _):
        with pytest.raises(urllib3.exceptions.SSLError, match="CERTIFICATE_VERIFY_FAILED"):
            pool.request("GET", f"https://{HOST}:{puerto}/", retries=False, timeout=5)


def test_minio_http_client_rechaza_http_plano_sin_fallback(ca_y_ajustes):
    _, ajustes = ca_y_ajustes
    servidor = http.server.HTTPServer((HOST, 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=servidor.handle_request, daemon=True).start()
    pool = minio_http_client(ajustes)
    with pytest.raises(urllib3.exceptions.HTTPError):
        pool.request("GET", f"https://{HOST}:{servidor.server_port}/", retries=False, timeout=3)
    servidor.server_close()


def test_requests_session_ignora_requests_ca_bundle_del_entorno(tmp_path, monkeypatch):
    ca_buena, ca_rogue = trustme.CA(), trustme.CA()
    ajustes = settings_con(ca_buena, tmp_path)
    rogue = tmp_path / "rogue.pem"
    ca_rogue.cert_pem.write_to_path(rogue)
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(rogue))
    sesion = requests_session(ajustes)
    with servidor_tls(ca_rogue) as (puerto, _):
        with pytest.raises(requests.exceptions.SSLError):
            sesion.get(f"https://{HOST}:{puerto}/", timeout=5)


def test_requests_session_ignora_curl_ca_bundle_del_entorno(tmp_path, monkeypatch):
    ca_buena, ca_rogue = trustme.CA(), trustme.CA()
    ajustes = settings_con(ca_buena, tmp_path)
    rogue = tmp_path / "rogue.pem"
    ca_rogue.cert_pem.write_to_path(rogue)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setenv("CURL_CA_BUNDLE", str(rogue))
    sesion = requests_session(ajustes)
    with servidor_tls(ca_rogue) as (puerto, _):
        with pytest.raises(requests.exceptions.SSLError):
            sesion.get(f"https://{HOST}:{puerto}/", timeout=5)


def test_requests_session_no_hereda_proxies_del_entorno(tmp_path, monkeypatch):
    ajustes = settings_con(trustme.CA(), tmp_path)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    assert requests_session(ajustes).trust_env is False


def test_requests_session_no_sigue_redireccion_a_http_plano(tmp_path):
    ca = trustme.CA()
    ajustes = settings_con(ca, tmp_path)
    plano = http.server.HTTPServer((HOST, 0), http.server.SimpleHTTPRequestHandler)
    visitas = []

    class Destino(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            visitas.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    plano.RequestHandlerClass = Destino
    threading.Thread(target=plano.handle_request, daemon=True).start()
    destino = f"http://{HOST}:{plano.server_port}/robado"
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert(HOST).configure_cert(contexto)
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(1)
    escucha.settimeout(5)

    def atender():
        conexion, _ = escucha.accept()
        with contexto.wrap_socket(conexion, server_side=True) as seguro:
            seguro.recv(4096)
            seguro.sendall(f"HTTP/1.1 302 Found\r\nLocation: {destino}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())

    threading.Thread(target=atender, daemon=True).start()
    try:
        sesion = requests_session(ajustes)
        try:
            respuesta = sesion.get(f"https://{HOST}:{escucha.getsockname()[1]}/", timeout=5)
            terminado_en_claro = respuesta.url.startswith("http://")
        except requests.exceptions.RequestException:
            terminado_en_claro = False
    finally:
        escucha.close()
        plano.server_close()
    assert not terminado_en_claro and not visitas


@pytest.mark.xfail(strict=True, reason="requests_session no impone TLS 1.3 minimo (limite declarado en la verificacion de implementacion)")
def test_requests_session_rechaza_servidor_tls12(tmp_path):
    ca = trustme.CA()
    sesion = requests_session(settings_con(ca, tmp_path))
    with servidor_tls(ca, max_version=ssl.TLSVersion.TLSv1_2) as (puerto, _):
        with pytest.raises(requests.exceptions.SSLError):
            sesion.get(f"https://{HOST}:{puerto}/", timeout=5)


def test_requests_session_verify_nunca_es_falso(tmp_path):
    sesion = requests_session(settings_con(trustme.CA(), tmp_path))
    assert sesion.verify not in (False, None, True)


def test_sesiones_distintas_no_comparten_la_ca(tmp_path):
    ca_a, ca_b = trustme.CA(), trustme.CA()
    sesion_a = requests_session(settings_con(ca_a, tmp_path, "a.pem"))
    sesion_b = requests_session(settings_con(ca_b, tmp_path, "b.pem"))
    with servidor_tls(ca_a) as (puerto, _):
        assert sesion_a.get(f"https://{HOST}:{puerto}/", timeout=5).status_code == 200
        with pytest.raises(requests.exceptions.SSLError):
            sesion_b.get(f"https://{HOST}:{puerto}/", timeout=5)
        assert sesion_a.get(f"https://{HOST}:{puerto}/", timeout=5).status_code == 200


from contextlib import contextmanager


@contextmanager
def _servidor_con_contexto(contexto):
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(5)
    escucha.settimeout(0.1)
    detenido = threading.Event()

    def atender():
        while not detenido.is_set():
            try:
                conexion, _ = escucha.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            try:
                conexion.settimeout(5)
                with contexto.wrap_socket(conexion, server_side=True):
                    pass
            except (ssl.SSLError, OSError):
                conexion.close()

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    try:
        yield escucha.getsockname()[1]
    finally:
        detenido.set()
        escucha.close()
        hilo.join(timeout=5)


def _pem_de_ca(ca, ajustes):
    cert = ajustes.ca_file.parent / "ca_como_servidor.pem"
    llave = ajustes.ca_file.parent / "ca_como_servidor.key"
    cert.write_bytes(ca.cert_pem.bytes())
    llave.write_bytes(ca.private_key_pem.bytes())
    return str(cert), str(llave)
