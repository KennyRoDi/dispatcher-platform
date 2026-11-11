import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
TERCEROS_PROHIBIDOS = {"redis", "fastapi", "minio", "requests", "psutil", "streamlit", "spacy", "transformers", "torch", "ultralytics", "cv2", "faster_whisper", "ctranslate2", "av", "jwt", "cryptography"}
CAPAS_EXTERNAS = {
    "domain": {"src.application", "src.adapters", "src.infrastructure"},
    "application": {"src.adapters", "src.infrastructure"},
}


def modulos_importados(codigo: str) -> set[str]:
    modulos = set()
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.add(nodo.module)
    return modulos


def importaciones_prohibidas(codigo: str, capa: str) -> set[str]:
    prohibidas = set()
    for modulo in modulos_importados(codigo):
        es_tercero = modulo.split(".")[0] in TERCEROS_PROHIBIDOS
        es_capa_externa = any(modulo.startswith(c) for c in CAPAS_EXTERNAS[capa])
        if es_tercero or es_capa_externa:
            prohibidas.add(modulo)
    return prohibidas


def test_detecta_importacion_de_infraestructura_en_dominio():
    codigo = "import redis\nfrom src.adapters.api import app\nfrom dataclasses import dataclass\n"
    assert importaciones_prohibidas(codigo, "domain") == {"redis", "src.adapters.api"}


def test_aplicacion_puede_importar_dominio_pero_no_adaptadores():
    codigo = "from src.domain.retry import next_delay\nimport src.adapters.redis_queue\n"
    assert importaciones_prohibidas(codigo, "application") == {"src.adapters.redis_queue"}


@pytest.mark.parametrize("capa", sorted(CAPAS_EXTERNAS))
def test_capa_respeta_regla_de_dependencias(capa):
    for archivo in (SRC / capa).rglob("*.py"):
        prohibidas = importaciones_prohibidas(archivo.read_text(encoding="utf-8"), capa)
        assert not prohibidas, f"{archivo}: {sorted(prohibidas)}"
