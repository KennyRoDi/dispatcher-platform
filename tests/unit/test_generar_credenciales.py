from datetime import timedelta

import pytest

from scripts.generar_credenciales import main
from src.adapters.jwt_tokens import JwtTokenVerifier
from src.application.ports import InvalidToken
from src.domain.rbac import Role
from tests.dobles import FakeClock


def _leer(ruta) -> dict[str, str]:
    return dict(linea.split("=", 1) for linea in ruta.read_text(encoding="utf-8").splitlines() if "=" in linea)


@pytest.fixture
def reloj():
    return FakeClock()


def test_escribe_secreto_y_tokens_con_los_roles_correctos(tmp_path, reloj):
    destino = tmp_path / ".env"
    assert main(["--env", str(destino)], clock=reloj) == 0
    valores = _leer(destino)
    assert len(valores["JWT_SECRET"]) >= 64
    verificador = JwtTokenVerifier(valores["JWT_SECRET"], reloj)
    assert verificador.verify(valores["WORKER_TOKEN"]).role is Role.SERVICIO
    assert verificador.verify(valores["API_TOKEN"]).role is Role.ADMINISTRADOR


def test_no_imprime_ningun_valor(tmp_path, reloj, capsys):
    destino = tmp_path / ".env"
    main(["--env", str(destino)], clock=reloj)
    salida = capsys.readouterr()
    for valor in _leer(destino).values():
        assert valor not in salida.out + salida.err


def test_conserva_las_demas_lineas_y_reutiliza_el_secreto(tmp_path, reloj):
    destino = tmp_path / ".env"
    destino.write_text("REDIS_PASSWORD=abc\nJWT_SECRET=" + "a" * 64 + "\nOTRA=1\n", encoding="utf-8")
    main(["--env", str(destino)], clock=reloj)
    valores = _leer(destino)
    assert valores["REDIS_PASSWORD"] == "abc" and valores["OTRA"] == "1"
    assert valores["JWT_SECRET"] == "a" * 64
    JwtTokenVerifier("a" * 64, reloj).verify(valores["WORKER_TOKEN"])


def test_rotar_cambia_el_secreto_e_invalida_los_tokens_anteriores(tmp_path, reloj):
    destino = tmp_path / ".env"
    main(["--env", str(destino)], clock=reloj)
    antes = _leer(destino)
    main(["--env", str(destino), "--rotar"], clock=reloj)
    despues = _leer(destino)
    assert despues["JWT_SECRET"] != antes["JWT_SECRET"]
    with pytest.raises(InvalidToken):
        JwtTokenVerifier(despues["JWT_SECRET"], reloj).verify(antes["WORKER_TOKEN"])


def test_la_vigencia_se_da_en_dias(tmp_path, reloj):
    destino = tmp_path / ".env"
    main(["--env", str(destino), "--dias", "2"], clock=reloj)
    valores = _leer(destino)
    verificador = JwtTokenVerifier(valores["JWT_SECRET"], reloj)
    reloj.advance(timedelta(days=1, hours=23))
    verificador.verify(valores["WORKER_TOKEN"])
    reloj.advance(timedelta(hours=2))
    with pytest.raises(InvalidToken):
        verificador.verify(valores["WORKER_TOKEN"])


def test_solo_worker_no_lleva_el_secreto_ni_el_token_de_administrador(tmp_path, reloj):
    destino, nodo = tmp_path / ".env", tmp_path / "worker.env"
    main(["--env", str(destino), "--solo-worker", str(nodo)], clock=reloj)
    assert list(_leer(nodo)) == ["WORKER_TOKEN"]
    assert _leer(nodo)["WORKER_TOKEN"] == _leer(destino)["WORKER_TOKEN"]


@pytest.mark.parametrize("dias", ["0", "-3", "x"])
def test_dias_invalidos_se_rechazan(tmp_path, dias):
    with pytest.raises(SystemExit):
        main(["--env", str(tmp_path / ".env"), "--dias", dias])
