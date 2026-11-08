import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from src.adapters.text_analyzer import TextAnalyzer
from src.application.ports import Analyzer
from src.domain.chat_message import ChatMessage
from src.domain.finding import Severity
from src.domain.severity import SeverityRules
from src.domain.text_analysis import MessageAnalysis
from tests.contratos import comprobar_analyzer
from tests.dobles import FakeConversationParser

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
REGLAS = {
    "severidad": [
        {"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"},
        {"categoria": "ofensivo", "umbral": 0.5, "nivel": "media"},
    ]
}
LEXICO = {"reunion": ["cafe", "plaza"], "conflicto": ["deuda", "pagar"]}
CUARTA_SALIDA = {"amenaza", "ofensivo", "sin_ofensa"}
NEUTRAL = MessageAnalysis(
    lemmas=("hola",), sentiment_label="neutral", sentiment_score=0.8, offense_score=0.0, threat_patterns=()
)
AMENAZA = MessageAnalysis(
    lemmas=("pagar", "deuda"),
    sentiment_label="negativo",
    sentiment_score=0.9,
    offense_score=0.1,
    threat_patterns=("vas a ver",),
)
OFENSA = MessageAnalysis(
    lemmas=("tonto",), sentiment_label="negativo", sentiment_score=0.7, offense_score=0.9, threat_patterns=()
)


class FakeTextModels:
    def __init__(self, por_texto=None):
        self.por_texto = por_texto or {}
        self.llamadas = []

    def analyze_messages(self, texts):
        self.llamadas.append(list(texts))
        return [self.por_texto.get(texto, NEUTRAL) for texto in texts]


def mensajes(cantidad, especiales=None):
    especiales = especiales or {}
    return [
        ChatMessage(INICIO + timedelta(minutes=i), "Ana" if i % 2 else "Beto", especiales.get(i, f"mensaje {i}"), f"chat.txt:{i + 1}")
        for i in range(cantidad)
    ]


@pytest.fixture
def archivo(tmp_path):
    ruta = tmp_path / "chat.txt"
    ruta.write_bytes("conversación sintética de prueba\n".encode("utf-8"))
    return ruta


def analizador(lista, modelos=None, tamano_lote=50):
    return TextAnalyzer(
        FakeConversationParser(lista),
        modelos or FakeTextModels(),
        SeverityRules.from_dict(REGLAS),
        LEXICO,
        tamano_lote=tamano_lote,
    )


def por_categoria(hallazgos):
    return {h.category: h for h in hallazgos}


def test_texto_con_amenaza_produce_categoria_y_severidad(archivo):
    lista = mensajes(3, {1: "si no pagas la deuda vas a ver"})
    modelos = FakeTextModels({"si no pagas la deuda vas a ver": AMENAZA})

    hallazgo = por_categoria(analizador(lista, modelos).analyze(archivo))["amenaza"]

    assert hallazgo.severity is Severity.ALTA
    assert hallazgo.confidence == 1.0
    assert hallazgo.evidence.position == "mensajes 1"
    assert "chat.txt:2" in hallazgo.detail
    assert lista[1].timestamp_utc.isoformat() in hallazgo.detail


def test_lote_sin_ofensas_reporta_sin_ofensa_explicito(archivo):
    hallazgos = analizador(mensajes(4)).analyze(archivo)

    categorias = [h.category for h in hallazgos]
    assert sorted(categorias) == ["palabras_clave", "sentimiento", "sin_ofensa", "tema"]
    sin_ofensa = por_categoria(hallazgos)["sin_ofensa"]
    assert sin_ofensa.severity is Severity.BAJA
    assert sin_ofensa.evidence.position == "mensajes 0-3"


def test_varios_lotes_producen_cuatro_salidas_cada_uno(archivo):
    modelos = FakeTextModels()

    hallazgos = analizador(mensajes(6), modelos, tamano_lote=2).analyze(archivo)

    assert len(hallazgos) == 12
    assert [len(llamada) for llamada in modelos.llamadas] == [2, 2, 2]
    posiciones = {h.evidence.position for h in hallazgos if h.category == "palabras_clave"}
    assert posiciones == {"mensajes 0-1", "mensajes 2-3", "mensajes 4-5"}
    for posicion in posiciones:
        del_lote = [h for h in hallazgos if h.evidence.position == posicion]
        assert {h.category for h in del_lote} - CUARTA_SALIDA == {"palabras_clave", "tema", "sentimiento"}
        assert len({h.category for h in del_lote} & CUARTA_SALIDA) == 1


def test_conversacion_vacia_no_produce_salidas(archivo):
    modelos = FakeTextModels()

    assert analizador([], modelos).analyze(archivo) == []
    assert modelos.llamadas == []


def test_lote_final_incompleto_se_analiza(archivo):
    modelos = FakeTextModels()

    hallazgos = analizador(mensajes(5), modelos, tamano_lote=2).analyze(archivo)

    assert [len(llamada) for llamada in modelos.llamadas] == [2, 2, 1]
    ultimo = [h for h in hallazgos if h.evidence.position == "mensajes 4"]
    assert len(ultimo) == 4


def test_cada_hallazgo_lleva_el_sha256_del_archivo(archivo):
    esperado = hashlib.sha256(archivo.read_bytes()).hexdigest()

    hallazgos = analizador(mensajes(3)).analyze(archivo)

    assert hallazgos
    assert {h.evidence.object_sha256 for h in hallazgos} == {esperado}


