import pytest

from src.domain.ground_truth import Comparison, GroundTruthItem, ObservedItem, compare


def test_la_exactitud_sin_elementos_es_indefinida():
    assert Comparison(scores=(), total=0, exact_matches=0).accuracy is None


def test_los_repetidos_con_ids_de_tipos_mezclados_dan_value_error():
    truth = [GroundTruthItem(1, frozenset()), GroundTruthItem(1, frozenset()),
             GroundTruthItem("a", frozenset()), GroundTruthItem("a", frozenset())]
    observed = [ObservedItem(1, frozenset()), ObservedItem("a", frozenset())]
    with pytest.raises(ValueError, match="repetidos"):
        compare(truth, observed)
