import pytest

from src.domain.frame_sampling import FrameSampling


def test_muestreo_de_fotogramas_acota_cantidad_y_cadencia():
    muestreo = FrameSampling(every_s=5, max_frames=4)

    assert muestreo.timestamps(12) == [0, 5, 10]
    assert muestreo.timestamps(5) == [0]
    assert muestreo.timestamps(0.5) == [0]
    assert muestreo.timestamps(10_000) == [0, 5, 10, 15]


def test_muestreo_sin_duracion_conocida_usa_el_tope():
    muestreo = FrameSampling(every_s=2, max_frames=3)

    assert muestreo.timestamps(None) == [0, 2, 4]
    assert muestreo.timestamps(0) == [0, 2, 4]
    assert muestreo.timestamps(float("nan")) == [0, 2, 4]


def test_muestreo_por_defecto_es_cinco_segundos_y_veinte_fotogramas():
    muestreo = FrameSampling()

    assert (muestreo.every_s, muestreo.max_frames) == (5, 20)
    assert len(muestreo.timestamps(3600)) == 20


@pytest.mark.parametrize("every_s", [0, -1, float("inf"), float("nan"), True, "5"])
def test_muestreo_rechaza_parametros_invalidos_de_cadencia(every_s):
    with pytest.raises(ValueError, match="FRAME_EVERY_S"):
        FrameSampling(every_s=every_s)


@pytest.mark.parametrize("max_frames", [0, -3, 2.5, True, "20"])
def test_muestreo_rechaza_parametros_invalidos_de_tope(max_frames):
    with pytest.raises(ValueError, match="FRAME_MAX"):
        FrameSampling(max_frames=max_frames)


def test_muestreo_desde_el_entorno_y_sus_valores_por_defecto():
    assert FrameSampling.from_env({"FRAME_EVERY_S": "2.5", "FRAME_MAX": "8"}) == FrameSampling(2.5, 8)
    assert FrameSampling.from_env({}) == FrameSampling()
    assert FrameSampling.from_env({"FRAME_EVERY_S": " ", "FRAME_MAX": ""}) == FrameSampling()


@pytest.mark.parametrize(
    "env", [{"FRAME_EVERY_S": "abc"}, {"FRAME_MAX": "1.5"}, {"FRAME_MAX": "0"}, {"FRAME_EVERY_S": "-2"}]
)
def test_muestreo_desde_el_entorno_rechaza_valores_invalidos(env):
    with pytest.raises(ValueError):
        FrameSampling.from_env(env)
