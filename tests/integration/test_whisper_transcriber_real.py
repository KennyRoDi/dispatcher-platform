import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

faster_whisper = pytest.importorskip("faster_whisper")

from src.adapters.whisper_transcriber import WhisperTranscriber  # noqa: E402
from src.domain.transcription import TranscriptSegment  # noqa: E402

CONFIG_REPO = Path(__file__).resolve().parents[2] / "config" / "audio.toml"
# La muestra con transcripción conocida llega en la parte 3; hasta entonces la nota se indica a mano.
NOTA = os.environ.get("F09_NOTA")
FRECUENCIA_DE_WHISPER = 16000
# Caso borde medido con el modelo real: una nota de 4.86 s dio un segmento con fin 5.00 s y otras salieron
# con tiempos redondeados de forma gruesa (4.00, 5.00), así que 20 ms no alcanza; 0.5 s los cubre.
HOLGURA_S = 0.5


@pytest.fixture(scope="module")
def transcriptor():
    return WhisperTranscriber.from_config(CONFIG_REPO)


def test_nota_produce_segmentos_ordenados_dentro_de_la_duracion(transcriptor):
    if not NOTA or not Path(NOTA).is_file():
        pytest.skip("define F09_NOTA con una nota de voz propia o con licencia [B.3]")
    duracion = len(faster_whisper.decode_audio(NOTA, sampling_rate=FRECUENCIA_DE_WHISPER)) / FRECUENCIA_DE_WHISPER

    segmentos = transcriptor.transcribe(Path(NOTA))

    assert segmentos
    assert all(isinstance(segmento, TranscriptSegment) for segmento in segmentos)
    assert all(type(valor) is float for s in segmentos for valor in (s.inicio, s.fin, s.confianza))
    assert [s.inicio for s in segmentos] == sorted(s.inicio for s in segmentos)
    assert all(s.fin <= duracion + HOLGURA_S for s in segmentos)
    assert " ".join(s.texto for s in segmentos).strip()


def test_archivo_que_no_es_audio_se_rechaza_con_value_error(transcriptor, tmp_path):
    texto = tmp_path / "no_es_audio.ogg"
    texto.write_text("texto sintetico con extension de audio", encoding="utf-8")

    with pytest.raises(ValueError):
        transcriptor.transcribe(texto)
