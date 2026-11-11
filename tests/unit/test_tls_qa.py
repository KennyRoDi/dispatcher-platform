import os

import pytest
import trustme

from src.infrastructure.tls import (
    TlsConfigError,
    TlsSettings,
    client_context,
    exigir_cifrado,
    redis_kwargs,
    requests_session,
)


@pytest.fixture
def ca_pem(tmp_path):
    path = tmp_path / "ca.pem"
    trustme.CA().cert_pem.write_to_path(path)
    return path


@pytest.fixture
def activo(ca_pem):
    return TlsSettings(enabled=True, ca_file=ca_pem)


@pytest.mark.parametrize(
    "valor",
    ["\x00off", "off\x00", "of​f", "ｏｆｆ", "falsе", "0\x00", "nó", "​false"],
)
def test_valores_unicode_o_con_nul_no_apagan_tls(valor, ca_pem):
    settings = TlsSettings.from_env({"TLS_ENABLED": valor, "TLS_CA_FILE": str(ca_pem)})

    assert settings.enabled is True


@pytest.mark.parametrize("valor", [" off ", "\toff\n", " FALSE "])
def test_espacios_unicode_alrededor_si_se_recortan(valor):
    assert TlsSettings.from_env({"TLS_ENABLED": valor}).enabled is False


def test_ruta_de_ca_con_nul_falla_cerrado():
    with pytest.raises(TlsConfigError):
        TlsSettings.from_env({"TLS_CA_FILE": "a\x00b"})


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="sin FIFO")
def test_ca_que_es_una_fifo_falla_sin_bloquear(tmp_path):
    fifo = tmp_path / "ca.fifo"
    os.mkfifo(fifo)

    with pytest.raises(TlsConfigError):
        TlsSettings.from_env({"TLS_CA_FILE": str(fifo)})


def test_ca_enlace_simbolico_a_un_pem_valido_funciona(tmp_path, ca_pem):
    enlace = tmp_path / "enlace.pem"
    enlace.symlink_to(ca_pem)

    contexto = client_context(TlsSettings.from_env({"TLS_CA_FILE": str(enlace)}))

    assert contexto.verify_mode.name == "CERT_REQUIRED"


def test_ca_enlace_simbolico_roto_o_en_bucle_falla(tmp_path):
    roto = tmp_path / "roto.pem"
    roto.symlink_to(tmp_path / "no-existe.pem")
    bucle = tmp_path / "bucle.pem"
    bucle.symlink_to(bucle)

    for ruta in (roto, bucle):
        with pytest.raises(TlsConfigError):
            TlsSettings.from_env({"TLS_CA_FILE": str(ruta)})


def test_ca_enorme_sin_certificados_falla_con_error_de_config(tmp_path):
    enorme = tmp_path / "enorme.pem"
    enorme.write_bytes(b"A" * (32 * 1024 * 1024))

    with pytest.raises(TlsConfigError):
        client_context(TlsSettings(enabled=True, ca_file=enorme))


def test_ca_con_certificado_y_basura_detras_sigue_siendo_valida(tmp_path):
    ca = tmp_path / "mixto.pem"
    ca.write_bytes(trustme.CA().cert_pem.bytes() + b"\nbasura\n")

    assert client_context(TlsSettings(enabled=True, ca_file=ca)).check_hostname is True


def test_ca_con_solo_una_llave_privada_falla(tmp_path):
    ca = tmp_path / "llave.pem"
    ca.write_bytes(trustme.CA().private_key_pem.bytes())

    with pytest.raises(TlsConfigError):
        client_context(TlsSettings(enabled=True, ca_file=ca))


def test_el_error_de_ca_ilegible_no_filtra_la_ruta_ni_el_contenido(tmp_path):
    ca = tmp_path / "secreto-ca.pem"
    ca.write_text("CONTENIDO-SECRETO-DE-LA-CA")

    with pytest.raises(TlsConfigError) as error:
        client_context(TlsSettings(enabled=True, ca_file=ca))

    assert "CONTENIDO-SECRETO" not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize("url", ["https://u:contrasena-secreta@h", "HTTP://u:contrasena-secreta@h"])
def test_los_mensajes_de_exigir_cifrado_no_incluyen_la_url(activo, url):
    for argumentos in ({"coordinator_url": url}, {"redis_url": url}):
        try:
            exigir_cifrado(activo, **argumentos)
        except TlsConfigError as error:
            assert "contrasena-secreta" not in str(error)


@pytest.mark.parametrize("url", ["rediss+unix:///tmp/s.sock", "unix:///tmp/s.sock", "redis+unix:///s", " rediss://h", "rediss:/h"])
def test_exigir_cifrado_rechaza_esquemas_de_redis_raros(activo, url):
    with pytest.raises(TlsConfigError):
        exigir_cifrado(activo, redis_url=url)


