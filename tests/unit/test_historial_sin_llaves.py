import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LLAVE_PRIVADA = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")
SECRETO_MINIO = re.compile(r"^[-+ ]\s*(?:export\s+)?MINIO_SECRET_KEY=(\S+)\s*$")
VALOR_DE_DEMO = "minioadmin"

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


def test_el_historial_no_contiene_llaves_privadas_ni_secretos_de_minio():
    hallazgos = []
    for numero, linea in enumerate(_lineas_del_historial(), 1):
        if LLAVE_PRIVADA.search(linea):
            hallazgos.append((numero, "llave privada"))
        for valor in SECRETO_MINIO.findall(linea):
            if valor != VALOR_DE_DEMO:
                hallazgos.append((numero, "MINIO_SECRET_KEY con valor"))
    assert hallazgos == []


def test_el_valor_de_demo_de_minio_es_el_unico_declarado():
    assert VALOR_DE_DEMO == "minioadmin"
    assert SECRETO_MINIO.search("+MINIO_SECRET_KEY=" + "x" * 8)
    assert LLAVE_PRIVADA.search("-----BEGIN RSA " + "PRIVATE KEY-----")
