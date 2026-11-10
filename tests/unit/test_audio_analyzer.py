import hashlib
import shutil
from pathlib import Path

import pytest

from src.adapters.audio_analyzer import AudioAnalyzer
from src.adapters.text_analyzer import cargar_ajustes_de_texto
from src.application.analyze_text import TextSettings
from src.application.ports import Analyzer
from src.domain.finding import Severity
from src.domain.severity import SeverityRules
from src.domain.text_analysis import MessageAnalysis
from src.domain.transcription import TranscriptSegment
from tests.contratos import comprobar_analyzer
from tests.dobles import FakeTextModels

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = {
    "severidad": [
        {"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"},
        {"categoria": "ofensivo", "umbral": 0.5, "nivel": "media"},
    ]
}
LEXICO = {"reunion": ["cafe", "plaza"], "conflicto": ["deuda", "pagar"]}
RF06 = {"palabras_clave", "tema", "sentimiento"}
CUARTA_SALIDA = {"amenaza", "ofensivo", "sin_ofensa"}
TEXTO_AMENAZA = "si no pagas la deuda vas a ver"
AMENAZA = MessageAnalysis(
    lemmas=("pagar", "deuda"),
    sentiment_label="negativo",
    sentiment_score=0.9,
    offense_score=0.1,
    threat_patterns=("vas a ver",),
)


class FakeTranscriber:
    def __init__(self, segmentos):
        self.segmentos = list(segmentos)
        self.llamadas = []

    def transcribe(self, path):
        self.llamadas.append(path)
        return list(self.segmentos)


@pytest.fixture
def nota(tmp_path):
    ruta = tmp_path / "nota.ogg"
    ruta.write_bytes(b"bytes sinteticos que simulan una nota de voz")
    return ruta


def ajustes(tamano_lote=50):
    return TextSettings(SeverityRules.from_dict(REGLAS), LEXICO, tamano_lote=tamano_lote)


def analizador(segmentos, modelos=None, tamano_lote=50):
    return AudioAnalyzer(FakeTranscriber(segmentos), modelos or FakeTextModels(), ajustes(tamano_lote))


def segmentos_regulares(cantidad, duracion=3.55):
    return [
        TranscriptSegment(round(i * duracion, 2), round((i + 1) * duracion, 2), f"frase {i}", 0.9)
        for i in range(cantidad)
    ]


def de_categoria(hallazgos, categoria):
    return [h for h in hallazgos if h.category == categoria]


def test_transcripcion_pasa_por_analisis_de_texto(nota):
    segmentos = [
        TranscriptSegment(0.0, 3.5, "nos vemos en la plaza", 0.92),
        TranscriptSegment(3.5, 8.25, TEXTO_AMENAZA, 0.81),
    ]
    modelos = FakeTextModels({TEXTO_AMENAZA: AMENAZA})

    hallazgos = analizador(segmentos, modelos).analyze(nota)

    transcripciones = de_categoria(hallazgos, "transcripcion")
    assert [(h.detail, h.evidence.position) for h in transcripciones] == [
        ("nos vemos en la plaza", "segmento 0 t=0.00-3.50s"),
        (TEXTO_AMENAZA, "segmento 1 t=3.50-8.25s"),
    ]
    assert [h.confidence for h in transcripciones] == pytest.approx([0.92, 0.81])
    assert all(h.severity is Severity.BAJA for h in transcripciones)
    for categoria in RF06:
        (hallazgo,) = de_categoria(hallazgos, categoria)
        assert hallazgo.evidence.position == "segmentos 0-1 t=0.00-8.25s"
    (amenaza,) = de_categoria(hallazgos, "amenaza")
    assert amenaza.severity is Severity.ALTA
    assert amenaza.evidence.position == "segmentos 1 t=3.50-8.25s"
    assert "1 t=3.50-8.25s" in amenaza.detail
    assert modelos.llamadas == [["nos vemos en la plaza", TEXTO_AMENAZA]]
    esperado = hashlib.sha256(nota.read_bytes()).hexdigest()
    assert {h.evidence.object_sha256 for h in hallazgos} == {esperado}


