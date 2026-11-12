from importlib import import_module

import pytest


def mod():
    return import_module("src.domain.retry")


def test_backoff_crece_y_respeta_maximo():
    esperas = [mod().next_delay(n, 1, 8, lambda: 0.5) for n in range(1, 8)]
    assert esperas == sorted(esperas)
    assert esperas[0] < esperas[3]
    assert max(esperas) <= 8
    assert esperas[-1] == esperas[-2] == pytest.approx(6)


def test_agota_intentos_y_falla():
    politica = mod().RetryPolicy(max_attempts=3, base=1, cap=30)
    decisiones = [mod().decide_retry(n, politica, lambda: 0.0) for n in (1, 2, 3, 4)]
    assert all(isinstance(d, mod().Retry) for d in decisiones[:2])
    assert decisiones[0].delay < decisiones[1].delay
    assert isinstance(decisiones[2], mod().GiveUp)
    assert isinstance(decisiones[3], mod().GiveUp)


def test_jitter_inyectado_acota_la_espera():
    minimo = mod().next_delay(3, 2, 100, lambda: 0.0)
    maximo = mod().next_delay(3, 2, 100, lambda: 0.999999)
    assert minimo == pytest.approx(4)
    assert maximo == pytest.approx(8, rel=1e-5)
    assert minimo < maximo <= 8


@pytest.mark.parametrize(
    "argumentos",
    [
        (0, 1, 8, 0.5),
        (1, 0, 8, 0.5),
        (1, -1, 8, 0.5),
        (1, 4, 2, 0.5),
        (1, 1, 8, 1.0),
        (1, 1, 8, -0.1),
    ],
)
def test_politica_invalida_se_rechaza(argumentos):
    intento, base, tope, jitter = argumentos
    with pytest.raises(ValueError):
        mod().next_delay(intento, base, tope, lambda: jitter)


def test_politica_con_parametros_invalidos_se_rechaza():
    for kwargs in ({"max_attempts": 0, "base": 1, "cap": 8}, {"max_attempts": 3, "base": 0, "cap": 8}, {"max_attempts": 3, "base": 4, "cap": 2}):
        with pytest.raises(ValueError):
            mod().RetryPolicy(**kwargs)
