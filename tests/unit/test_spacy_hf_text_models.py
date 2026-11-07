import importlib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.adapters.spacy_hf_text_models import SpacyHfTextModels, leer_config_modelos
from src.domain.text_analysis import MessageAnalysis

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_REPO = RAIZ / "config" / "texto.toml"
MODULO = "src.adapters.spacy_hf_text_models"
BIBLIOTECAS_PESADAS = ("spacy", "transformers", "torch")
PALABRAS_VACIAS = {"la", "el", "de", "que", "a", "me", "no", "si", "lo"}
PUNTUACION = set(".,;:!?¿¡")
NEUTRO = {"NEG": 0.1, "NEU": 0.8, "POS": 0.1}
INOFENSIVO = {"HS": 0.01, "TR": 0.01, "AG": 0.01}


@dataclass(frozen=True)
class Token:
    text: str
    lemma_: str
    is_stop: bool
    is_punct: bool
    is_space: bool = False


@dataclass(frozen=True)
class Doc:
    text: str
    tokens: tuple[Token, ...]

    def __iter__(self):
        return iter(self.tokens)


@dataclass(frozen=True)
class Span:
    label_: str


class FakeNlp:
    def __init__(self, lemas=None):
        self.lemas = lemas or {}
        self.llamadas = []

    def pipe(self, texts):
        texts = list(texts)
        self.llamadas.append(texts)
        return (self._doc(texto) for texto in texts)

    def _doc(self, texto):
        palabras = re.findall(r"\w+|[^\w\s]", texto)
        return Doc(texto, tuple(self._token(p) for p in palabras))

    def _token(self, palabra):
        lema = self.lemas.get(palabra, palabra)
        return Token(palabra, lema, palabra.lower() in PALABRAS_VACIAS, palabra in PUNTUACION)


class FakeMatcher:
    def __init__(self, etiquetas_por_texto=None):
        self.etiquetas_por_texto = etiquetas_por_texto or {}

    def __call__(self, doc, *, as_spans):
        return [Span(etiqueta) for etiqueta in self.etiquetas_por_texto.get(doc.text, [])] if as_spans else []


class FakePipeline:
    def __init__(self, por_texto=None, por_defecto=None, faltantes=0):
        self.por_texto = por_texto or {}
        self.por_defecto = por_defecto
        self.faltantes = faltantes
        self.llamadas = []

    def __call__(self, texts, **kwargs):
        texts = list(texts)
        self.llamadas.append(texts)
        salida = [
            [{"label": etiqueta, "score": puntaje} for etiqueta, puntaje in self.por_texto.get(t, self.por_defecto).items()]
            for t in texts
        ]
        return salida[: len(salida) - self.faltantes]


def modelos(nlp=None, matcher=None, sentimiento=None, ofensa=None):
    return SpacyHfTextModels(
        nlp=nlp or FakeNlp(),
        matcher=matcher or FakeMatcher(),
        sentimiento=sentimiento or FakePipeline(por_defecto=NEUTRO),
        ofensa=ofensa or FakePipeline(por_defecto=INOFENSIVO),
    )


@pytest.mark.parametrize(
    ("puntajes", "etiqueta", "puntaje"),
    [
        ({"NEG": 0.1, "NEU": 0.2, "POS": 0.7}, "positivo", 0.7),
        ({"NEG": 0.6, "NEU": 0.3, "POS": 0.1}, "negativo", 0.6),
        ({"NEG": 0.2, "NEU": 0.5, "POS": 0.3}, "neutral", 0.5),
    ],
)
def test_sentimiento_traduce_la_etiqueta_mas_probable_con_su_puntaje(puntajes, etiqueta, puntaje):
    [analisis] = modelos(sentimiento=FakePipeline(por_defecto=puntajes)).analyze_messages(["hola"])

    assert analisis.sentiment_label == etiqueta
    assert analisis.sentiment_score == pytest.approx(puntaje)


def test_etiqueta_de_sentimiento_desconocida_del_modelo_se_rechaza():
    sentimiento = FakePipeline(por_defecto={"MIXED": 0.9, "POS": 0.1})

    with pytest.raises(ValueError, match="etiqueta"):
        modelos(sentimiento=sentimiento).analyze_messages(["hola"])


NOMBRES_DE_OFENSA = [("HS", "TR", "AG"), ("hateful", "targeted", "aggressive")]


@pytest.mark.parametrize(("odio", "dirigido", "agresivo"), NOMBRES_DE_OFENSA)
@pytest.mark.parametrize(("p_odio", "p_agresivo", "esperado"), [(0.3, 0.6, 0.6), (0.8, 0.2, 0.8)])
def test_ofensa_es_el_maximo_de_odio_y_agresividad(odio, dirigido, agresivo, p_odio, p_agresivo, esperado):
    ofensa = FakePipeline(por_defecto={odio: p_odio, dirigido: 0.1, agresivo: p_agresivo})

    [analisis] = modelos(ofensa=ofensa).analyze_messages(["eres un tonto"])

    assert analisis.offense_score == pytest.approx(esperado)


