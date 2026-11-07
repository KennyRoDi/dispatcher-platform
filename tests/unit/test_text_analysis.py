import pytest

from src.domain.text_analysis import MessageAnalysis, lotes, palabras_clave, sentimiento_del_lote, tema

LEXICO = {"reunion": ["cafe", "plaza"], "conflicto": ["deuda", "pagar"]}


def analisis(etiqueta, puntaje):
    return MessageAnalysis(lemmas=(), sentiment_label=etiqueta, sentiment_score=puntaje, offense_score=0.0, threat_patterns=())


def test_lotes_parte_en_bloques_del_tamano_dado_con_el_ultimo_incompleto():
    assert [list(lote) for lote in lotes([1, 2, 3, 4, 5], 2)] == [[1, 2], [3, 4], [5]]


def test_lotes_de_una_lista_vacia_no_produce_ninguno():
    assert list(lotes([], 3)) == []


@pytest.mark.parametrize("tamano", [0, -1])
def test_lotes_rechaza_tamano_no_positivo(tamano):
    with pytest.raises(ValueError):
        list(lotes([1], tamano))


def test_palabras_clave_ordena_por_frecuencia_y_corta_en_n():
    lemas = ["casa", "deuda", "pagar", "deuda", "pagar", "deuda", "plaza"]

    assert palabras_clave(lemas, 2) == ["deuda", "pagar"]


def test_palabras_clave_desempata_por_primera_aparicion():
    assert palabras_clave(["plaza", "cafe", "cafe", "plaza", "sol"], 3) == ["plaza", "cafe", "sol"]


def test_tema_elige_el_de_mas_coincidencias_con_su_proporcion():
    nombre, confianza = tema(["deuda", "pagar", "cafe", "hola"], LEXICO)

    assert nombre == "conflicto"
    assert confianza == pytest.approx(0.5)


@pytest.mark.parametrize("lemas", [["hola", "sol"], []])
def test_tema_sin_coincidencias_es_sin_tema(lemas):
    assert tema(lemas, LEXICO) == ("sin_tema", 0.0)


def test_sentimiento_elige_la_etiqueta_mayoritaria_y_promedia_su_puntaje():
    lote = [analisis("negativo", 0.9), analisis("positivo", 0.6), analisis("negativo", 0.7)]

    etiqueta, confianza = sentimiento_del_lote(lote)

    assert etiqueta == "negativo"
    assert confianza == pytest.approx(0.8)


def test_sentimiento_de_un_solo_mensaje_conserva_su_puntaje():
    assert sentimiento_del_lote([analisis("positivo", 0.65)]) == ("positivo", pytest.approx(0.65))
