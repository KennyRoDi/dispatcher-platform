import re
import sys
from pathlib import Path

import pytest

from src.adapters.whisper_transcriber import ConfigWhisper, cargar_config_de_audio

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_REPO = RAIZ / "config" / "audio.toml"
REVISION = "a" * 40
CAMPOS_VALIDOS = {
    "nombre": '"base"',
    "revision": f'"{REVISION}"',
    "idioma": '"es"',
    "compute_type": '"int8"',
    "beam_size": "5",
    "hilos": "0",
}


def escribir_config(ruta, **cambios):
    campos = {**CAMPOS_VALIDOS, **cambios}
    lineas = [f"{clave} = {valor}" for clave, valor in campos.items() if valor is not None]
    ruta.write_text("[modelo]\n" + "\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


@pytest.fixture(autouse=True)
def sin_faster_whisper(monkeypatch):
    # Un None en sys.modules hace fallar cualquier `import` de esa biblioteca, esté o no instalada.
    for biblioteca in ("faster_whisper", "ctranslate2", "av"):
        monkeypatch.setitem(sys.modules, biblioteca, None)


def test_config_valida_se_carga_con_sus_valores(tmp_path):
    config = cargar_config_de_audio(escribir_config(tmp_path / "audio.toml"))

    assert config == ConfigWhisper(
        nombre="base", revision=REVISION, idioma="es", compute_type="int8", beam_size=5, hilos=0
    )


@pytest.mark.parametrize("compute_type", ["int8", "float32"])
def test_admite_los_compute_type_que_compara_m5(tmp_path, compute_type):
    ruta = escribir_config(tmp_path / "audio.toml", compute_type=f'"{compute_type}"')

    assert cargar_config_de_audio(ruta).compute_type == compute_type


@pytest.mark.parametrize(
    "cambios",
    [
        {"idioma": '""'},
        {"idioma": None},
        {"idioma": "1"},
        {"compute_type": '"int4"'},
        {"compute_type": '"rapido"'},
        {"compute_type": None},
        {"beam_size": "0"},
        {"beam_size": "-1"},
        {"beam_size": "2.5"},
        {"beam_size": "true"},
        {"beam_size": None},
        {"nombre": '""'},
        {"nombre": None},
        {"revision": '""'},
        {"revision": None},
        {"hilos": "-1"},
        {"hilos": '"cuatro"'},
    ],
    ids=[
        "idioma-vacio",
        "sin-idioma",
        "idioma-no-texto",
        "compute-type-int4",
        "compute-type-desconocido",
        "sin-compute-type",
        "beam-size-cero",
        "beam-size-negativo",
        "beam-size-decimal",
        "beam-size-bool",
        "sin-beam-size",
        "nombre-vacio",
        "sin-nombre",
        "revision-vacia",
        "sin-revision",
        "hilos-negativo",
        "hilos-texto",
    ],
)
def test_config_invalida_falla_con_value_error(tmp_path, cambios):
    with pytest.raises(ValueError):
        cargar_config_de_audio(escribir_config(tmp_path / "audio.toml", **cambios))


@pytest.mark.parametrize("contenido", ["", 'modelo = "base"\n'], ids=["sin-tabla", "modelo-texto"])
def test_sin_tabla_modelo_falla_con_value_error(tmp_path, contenido):
    ruta = tmp_path / "audio.toml"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(ValueError, match="modelo"):
        cargar_config_de_audio(ruta)


def test_config_del_repositorio_fija_modelo_base_en_espanol_con_int8():
    config = cargar_config_de_audio(CONFIG_REPO)

    assert (config.nombre, config.idioma, config.compute_type) == ("base", "es", "int8")
    assert config.beam_size >= 1


def test_config_del_repositorio_fija_la_revision_de_los_pesos():
    config = cargar_config_de_audio(CONFIG_REPO)

    assert re.fullmatch(r"[0-9a-f]{40}", config.revision), "la revisión debe ser el commit del repositorio de pesos"
