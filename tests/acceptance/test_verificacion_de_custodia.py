import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from tests.ayudas_custodia import (
    CONTENIDO_A,
    CONTENIDO_B,
    RESULTADO_A,
    RESULTADO_A2,
    alterar_actor,
    escribir_lineas,
    escribir_llave,
    escribir_objetos,
    lineas_de,
    log_en_disco,
    sha,
)

pytestmark = pytest.mark.acceptance

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def escenario(tmp_path):
    llave = escribir_llave(tmp_path / "custodia.custody-key", os.urandom(32))
    log = tmp_path / "custodia.jsonl"
    ancla = log_en_disco(log, llave.read_bytes())
    objetos = escribir_objetos(tmp_path / "objetos", CONTENIDO_A, CONTENIDO_B, RESULTADO_A, RESULTADO_A2)
    return llave, log, ancla, objetos


def verificar(llave, log, ancla, objetos):
    entorno = {**os.environ, "PYTHONPATH": str(RAIZ)}
    entorno.pop("CUSTODY_KEY_FILE", None)
    if llave is not None:
        entorno["CUSTODY_KEY_FILE"] = str(llave)
    comando = [sys.executable, "-m", "scripts.verify_custody", "--log", str(log), "--anchor", str(ancla), "--store", str(objetos)]
    return subprocess.run(comando, cwd=RAIZ, env=entorno, capture_output=True, text=True, timeout=60)


def salida(resultado):
    return resultado.stdout + resultado.stderr


def test_antes_de_manipular_el_verificador_pasa(escenario):
    resultado = verificar(*escenario)
    assert resultado.returncode == 0, salida(resultado)
    assert "ok" in salida(resultado).lower()


def test_tras_alterar_una_entrada_del_log_falla_e_indica_la_posicion(escenario):
    llave, log, ancla, objetos = escenario
    lineas = lineas_de(log)
    lineas[1] = alterar_actor(lineas[1])
    escribir_lineas(log, lineas)
    resultado = verificar(llave, log, ancla, objetos)
    assert resultado.returncode != 0
    assert [linea for linea in salida(resultado).splitlines() if "2" in linea and "sello" in linea]


def test_tras_truncar_el_log_falla_e_indica_la_posicion(escenario):
    llave, log, ancla, objetos = escenario
    escribir_lineas(log, lineas_de(log)[:2])
    resultado = verificar(llave, log, ancla, objetos)
    assert resultado.returncode != 0
    assert [linea for linea in salida(resultado).splitlines() if "4" in linea and "truncado" in linea]


def test_tras_alterar_una_evidencia_falla_e_indica_posicion_y_hash(escenario):
    llave, log, ancla, objetos = escenario
    (objetos / sha(CONTENIDO_A)).write_bytes(b"evidencia manipulada")
    resultado = verificar(llave, log, ancla, objetos)
    assert resultado.returncode != 0
    assert [linea for linea in salida(resultado).splitlines() if "1" in linea and sha(CONTENIDO_A) in linea]


def test_sin_llave_el_verificador_falla_cerrado(escenario):
    _, log, ancla, objetos = escenario
    resultado = verificar(None, log, ancla, objetos)
    assert resultado.returncode == 2
    assert "ok" not in salida(resultado).lower().split()