def test_posiciones_de_audio_no_usan_indices_de_mensaje_ni_hora_ficticia(nota):
    segmentos = [TranscriptSegment(4.2, 7.85, TEXTO_AMENAZA, 0.8), TranscriptSegment(12.0, 15.1, TEXTO_AMENAZA, 0.7)]

    hallazgos = analizador(segmentos, FakeTextModels({TEXTO_AMENAZA: AMENAZA})).analyze(nota)

    assert all(not h.evidence.position.startswith("mensaje") for h in hallazgos)
    (amenaza,) = de_categoria(hallazgos, "amenaza")
    assert amenaza.evidence.position == "segmentos 0,1 t=4.20-7.85s,12.00-15.10s"
    assert "1970" not in amenaza.detail


def test_transcriptor_recibe_la_ruta_de_la_nota(nota):
    transcriptor = FakeTranscriber([])

    AudioAnalyzer(transcriptor, FakeTextModels(), ajustes()).analyze(nota)

    assert transcriptor.llamadas == [nota]


def test_nota_sin_segmentos_devuelve_lista_vacia(nota):
    modelos = FakeTextModels()

    assert analizador([], modelos).analyze(nota) == []
    assert modelos.llamadas == []


def test_segmentos_de_texto_vacio_se_descartan(nota):
    segmentos = [
        TranscriptSegment(0.0, 2.0, "hola", 0.9),
        TranscriptSegment(2.0, 4.0, "   ", 0.4),
        TranscriptSegment(4.0, 6.0, "adios", 0.8),
    ]
    modelos = FakeTextModels()

    hallazgos = analizador(segmentos, modelos).analyze(nota)

    transcripciones = de_categoria(hallazgos, "transcripcion")
    assert [h.detail for h in transcripciones] == ["hola", "adios"]
    assert "t=0.00-2.00s" in transcripciones[0].evidence.position
    assert "t=4.00-6.00s" in transcripciones[1].evidence.position
    assert modelos.llamadas == [["hola", "adios"]]


def test_nota_con_solo_segmentos_vacios_devuelve_lista_vacia(nota):
    modelos = FakeTextModels()
    segmentos = [TranscriptSegment(0.0, 1.0, "", 0.1), TranscriptSegment(1.0, 2.0, " ", 0.1)]

    assert analizador(segmentos, modelos).analyze(nota) == []
    assert modelos.llamadas == []


def test_mas_segmentos_que_el_tamano_de_lote_producen_un_analisis_por_lote(nota):
    modelos = FakeTextModels()

    hallazgos = analizador(segmentos_regulares(8), modelos, tamano_lote=6).analyze(nota)

    assert [len(llamada) for llamada in modelos.llamadas] == [6, 2]
    assert len(de_categoria(hallazgos, "transcripcion")) == 8
    posiciones = [h.evidence.position for h in de_categoria(hallazgos, "palabras_clave")]
    assert posiciones == ["segmentos 0-5 t=0.00-21.30s", "segmentos 6-7 t=21.30-28.40s"]
    for posicion in posiciones:
        del_lote = {h.category for h in hallazgos if h.evidence.position == posicion}
        assert RF06 <= del_lote
        assert len(del_lote & CUARTA_SALIDA) == 1


def test_transcripciones_siguen_el_orden_de_los_segmentos(nota):
    hallazgos = analizador(segmentos_regulares(4)).analyze(nota)

    transcripciones = de_categoria(hallazgos, "transcripcion")
    assert [h.detail for h in transcripciones] == ["frase 0", "frase 1", "frase 2", "frase 3"]
    assert [h.evidence.position for h in transcripciones] == [
        "segmento 0 t=0.00-3.55s",
        "segmento 1 t=3.55-7.10s",
        "segmento 2 t=7.10-10.65s",
        "segmento 3 t=10.65-14.20s",
    ]


