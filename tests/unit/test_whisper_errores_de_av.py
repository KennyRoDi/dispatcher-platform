import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.adapters.whisper_transcriber import ConfigWhisper, WhisperTranscriber

CONFIG = ConfigWhisper(nombre="base", revision="a" * 40, idioma="es", compute_type="int8", beam_size=3, hilos=2)


class FFmpegErrorFalso(Exception):
    pass


class ModeloQueFalla:
    def __init__(self, error):
        self.error = error

    def transcribe(self, audio, **opciones):
        raise self.error


@dataclass
class Segmento:
    start: float
    end: float
    text: str
    avg_logprob: float


class ModeloQueFallaAlRecorrer:
    def __init__(self, error):
        self.error = error

    def transcribe(self, audio, **opciones):
        return self._generar(), None

    def _generar(self):
        yield Segmento(0.0, 1.0, " hola", -0.1)
        raise self.error


@pytest.fixture
def con_av_falso(monkeypatch):
    paquete = types.ModuleType("av")
    paquete.__path__ = []
    errores = types.ModuleType("av.error")
    errores.FFmpegError = FFmpegErrorFalso
    paquete.error = errores
    monkeypatch.setitem(sys.modules, "av", paquete)
    monkeypatch.setitem(sys.modules, "av.error", errores)


@pytest.fixture
def sin_av(monkeypatch):
    monkeypatch.setitem(sys.modules, "av", None)
    monkeypatch.delitem(sys.modules, "av.error", raising=False)


@pytest.fixture
def nota(tmp_path):
    ruta = tmp_path / "nota.ogg"
    ruta.write_bytes(b"bytes sinteticos")
    return ruta


def transcribir(modelo, nota):
    return WhisperTranscriber(modelo, CONFIG).transcribe(Path(nota))


class SinMemoria(FFmpegErrorFalso, MemoryError):
    pass


class TiempoAgotado(FFmpegErrorFalso, TimeoutError):
    pass


class Reintentable(FFmpegErrorFalso, BlockingIOError):
    pass


class Interrumpido(FFmpegErrorFalso, InterruptedError):
    pass


class SinPermiso(FFmpegErrorFalso, PermissionError):
    pass


TRANSITORIOS = [SinMemoria, TiempoAgotado, Reintentable, Interrumpido, SinPermiso]
IDS_TRANSITORIOS = ["enomem", "etimedout", "eagain", "eintr", "eacces"]


@pytest.mark.parametrize("clase", TRANSITORIOS, ids=IDS_TRANSITORIOS)
def test_error_transitorio_de_av_se_propaga_para_poder_reintentarse(con_av_falso, nota, clase):
    error = clase("transitorio")

    with pytest.raises(clase) as capturado:
        transcribir(ModeloQueFalla(error), nota)

    assert capturado.value is error


@pytest.mark.parametrize("clase", TRANSITORIOS, ids=IDS_TRANSITORIOS)
def test_error_transitorio_al_recorrer_los_segmentos_se_propaga(con_av_falso, nota, clase):
    with pytest.raises(clase):
        transcribir(ModeloQueFallaAlRecorrer(clase("transitorio")), nota)


class NoExiste(FFmpegErrorFalso, FileNotFoundError):
    pass


@pytest.mark.parametrize("error", [NoExiste("no existe"), OSError("lectura")], ids=["no-existe", "oserror"])
def test_error_permanente_de_entrada_sigue_siendo_value_error_con_la_ruta(con_av_falso, nota, error):
    with pytest.raises(ValueError, match="nota.ogg"):
        transcribir(ModeloQueFalla(error), nota)


def test_ffmpeg_error_que_no_es_oserror_ni_valueerror_se_rechaza_con_value_error(con_av_falso, nota):
    with pytest.raises(ValueError, match="nota.ogg"):
        transcribir(ModeloQueFalla(FFmpegErrorFalso("Decoder not found")), nota)


def test_ffmpeg_error_al_recorrer_los_segmentos_se_rechaza_con_value_error(con_av_falso, nota):
    with pytest.raises(ValueError, match="nota.ogg"):
        transcribir(ModeloQueFallaAlRecorrer(FFmpegErrorFalso("Decoder not found")), nota)


def test_sin_av_un_error_ajeno_a_la_entrada_se_propaga_sin_convertirse(sin_av, nota):
    error = FFmpegErrorFalso("no es de la entrada")

    with pytest.raises(FFmpegErrorFalso) as capturado:
        transcribir(ModeloQueFalla(error), nota)

    assert capturado.value is error


@pytest.mark.parametrize("error", [OSError("lectura"), FileNotFoundError("no existe"), IndexError("sin audio")])
def test_sin_av_los_errores_de_entrada_siguen_dando_value_error(sin_av, nota, error):
    with pytest.raises(ValueError, match="nota.ogg"):
        transcribir(ModeloQueFalla(error), nota)


@pytest.mark.parametrize(
    "error",
    [ConnectionResetError("reset"), BrokenPipeError("pipe"), IsADirectoryError("directorio"), NotADirectoryError("no")],
    ids=["connection-reset", "broken-pipe", "es-directorio", "no-es-directorio"],
)
def test_otros_oserror_de_entrada_se_rechazan_con_value_error(sin_av, nota, error):
    with pytest.raises(ValueError, match="nota.ogg"):
        transcribir(ModeloQueFalla(error), nota)


def test_memoryerror_real_sin_av_se_propaga(sin_av, nota):
    with pytest.raises(MemoryError):
        transcribir(ModeloQueFalla(MemoryError()), nota)
