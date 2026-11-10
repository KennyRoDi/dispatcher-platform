import pytest

from src.adapters.whisper_transcriber import cargar_config_de_audio


def config_con_idioma(ruta, idioma):
    ruta.write_text(
        f'[modelo]\nnombre = "base"\nrevision = "{"a" * 40}"\nidioma = "{idioma}"\n'
        'compute_type = "int8"\nbeam_size = 5\nhilos = 0\n',
        encoding="utf-8",
    )
    return ruta


@pytest.mark.parametrize("idioma", ["es", "en", "haw", "yue"])
def test_idioma_que_whisper_conoce_se_acepta(tmp_path, idioma):
    assert cargar_config_de_audio(config_con_idioma(tmp_path / "audio.toml", idioma)).idioma == idioma


@pytest.mark.parametrize(
    "idioma",
    ["xx", " es ", "es ", " es", "ES", "esp", "español", "ca-ES"],
    ids=["desconocido", "espacios-ambos", "espacio-final", "espacio-inicial", "mayusculas", "tres-letras", "nombre", "region"],
)
def test_idioma_que_whisper_no_conoce_falla_al_cargar_con_value_error(tmp_path, idioma):
    with pytest.raises(ValueError, match="idioma"):
        cargar_config_de_audio(config_con_idioma(tmp_path / "audio.toml", idioma))