@pytest.mark.parametrize("url", ["HTTPS://h:8443", "https://[::1]:8443/", "https://u:p@h/", "rediss://[::1]:6380/0", "RedisS://h"])
def test_exigir_cifrado_acepta_variantes_validas(activo, url):
    exigir_cifrado(activo, coordinator_url=url) if url.lower().startswith("https") else exigir_cifrado(activo, redis_url=url)


@pytest.mark.parametrize("url", ["https://", "https:///ruta", "https://:8443"])
@pytest.mark.xfail(strict=True, reason="exigir_cifrado solo mira el prefijo: acepta URL https sin host")
def test_exigir_cifrado_rechaza_url_https_sin_host(activo, url):
    with pytest.raises(TlsConfigError):
        exigir_cifrado(activo, coordinator_url=url)


@pytest.mark.parametrize("url", ["rediss://", "rediss:///0", "rediss://:6380"])
@pytest.mark.xfail(strict=True, reason="exigir_cifrado solo mira el prefijo: acepta rediss sin host")
def test_exigir_cifrado_rechaza_rediss_sin_host(activo, url):
    with pytest.raises(TlsConfigError):
        exigir_cifrado(activo, redis_url=url)


@pytest.mark.parametrize(
    "url",
    [
        "rediss://h:6380/0?ssl_cert_reqs=none",
        "rediss://h:6380/0?ssl_cert_reqs=optional",
        "rediss://h:6380/0?ssl_check_hostname=false",
    ],
)
@pytest.mark.xfail(strict=True, reason="la query de la URL de redis-py puede desactivar la verificacion y exigir_cifrado la acepta")
def test_exigir_cifrado_rechaza_redis_que_desactiva_la_verificacion(activo, url):
    with pytest.raises(TlsConfigError):
        exigir_cifrado(activo, redis_url=url)


@pytest.mark.parametrize("valor", [0, "false", "False", "no", ""])
@pytest.mark.xfail(strict=True, reason="minio_secure solo se rechaza si es exactamente False; 0 o 'false' pasan")
def test_exigir_cifrado_rechaza_minio_secure_falso_no_booleano(activo, valor):
    with pytest.raises(TlsConfigError):
        exigir_cifrado(activo, minio_secure=valor)


@pytest.mark.xfail(strict=True, reason="redis_kwargs con ca_file=None produce ssl_ca_certs='None' en vez de fallar cerrado")
def test_redis_kwargs_con_tls_activo_sin_ca_falla_cerrado():
    with pytest.raises(TlsConfigError):
        redis_kwargs(TlsSettings(enabled=True, ca_file=None))


@pytest.mark.xfail(strict=True, reason="requests_session con ca_file=None deja verify=None (CA del sistema o variable de entorno)")
def test_requests_session_con_tls_activo_sin_ca_falla_cerrado():
    with pytest.raises(TlsConfigError):
        requests_session(TlsSettings(enabled=True, ca_file=None))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos")
@pytest.mark.xfail(strict=True, reason="from_env solo comprueba is_file: una CA sin permiso de lectura se descubre al primer connect")
def test_from_env_con_ca_sin_permiso_de_lectura_falla_al_arrancar(tmp_path):
    ca = tmp_path / "ca.pem"
    trustme.CA().cert_pem.write_to_path(ca)
    ca.chmod(0)
    try:
        with pytest.raises(TlsConfigError):
            TlsSettings.from_env({"TLS_CA_FILE": str(ca)})
    finally:
        ca.chmod(0o600)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos")
def test_client_context_con_ca_sin_permiso_de_lectura_falla_cerrado(tmp_path):
    ca = tmp_path / "ca.pem"
    trustme.CA().cert_pem.write_to_path(ca)
    ca.chmod(0)
    try:
        with pytest.raises(TlsConfigError):
            client_context(TlsSettings(enabled=True, ca_file=ca))
    finally:
        ca.chmod(0o600)


@pytest.mark.xfail(strict=True, reason="requests_session y redis_kwargs no validan la CA: una CA corrupta solo falla al primer connect")
def test_requests_session_con_ca_corrupta_falla_al_construir(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("basura")
    with pytest.raises(TlsConfigError):
        requests_session(TlsSettings(enabled=True, ca_file=ca))


@pytest.mark.xfail(strict=True, reason="ca_file relativo se guarda tal cual: un chdir posterior (demonio, servicio) rompe la CA")
def test_ca_relativa_se_resuelve_al_leer_el_entorno(tmp_path, ca_pem, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = TlsSettings.from_env({"TLS_CA_FILE": "ca.pem"})
    monkeypatch.chdir("/")

    assert settings.ca_file.is_absolute()
