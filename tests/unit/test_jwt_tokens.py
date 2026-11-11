import base64
import json
import secrets
from datetime import timedelta

import jwt
import pytest

from src.adapters.jwt_tokens import JwtTokenVerifier, issue_token, verificador_desde_entorno
from src.application.ports import Identity, InvalidToken, TokenVerifier
from src.domain.rbac import Action, Role, can
from tests.dobles import FakeClock


@pytest.fixture
def secreto():
    return secrets.token_hex(32)


@pytest.fixture
def reloj():
    return FakeClock()


@pytest.fixture
def verificador(secreto, reloj):
    return JwtTokenVerifier(secreto, reloj)


def reclamos(reloj, **cambios):
    ahora = int(reloj.now().timestamp())
    base = {"sub": "ana", "role": "analista", "iat": ahora, "exp": ahora + 3600}
    base.update(cambios)
    return {nombre: valor for nombre, valor in base.items() if valor is not None}


def firmar(secreto, reclamos_, algoritmo="HS256"):
    return jwt.encode(reclamos_, secreto, algorithm=algoritmo)


def base64url(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


@pytest.mark.parametrize("rol", list(Role))
def test_token_emitido_se_verifica_con_su_sujeto_y_rol(secreto, reloj, verificador, rol):
    token = issue_token(secreto, role=rol, subject="demo", clock=reloj)
    assert verificador.verify(token) == Identity("demo", rol)


def test_el_token_dura_60_minutos_por_defecto(secreto, reloj, verificador):
    token = issue_token(secreto, role=Role.ANALISTA, subject="demo", clock=reloj)
    reloj.advance(timedelta(minutes=59, seconds=59))
    assert verificador.verify(token).subject == "demo"
    reloj.advance(timedelta(seconds=2))
    with pytest.raises(InvalidToken):
        verificador.verify(token)


def test_la_duracion_se_puede_cambiar(secreto, reloj, verificador):
    token = issue_token(secreto, role=Role.ANALISTA, subject="demo", clock=reloj, minutes=5)
    reloj.advance(timedelta(minutes=4))
    verificador.verify(token)
    reloj.advance(timedelta(minutes=2))
    with pytest.raises(InvalidToken):
        verificador.verify(token)


def test_el_token_emitido_lleva_los_cuatro_reclamos_obligatorios(secreto, reloj):
    token = issue_token(secreto, role=Role.SUPERVISOR, subject="sol", clock=reloj, minutes=10)
    contenido = jwt.decode(token, secreto, algorithms=["HS256"], options={"verify_exp": False, "verify_iat": False})
    ahora = int(reloj.now().timestamp())
    assert contenido == {"sub": "sol", "role": "supervisor", "iat": ahora, "exp": ahora + 600}


def test_se_usa_el_reloj_inyectado_y_no_el_real(secreto, reloj, verificador):
    token = firmar(secreto, reclamos(reloj))
    assert verificador.verify(token).subject == "ana"


def test_token_expirado_es_invalido(secreto, reloj, verificador):
    ahora = int(reloj.now().timestamp())
    with pytest.raises(InvalidToken):
        verificador.verify(firmar(secreto, reclamos(reloj, iat=ahora - 7200, exp=ahora - 1)))


def test_no_hay_tolerancia_de_reloj(secreto, reloj, verificador):
    ahora = int(reloj.now().timestamp())
    token = firmar(secreto, reclamos(reloj, exp=ahora + 10))
    reloj.advance(timedelta(seconds=11))
    with pytest.raises(InvalidToken):
        verificador.verify(token)


def test_firma_de_otro_secreto_es_invalida(reloj, verificador):
    token = firmar(secrets.token_hex(32), reclamos(reloj))
    with pytest.raises(InvalidToken):
        verificador.verify(token)


def test_contenido_alterado_con_la_firma_original_es_invalido(secreto, reloj, verificador):
    cabecera, _, firma = firmar(secreto, reclamos(reloj)).split(".")
    alterado = base64url(json.dumps(reclamos(reloj, role="administrador")).encode())
    with pytest.raises(InvalidToken):
        verificador.verify(f"{cabecera}.{alterado}.{firma}")


def test_algoritmo_none_es_invalido(reloj, verificador):
    with pytest.raises(InvalidToken):
        verificador.verify(jwt.encode(reclamos(reloj), None, algorithm="none"))


def test_algoritmo_none_armado_a_mano_es_invalido(reloj, verificador):
    cabecera = base64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    contenido = base64url(json.dumps(reclamos(reloj, role="administrador")).encode())
    with pytest.raises(InvalidToken):
        verificador.verify(f"{cabecera}.{contenido}.")


@pytest.mark.parametrize("algoritmo", ["HS384", "HS512"])
def test_otro_algoritmo_hmac_con_el_mismo_secreto_es_invalido(secreto, reloj, verificador, algoritmo):
    with pytest.raises(InvalidToken):
        verificador.verify(firmar(secreto, reclamos(reloj), algoritmo))


@pytest.mark.parametrize("faltante", ["sub", "role", "iat", "exp"])
def test_reclamo_obligatorio_ausente_es_invalido(secreto, reloj, verificador, faltante):
    with pytest.raises(InvalidToken):
        verificador.verify(firmar(secreto, reclamos(reloj, **{faltante: None})))


@pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c", "....", "Bearer abc", " "])
def test_token_mal_formado_es_invalido(verificador, token):
    with pytest.raises(InvalidToken):
        verificador.verify(token)


@pytest.mark.parametrize("rol", ["root", "ADMINISTRADOR", "", "supervisor "])
def test_rol_desconocido_se_autentica_pero_sin_permisos(secreto, reloj, verificador, rol):
    identidad = verificador.verify(firmar(secreto, reclamos(reloj, role=rol)))
    assert identidad.subject == "ana"
    assert not any(can(identidad.role, accion) for accion in Action)


def test_secreto_de_32_bytes_se_acepta(reloj):
    assert isinstance(JwtTokenVerifier(secrets.token_hex(16), reloj), TokenVerifier)


@pytest.mark.parametrize("longitud", [0, 1, 31])
def test_secreto_corto_se_rechaza(reloj, longitud):
    with pytest.raises(ValueError):
        JwtTokenVerifier(secrets.token_hex(16)[:longitud], reloj)


def test_el_error_por_secreto_corto_no_revela_el_secreto(reloj):
    corto = secrets.token_hex(16)[:31]
    with pytest.raises(ValueError) as error:
        JwtTokenVerifier(corto, reloj)
    assert corto not in str(error.value)


def test_sin_secreto_no_se_construye_el_verificador(reloj):
    with pytest.raises(ValueError):
        JwtTokenVerifier(None, reloj)


def test_no_se_emiten_tokens_con_secreto_corto(reloj):
    with pytest.raises(ValueError):
        issue_token(secrets.token_hex(15), role=Role.ANALISTA, subject="demo", clock=reloj)


def test_sin_ninguna_variable_se_falla_cerrado(reloj):
    verificador = verificador_desde_entorno({}, reloj)
    assert isinstance(verificador, TokenVerifier)
    token = issue_token(secrets.token_hex(32), role=Role.ADMINISTRADOR, subject="demo", clock=reloj)
    for candidato in (token, "", "basura"):
        with pytest.raises(InvalidToken):
            verificador.verify(candidato)


def test_secreto_por_variable_de_desarrollo(secreto, reloj):
    verificador = verificador_desde_entorno({"JWT_SECRET": secreto}, reloj)
    token = issue_token(secreto, role=Role.ANALISTA, subject="demo", clock=reloj)
    assert verificador.verify(token) == Identity("demo", Role.ANALISTA)


def test_secreto_corto_por_variable_se_rechaza(reloj):
    with pytest.raises(ValueError):
        verificador_desde_entorno({"JWT_SECRET": secrets.token_hex(15)}, reloj)


def secreto_en_archivo(tmp_path, contenido, modo):
    archivo = tmp_path / "jwt.key"
    archivo.write_text(contenido)
    archivo.chmod(modo)
    return str(archivo)


def test_secreto_desde_archivo_con_permisos_0400(tmp_path, secreto, reloj):
    ruta = secreto_en_archivo(tmp_path, secreto, 0o400)
    verificador = verificador_desde_entorno({"JWT_SECRET_FILE": ruta}, reloj)
    token = issue_token(secreto, role=Role.SUPERVISOR, subject="sol", clock=reloj)
    assert verificador.verify(token) == Identity("sol", Role.SUPERVISOR)


def test_el_salto_de_linea_final_del_archivo_no_forma_parte_del_secreto(tmp_path, secreto, reloj):
    ruta = secreto_en_archivo(tmp_path, secreto + "\n", 0o400)
    verificador = verificador_desde_entorno({"JWT_SECRET_FILE": ruta}, reloj)
    token = issue_token(secreto, role=Role.ANALISTA, subject="demo", clock=reloj)
    assert verificador.verify(token).subject == "demo"


@pytest.mark.parametrize("modo", [0o644, 0o640, 0o604, 0o666])
def test_archivo_de_secreto_legible_por_otros_se_rechaza(tmp_path, secreto, reloj, modo):
    ruta = secreto_en_archivo(tmp_path, secreto, modo)
    with pytest.raises(ValueError):
        verificador_desde_entorno({"JWT_SECRET_FILE": ruta}, reloj)


def test_archivo_con_secreto_corto_se_rechaza(tmp_path, reloj):
    ruta = secreto_en_archivo(tmp_path, secrets.token_hex(15), 0o400)
    with pytest.raises(ValueError):
        verificador_desde_entorno({"JWT_SECRET_FILE": ruta}, reloj)


def test_archivo_inexistente_se_rechaza(tmp_path, reloj):
    with pytest.raises(ValueError):
        verificador_desde_entorno({"JWT_SECRET_FILE": str(tmp_path / "no-existe")}, reloj)


def test_el_archivo_tiene_prioridad_sobre_la_variable(tmp_path, reloj):
    del_archivo, de_la_variable = secrets.token_hex(32), secrets.token_hex(32)
    ruta = secreto_en_archivo(tmp_path, del_archivo, 0o400)
    verificador = verificador_desde_entorno({"JWT_SECRET_FILE": ruta, "JWT_SECRET": de_la_variable}, reloj)
    verificador.verify(issue_token(del_archivo, role=Role.ANALISTA, subject="demo", clock=reloj))
    with pytest.raises(InvalidToken):
        verificador.verify(issue_token(de_la_variable, role=Role.ANALISTA, subject="demo", clock=reloj))
