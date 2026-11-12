from pathlib import Path

import pytest

from src.adapters.audio_analyzer import AudioAnalyzer
from src.adapters.image_analyzer import ImageAnalyzer
from src.adapters.text_analyzer import TextAnalyzer
from src.domain.image_detection import Detection
from src.domain.transcription import TranscriptSegment
from src.infrastructure.analizadores import ConstructoresDeModelos, crear_analizador
from tests.contratos import comprobar_analyzer
from tests.dobles import FakeTextModels

CONFIG = Path(__file__).resolve().parents[2] / "config"
ENV = {"CONFIG_DIR": str(CONFIG)}
CHAT = "3/11/26, 08:15 - Ana: Hola\n3/11/26, 08:17 - Luis: Nos vemos\n"


class DetectorFalso:
    def detect(self, path):
        return [Detection("knife", 0.9, (1, 2, 30, 40))]


class TranscriptorFalso:
    def transcribe(self, path):
        return [TranscriptSegment(0.0, 1.5, "hola", 0.9)]


class Constructores:
    def __init__(self):
        self.cargas = {"textos": 0, "detector": 0, "transcriptor": 0}

    def textos(self, config):
        self.cargas["textos"] += 1
        return FakeTextModels()

    def detector(self, config, pesos):
        self.cargas["detector"] += 1
        return DetectorFalso()

    def transcriptor(self, config):
        self.cargas["transcriptor"] += 1
        return TranscriptorFalso()

    def como_dataclass(self):
        return ConstructoresDeModelos(self.textos, self.detector, self.transcriptor)


@pytest.fixture
def constructores():
    return Constructores()


def fuente(tmp_path, nombre, contenido):
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return ruta


@pytest.mark.parametrize("tipo,nombre,contenido,clase", [
    ("text", "fuente.txt", CHAT.encode(), TextAnalyzer),
    ("image", "fuente.jpg", b"imagen sintetica", ImageAnalyzer),
    ("audio", "fuente.ogg", b"audio sintetico", AudioAnalyzer),
])
def test_crear_analizador_devuelve_el_analizador_de_cada_tipo(constructores, tmp_path, tipo, nombre, contenido, clase):
    analizador = crear_analizador(tipo, ENV, constructores.como_dataclass())
    assert isinstance(analizador, clase)
    comprobar_analyzer(analizador, fuente(tmp_path, nombre, contenido))


def test_crear_analizador_rechaza_un_tipo_desconocido(constructores):
    with pytest.raises(ValueError, match="video"):
        crear_analizador("video", ENV, constructores.como_dataclass())
    assert constructores.cargas == {"textos": 0, "detector": 0, "transcriptor": 0}


def test_crear_analizador_carga_los_modelos_una_sola_vez(constructores, tmp_path):
    analizador = crear_analizador("audio", ENV, constructores.como_dataclass())
    ruta = fuente(tmp_path, "fuente.ogg", b"audio sintetico")
    analizador.analyze(ruta)
    analizador.analyze(ruta)
    assert constructores.cargas == {"textos": 1, "detector": 0, "transcriptor": 1}


def test_crear_analizador_de_texto_rechaza_csv_sin_parser(constructores, tmp_path):
    analizador = crear_analizador("text", ENV, constructores.como_dataclass())
    with pytest.raises(ValueError, match="no hay parser"):
        analizador.analyze(fuente(tmp_path, "fuente.csv", b"a,b"))
