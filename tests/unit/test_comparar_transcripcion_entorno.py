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


def _preparar(tmp_path):
    muestra = tmp_path / "audio"
    muestra.mkdir()
    (muestra / "neutra_1.ogg").write_bytes(b"bytes sinteticos")
    nota = {"archivo": "neutra_1.ogg", "texto_esperado": "hola", "procedencia": "sintetica", "licencia": "CC BY 4.0"}
    esperadas = tmp_path / "transcripciones.json"
    esperadas.write_text(json.dumps({"notas": [nota]}), encoding="utf-8")
    salida = tmp_path / "r.md"
    return ["--muestra", str(muestra), "--esperadas", str(esperadas), "--salida", str(salida)], salida


def _modulo_de_texto_falso(monkeypatch, error):
    import types

    modulo = types.ModuleType("src.adapters.spacy_hf_text_models")

    class SpacyHfTextModels:
        @staticmethod
        def from_config(ruta):
            raise error

    modulo.SpacyHfTextModels = SpacyHfTextModels
    monkeypatch.setitem(sys.modules, "src.adapters.spacy_hf_text_models", modulo)


def test_value_error_de_la_carga_de_modelos_de_texto_llega_sin_envolverse(tmp_path, monkeypatch, capsys):
    argv, salida = _preparar(tmp_path)
    _modulo_de_texto_falso(monkeypatch, ValueError("modelo de spaCy con otra versión"))

    resultado = main(argv, transcriptor=TranscriptorQueNoDebeLlamarse(), versiones=VERSIONES)

    assert resultado == 1
    error = capsys.readouterr().err
    assert "otra versión" in error and "falta una biblioteca" not in error
    assert not salida.exists()


def test_el_error_de_biblioteca_de_texto_nombra_la_causa(tmp_path, monkeypatch, capsys):
    argv, _ = _preparar(tmp_path)
    _modulo_de_texto_falso(monkeypatch, ImportError("No module named 'transformers'"))

    assert main(argv, transcriptor=TranscriptorQueNoDebeLlamarse(), versiones=VERSIONES) == 1

    assert "transformers" in capsys.readouterr().err


def test_value_error_de_from_config_del_transcriptor_llega_sin_envolverse(tmp_path, monkeypatch, capsys):
    from scripts import comparar_transcripcion as script
    from tests.dobles import FakeTextModels

    def invalida(ruta):
        raise ValueError("compute_type inválido")

    monkeypatch.setattr(script.WhisperTranscriber, "from_config", staticmethod(invalida))
    argv, salida = _preparar(tmp_path)

    assert main(argv, modelos=FakeTextModels({}), versiones=VERSIONES) == 1

    error = capsys.readouterr().err
    assert "compute_type inválido" in error and "falta una biblioteca" not in error
    assert not salida.exists()


def test_sin_metadatos_no_se_carga_ningun_modelo(tmp_path, monkeypatch, capsys):
    from importlib import metadata

    def sin_paquete(nombre):
        raise metadata.PackageNotFoundError(nombre)

    monkeypatch.setattr(metadata, "version", sin_paquete)
    argv, salida = _preparar(tmp_path)
    _modulo_de_texto_falso(monkeypatch, AssertionError("se cargaron modelos antes de validar versiones"))

    assert main(argv, transcriptor=TranscriptorQueNoDebeLlamarse()) == 1

    assert "faster-whisper" in capsys.readouterr().err
    assert not salida.exists()
