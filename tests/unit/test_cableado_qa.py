import logging
import secrets
import subprocess

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from scripts.emitir_token import emitir
from scripts.emitir_token import main as emitir_main
from src.adapters.jwt_tokens import UtcClock, issue_token
from src.application.ports import Identity
from src.coordinator import conexion
from src.coordinator.seguridad import obtener_verificador
from src.domain.rbac import Role
from tests.dobles import FakeClock

SECRETO = secrets.token_hex(32)


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(conexion, "redis_client", fakeredis.FakeRedis(decode_responses=True))
    monkeypatch.setenv("JWT_SECRET", SECRETO)
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)


@pytest.mark.xfail(
    strict=True,
    reason="el middleware compara scope['path'] sin quitar root_path: con root_path /health da 401 y rompe el healthcheck tras un proxy con prefijo (falla cerrado, no es bypass)",
)
def test_la_ruta_publica_health_funciona_con_root_path():
    cliente = TestClient(main.crear_app({}), root_path="/api")
    assert cliente.get("/api/health").status_code == 200


@pytest.mark.xfail(
    strict=True,
    reason="AutenticacionPrevia y autorizar verifican la firma las dos: HMAC y decodificacion duplicados por peticion",
)
def test_el_token_se_verifica_una_sola_vez_por_peticion():
    llamadas = []

    class Contador:
        def verify(self, token):
            llamadas.append(token)
            return Identity("u", Role.SUPERVISOR)

    app = main.crear_app({})
    app.dependency_overrides[obtener_verificador] = Contador
    TestClient(app).get("/stats", headers={"Authorization": "Bearer x"})
    assert len(llamadas) == 1


@pytest.mark.xfail(
    strict=True,
    reason="desactivar la autenticacion con AUTH_ENABLED no deja ningun aviso en el registro",
)
def test_desactivar_la_autenticacion_se_registra_como_advertencia(caplog):
    with caplog.at_level(logging.WARNING):
        main.crear_app({"AUTH_ENABLED": "false"})
    assert any("autenticacion" in r.getMessage().lower() for r in caplog.records)


@pytest.mark.xfail(
    strict=True,
    reason="emitir acepta sub vacio o de espacios y produce un token que JwtTokenVerifier rechaza ('sub vacio')",
)
@pytest.mark.parametrize("sub", ["", "   "])
def test_emitir_rechaza_un_sub_que_el_verificador_no_aceptaria(sub):
    with pytest.raises(ValueError):
        emitir({"JWT_SECRET": SECRETO}, rol="analista", sub=sub, minutos=5, clock=FakeClock())


@pytest.mark.xfail(
    strict=True,
    reason="--minutos grande da OverflowError sin atrapar (traza) en vez de 'error: ...' y codigo 1",
)
@pytest.mark.parametrize("minutos", ["5000000000", "99999999999999"])
def test_minutos_extremos_terminan_con_error_limpio(minutos, capsys):
    codigo = emitir_main(
        ["--rol", "analista", "--sub", "x", "--minutos", minutos],
        env={"JWT_SECRET": SECRETO},
        clock=UtcClock(),
    )
    assert codigo == 1
    assert capsys.readouterr().err.startswith("error:")


@pytest.mark.xfail(
    strict=True,
    reason="un secreto en JWT_SECRET con byte invalido filtra el caracter y su posicion en el error de UnicodeEncodeError",
)
def test_un_secreto_no_utf8_no_filtra_bytes_en_el_error(capsys):
    secreto = "A" * 16 + "\udcff" + "z" * 40
    codigo = emitir_main(
        ["--rol", "analista", "--sub", "x"], env={"JWT_SECRET": secreto}, clock=UtcClock()
    )
    texto = capsys.readouterr()
    assert codigo == 1
    assert "udcff" not in texto.err and "position" not in texto.err


@pytest.mark.xfail(
    strict=True,
    reason=".gitignore solo cubre jwt.secret, *.key y .env: nombres habituales del secreto quedan versionables",
)
@pytest.mark.parametrize("nombre", ["jwt_secret", "jwt-secret", "jwt.secret.bak", "demo.secret", ".env.local", ".env.prod"])
def test_el_gitignore_cubre_nombres_habituales_del_secreto(nombre):
    resultado = subprocess.run(["git", "check-ignore", "-q", nombre], capture_output=True)
    assert resultado.returncode == 0


def test_los_tokens_con_cabecera_duplicada_usan_siempre_la_primera():
    token = issue_token(SECRETO, role=Role.SUPERVISOR, subject="u", clock=UtcClock())
    cliente = TestClient(main.crear_app({}))
    malo_primero = cliente.get("/stats", headers=[("Authorization", "Bearer x"), ("Authorization", f"Bearer {token}")])
    bueno_primero = cliente.get("/stats", headers=[("Authorization", f"Bearer {token}"), ("Authorization", "Bearer x")])
    assert (malo_primero.status_code, bueno_primero.status_code) == (401, 200)