@pytest.mark.parametrize(("odio", "dirigido", "agresivo"), NOMBRES_DE_OFENSA)
def test_dirigido_por_si_solo_no_cuenta_como_ofensa(odio, dirigido, agresivo):
    ofensa = FakePipeline(por_defecto={odio: 0.1, dirigido: 0.99, agresivo: 0.2})

    [analisis] = modelos(ofensa=ofensa).analyze_messages(["tú sabes lo que hiciste"])

    assert analisis.offense_score == pytest.approx(0.2)


def test_lemas_en_minuscula_sin_palabras_vacias_ni_puntuacion():
    nlp = FakeNlp(lemas={"Pagas": "Pagar", "deudas": "Deuda", "Mañana": "mañana"})

    [analisis] = modelos(nlp=nlp).analyze_messages(["¿Pagas la deudas mañana, o no? Mañana."])

    assert analisis.lemmas == ("pagar", "deuda", "mañana", "o", "mañana")


def test_patrones_de_amenaza_encontrados_se_devuelven_sin_repetir():
    texto = "si no pagas vas a ver, vas a ver"
    matcher = FakeMatcher({texto: ["vas_a_ver", "vas_a_ver", "si_no_pagas"]})

    [amenaza, tranquilo] = modelos(matcher=matcher).analyze_messages([texto, "nos vemos en la plaza"])

    assert amenaza.threat_patterns == ("vas_a_ver", "si_no_pagas")
    assert tranquilo.threat_patterns == ()


def test_una_llamada_por_lote_a_spacy_y_a_cada_pipeline_con_resultados_en_orden():
    nlp = FakeNlp()
    sentimiento = FakePipeline(
        por_texto={"a": {"NEG": 0.9, "NEU": 0.05, "POS": 0.05}, "b": {"NEG": 0.05, "NEU": 0.05, "POS": 0.9}},
        por_defecto=NEUTRO,
    )
    ofensa = FakePipeline(por_texto={"b": {"HS": 0.7, "TR": 0.1, "AG": 0.1}}, por_defecto=INOFENSIVO)
    textos = ["a", "b", "c"]

    analisis = modelos(nlp=nlp, sentimiento=sentimiento, ofensa=ofensa).analyze_messages(textos)

    assert nlp.llamadas == [textos]
    assert sentimiento.llamadas == [textos]
    assert ofensa.llamadas == [textos]
    assert all(isinstance(a, MessageAnalysis) for a in analisis)
    assert [a.sentiment_label for a in analisis] == ["negativo", "positivo", "neutral"]
    assert [a.offense_score for a in analisis] == pytest.approx([0.01, 0.7, 0.01])


@pytest.mark.parametrize("modelo", ["sentimiento", "ofensa"])
def test_pipeline_que_devuelve_menos_resultados_que_textos_se_rechaza(modelo):
    por_defecto = NEUTRO if modelo == "sentimiento" else INOFENSIVO
    incompleto = {modelo: FakePipeline(por_defecto=por_defecto, faltantes=1)}

    with pytest.raises(ValueError):
        modelos(**incompleto).analyze_messages(["a", "b"])


def test_importar_el_modulo_no_importa_spacy_ni_transformers(monkeypatch):
    # Un None en sys.modules hace fallar cualquier `import` de esa biblioteca, esté o no instalada.
    for biblioteca in BIBLIOTECAS_PESADAS:
        monkeypatch.setitem(sys.modules, biblioteca, None)
    monkeypatch.delitem(sys.modules, MODULO, raising=False)

    modulo = importlib.import_module(MODULO)

    assert hasattr(modulo, "SpacyHfTextModels")
    assert all(sys.modules[biblioteca] is None for biblioteca in BIBLIOTECAS_PESADAS)


def test_from_config_carga_los_modelos_con_importacion_diferida(monkeypatch):
    for biblioteca in BIBLIOTECAS_PESADAS:
        monkeypatch.setitem(sys.modules, biblioteca, None)

    with pytest.raises(ImportError):
        SpacyHfTextModels.from_config(CONFIG_REPO)


def test_el_modulo_cita_los_modelos_y_sus_licencias():
    fuente = (RAIZ / "src" / "adapters" / "spacy_hf_text_models.py").read_text(encoding="utf-8")

    for cita in ("es_core_news_sm", "GPL-3.0", "pysentimiento/robertuito-sentiment-analysis", "pysentimiento/robertuito-hate-speech"):
        assert cita in fuente
    assert re.search(r"no comercial|non-commercial", fuente, re.IGNORECASE)