def test_audio_analyzer_cumple_el_contrato_de_analyzer(nota):
    segmentos = [TranscriptSegment(0.0, 3.5, "hola", 0.9), TranscriptSegment(3.5, 8.0, TEXTO_AMENAZA, 0.8)]
    instancia = analizador(segmentos, FakeTextModels({TEXTO_AMENAZA: AMENAZA}))

    assert isinstance(instancia, Analyzer)
    comprobar_analyzer(instancia, nota)


def copiar_config_de_texto(tmp_path):
    destino = tmp_path / "texto.toml"
    shutil.copyfile(RAIZ / "config" / "texto.toml", destino)
    return destino


def severidad_de_amenaza(config, nota):
    transcriptor = FakeTranscriber([TranscriptSegment(0.0, 2.5, TEXTO_AMENAZA, 0.9)])
    instancia = AudioAnalyzer.from_config(transcriptor, FakeTextModels({TEXTO_AMENAZA: AMENAZA}), config)
    (amenaza,) = de_categoria(instancia.analyze(nota), "amenaza")
    return amenaza.severity


def test_from_config_con_la_configuracion_de_texto_marca_amenaza_alta(tmp_path, nota):
    assert severidad_de_amenaza(copiar_config_de_texto(tmp_path), nota) is Severity.ALTA


def test_from_config_aplica_las_reglas_del_archivo(tmp_path, nota):
    config = copiar_config_de_texto(tmp_path)
    contenido = config.read_text(encoding="utf-8")
    config.write_text(contenido.replace('nivel = "alta"', 'nivel = "media"'), encoding="utf-8")

    assert severidad_de_amenaza(config, nota) is Severity.MEDIA


def test_from_config_aplica_el_tamano_de_lote_del_archivo(tmp_path, nota):
    config = copiar_config_de_texto(tmp_path)
    contenido = config.read_text(encoding="utf-8")
    config.write_text(contenido.replace("tamano_lote = 50", "tamano_lote = 2"), encoding="utf-8")
    modelos = FakeTextModels()

    AudioAnalyzer.from_config(FakeTranscriber(segmentos_regulares(5)), modelos, config).analyze(nota)

    assert [len(llamada) for llamada in modelos.llamadas] == [2, 2, 1]


def test_cargar_ajustes_de_texto_lee_el_archivo(tmp_path):
    config = tmp_path / "texto.toml"
    config.write_text(
        "tamano_lote = 7\n"
        "n_palabras_clave = 3\n"
        "umbral_ofensa = 0.4\n\n"
        "[[severidad]]\n"
        'categoria = "amenaza"\n'
        "umbral = 0.5\n"
        'nivel = "alta"\n\n'
        "[temas]\n"
        'conflicto = ["deuda"]\n',
        encoding="utf-8",
    )

    leidos = cargar_ajustes_de_texto(config)

    assert isinstance(leidos, TextSettings)
    assert (leidos.tamano_lote, leidos.n_palabras_clave, leidos.umbral_ofensa) == (7, 3, pytest.approx(0.4))
    assert dict(leidos.lexico) == {"conflicto": ["deuda"]}
    assert leidos.reglas.severity_for("amenaza", 1.0) is Severity.ALTA


def test_cargar_ajustes_de_texto_usa_valores_por_omision(tmp_path):
    config = tmp_path / "texto.toml"
    config.write_text('[[severidad]]\ncategoria = "amenaza"\numbral = 0.5\nnivel = "alta"\n', encoding="utf-8")

    leidos = cargar_ajustes_de_texto(config)

    assert (leidos.tamano_lote, leidos.n_palabras_clave, leidos.umbral_ofensa) == (50, 5, 0.5)
    assert dict(leidos.lexico) == {}


def test_cargar_ajustes_de_texto_rechaza_umbral_de_ofensa_fuera_de_rango(tmp_path):
    config = tmp_path / "texto.toml"
    config.write_text(
        'umbral_ofensa = 2\n\n[[severidad]]\ncategoria = "amenaza"\numbral = 0.5\nnivel = "alta"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="umbral_ofensa"):
        cargar_ajustes_de_texto(config)
