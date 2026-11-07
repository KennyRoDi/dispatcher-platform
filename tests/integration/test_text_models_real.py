from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("spacy")
pytest.importorskip("transformers")

from src.adapters.spacy_hf_text_models import SpacyHfTextModels  # noqa: E402
from src.domain.text_analysis import MessageAnalysis  # noqa: E402

CONFIG_REPO = Path(__file__).resolve().parents[2] / "config" / "texto.toml"
ETIQUETAS = {"positivo", "neutral", "negativo"}
# Conversación sintética, sin personas reales [B.3]; la amenaza es ficticia.
MUESTRA = [
    "Hola, ¿nos vemos mañana a las cinco en la plaza?",
    "¡Qué alegría! Gracias por invitarme al café.",
    "Si no me pagas la deuda, vas a ver lo que te pasa.",
    "Vas a ver lo que te pasa si no pagas.",
]
INDICES_AMENAZA = {2, 3}


@pytest.fixture(scope="module")
def analisis():
    return SpacyHfTextModels.from_config(CONFIG_REPO).analyze_messages(MUESTRA)


def test_devuelve_un_analisis_valido_por_mensaje(analisis):
    assert len(analisis) == len(MUESTRA)
    for resultado in analisis:
        assert isinstance(resultado, MessageAnalysis)
        assert resultado.sentiment_label in ETIQUETAS
        assert 0 <= resultado.sentiment_score <= 1
        assert 0 <= resultado.offense_score <= 1
        assert all(lema == lema.lower() for lema in resultado.lemmas)


def test_la_amenaza_ficticia_se_marca_y_los_mensajes_tranquilos_no(analisis):
    assert all("vas_a_ver" in analisis[i].threat_patterns for i in INDICES_AMENAZA)
    assert all(not a.threat_patterns for i, a in enumerate(analisis) if i not in INDICES_AMENAZA)
