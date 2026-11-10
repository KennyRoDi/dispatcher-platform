import json
import sys

from scripts.comparar_transcripcion import main

VERSIONES = {"faster-whisper": "1.2.1", "ctranslate2": "4.7.1"}


class TranscriptorQueNoDebeLlamarse:
    def transcribe(self, path):
        raise AssertionError(f"se transcribió {path} sin modelos de texto")


def test_main_sin_bibliotecas_de_texto_falla_con_error_y_codigo_1_sin_traceback(tmp_path, monkeypatch, capsys):
    muestra = tmp_path / "audio"
    muestra.mkdir()
    (muestra / "neutra_1.ogg").write_bytes(b"bytes sinteticos")
    esperadas = tmp_path / "transcripciones.json"
    nota = {"archivo": "neutra_1.ogg", "texto_esperado": "hola", "procedencia": "sintetica", "licencia": "CC BY 4.0"}
    esperadas.write_text(json.dumps({"notas": [nota]}), encoding="utf-8")
    salida = tmp_path / "r.md"
    for modulo in ("spacy", "transformers"):
        monkeypatch.setitem(sys.modules, modulo, None)
    monkeypatch.delitem(sys.modules, "src.adapters.spacy_hf_text_models", raising=False)

    resultado = main(
        ["--muestra", str(muestra), "--esperadas", str(esperadas), "--salida", str(salida)],
        transcriptor=TranscriptorQueNoDebeLlamarse(),
        versiones=VERSIONES,
    )

    assert resultado == 1
    assert capsys.readouterr().err.startswith("error:")
    assert not salida.exists()
