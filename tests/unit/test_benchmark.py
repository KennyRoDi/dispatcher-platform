import pytest

from src.domain.benchmark import Corrida, ResumenConfig, resumir


def corrida(config="cpu-int8-h1", repeticion=1, segundos=2.0, audio=4.0, memoria=500.0):
    return Corrida(config, repeticion, segundos, audio, memoria)


def test_resumen_calcula_latencia_y_throughput():
    corridas = [corrida(repeticion=1, segundos=2.0, memoria=500.0), corrida(repeticion=2, segundos=4.0, memoria=620.0)]

    [resumen] = resumir(corridas)

    assert isinstance(resumen, ResumenConfig)
    assert resumen.config == "cpu-int8-h1"
    assert resumen.latencia_media_s == pytest.approx(3.0)
    assert resumen.throughput_x_realtime == pytest.approx(8.0 / 6.0)
    assert resumen.memoria_pico_mb == 620.0
    assert resumen.repeticiones == 2


def test_resumen_agrupa_por_configuracion_y_exige_repeticiones():
    corridas = [corrida("a", 1, 1.0), corrida("b", 1, 2.0), corrida("a", 2, 3.0)]

    resumenes = resumir(corridas)

    assert [r.config for r in resumenes] == ["a", "b"]
    assert [r.repeticiones for r in resumenes] == [2, 1]
    with pytest.raises(ValueError):
        resumir([])


def test_p95_con_pocas_repeticiones():
    [una] = resumir([corrida(segundos=2.5)])
    [dos] = resumir([corrida(repeticion=1, segundos=1.0), corrida(repeticion=2, segundos=3.0)])

    assert una.latencia_p95_s == 2.5
    assert dos.latencia_p95_s == 3.0


def test_p95_por_rango_mas_cercano_con_veinte_corridas():
    corridas = [corrida(repeticion=i, segundos=float(i)) for i in range(1, 21)]

    [resumen] = resumir(corridas)

    assert resumen.latencia_p95_s == 19.0


def test_corrida_invalida_se_rechaza():
    with pytest.raises(ValueError):
        resumir([corrida(segundos=0.0)])
