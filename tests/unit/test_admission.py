from importlib import import_module

import pytest

from src.workers.config import Settings


def admite(actual, limite, huella, margen):
    return import_module("src.domain.admission").admits(
        current=actual, max=limite, footprint=huella, margin=margen
    )


def test_rechaza_si_no_cabe_huella_con_margen():
    assert admite(actual=700, limite=1000, huella=250, margen=100) is False


def test_admite_si_cabe_con_holgura():
    assert admite(actual=500, limite=1000, huella=250, margen=100) is True


def test_admite_en_el_limite_exacto():
    assert admite(actual=650, limite=1000, huella=250, margen=100) is True
    assert admite(actual=651, limite=1000, huella=250, margen=100) is False


def test_uso_sobre_el_limite_no_admite():
    assert admite(actual=1200, limite=1000, huella=1, margen=0) is False


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("actual", -1),
        ("actual", 1.5),
        ("actual", True),
        ("limite", 0),
        ("huella", 0),
        ("huella", "100"),
        ("margen", -1),
        ("margen", None),
    ],
)
def test_rechaza_valores_invalidos(campo, valor):
    args = {"actual": 0, "limite": 1000, "huella": 100, "margen": 10}
    args[campo] = valor
    with pytest.raises((TypeError, ValueError)):
        admite(**args)


def test_huella_minima_de_las_colas_atendidas():
    tabla = import_module("src.domain.admission").FootprintTable(
        {"transcode_video": 900, "extract_metadata": 50, "extract_audio": 200}
    )
    assert tabla.minimum(["transcode_video", "extract_audio"]) == 200
    assert tabla.minimum(["transcode_video"]) == 900


def test_tabla_rechaza_operacion_sin_huella_o_valor_invalido():
    tabla_cls = import_module("src.domain.admission").FootprintTable
    tabla = tabla_cls({"extract_audio": 200})
    with pytest.raises(ValueError):
        tabla.minimum(["transcode_video"])
    with pytest.raises(ValueError):
        tabla_cls({"extract_audio": 0})


def cargar(env, colas=("extract_audio",)):
    return import_module("src.workers.config").load_admission_config(env, colas)


def test_configuracion_sin_huella_ni_margen_falla():
    with pytest.raises(ValueError):
        cargar({})
    with pytest.raises(ValueError):
        cargar({"ADMISSION_MARGIN_BYTES": "100"})
    with pytest.raises(ValueError):
        cargar({"FOOTPRINT_EXTRACT_AUDIO_BYTES": "200"})


def test_configuracion_completa_devuelve_tabla_y_margen():
    tabla, margen = cargar(
        {"ADMISSION_MARGIN_BYTES": "100", "FOOTPRINT_EXTRACT_AUDIO_BYTES": "200"}
    )
    assert margen == 100
    assert tabla.minimum(["extract_audio"]) == 200


def test_configuracion_rechaza_valores_no_numericos():
    with pytest.raises(ValueError):
        cargar({"ADMISSION_MARGIN_BYTES": "mucho", "FOOTPRINT_EXTRACT_AUDIO_BYTES": "200"})


def test_settings_no_trae_valores_predeterminados_de_admision():
    campos = Settings.__dataclass_fields__
    assert not any("footprint" in c or "margin" in c for c in campos)
