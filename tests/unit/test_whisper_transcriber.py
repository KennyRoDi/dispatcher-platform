import importlib
import math
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from src.adapters.whisper_transcriber import ConfigWhisper, WhisperTranscriber
from src.domain.transcription import TranscriptSegment

RAIZ = Path(__file__).resolve().parents[2]
MODULO = "src.adapters.whisper_transcriber"
BIBLIOTECAS_PESADAS = ("faster_whisper", "ctranslate2", "av")
CONFIG = ConfigWhisper(nombre="base", revision="a" * 40, idioma="es", compute_type="int8", beam_size=3, hilos=2)


# Imita faster_whisper.transcribe.Segment: el texto llega con el espacio inicial que deja Whisper.
@dataclass(frozen=True)
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float
    id: int = 0
    no_speech_prob: float = 0.01


@dataclass(frozen=True)
class FakeInfo:
    language: str = "es"
    duration: float = 30.0


# WhisperModel.transcribe devuelve (generador de Segment, TranscriptionInfo); el generador es perezoso.
class FakeWhisperModel:
    def __init__(self, segmentos=(), error=None, error_al_iterar=None):
        self.segmentos = list(segmentos)
        self.error = error
        self.error_al_iterar = error_al_iterar
        self.llamadas = []

    def transcribe(self, audio, **opciones):
        self.llamadas.append((audio, opciones))
        if self.error is not None:
            raise self.error
        return self._generar(), FakeInfo()

    def _generar(self):
        yield from self.segmentos
        if self.error_al_iterar is not None:
            raise self.error_al_iterar


@pytest.fixture
def nota(tmp_path):
    ruta = tmp_path / "nota.ogg"
    ruta.write_bytes(b"bytes sinteticos que simulan una nota de voz")
    return ruta


def transcribir(segmentos, nota, config=CONFIG):
    return WhisperTranscriber(FakeWhisperModel(segmentos), config).transcribe(nota)


def test_cada_segmento_se_traduce_a_transcript_segment(nota):
    segmentos = [
        FakeSegment(0.0, 4.2, " Hola, ¿nos vemos mañana?", -0.105),
        FakeSegment(4.2, 7.85, " Si no pagas vas a ver.", -0.2),
    ]

    resultado = transcribir(segmentos, nota)

    assert all(isinstance(segmento, TranscriptSegment) for segmento in resultado)
    assert [(s.inicio, s.fin, s.texto) for s in resultado] == [
        (0.0, 4.2, "Hola, ¿nos vemos mañana?"),
        (4.2, 7.85, "Si no pagas vas a ver."),
    ]
    assert [s.confianza for s in resultado] == pytest.approx([math.exp(-0.105), math.exp(-0.2)])


def test_sin_segmentos_devuelve_lista_vacia(nota):
    assert transcribir([], nota) == []


@pytest.mark.parametrize("tipo", [np.float32, np.float64], ids=["float32", "float64"])
def test_tiempos_y_confianza_de_numpy_quedan_en_float_nativo(nota, tipo):
    [segmento] = transcribir([FakeSegment(tipo(1.5), tipo(3.25), " texto", tipo(-0.3))], nota)

    assert all(type(valor) is float for valor in (segmento.inicio, segmento.fin, segmento.confianza))
    assert (segmento.inicio, segmento.fin) == pytest.approx((1.5, 3.25))
    assert segmento.confianza == pytest.approx(math.exp(-0.3), rel=1e-6)


@pytest.mark.parametrize(
    "avg_logprob, confianza",
    [(-0.5, math.exp(-0.5)), (0.0, 1.0), (0.3, 1.0), (-60.0, math.exp(-60.0)), (float("-inf"), 0.0)],
    ids=["negativo", "cero", "positivo-se-acota-a-uno", "muy-negativo", "menos-infinito"],
)
def test_confianza_es_exp_de_avg_logprob_acotada_a_uno(nota, avg_logprob, confianza):
    [segmento] = transcribir([FakeSegment(0.0, 1.0, " hola", avg_logprob)], nota)

    assert segmento.confianza == pytest.approx(confianza)
    assert 0.0 <= segmento.confianza <= 1.0


def test_transcribe_la_ruta_recibida_con_el_idioma_y_beam_size_del_config(nota):
    modelo = FakeWhisperModel([FakeSegment(0.0, 1.0, " hola", -0.1)])

    WhisperTranscriber(modelo, CONFIG).transcribe(nota)

    [(audio, opciones)] = modelo.llamadas
    assert Path(audio) == nota
    assert opciones.get("language") == "es"
    assert opciones.get("beam_size") == 3


