from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_AUDIO = RAIZ / "config" / "audio.toml"
CONFIG_TEXTO = RAIZ / "config" / "texto.toml"
MUESTRA = RAIZ / "tests" / "datos" / "audio"
ESPERADAS = MUESTRA / "transcripciones.json"
RF06 = {"palabras_clave", "tema", "sentimiento"}


def test_analizador_real_compara_transcripcion_con_la_esperada_y_marca_la_amenaza():
    pytest.importorskip("faster_whisper")
    pytest.importorskip("spacy")
    pytest.importorskip("transformers")
    if not ESPERADAS.is_file():
        pytest.skip(f"falta la muestra con transcripción conocida: {ESPERADAS} (voz propia o con licencia [B.3])")
    from scripts.comparar_transcripcion import evaluar, generar_markdown, leer_esperadas
    from src.adapters.hashing import sha256_de_archivo
    from src.adapters.spacy_hf_text_models import SpacyHfTextModels
    from src.adapters.whisper_transcriber import WhisperTranscriber, cargar_config_de_audio
    from src.domain.finding import Severity

    notas = leer_esperadas(ESPERADAS, MUESTRA)
    try:
        transcriptor = WhisperTranscriber.from_config(CONFIG_AUDIO)
        modelos = SpacyHfTextModels.from_config(CONFIG_TEXTO)
    except (OSError, ImportError) as error:
        pytest.skip(f"faltan los pesos o modelos descargados: {error}")

    resultados = evaluar(transcriptor, modelos, CONFIG_TEXTO, MUESTRA, notas)

    assert len(resultados) == len(notas)
    for resultado in resultados:
        sha = sha256_de_archivo(MUESTRA / resultado.archivo)
        assert resultado.wer >= 0
        assert resultado.segmentos
        assert all(s.fin >= s.inicio for s in resultado.segmentos)
        assert RF06 <= {h.category for h in resultado.hallazgos}
        transcripciones = [h for h in resultado.hallazgos if h.category == "transcripcion"]
        assert len(transcripciones) == len([s for s in resultado.segmentos if s.texto])
        assert all("t=" in h.evidence.position for h in transcripciones)
        assert {h.evidence.object_sha256 for h in resultado.hallazgos} == {sha}
    con_amenaza = [r for r in resultados if "amenaza" in r.archivo.lower()]
    assert con_amenaza, "la muestra debe incluir una nota de amenaza"
    # El WER se registra tal como salga, sin umbral; solo se exige que la amenaza se detecte.
    assert any(h.category == "amenaza" and h.severity is Severity.ALTA for r in con_amenaza for h in r.hallazgos)
    config = cargar_config_de_audio(CONFIG_AUDIO)
    texto = generar_markdown("pytest -m acceptance", config, {"faster-whisper": "instalada"}, notas, resultados)
    assert "## Límites" in texto
