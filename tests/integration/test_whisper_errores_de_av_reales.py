from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("faster_whisper")
av = pytest.importorskip("av")
numpy = pytest.importorskip("numpy")

from src.adapters.whisper_transcriber import WhisperTranscriber  # noqa: E402

CONFIG_REPO = Path(__file__).resolve().parents[2] / "config" / "audio.toml"


@pytest.fixture(scope="module")
def transcriptor():
    return WhisperTranscriber.from_config(CONFIG_REPO)


@pytest.fixture
def video_sin_pista_de_audio(tmp_path):
    ruta = tmp_path / "sin_audio.mp4"
    with av.open(str(ruta), "w") as contenedor:
        flujo = contenedor.add_stream("mpeg4", rate=10)
        flujo.width, flujo.height, flujo.pix_fmt = 64, 64, "yuv420p"
        for _ in range(5):
            cuadro = av.VideoFrame.from_ndarray(numpy.zeros((64, 64, 3), dtype=numpy.uint8), format="rgb24")
            contenedor.mux(flujo.encode(cuadro))
        contenedor.mux(flujo.encode())
    return ruta


def test_archivo_sin_pista_de_audio_se_rechaza_con_value_error(transcriptor, video_sin_pista_de_audio):
    with pytest.raises(ValueError, match="audio legible"):
        transcriptor.transcribe(video_sin_pista_de_audio)


def test_archivo_de_texto_con_extension_de_audio_se_rechaza_con_value_error_de_audio_legible(transcriptor, tmp_path):
    texto = tmp_path / "no_es_audio.ogg"
    texto.write_text("texto sintetico con extension de audio", encoding="utf-8")

    with pytest.raises(ValueError, match="audio legible"):
        transcriptor.transcribe(texto)


def test_archivo_vacio_se_rechaza_con_value_error(transcriptor, tmp_path):
    vacio = tmp_path / "vacio.ogg"
    vacio.write_bytes(b"")

    with pytest.raises(ValueError, match="audio legible"):
        transcriptor.transcribe(vacio)
