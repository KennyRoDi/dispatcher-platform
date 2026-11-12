import os
import secrets
import stat
from datetime import datetime, timedelta, timezone

import pytest

from scripts.emitir_token import emitir, main
from src.adapters.jwt_tokens import JwtTokenVerifier
from src.domain.rbac import Role
from tests.dobles import FakeClock

SECRETO = secrets.token_hex(32)
INICIO = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def reloj():
    return FakeClock(INICIO)


def verificar(token, reloj, secreto=SECRETO):
    return JwtTokenVerifier(secreto, reloj).verify(token)


@pytest.mark.parametrize("rol", list(Role))
def test_emitir_produce_un_token_que_el_verificador_acepta(rol, reloj):
    token = emitir({"JWT_SECRET": SECRETO}, rol=rol.value, sub="demo", minutos=30, clock=reloj)
    identidad = verificar(token, reloj)
    assert (identidad.subject, identidad.role) == ("demo", rol)


def test_emitir_respeta_los_minutos_de_expiracion(reloj):
    token = emitir({"JWT_SECRET": SECRETO}, rol="analista", sub="demo", minutos=30, clock=reloj)
    reloj.advance(timedelta(minutes=29))
    assert verificar(token, reloj).subject == "demo"
    reloj.advance(timedelta(minutes=1))
    with pytest.raises(Exception):
        verificar(token, reloj)


@pytest.mark.skipif(os.name == "nt", reason="os.O_NONBLOCK y permisos de archivo")
def test_emitir_lee_el_secreto_del_archivo_antes_que_de_la_variable(tmp_path, reloj):
    archivo = tmp_path / "jwt.key"
    archivo.write_text(SECRETO + "\n")
    archivo.chmod(stat.S_IRUSR)
    entorno = {"JWT_SECRET_FILE": str(archivo), "JWT_SECRET": secrets.token_hex(32)}
    token = emitir(entorno, rol="supervisor", sub="s", minutos=5, clock=reloj)
    assert verificar(token, reloj).role is Role.SUPERVISOR


def test_emitir_rechaza_rol_desconocido(reloj):
    with pytest.raises(ValueError):
        emitir({"JWT_SECRET": SECRETO}, rol="root", sub="demo", minutos=5, clock=reloj)


@pytest.mark.parametrize("entorno", [{}, {"JWT_SECRET": ""}, {"JWT_SECRET": "corto"}])
def test_emitir_sin_secreto_valido_falla(entorno, reloj):
    with pytest.raises(ValueError):
        emitir(entorno, rol="analista", sub="demo", minutos=5, clock=reloj)


def test_main_imprime_solo_el_token_en_salida_estandar(capsys, reloj):
    codigo = main(
        ["--rol", "analista", "--sub", "demo", "--minutos", "30"],
        env={"JWT_SECRET": SECRETO},
        clock=reloj,
    )
    salida = capsys.readouterr()
    assert codigo == 0
    assert verificar(salida.out.strip(), reloj).subject == "demo"
    assert SECRETO not in salida.out + salida.err


def test_main_usa_60_minutos_por_defecto(capsys, reloj):
    main(["--rol", "analista", "--sub", "demo"], env={"JWT_SECRET": SECRETO}, clock=reloj)
    token = capsys.readouterr().out.strip()
    reloj.advance(timedelta(minutes=59))
    assert verificar(token, reloj).subject == "demo"
    reloj.advance(timedelta(minutes=1))
    with pytest.raises(Exception):
        verificar(token, reloj)


def test_main_rol_invalido_sale_con_error_de_uso(capsys):
    with pytest.raises(SystemExit) as salida:
        main(["--rol", "root", "--sub", "demo"], env={"JWT_SECRET": SECRETO})
    assert salida.value.code == 2
    assert capsys.readouterr().out == ""


def test_main_exige_rol_y_sub():
    with pytest.raises(SystemExit):
        main(["--sub", "demo"], env={"JWT_SECRET": SECRETO})
    with pytest.raises(SystemExit):
        main(["--rol", "analista"], env={"JWT_SECRET": SECRETO})


def test_main_sin_secreto_falla_sin_token_ni_traza(capsys, reloj):
    codigo = main(["--rol", "analista", "--sub", "demo"], env={}, clock=reloj)
    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert "JWT_SECRET" in salida.err
    assert "Traceback" not in salida.err


def test_main_con_secreto_corto_no_lo_imprime(capsys, reloj):
    codigo = main(["--rol", "analista", "--sub", "demo"], env={"JWT_SECRET": "abc123corto"}, clock=reloj)
    salida = capsys.readouterr()
    assert codigo == 1
    assert "abc123corto" not in salida.out + salida.err


@pytest.mark.parametrize("minutos", ["0", "-5", "abc"])
def test_main_minutos_invalidos_es_error_de_uso(minutos):
    with pytest.raises(SystemExit) as salida:
        main(["--rol", "analista", "--sub", "demo", "--minutos", minutos], env={"JWT_SECRET": SECRETO})
    assert salida.value.code == 2
