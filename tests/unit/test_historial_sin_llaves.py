import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LLAVE_PRIVADA = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")
SECRETO_MINIO = re.compile(r"^[-+ ]\s*(?:export\s+)?MINIO_SECRET_KEY=(\S+)\s*$")
VALOR_DE_DEMO = "minioadmin"
# Las pruebas de TLS escriben un PEM falso con este cuerpo; `git log --all` lo ve en cualquier rama que lo contenga.
CUERPO_DE_PRUEBA = "LLAVE-SECRETA-"

pytestmark = pytest.mark.skipif(
    not (shutil.which("git") and (RAIZ / ".git").exists()), reason="requiere git y el historial del repositorio"
)


def _lineas_del_historial():
    proceso = subprocess.Popen(
        ["git", "log", "-p", "--all", "--no-color"],
        cwd=RAIZ,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        errors="replace",
    )
    with proceso:
        yield from proceso.stdout
    assert proceso.returncode == 0


def _hallazgos(lineas):
    hallazgos = []
    for numero, linea in enumerate(lineas, 1):
        if CUERPO_DE_PRUEBA in linea:
            continue
        if LLAVE_PRIVADA.search(linea):
            hallazgos.append((numero, "llave privada"))
        for valor in SECRETO_MINIO.findall(linea):
            if valor != VALOR_DE_DEMO:
                hallazgos.append((numero, "MINIO_SECRET_KEY con valor"))
    return hallazgos


def test_el_historial_no_contiene_llaves_privadas_ni_secretos_de_minio():
    assert _hallazgos(_lineas_del_historial()) == []


def test_un_pem_falso_de_prueba_no_cuenta_pero_uno_con_otro_cuerpo_si():
    encabezado = "-----BEGIN " + "PRIVATE KEY-----"
    falso = f"+    ruta.write_text('{encabezado}" + "\\nLLAVE-SECRETA-123')\n"
    real = f"+    clave = '{encabezado}" + "\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC')\n"
    assert _hallazgos([falso]) == []
    assert _hallazgos([real]) == [(1, "llave privada")]


def test_el_valor_de_demo_de_minio_es_el_unico_declarado():
    assert VALOR_DE_DEMO == "minioadmin"
    assert SECRETO_MINIO.search("+MINIO_SECRET_KEY=" + "x" * 8)
    assert LLAVE_PRIVADA.search("-----BEGIN RSA " + "PRIVATE KEY-----")
