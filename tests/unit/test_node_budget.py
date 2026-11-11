from importlib import import_module

import pytest


def validar(limites, ram, reserva):
    return import_module("src.domain.node_budget").validate_node_budget(
        worker_limits=limites, node_memory=ram, reserve=reserva
    )


def test_preflight_rechaza_suma_de_limites_mayor_a_ram():
    with pytest.raises(ValueError):
        validar([600, 500], ram=1000, reserva=100)


@pytest.mark.parametrize("ram", [1000, 1001])
def test_presupuesto_igual_o_menor_a_ram_es_valido(ram):
    assert validar([400, 500], ram=ram, reserva=100) is None


def test_reserva_se_suma_antes_de_comparar_con_ram():
    with pytest.raises(ValueError):
        validar([400, 500], ram=1000, reserva=101)


def test_cada_replica_consume_su_limite_aunque_sean_iguales():
    assert validar([300, 300, 300], ram=1000, reserva=100) is None
    with pytest.raises(ValueError):
        validar([300, 300, 300, 300], ram=1000, reserva=100)


def test_reserva_cero_explicita_es_valida():
    assert validar([1000], ram=1000, reserva=0) is None


def test_configuracion_de_limites_ausente_se_rechaza():
    with pytest.raises(ValueError):
        validar(None, ram=1000, reserva=100)


@pytest.mark.parametrize("limite", [None, 0, -1, "max", "100", 1.5, True])
def test_limite_invalido_de_cualquier_worker_se_rechaza(limite):
    with pytest.raises(ValueError):
        validar([100, limite], ram=1000, reserva=100)


@pytest.mark.parametrize("ram", [None, 0, -1, "max", "1000", 1000.5, True])
def test_ram_ausente_o_invalida_se_rechaza(ram):
    with pytest.raises(ValueError):
        validar([100], ram=ram, reserva=10)


@pytest.mark.parametrize("reserva", [None, -1, "100", 1.5, True])
def test_reserva_ausente_o_invalida_se_rechaza(reserva):
    with pytest.raises(ValueError):
        validar([100], ram=1000, reserva=reserva)


def test_presupuesto_no_modifica_los_limites_del_operador():
    limites = [200, 300]
    validar(limites, ram=1000, reserva=100)
    assert limites == [200, 300]
