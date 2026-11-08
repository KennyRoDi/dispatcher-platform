import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "texto.toml"
CONVERSACION = RAIZ / "tests" / "datos" / "aciertos_texto_conversacion.json"
ETIQUETAS = RAIZ / "tests" / "datos" / "aciertos_texto_etiquetas.json"
CUARTA_SALIDA = {"amenaza", "ofensivo", "sin_ofensa"}


def test_analizador_real_da_las_cuatro_salidas_y_la_tabla_de_aciertos():
    pytest.importorskip("spacy")
    pytest.importorskip("transformers")
    from scripts.aciertos_texto import agrupar_por_lote, comparar, construir_analizador, generar_markdown, leer_etiquetas
    from src.adapters.spacy_hf_text_models import SpacyHfTextModels

    etiquetas = leer_etiquetas(ETIQUETAS)
    modelos = SpacyHfTextModels.from_config(CONFIG)

    hallazgos = construir_analizador(CONFIG, modelos, etiquetas.tamano_lote).analyze(CONVERSACION)
    grupos = agrupar_por_lote(hallazgos)

    assert len(grupos) == len(etiquetas.lotes)
    for grupo in grupos:
        assert set(grupo) == {"palabras_clave", "tema", "sentimiento", "ofensa"}
        assert grupo["ofensa"].category in CUARTA_SALIDA
    with open(CONFIG, "rb") as archivo:
        config = tomllib.load(archivo)
    texto = generar_markdown("pytest -m acceptance", config, etiquetas.tamano_lote, comparar(hallazgos, etiquetas))
    assert "| Categoría | Lotes | Aciertos | Errores |" in texto