def leer_repo():
    with open(CONFIG_REPO, "rb") as archivo:
        return leer_config_modelos(tomllib.load(archivo))


def test_config_del_repositorio_fija_los_tres_modelos_con_su_revision():
    config = leer_repo()

    assert config.spacy.nombre == "es_core_news_sm"
    assert re.fullmatch(r"\d+\.\d+\.\d+", config.spacy.revision)
    assert config.sentimiento.nombre == "pysentimiento/robertuito-sentiment-analysis"
    assert config.ofensa.nombre == "pysentimiento/robertuito-hate-speech"
    for modelo in (config.sentimiento, config.ofensa):
        assert re.fullmatch(r"[0-9a-f]{40}", modelo.revision), "la revisión debe ser un commit, no una rama"


def test_config_del_repositorio_trae_patrones_de_amenaza():
    patrones = leer_repo().patrones_amenaza

    assert patrones
    assert all(p.nombre and p.tokens for p in patrones)


MODELOS_VALIDOS = {
    "spacy": {"nombre": "es_core_news_sm", "revision": "3.8.0"},
    "sentimiento": {"nombre": "pysentimiento/robertuito-sentiment-analysis", "revision": "a" * 40},
    "ofensa": {"nombre": "pysentimiento/robertuito-hate-speech", "revision": "b" * 40},
}
PATRON_VALIDO = {"nombre": "vas_a_ver", "patron": [{"LEMMA": "ir"}, {"LOWER": "a"}, {"LOWER": "ver"}]}


def test_patrones_se_leen_del_formato_toml():
    datos = tomllib.loads(
        "[modelos.spacy]\n"
        'nombre = "es_core_news_sm"\nrevision = "3.8.0"\n\n'
        "[modelos.sentimiento]\n"
        f'nombre = "pysentimiento/robertuito-sentiment-analysis"\nrevision = "{"a" * 40}"\n\n'
        "[modelos.ofensa]\n"
        f'nombre = "pysentimiento/robertuito-hate-speech"\nrevision = "{"b" * 40}"\n\n'
        "[[patrones_amenaza]]\n"
        'nombre = "vas_a_ver"\n'
        'patron = [{ LEMMA = "ir" }, { LOWER = "a" }, { LOWER = "ver" }]\n'
    )

    [patron] = leer_config_modelos(datos).patrones_amenaza

    assert patron.nombre == "vas_a_ver"
    assert list(patron.tokens) == [{"LEMMA": "ir"}, {"LOWER": "a"}, {"LOWER": "ver"}]


@pytest.mark.parametrize(
    "patrones",
    [
        None,
        [],
        "vas a ver",
        [{"patron": PATRON_VALIDO["patron"]}],
        [{"nombre": "", "patron": PATRON_VALIDO["patron"]}],
        [{"nombre": 3, "patron": PATRON_VALIDO["patron"]}],
        [{"nombre": "vas_a_ver"}],
        [{"nombre": "vas_a_ver", "patron": []}],
        [{"nombre": "vas_a_ver", "patron": "vas a ver"}],
        [{"nombre": "vas_a_ver", "patron": ["ir", "a", "ver"]}],
        [{"nombre": "vas_a_ver", "patron": [{}]}],
        ["vas_a_ver"],
    ],
)
def test_patron_de_amenaza_mal_formado_se_rechaza(patrones):
    datos = {"modelos": MODELOS_VALIDOS}
    if patrones is not None:
        datos["patrones_amenaza"] = patrones

    with pytest.raises(ValueError, match="patr"):
        leer_config_modelos(datos)


def sin(modelo=None, campo=None):
    copia = {nombre: dict(datos) for nombre, datos in MODELOS_VALIDOS.items()}
    if campo is None:
        del copia[modelo]
    else:
        del copia[modelo][campo]
    return copia


@pytest.mark.parametrize(
    ("modelos_toml", "mensaje"),
    [
        (None, "modelos"),
        ("es_core_news_sm", "modelos"),
        (sin("spacy"), "spacy"),
        (sin("sentimiento"), "sentimiento"),
        (sin("ofensa"), "ofensa"),
        (sin("ofensa", "nombre"), "nombre"),
        (sin("sentimiento", "revision"), "revision"),
        ({**MODELOS_VALIDOS, "ofensa": {"nombre": "pysentimiento/robertuito-hate-speech", "revision": ""}}, "revision"),
    ],
)
def test_modelos_mal_formados_se_rechazan(modelos_toml, mensaje):
    datos = {"patrones_amenaza": [PATRON_VALIDO]}
    if modelos_toml is not None:
        datos["modelos"] = modelos_toml

    with pytest.raises(ValueError, match=mensaje):
        leer_config_modelos(datos)