def test_segmentos_desordenados_se_devuelven_ordenados_por_inicio(nota):
    segmentos = [
        FakeSegment(9.0, 12.0, " tercero", -0.1),
        FakeSegment(0.0, 4.0, " primero", -0.1),
        FakeSegment(4.0, 9.0, " segundo", -0.1),
    ]

    resultado = transcribir(segmentos, nota)

    assert [s.texto for s in resultado] == ["primero", "segundo", "tercero"]
    assert [s.inicio for s in resultado] == [0.0, 4.0, 9.0]


def test_avg_logprob_nan_no_se_reporta_como_confianza_maxima(nota):
    # min(0.0, nan) devuelve 0.0 porque toda comparación con NaN es falsa: sin rechazarlo, la confianza sería 1.0.
    with pytest.raises(ValueError):
        transcribir([FakeSegment(0.0, 1.0, " hola", float("nan"))], nota)


class InvalidDataErrorFalso(ValueError):
    pass


# PyAV 12+ define InvalidDataError(FFmpegError, ValueError) y FileNotFoundError(FFmpegError, FileNotFoundError);
# no se pudo comprobar aquí porque av no está instalado: lo confirma la integración.
ERRORES_DE_DECODIFICACION = [
    InvalidDataErrorFalso("[Errno 1094995529] Invalid data found when processing input"),
    FileNotFoundError("[Errno 2] No such file or directory"),
    OSError("error de lectura"),
]
IDS_DE_ERROR = ["invalid-data", "no-existe", "oserror"]


@pytest.mark.parametrize("error", ERRORES_DE_DECODIFICACION, ids=IDS_DE_ERROR)
def test_archivo_que_no_se_puede_decodificar_se_rechaza_con_value_error(tmp_path, error):
    texto = tmp_path / "no_es_audio.ogg"
    texto.write_text("esto no es audio", encoding="utf-8")

    with pytest.raises(ValueError, match="no_es_audio.ogg"):
        WhisperTranscriber(FakeWhisperModel(error=error), CONFIG).transcribe(texto)


@pytest.mark.parametrize("error", ERRORES_DE_DECODIFICACION, ids=IDS_DE_ERROR)
def test_error_de_decodificacion_al_recorrer_los_segmentos_se_rechaza_con_value_error(tmp_path, error):
    # El generador de faster-whisper es perezoso: un error puede aparecer después de devolver el primer segmento.
    truncada = tmp_path / "truncada.ogg"
    truncada.write_bytes(b"OggS cabecera truncada")
    modelo = FakeWhisperModel([FakeSegment(0.0, 1.0, " hola", -0.1)], error_al_iterar=error)

    with pytest.raises(ValueError, match="truncada.ogg"):
        WhisperTranscriber(modelo, CONFIG).transcribe(truncada)


def test_importar_el_modulo_no_importa_faster_whisper_ctranslate2_ni_av(monkeypatch):
    for biblioteca in BIBLIOTECAS_PESADAS:
        monkeypatch.setitem(sys.modules, biblioteca, None)
    monkeypatch.delitem(sys.modules, MODULO, raising=False)

    modulo = importlib.import_module(MODULO)

    assert hasattr(modulo, "WhisperTranscriber")
    assert all(sys.modules[biblioteca] is None for biblioteca in BIBLIOTECAS_PESADAS)


def escribir_config(ruta, compute_type="float32", beam_size=4, hilos=6):
    ruta.write_text(
        f'[modelo]\nnombre = "base"\nrevision = "{"b" * 40}"\nidioma = "es"\n'
        f'compute_type = "{compute_type}"\nbeam_size = {beam_size}\nhilos = {hilos}\n',
        encoding="utf-8",
    )
    return ruta


class FasterWhisperFalso:
    def __init__(self):
        self.cargados = []

    def instalar(self, monkeypatch):
        modulo = types.ModuleType("faster_whisper")
        modulo.WhisperModel = self._whisper_model
        monkeypatch.setitem(sys.modules, "faster_whisper", modulo)
        return self

    def _whisper_model(self, model_size_or_path, **opciones):
        self.cargados.append((model_size_or_path, opciones))
        return FakeWhisperModel([FakeSegment(0.0, 2.0, " hola", -0.1)])


