import pytest

from scripts.measure.m3_chunks import parse_chunk_sizes


def test_parsea_tamanos_de_chunk_binarios():
    assert parse_chunk_sizes("256K,1M,4M,16M") == [256 * 1024, 1 << 20, 4 << 20, 16 << 20]


@pytest.mark.parametrize("valor", ["", "1M,", "1M,1M", "0,4M", "4G"])
def test_rechaza_tamanos_duplicados_o_invalidos(valor):
    with pytest.raises(ValueError):
        parse_chunk_sizes(valor)
