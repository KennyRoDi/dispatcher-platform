import os
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "imagen.toml"
MUESTRA = RAIZ / "tests" / "datos" / "imagenes"
ETIQUETAS = MUESTRA / "etiquetas.json"
# Los pesos no se descargan aquí: se colocan antes, como en la prueba de integración de F-08.
DIRECTORIO_PESOS = Path(os.environ.get("F08_DIRECTORIO_PESOS", RAIZ))


def test_analizador_real_reporta_categoria_y_confianza_y_da_la_tabla_de_aciertos():
    pytest.importorskip("ultralytics")
    if not ETIQUETAS.is_file():
        pytest.skip(f"falta la muestra etiquetada: {ETIQUETAS} (fotos propias o con licencia [B.3])")
    from scripts.aciertos_imagen import construir_analizador, evaluar, generar_markdown, leer_etiquetas, tabla_aciertos
    from src.adapters.hashing import sha256_de_archivo
    from src.adapters.yolo_detector import YoloDetector

    with open(CONFIG, "rb") as archivo:
        config = tomllib.load(archivo)
    categorias = tuple(sorted(set(config["clases"].values())))
    try:
        detector = YoloDetector.from_config(CONFIG, DIRECTORIO_PESOS)
    except FileNotFoundError as error:
        pytest.skip(f"faltan los pesos fijados en config/imagen.toml dentro de {DIRECTORIO_PESOS}: {error}")
    etiquetas = leer_etiquetas(ETIQUETAS, MUESTRA, categorias)

    resultados = evaluar(construir_analizador(CONFIG, detector), MUESTRA, etiquetas)

    assert len(resultados) == len(etiquetas)
    for resultado in resultados:
        sha = sha256_de_archivo(MUESTRA / resultado.archivo)
        for hallazgo in resultado.hallazgos:
            assert hallazgo.category in categorias
            assert 0 <= hallazgo.confidence <= 1
            assert hallazgo.evidence.object_sha256 == sha
            assert hallazgo.evidence.position.startswith("caja ")
    # RF-07 pide que una imagen positiva dé su categoría; cuántas lo logran lo dice la tabla, sin umbral.
    assert any(
        resultado.esperada in {hallazgo.category for hallazgo in resultado.hallazgos}
        for resultado in resultados
        if resultado.esperada is not None
    )
    filas = tabla_aciertos(resultados, categorias)
    assert all(
        f.verdaderos_positivos + f.falsos_positivos + f.falsos_negativos + f.verdaderos_negativos == len(etiquetas)
        for f in filas
    )
    versiones = {"ultralytics": "instalada", "torch": "instalada"}
    texto = generar_markdown("pytest -m acceptance", config, versiones, etiquetas, resultados)
    assert "| Categoría | VP | FP | FN | VN |" in texto
