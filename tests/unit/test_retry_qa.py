import math

import pytest

from src.domain.retry import GiveUp, Retry, RetryPolicy, decide_retry, next_delay


def test_primer_reintento_espera_entre_base_y_dos_veces_base():
    politica = RetryPolicy(max_attempts=5, base=4, cap=1000)
    minimo = decide_retry(1, politica, lambda: 0.0)
    maximo = decide_retry(1, politica, lambda: 0.999999)
    assert minimo.delay == pytest.approx(4)
    assert maximo.delay == pytest.approx(8, rel=1e-5)


def test_con_n_igual_a_uno_nunca_se_reintenta():
    politica = RetryPolicy(max_attempts=1, base=1, cap=8)
    assert isinstance(decide_retry(1, politica, lambda: 0.0), GiveUp)


def test_con_n_intentos_hay_n_menos_uno_esperas():
    politica = RetryPolicy(max_attempts=5, base=1, cap=100)
    decisiones = [decide_retry(n, politica, lambda: 0.0) for n in range(1, 6)]
    assert sum(isinstance(d, Retry) for d in decisiones) == 4
    assert isinstance(decisiones[-1], GiveUp)


def test_la_espera_nunca_supera_el_tope_con_jitter_maximo():
    for intento in range(1, 40):
        assert next_delay(intento, 1, 8, lambda: 0.9999999) <= 8


def test_tope_igual_a_base_es_valido_y_constante():
    assert next_delay(1, 5, 5, lambda: 0.0) == next_delay(30, 5, 5, lambda: 0.0)


@pytest.mark.parametrize("jitter", [math.nan, math.inf, -math.inf, 1.0, -1e-9])
def test_jitter_fuera_de_rango_o_no_finito_se_rechaza(jitter):
    with pytest.raises(ValueError):
        next_delay(1, 1, 8, lambda: jitter)


@pytest.mark.parametrize("intento", [0, -1, -100])
def test_intento_no_positivo_se_rechaza(intento):
    with pytest.raises(ValueError):
        next_delay(intento, 1, 8, lambda: 0.5)


def test_intento_enorme_con_base_entera_respeta_el_tope():
    assert next_delay(5000, 1, 8, lambda: 0.0) == pytest.approx(4)


@pytest.mark.xfail(strict=True, raises=OverflowError, reason="DEFECTO QA: 2**(attempt-1) * base float desborda para attempt > ~1025; debería acotarse al tope")
def test_intento_enorme_con_base_float_respeta_el_tope():
    assert next_delay(2000, 1.0, 8.0, lambda: 0.0) == pytest.approx(4)


@pytest.mark.xfail(strict=True, reason="DEFECTO QA: RetryPolicy acepta base=NaN porque las comparaciones con NaN son falsas")
def test_politica_con_base_nan_se_rechaza():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=3, base=math.nan, cap=8)


@pytest.mark.xfail(strict=True, reason="DEFECTO QA: RetryPolicy acepta cap=NaN")
def test_politica_con_tope_nan_se_rechaza():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=3, base=1, cap=math.nan)


@pytest.mark.parametrize("n", [0, -1])
def test_politica_con_maximo_no_positivo_se_rechaza(n):
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=n, base=1, cap=8)


def test_decide_retry_con_intentos_negativos_se_rechaza():
    with pytest.raises(ValueError):
        decide_retry(-1, RetryPolicy(max_attempts=3, base=1, cap=8), lambda: 0.0)


def test_decide_retry_consulta_el_jitter_una_sola_vez_y_ninguna_al_rendirse():
    llamadas = []
    politica = RetryPolicy(max_attempts=2, base=1, cap=8)
    decide_retry(1, politica, lambda: llamadas.append(1) or 0.0)
    decide_retry(2, politica, lambda: llamadas.append(1) or 0.0)
    assert len(llamadas) == 1
