import base64
import hashlib
import hmac
import json
import logging
import secrets

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from src.adapters.jwt_tokens import JwtTokenVerifier
from src.application.ports import InvalidToken
from src.coordinator.seguridad import autorizar, obtener_verificador
from tests.dobles import FakeClock


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def token_firmado(secreto: str, payload: bytes) -> str:
    cuerpo = f"{_b64(b'{\"alg\":\"HS256\",\"typ\":\"JWT\"}')}.{_b64(payload)}"
    firma = hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).digest()
    return f"{cuerpo}.{_b64(firma)}"


def payload(reloj, **cambios):
    ahora = int(reloj.now().timestamp())
    base = {"sub": "u", "role": "analista", "iat": ahora, "exp": ahora + 600}
    return json.dumps({**base, **cambios}, allow_nan=True).encode()


@pytest.fixture
def secreto():
    return secrets.token_hex(32)


@pytest.fixture
def reloj():
    return FakeClock()


@pytest.mark.parametrize("campo", ["exp", "iat"])
def test_exp_o_iat_nan_se_rechazan(secreto, reloj, campo):
    token = token_firmado(secreto, payload(reloj, **{campo: float("nan")}))
    with pytest.raises(InvalidToken):
        JwtTokenVerifier(secreto, reloj).verify(token)


@pytest.mark.parametrize("sujeto", ["", " "])
def test_sub_vacio_se_rechaza(secreto, reloj, sujeto):
    token = token_firmado(secreto, payload(reloj, sub=sujeto))
    with pytest.raises(InvalidToken):
        JwtTokenVerifier(secreto, reloj).verify(token)


def test_archivo_de_secreto_no_utf8_no_filtra_bytes_al_log(tmp_path, monkeypatch, caplog):
    ruta = tmp_path / "llave"
    ruta.write_bytes(b"\xa7" + secrets.token_bytes(40))
    ruta.chmod(0o600)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET_FILE", str(ruta))
    with caplog.at_level(logging.DEBUG):
        obtener_verificador()
    assert "0xa7" not in caplog.text


def test_configuracion_invalida_no_inunda_el_log_por_peticion(monkeypatch, caplog):
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
    monkeypatch.setenv("JWT_SECRET", "corto")
    app = FastAPI()
    app.add_api_route("/x", lambda: {"ok": True}, dependencies=[Depends(autorizar)])
    cliente = TestClient(app)
    with caplog.at_level(logging.ERROR):
        for _ in range(20):
            assert cliente.get("/x").status_code == 401
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) <= 1


@pytest.mark.xfail(strict=True, reason="QA F-26: FastAPI parsea el cuerpo JSON antes de ejecutar la dependencia")
@pytest.mark.parametrize("cabecera", [None, "Bearer basura"])
def test_json_roto_sin_credenciales_validas_es_401_y_no_422(cabecera):
    app = FastAPI()
    router = APIRouter(dependencies=[Depends(autorizar)])

    def crear(cuerpo: dict) -> dict:
        return {"ok": True}

    router.add_api_route("/cases", crear, methods=["POST"])
    app.include_router(router)
    cabeceras = {"content-type": "application/json"}
    if cabecera:
        cabeceras["Authorization"] = cabecera
    respuesta = TestClient(app).post("/cases", content=b"{", headers=cabeceras)
    assert respuesta.status_code == 401
