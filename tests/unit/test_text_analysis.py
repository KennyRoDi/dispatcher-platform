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


def test_tema_ignora_tildes_y_mayusculas_de_los_lemas():
    assert tema(["Reunión", "café"], {"reunion": ["reunion", "cafe"]}) == ("reunion", 1.0)


def test_tema_ignora_tildes_y_mayusculas_del_lexico():
    assert tema(["reunion", "deuda"], {"reunion": ["Reunión"], "conflicto": ["DEUDA"]})[1] == 0.5
    assert tema(["cafe", "cafe"], {"reunion": ["Café"]}) == ("reunion", 1.0)


def test_tema_trata_la_enie_como_n():
    assert tema(["año"], {"tiempo": ["ano"]}) == ("tiempo", 1.0)


def analisis_con(**cambios):
    campos = dict(lemmas=(), sentiment_label="neutral", sentiment_score=0.5, offense_score=0.0, threat_patterns=())
    campos.update(cambios)
    return MessageAnalysis(**campos)


@pytest.mark.parametrize("etiqueta", ["positivo", "neutral", "negativo"])
def test_etiquetas_de_sentimiento_validas_se_aceptan(etiqueta):
    assert analisis_con(sentiment_label=etiqueta).sentiment_label == etiqueta


@pytest.mark.parametrize("etiqueta", ["POS", "Positivo", "feliz", "", None])
def test_etiqueta_de_sentimiento_desconocida_se_rechaza(etiqueta):
    with pytest.raises(ValueError, match="etiqueta de sentimiento"):
        analisis_con(sentiment_label=etiqueta)


PUNTAJES_INVALIDOS = [-0.1, 1.1, float("nan"), float("inf"), True, "0.5", None]


@pytest.mark.parametrize("campo", ["sentiment_score", "offense_score"])
@pytest.mark.parametrize("puntaje", PUNTAJES_INVALIDOS)
def test_puntaje_del_modelo_fuera_de_rango_se_rechaza(campo, puntaje):
    with pytest.raises(ValueError, match=campo):
        analisis_con(**{campo: puntaje})


@pytest.mark.parametrize("campo", ["sentiment_score", "offense_score"])
@pytest.mark.parametrize("puntaje", [0, 0.0, 1, 1.0])
def test_puntaje_en_los_extremos_se_acepta(campo, puntaje):
    assert getattr(analisis_con(**{campo: puntaje}), campo) == puntaje
