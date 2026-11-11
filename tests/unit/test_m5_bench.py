import json

import pytest

from scripts.measure import m5_bench
from src.domain.benchmark import ResumenConfig, resumir


class RelojFalso:
    def __init__(self, paso):
        self.paso = paso
        self.t = 0.0

    def __call__(self):
        self.t += self.paso
        return self.t


class TranscriptorFalso:
    def __init__(self):
        self.llamadas = []

    def transcribe(self, path):
        self.llamadas.append(path)
        return []


def test_parsear_configs_combina_computo_e_hilos():
    configs = m5_bench.parsear_configs("cpu-float32,cpu-int8", "1,2")

    assert configs == [
        m5_bench.Config("cpu-float32", "float32", 1),
        m5_bench.Config("cpu-float32", "float32", 2),
        m5_bench.Config("cpu-int8", "int8", 1),
        m5_bench.Config("cpu-int8", "int8", 2),
    ]
    assert [c.nombre for c in configs][:2] == ["cpu-float32-h1", "cpu-float32-h2"]


def test_parsear_configs_rechaza_computo_desconocido_o_hilos_invalidos():
    with pytest.raises(ValueError):
        m5_bench.parsear_configs("tpu-int4", "1")
    with pytest.raises(ValueError):
        m5_bench.parsear_configs("cpu-int8", "0")


def test_medir_descarta_calentamiento_y_mide_cada_repeticion(tmp_path):
    transcriptor = TranscriptorFalso()
    audio = tmp_path / "a.wav"
    config = m5_bench.Config("cpu-int8", "int8", 1)

    corridas = m5_bench.medir(
        config, [audio], repeticiones=3, transcriptor=transcriptor,
        reloj=RelojFalso(2.0), memoria_mb=lambda: 512.0, duracion_audio=lambda p: 4.0,
    )

    assert len(transcriptor.llamadas) == 1 + 3
    assert len(corridas) == 3
    assert [c.repeticion for c in corridas] == [1, 2, 3]
    assert all(c.config == "cpu-int8-h1" and c.segundos == pytest.approx(2.0) for c in corridas)
    assert all(c.audio_segundos == 4.0 and c.memoria_pico_mb == 512.0 for c in corridas)


def test_medir_suma_los_audios_de_cada_repeticion(tmp_path):
    audios = [tmp_path / "a.wav", tmp_path / "b.wav"]

    corridas = m5_bench.medir(
        m5_bench.Config("cpu-int8", "int8", 2), audios, repeticiones=1, transcriptor=TranscriptorFalso(),
        reloj=RelojFalso(1.0), memoria_mb=lambda: 100.0, duracion_audio=lambda p: 3.0,
    )

    assert corridas[0].audio_segundos == 6.0


def test_medir_exige_audio_y_repeticiones(tmp_path):
    comun = dict(transcriptor=TranscriptorFalso(), reloj=RelojFalso(1.0), memoria_mb=lambda: 1.0, duracion_audio=lambda p: 1.0)
    config = m5_bench.Config("cpu-int8", "int8", 1)

    with pytest.raises(ValueError):
        m5_bench.medir(config, [], repeticiones=1, **comun)
    with pytest.raises(ValueError):
        m5_bench.medir(config, [tmp_path / "a.wav"], repeticiones=0, **comun)


def test_escribir_json_guarda_una_fila_por_configuracion(tmp_path):
    from src.domain.benchmark import Corrida

    resumenes = resumir([Corrida("a", 1, 2.0, 4.0, 300.0), Corrida("b", 1, 1.0, 4.0, 400.0)])
    destino = tmp_path / "salida.json"

    m5_bench.escribir_json(resumenes, destino)

    filas = json.loads(destino.read_text(encoding="utf-8"))
    assert [f["config"] for f in filas] == ["a", "b"]
    assert {"latencia_media_s", "latencia_p95_s", "throughput_x_realtime", "memoria_pico_mb", "repeticiones"} <= set(filas[0])
    assert all(isinstance(r, ResumenConfig) for r in resumenes)
