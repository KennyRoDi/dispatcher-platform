import json
import wave
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("faster_whisper")
pytest.importorskip("psutil")

from scripts.measure import m5_bench  # noqa: E402

FRECUENCIA = 16000


def silencio(ruta: Path, segundos: int) -> Path:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(b"\x00\x00" * FRECUENCIA * segundos)
    return ruta


def test_bench_corto_en_cpu_dos_configuraciones(tmp_path):
    audio = silencio(tmp_path / "silencio.wav", 2)
    salida = tmp_path / "m5.json"

    resumenes = m5_bench.ejecutar(
        configs=m5_bench.parsear_configs("cpu-int8,cpu-float32", "1"),
        audios=[audio], repeticiones=2, config_whisper=Path(__file__).resolve().parents[2] / "config" / "audio.toml",
        salida=salida,
    )

    assert [r.config for r in resumenes] == ["cpu-int8-h1", "cpu-float32-h1"]
    assert all(r.repeticiones == 2 and r.latencia_media_s > 0 and r.memoria_pico_mb > 0 for r in resumenes)
    assert all(r.throughput_x_realtime > 0 for r in resumenes)
    assert len(json.loads(salida.read_text(encoding="utf-8"))) == 2
