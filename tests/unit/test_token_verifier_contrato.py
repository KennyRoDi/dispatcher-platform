import secrets

import pytest

from src.adapters.jwt_tokens import JwtTokenVerifier, issue_token
from src.application.ports import Identity, InvalidToken, TokenVerifier
from src.domain.rbac import Role
from tests.contratos import comprobar_token_verifier
from tests.dobles import FakeClock, FakeTokenVerifier


def test_el_doble_cumple_el_puerto_y_el_contrato():
    identidad = Identity("ana", Role.ANALISTA)
    doble = FakeTokenVerifier({"tok-ana": identidad})
    comprobar_token_verifier(doble, "tok-ana", identidad, ["tok-otro", "basura"])


def test_el_adaptador_jwt_cumple_el_puerto_y_el_contrato():
    secreto = secrets.token_hex(32)
    reloj = FakeClock()
    token = issue_token(secreto, role=Role.SUPERVISOR, subject="sol", clock=reloj)
    verificador = JwtTokenVerifier(secreto, reloj)
    comprobar_token_verifier(
        verificador,
        token,
        Identity("sol", Role.SUPERVISOR),
        [token + "x", "basura", issue_token(secrets.token_hex(32), role=Role.SUPERVISOR, subject="sol", clock=reloj)],
    )


def test_el_adaptador_jwt_es_un_token_verifier():
    assert isinstance(JwtTokenVerifier(secrets.token_hex(32), FakeClock()), TokenVerifier)


def test_la_identidad_es_un_valor_inmutable_con_sujeto_y_rol():
    identidad = Identity("ana", Role.ANALISTA)
    assert (identidad.subject, identidad.role) == ("ana", Role.ANALISTA)
    assert identidad == Identity("ana", Role.ANALISTA)
    with pytest.raises(AttributeError):
        identidad.subject = "otra"


def test_token_invalido_es_una_excepcion_normal():
    assert issubclass(InvalidToken, Exception)
    assert not issubclass(InvalidToken, KeyError)