def test_posicion_usa_rango_del_lote_e_indices_marcados_en_orden_de_parse(archivo):
    texto = "te vas a arrepentir"
    lista = mensajes(30, {15: texto, 18: texto})
    modelos = FakeTextModels({texto: AMENAZA})

    hallazgos = analizador(lista, modelos, tamano_lote=12).analyze(archivo)

    segundo_lote = [h for h in hallazgos if h.category != "amenaza" and h.evidence.position == "mensajes 12-23"]
    assert {h.category for h in segundo_lote} == {"palabras_clave", "tema", "sentimiento"}
    amenazas = [h for h in hallazgos if h.category == "amenaza"]
    assert [h.evidence.position for h in amenazas] == ["mensajes 15,18"]
    assert any(h.evidence.position == "mensajes 24-29" for h in hallazgos)


def test_amenaza_prevalece_sobre_ofensivo_en_el_mismo_lote(archivo):
    lista = mensajes(3, {0: "eres un tonto", 2: "pagas o vas a ver"})
    modelos = FakeTextModels({"eres un tonto": OFENSA, "pagas o vas a ver": AMENAZA})

    categorias = {h.category for h in analizador(lista, modelos).analyze(archivo)}

    assert "amenaza" in categorias
    assert not categorias & {"ofensivo", "sin_ofensa"}


def test_ofensa_sin_amenaza_produce_ofensivo_con_severidad_media(archivo):
    lista = mensajes(3, {2: "eres un tonto"})
    modelos = FakeTextModels({"eres un tonto": OFENSA})

    hallazgo = por_categoria(analizador(lista, modelos).analyze(archivo))["ofensivo"]

    assert hallazgo.severity is Severity.MEDIA
    assert hallazgo.confidence == pytest.approx(0.9)
    assert hallazgo.evidence.position == "mensajes 2"


def test_salidas_del_lote_resumen_palabras_clave_tema_y_sentimiento(archivo):
    lista = mensajes(2, {0: "a", 1: "b"})
    modelos = FakeTextModels({
        "a": MessageAnalysis(("deuda", "pagar", "deuda"), "negativo", 0.8, 0.0, ()),
        "b": MessageAnalysis(("deuda", "cafe"), "negativo", 0.6, 0.0, ()),
    })

    hallazgos = por_categoria(analizador(lista, modelos).analyze(archivo))

    assert hallazgos["palabras_clave"].detail == "deuda, pagar, cafe"
    assert hallazgos["palabras_clave"].confidence == 1.0
    assert hallazgos["tema"].detail == "conflicto"
    assert hallazgos["tema"].confidence == pytest.approx(0.8)
    assert hallazgos["sentimiento"].detail == "negativo"
    assert hallazgos["sentimiento"].confidence == pytest.approx(0.7)
    assert all(h.severity is Severity.BAJA for h in hallazgos.values())


def test_text_analyzer_cumple_el_contrato_de_analyzer(archivo):
    lista = mensajes(3, {1: "pagas o vas a ver"})
    instancia = analizador(lista, FakeTextModels({"pagas o vas a ver": AMENAZA}))

    assert isinstance(instancia, Analyzer)
    comprobar_analyzer(instancia, archivo)


class ModelosConCantidadErronea:
    def __init__(self, sobrantes):
        self.sobrantes = sobrantes

    def analyze_messages(self, texts):
        analisis = [AMENAZA if "vas a ver" in texto else NEUTRAL for texto in texts]
        return (analisis + [NEUTRAL] * self.sobrantes)[: len(texts) + self.sobrantes]


@pytest.mark.parametrize("sobrantes", [-1, 1])
def test_modelo_con_un_analisis_por_mensaje_distinto_se_rechaza(archivo, sobrantes):
    # Si el modelo omite el último mensaje, la amenaza desaparecería y el lote saldría sin_ofensa.
    lista = mensajes(3, {2: "pagas o vas a ver"})

    with pytest.raises(ValueError):
        analizador(lista, ModelosConCantidadErronea(sobrantes)).analyze(archivo)


def test_confianza_de_ofensivo_es_el_maximo_de_los_marcados(archivo):
    leve = MessageAnalysis(("tonto",), "negativo", 0.7, 0.6, ())
    lista = mensajes(3, {0: "eres un tonto", 2: "eres muy tonto"})
    modelos = FakeTextModels({"eres un tonto": leve, "eres muy tonto": OFENSA})

    hallazgo = por_categoria(analizador(lista, modelos).analyze(archivo))["ofensivo"]

    assert hallazgo.confidence == pytest.approx(0.9)
    assert hallazgo.evidence.position == "mensajes 0,2"


@pytest.mark.parametrize("umbral_ofensa", [2, -0.1, float("nan"), float("inf"), "0.5", True])
def test_umbral_de_ofensa_fuera_de_rango_se_rechaza(umbral_ofensa):
    with pytest.raises(ValueError, match="umbral_ofensa"):
        TextAnalyzer(
            FakeConversationParser([]),
            FakeTextModels(),
            SeverityRules.from_dict(REGLAS),
            LEXICO,
            umbral_ofensa=umbral_ofensa,
        )


def test_from_config_rechaza_umbral_de_ofensa_fuera_de_rango(tmp_path):
    config = tmp_path / "texto.toml"
    config.write_text(
        "umbral_ofensa = 2\n\n"
        "[[severidad]]\n"
        'categoria = "amenaza"\n'
        "umbral = 0.5\n"
        'nivel = "alta"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="umbral_ofensa"):
        TextAnalyzer.from_config(FakeConversationParser([]), FakeTextModels(), config)
