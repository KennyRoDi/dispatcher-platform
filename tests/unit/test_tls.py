import logging
import ssl

import pytest
import redis
import requests
import trustme
import urllib3

from src.infrastructure.tls import (
    TlsConfigError,
    TlsSettings,
    client_context,
    exigir_cifrado,
    minio_http_client,
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


@pytest.fixture
def apagado():
    return TlsSettings(enabled=False, ca_file=None)


def test_tls_activo_por_defecto_con_ca(ca_pem):
    settings = TlsSettings.from_env({"TLS_CA_FILE": str(ca_pem)})

    assert settings.enabled is True
    assert settings.ca_file == ca_pem


def test_from_env_sin_argumento_lee_el_entorno_del_proceso(monkeypatch, ca_pem):
    monkeypatch.delenv("TLS_ENABLED", raising=False)
    monkeypatch.setenv("TLS_CA_FILE", str(ca_pem))

    settings = TlsSettings.from_env()

    assert settings.enabled is True
    assert settings.ca_file == ca_pem


@pytest.mark.parametrize("valor", ["0", "false", "no", "off", "FALSE", "Off", " no "])
def test_solo_estos_valores_apagan_tls(valor):
    settings = TlsSettings.from_env({"TLS_ENABLED": valor})

    assert settings.enabled is False


@pytest.mark.parametrize("valor", ["1", "true", "yes", "on", "", "2", "talvez", "falso", "disabled"])
def test_valores_raros_dejan_tls_activo(valor, ca_pem):
    settings = TlsSettings.from_env({"TLS_ENABLED": valor, "TLS_CA_FILE": str(ca_pem)})

    assert settings.enabled is True


def test_tls_apagado_no_exige_ca():
    settings = TlsSettings.from_env({"TLS_ENABLED": "false"})

    assert settings.enabled is False
    assert settings.ca_file is None


def test_tls_apagado_avisa_en_el_registro(caplog):
    with caplog.at_level(logging.WARNING):
        TlsSettings.from_env({"TLS_ENABLED": "false"})

    assert any(
        r.levelno >= logging.WARNING and "TLS" in r.getMessage() for r in caplog.records
    )


@pytest.mark.parametrize("env", [{}, {"TLS_CA_FILE": ""}, {"TLS_CA_FILE": "   "}])
def test_tls_activo_sin_ca_falla(env):
    with pytest.raises(TlsConfigError, match="TLS_CA_FILE"):
        TlsSettings.from_env(env)


def test_la_falla_de_config_es_value_error():
    assert issubclass(TlsConfigError, ValueError)


def test_ca_inexistente_falla(tmp_path):
    with pytest.raises(TlsConfigError, match="TLS_CA_FILE"):
        TlsSettings.from_env({"TLS_CA_FILE": str(tmp_path / "no-existe.pem")})


def test_ca_que_es_un_directorio_falla(tmp_path):
    with pytest.raises(TlsConfigError):
        TlsSettings.from_env({"TLS_CA_FILE": str(tmp_path)})


@pytest.mark.parametrize("contenido", [b"", b"esto no es pem\n", b"-----BEGIN CERTIFICATE-----\nbasura\n-----END CERTIFICATE-----\n"])
def test_ca_vacia_o_corrupta_falla(tmp_path, contenido):
    ruta = tmp_path / "ca.pem"
    ruta.write_bytes(contenido)

    with pytest.raises(TlsConfigError):
        client_context(TlsSettings.from_env({"TLS_CA_FILE": str(ruta)}))


def test_el_error_de_ca_corrupta_no_filtra_el_contenido(tmp_path):
    ruta = tmp_path / "ca.pem"
    cabecera = "-----BEGIN " + "PRIVATE KEY-----"
    ruta.write_text(f"{cabecera}\nLLAVE-SECRETA-123\n-----END PRIVATE KEY-----\n")

    with pytest.raises(TlsConfigError) as error:
        client_context(TlsSettings(enabled=True, ca_file=ruta))

    assert "LLAVE-SECRETA-123" not in str(error.value)
    assert "PRIVATE KEY" not in str(error.value)


def test_contexto_exige_tls13_cert_requerido_y_hostname(activo):
    contexto = client_context(activo)

    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.minimum_version == ssl.TLSVersion.TLSv1_3
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_contexto_confia_en_la_ca_dada(activo):
    contexto = client_context(activo)

    assert len(contexto.get_ca_certs()) == 1


def test_contexto_sin_tls_no_degrada_a_claro(apagado):
    with pytest.raises(TlsConfigError):
        client_context(apagado)


@pytest.mark.parametrize(
    "argumentos",
    [
        {"coordinator_url": "http://coordinador:8443"},
        {"coordinator_url": "HTTP://coordinador:8443"},
        {"coordinator_url": "coordinador:8443"},
        {"redis_url": "redis://redis:6380/0"},
        {"redis_url": "REDIS://redis:6380/0"},
        {"minio_secure": False},
    ],
)
def test_exigir_cifrado_rechaza_http_redis_plano_y_minio_inseguro(activo, argumentos):
    with pytest.raises(ValueError):
        exigir_cifrado(activo, **argumentos)


def test_exigir_cifrado_acepta_transporte_cifrado(activo):
    exigir_cifrado(
        activo,
        coordinator_url="https://coordinador:8443",
        redis_url="rediss://redis:6380/0",
        minio_secure=True,
    )


def test_exigir_cifrado_ignora_lo_no_informado(activo):
    exigir_cifrado(activo)


def test_exigir_cifrado_rechaza_aunque_lo_demas_sea_cifrado(activo):
    with pytest.raises(ValueError):
        exigir_cifrado(
            activo,
            coordinator_url="https://coordinador:8443",
            redis_url="rediss://redis:6380/0",
            minio_secure=False,
        )


def test_el_rechazo_no_filtra_credenciales_de_la_url(activo):
    with pytest.raises(ValueError) as error:
        exigir_cifrado(activo, redis_url="redis://usuario:CLAVE-SECRETA@redis:6379/0")

    assert "CLAVE-SECRETA" not in str(error.value)


def test_sin_tls_exigir_cifrado_no_cambia_el_comportamiento(apagado):
    exigir_cifrado(
        apagado,
        coordinator_url="http://coordinador:8000",
        redis_url="redis://redis:6379/0",
        minio_secure=False,
    )


def test_kwargs_de_redis_con_tls(activo, ca_pem):
    kwargs = redis_kwargs(activo)

    assert kwargs["ssl"] is True
    assert kwargs["ssl_ca_certs"] == str(ca_pem)
    assert kwargs["ssl_cert_reqs"] == "required"
    assert kwargs["ssl_check_hostname"] is True
    assert kwargs["ssl_min_version"] == ssl.TLSVersion.TLSv1_3


def test_kwargs_de_redis_construyen_un_cliente_ssl(activo):
    cliente = redis.Redis(host="redis", port=6380, **redis_kwargs(activo))

    assert issubclass(cliente.connection_pool.connection_class, redis.SSLConnection)


def test_requests_session_verifica_contra_la_ca(activo, ca_pem):
    sesion = requests_session(activo)

    assert isinstance(sesion, requests.Session)
    assert sesion.verify == str(ca_pem)


def test_minio_http_client_usa_el_contexto_tls(activo):
    cliente = minio_http_client(activo)

    assert isinstance(cliente, urllib3.PoolManager)
    contexto = cliente.connection_pool_kw["ssl_context"]
    assert contexto.minimum_version == ssl.TLSVersion.TLSv1_3
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_sin_tls_el_comportamiento_no_cambia(apagado):
    assert redis_kwargs(apagado) == {}
    assert minio_http_client(apagado) is None
    assert requests_session(apagado).verify is True


def test_worker_con_tls_desactivado_no_exige_ca():
    from src.workers.config import Settings, make_redis

    settings = Settings.from_env({"TLS_ENABLED": "false"})
    pool = make_redis(settings, TlsSettings.from_env({"TLS_ENABLED": "false"})).connection_pool
    assert "ssl_ca_certs" not in pool.connection_kwargs
    assert pool.connection_class.__name__ == "Connection"
