from importlib import import_module

import pytest


def mod():
    return import_module("src.domain.oom_policy")


def test_codigo_menos_9_con_oom_kill_es_oom():
    assert mod().classify_exit(-9, 1) is mod().ExitCause.OOM


def test_codigo_137_con_oom_kill_es_oom():
    assert mod().classify_exit(137, 2) is mod().ExitCause.OOM


def test_menos_9_sin_oom_kill_es_killed():
    assert mod().classify_exit(-9, 0) is mod().ExitCause.KILLED


def test_cero_es_ok_aunque_haya_oom_kill_de_otro_proceso():
    assert mod().classify_exit(0, 1) is mod().ExitCause.OK


def test_otro_codigo_es_failed():
    assert mod().classify_exit(1, 0) is mod().ExitCause.FAILED


def test_oom_aumenta_reserva_y_no_gasta_intentos():
    politica = mod().OomPolicy(max_requeues=2, step_factor=1.5)
    decision = politica.decide(oom_count=0, reserve=1000)
    assert isinstance(decision, mod().Requeue)
    assert decision.reserve == 1500


def test_oom_segundo_reencolado_sigue_creciendo():
    politica = mod().OomPolicy(max_requeues=2, step_factor=1.5)
    decision = politica.decide(oom_count=1, reserve=1500)
    assert isinstance(decision, mod().Requeue)
    assert decision.reserve == 2250


def test_oom_agotado_falla_con_causa_oom():
    politica = mod().OomPolicy(max_requeues=2, step_factor=1.5)
    decision = politica.decide(oom_count=2, reserve=2250)
    assert isinstance(decision, mod().GiveUp)
    assert decision.cause == "oom"


@pytest.mark.parametrize("maximo,factor", [(-1, 1.5), (2, 1.0), (2, 0.5)])
def test_politica_invalida_se_rechaza(maximo, factor):
    with pytest.raises(ValueError):
        mod().OomPolicy(max_requeues=maximo, step_factor=factor)