def test_from_config_carga_el_modelo_una_sola_vez(monkeypatch, tmp_path, nota):
    falso = FasterWhisperFalso().instalar(monkeypatch)
    transcriptor = WhisperTranscriber.from_config(escribir_config(tmp_path / "audio.toml"))

    for _ in range(3):
        [segmento] = transcriptor.transcribe(nota)
        assert segmento.texto == "hola"

    assert len(falso.cargados) == 1


def test_from_config_carga_en_cpu_con_la_revision_compute_type_e_hilos_del_config(monkeypatch, tmp_path):
    falso = FasterWhisperFalso().instalar(monkeypatch)

    WhisperTranscriber.from_config(escribir_config(tmp_path / "audio.toml", compute_type="float32", hilos=6))

    [(nombre, opciones)] = falso.cargados
    assert nombre == "base"
    assert opciones.get("device") == "cpu"
    assert opciones.get("compute_type") == "float32"
    assert opciones.get("cpu_threads") == 6
    assert opciones.get("revision") == "b" * 40


def test_from_config_permite_fijar_hilos_intra_op_y_workers_inter_op(monkeypatch, tmp_path):
    falso = FasterWhisperFalso().instalar(monkeypatch)

    WhisperTranscriber.from_config(
        escribir_config(tmp_path / "audio.toml", hilos=6), num_workers=3, hilos=1
    )

    [(_, opciones)] = falso.cargados
    assert opciones.get("cpu_threads") == 1
    assert opciones.get("num_workers") == 3


def test_from_config_rechaza_override_de_hilos_no_positivo(monkeypatch, tmp_path):
    falso = FasterWhisperFalso().instalar(monkeypatch)

    with pytest.raises(ValueError, match="hilos"):
        WhisperTranscriber.from_config(escribir_config(tmp_path / "audio.toml"), hilos=0)

    assert falso.cargados == []


def test_from_config_usa_idioma_y_beam_size_del_config_al_transcribir(monkeypatch, tmp_path, nota):
    modelo = FakeWhisperModel([FakeSegment(0.0, 1.0, " hola", -0.1)])
    modulo = types.ModuleType("faster_whisper")
    modulo.WhisperModel = lambda *args, **kwargs: modelo
    monkeypatch.setitem(sys.modules, "faster_whisper", modulo)

    WhisperTranscriber.from_config(escribir_config(tmp_path / "audio.toml", beam_size=4)).transcribe(nota)

    [(_, opciones)] = modelo.llamadas
    assert (opciones.get("language"), opciones.get("beam_size")) == ("es", 4)


def test_from_config_importa_faster_whisper_solo_al_cargar(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    with pytest.raises(ImportError):
        WhisperTranscriber.from_config(escribir_config(tmp_path / "audio.toml"))


@pytest.mark.parametrize(
    "compute_type, beam_size", [("rapido", 4), ("int8", 0)], ids=["compute-type-desconocido", "beam-size-cero"]
)
def test_from_config_invalido_falla_antes_de_cargar_el_modelo(monkeypatch, tmp_path, compute_type, beam_size):
    falso = FasterWhisperFalso().instalar(monkeypatch)
    config = escribir_config(tmp_path / "audio.toml", compute_type=compute_type, beam_size=beam_size)

    with pytest.raises(ValueError):
        WhisperTranscriber.from_config(config)

    assert falso.cargados == []


def test_el_modulo_cita_faster_whisper_whisper_y_su_licencia_mit():
    fuente = (RAIZ / "src" / "adapters" / "whisper_transcriber.py").read_text(encoding="utf-8")

    assert "faster-whisper" in fuente
    assert "SYSTRAN" in fuente
    assert "OpenAI" in fuente
    assert "MIT" in fuente


# PyAV 19.0.2 (av/container/streams.py, _get_streams) indexa la tupla de pistas de audio: un archivo que FFmpeg
# abre pero no trae audio, como un video sin pista de audio o una imagen, da IndexError en container.decode(audio=0).
def test_archivo_sin_pista_de_audio_se_rechaza_con_value_error(tmp_path):
    imagen = tmp_path / "sin_audio.ogg"
    imagen.write_bytes(b"PNG imagen sintetica sin pista de audio")
    modelo = FakeWhisperModel(error=IndexError("tuple index out of range"))

    with pytest.raises(ValueError, match="sin_audio.ogg"):
        WhisperTranscriber(modelo, CONFIG).transcribe(imagen)
