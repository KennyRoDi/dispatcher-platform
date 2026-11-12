import pytest

from src.domain.priority import Priority


def test_prioridad_se_mapea_a_normal_y_high_en_un_solo_lugar():
    assert Priority.MEDIA.to_contract() == "normal"
    assert Priority.ALTA.to_contract() == "high"
    assert Priority.from_contract("normal") is Priority.MEDIA
    assert Priority.from_contract("high") is Priority.ALTA
    for prioridad in (Priority.MEDIA, Priority.ALTA):
        assert Priority.from_contract(prioridad.to_contract()) is prioridad

    for texto in ("", "urgent", "media", "alta", "baja", "critica"):
        with pytest.raises(ValueError):
            Priority.from_contract(texto)
    for sin_palabra_de_contrato in (Priority.BAJA, Priority.CRITICA):
        with pytest.raises(ValueError):
            sin_palabra_de_contrato.to_contract()
