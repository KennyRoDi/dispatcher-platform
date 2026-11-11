import os

import pytest

from scripts.verify_custody import main
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


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def entorno(tmp_path, llave, monkeypatch):
    ruta_llave = escribir_llave(tmp_path / "custodia.custody-key", llave)
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(ruta_llave))
    log = tmp_path / "custodia.jsonl"
    ancla = log_en_disco(log, llave)
    return log, ancla, escribir_objetos(tmp_path / "objetos", CONTENIDO_A, CONTENIDO_B, RESULTADO_A, RESULTADO_A2)


def ejecutar(capsys, *argumentos):
    try:
        codigo = main([str(argumento) for argumento in argumentos])
    except SystemExit as salida:
        codigo = salida.code
    captura = capsys.readouterr()
    return codigo, captura.out + captura.err


def lineas_con(salida, *textos):
    return [linea for linea in salida.splitlines() if all(texto in linea for texto in textos)]


def test_cadena_sana_sale_con_cero(entorno, capsys):
    log, ancla, objetos = entorno
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 0
    assert "ok" in salida.lower()


def test_sin_store_no_se_comprueba_la_evidencia(entorno, capsys):
    log, ancla, objetos = entorno
    (objetos / sha(CONTENIDO_A)).write_bytes(b"manipulada")
    assert ejecutar(capsys, "--log", log, "--anchor", ancla)[0] == 0


def test_entrada_alterada_sale_distinto_de_cero_con_posicion_y_motivo(entorno, capsys):
    log, ancla, objetos = entorno
    lineas = lineas_de(log)
    lineas[1] = alterar_actor(lineas[1])
    escribir_lineas(log, lineas)
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 1
    assert lineas_con(salida, "2", "sello")
    assert "ok" not in salida.lower().split()


def test_log_truncado_sale_distinto_de_cero(entorno, capsys):
    log, ancla, objetos = entorno
    escribir_lineas(log, lineas_de(log)[:2])
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 1
    assert lineas_con(salida, "4", "truncado")


def test_ancla_ausente_sale_distinto_de_cero(entorno, capsys):
    log, ancla, objetos = entorno
    ancla.unlink()
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 1
    assert lineas_con(salida, "ancla")


def test_evidencia_alterada_informa_posicion_y_hash_esperado(entorno, capsys):
    log, ancla, objetos = entorno
    (objetos / sha(CONTENIDO_A)).write_bytes(b"manipulada")
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 1
    assert lineas_con(salida, "1", "evidencia", sha(CONTENIDO_A))


def test_evidencia_ausente_sale_distinto_de_cero(entorno, capsys):
    log, ancla, objetos = entorno
    (objetos / sha(CONTENIDO_B)).unlink()
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 1
    assert lineas_con(salida, "4", "evidencia")


def test_resultado_intermedio_no_guardado_no_falla(entorno, capsys):
    log, ancla, objetos = entorno
    (objetos / sha(RESULTADO_A)).unlink()
    assert ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)[0] == 0


def test_sin_variable_de_llave_falla_cerrado_con_dos(entorno, capsys, monkeypatch):
    log, ancla, objetos = entorno
    monkeypatch.delenv("CUSTODY_KEY_FILE")
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert codigo == 2
    assert "ok" not in salida.lower().split()


def test_llave_con_permisos_abiertos_falla_cerrado(entorno, capsys, tmp_path, llave, monkeypatch):
    log, ancla, objetos = entorno
    abierta = escribir_llave(tmp_path / "abierta.custody-key", llave, modo=0o644)
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(abierta))
    assert ejecutar(capsys, "--log", log, "--anchor", ancla)[0] == 2


def test_llave_de_largo_incorrecto_falla_cerrado(entorno, capsys, tmp_path, monkeypatch):
    log, ancla, objetos = entorno
    corta = escribir_llave(tmp_path / "corta.custody-key", os.urandom(16))
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(corta))
    assert ejecutar(capsys, "--log", log, "--anchor", ancla)[0] == 2


def test_llave_equivocada_no_valida_la_cadena(entorno, capsys, tmp_path, monkeypatch):
    log, ancla, objetos = entorno
    otra = escribir_llave(tmp_path / "otra.custody-key", os.urandom(32))
    monkeypatch.setenv("CUSTODY_KEY_FILE", str(otra))
    codigo, salida = ejecutar(capsys, "--log", log, "--anchor", ancla)
    assert codigo == 1
    assert lineas_con(salida, "1", "sello")


def test_la_llave_no_aparece_en_la_salida(entorno, capsys, llave):
    log, ancla, objetos = entorno
    _, salida = ejecutar(capsys, "--log", log, "--anchor", ancla, "--store", objetos)
    assert llave.hex() not in salida


def test_log_inexistente_no_sale_con_cero(entorno, capsys, tmp_path):
    _, ancla, objetos = entorno
    codigo, _ = ejecutar(capsys, "--log", tmp_path / "no-existe.jsonl", "--anchor", ancla)
    assert codigo not in (0, None)


def test_sin_argumentos_obligatorios_no_sale_con_cero(entorno, capsys):
    codigo, _ = ejecutar(capsys)
    assert codigo not in (0, None)
