import socket
import ssl
import threading
from contextlib import contextmanager

import pytest
import requests
import trustme

from src.infrastructure.tls import TlsSettings, client_context, requests_session

pytestmark = pytest.mark.integration

HOST = "127.0.0.1"
RESPUESTA = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"


def settings_con(ca: trustme.CA, tmp_path, nombre="ca.pem") -> TlsSettings:
    ruta = tmp_path / nombre
    ca.cert_pem.write_to_path(ruta)
    return TlsSettings(enabled=True, ca_file=ruta)


@contextmanager
def servidor_tls(ca: trustme.CA, identidades=(HOST,), max_version=None):
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert(*identidades).configure_cert(contexto)
    if max_version is not None:
        contexto.maximum_version = max_version
    escucha = socket.socket()
    escucha.bind((HOST, 0))
    escucha.listen(5)
    escucha.settimeout(0.1)
    errores: list[Exception] = []
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
                with contexto.wrap_socket(conexion, server_side=True) as seguro:
                    seguro.recv(4096)
                    seguro.sendall(RESPUESTA)
            except (ssl.SSLError, OSError) as error:
                errores.append(error)
                conexion.close()

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    try:
        yield escucha.getsockname()[1], errores
    finally:
        detenido.set()
        escucha.close()
        hilo.join(timeout=5)


def test_cliente_con_ca_completa_el_handshake_tls13(tmp_path):
    ca = trustme.CA()
    contexto = client_context(settings_con(ca, tmp_path))

    with servidor_tls(ca) as (puerto, _):
        with socket.create_connection((HOST, puerto), timeout=5) as crudo:
            with contexto.wrap_socket(crudo, server_hostname=HOST) as seguro:
                assert seguro.version() == "TLSv1.3"
                seguro.sendall(b"GET / HTTP/1.1\r\n\r\n")
                assert seguro.recv(4096).endswith(b"ok")


def test_cliente_sin_la_ca_es_rechazado(tmp_path):
    ca_servidor = trustme.CA()
    contexto = client_context(settings_con(trustme.CA(), tmp_path))

    with servidor_tls(ca_servidor) as (puerto, _):
        with socket.create_connection((HOST, puerto), timeout=5) as crudo:
            with pytest.raises(ssl.SSLCertVerificationError):
                contexto.wrap_socket(crudo, server_hostname=HOST)


def test_hostname_distinto_al_san_es_rechazado(tmp_path):
    ca = trustme.CA()
    contexto = client_context(settings_con(ca, tmp_path))

    with servidor_tls(ca, identidades=("otro.example",)) as (puerto, _):
        with socket.create_connection((HOST, puerto), timeout=5) as crudo:
            with pytest.raises(ssl.SSLCertVerificationError):
                contexto.wrap_socket(crudo, server_hostname=HOST)


def test_cliente_tls12_es_rechazado_por_el_contexto(tmp_path):
    ca = trustme.CA()
    contexto = client_context(settings_con(ca, tmp_path))

    with servidor_tls(ca, max_version=ssl.TLSVersion.TLSv1_2) as (puerto, _):
        with socket.create_connection((HOST, puerto), timeout=5) as crudo:
            with pytest.raises(ssl.SSLError):
                contexto.wrap_socket(crudo, server_hostname=HOST)


def test_cliente_en_claro_contra_servidor_tls_falla(tmp_path):
    ca = trustme.CA()

    with servidor_tls(ca) as (puerto, errores):
        with socket.create_connection((HOST, puerto), timeout=5) as crudo:
            crudo.settimeout(5)
            crudo.sendall(b"GET / HTTP/1.1\r\n\r\n")
            try:
                recibido = crudo.recv(4096)
            except ConnectionError:
                recibido = b""
        assert b"ok" not in recibido
        assert not recibido.startswith(b"HTTP/")


def test_requests_contra_https_local_verifica_la_ca(tmp_path):
    ca = trustme.CA()
    sesion = requests_session(settings_con(ca, tmp_path))

    with servidor_tls(ca) as (puerto, _):
        respuesta = sesion.get(f"https://{HOST}:{puerto}/", timeout=5)

    assert respuesta.status_code == 200
    assert respuesta.text == "ok"


def test_requests_con_otra_ca_es_rechazado(tmp_path):
    sesion = requests_session(settings_con(trustme.CA(), tmp_path))

    with servidor_tls(trustme.CA()) as (puerto, _):
        with pytest.raises(requests.exceptions.SSLError):
            sesion.get(f"https://{HOST}:{puerto}/", timeout=5)
