"""Hallazgos del QA sobre el verificador de custodia (F-29 parte 3), todos con xfail estricto."""

import os

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

import scripts.verify_custody as cli
from scripts.verify_custody import main
from src.adapters.jsonl_custody_log import JsonlCustodyLog
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
    registrar_pasos,
    sha,
)
from tests.dobles import FakeClock


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def entorno(tmp_path, llave, monkeypatch):
    ruta_llave = escribir_llave(tmp_path / "custodia.custody-key", llave)
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(ruta_llave))
    log = tmp_path / "custodia.jsonl"
    ancla = log_en_disco(log, llave)
    objetos = escribir_objetos(tmp_path / "objetos", CONTENIDO_A, CONTENIDO_B, RESULTADO_A, RESULTADO_A2)
    return log, ancla, objetos


def ejecutar(capsys, *argumentos):
    try:
        codigo = main([str(argumento) for argumento in argumentos])
    except SystemExit as salida:
        codigo = salida.code
    captura = capsys.readouterr()
    return codigo, captura.out + captura.err


def test_un_log_con_bytes_utf8_invalidos_no_pasa(tmp_path, llave, monkeypatch, capsys):
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(escribir_llave(tmp_path / "k.custody-key", llave)))
    log = tmp_path / "log.jsonl"
    JsonlCustodyLog(log, llave, FakeClock()).record(sha(CONTENIDO_A), "ingreso", sha(CONTENIDO_A), "ac�tor")
    crudo = log.read_bytes()
    assert b"\xef\xbf\xbd" in crudo
    log.write_bytes(crudo.replace(b"\xef\xbf\xbd", b"\xff"))
    ancla = log.with_name(log.name + ".head")
    codigo, _ = ejecutar(capsys, "--log", log, "--anchor", ancla)
    assert codigo not in (0, None)


def test_un_anexo_legitimo_durante_la_verificacion_no_es_truncado(entorno, llave, capsys, monkeypatch):
    log, ancla, _ = entorno
    leer = cli._read_lines

    def leer_y_luego_anexar(ruta):
        lineas = leer(ruta)
        registrar_pasos(JsonlCustodyLog(log, llave, FakeClock()), [(CONTENIDO_B, "ingreso", CONTENIDO_B, "recepcion")])
        return lineas

    monkeypatch.setattr(cli, "_read_lines", leer_y_luego_anexar)
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla)
    assert codigo == 0, salida


@pytest.mark.xfail(
    strict=True,
    reason="QA-3 (baja): con una llave mal formada el mensaje habla de KEK_FILE/KEK (texto de F-28) aunque la "
    "variable es CUSTODY_KEY_FILE; el CLI no traduce el error",
)
def test_el_error_de_llave_nombra_la_variable_de_custodia(entorno, tmp_path, llave, capsys, monkeypatch):
    log, ancla, _ = entorno
    abierta = escribir_llave(tmp_path / "abierta.custody-key", llave, modo=0o644)
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(abierta))
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla)
    assert codigo == 2
    assert "CUSTODY_KEY_FILE" in salida


@pytest.mark.xfail(
    strict=True,
    reason="QA-4 (baja): un objeto ilegible (PermissionError) aborta con exit 2 y se pierden las violaciones de "
    "cadena ya encontradas (aquí el sello de la entrada 4); el fallo es cerrado pero el informe es incompleto",
)
@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos de archivo")
def test_un_objeto_ilegible_no_oculta_la_violacion_de_cadena(entorno, capsys):
    log, ancla, objetos = entorno
    lineas = lineas_de(log)
    lineas[3] = alterar_actor(lineas[3])
    escribir_lineas(log, lineas)
    objeto = objetos / sha(CONTENIDO_A)
    objeto.chmod(0)
    try:
        _, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    finally:
        objeto.chmod(0o644)
    assert "sello" in salida
