import os
from pathlib import Path
from threading import Event

import pytest

from scripts.measure.comparar_carga import MeasurementRunner, validar_equivalencia
from src.domain.transcription import TranscriptSegment


class TranscriberDeterminista:
    def transcribe(self, _path):
        return [TranscriptSegment(0.25, 1.5, "texto sintético", 0.875)]


class TranscriberBloqueado:
    def transcribe(self, _path):
        Event().wait()


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_measurement_runner_ejecuta_ambas_estrategias_y_recolecta_hijos(tmp_path):
    factory = lambda _workers: TranscriberDeterminista()
    runner = MeasurementRunner(factory, timeout=2, cgroup=tmp_path)
    outputs = {}

    for strategy in ("por_proceso", "workers_compartidos"):
        outputs[strategy], snapshots, baseline = runner.run(
            strategy, 2, Path("audio-sintético.ogg"), measure=False
        )
        assert snapshots == []
        assert baseline is None

    validar_equivalencia(outputs)
    assert outputs["por_proceso"] == outputs["workers_compartidos"]


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_measurement_runner_termina_y_recolecta_al_fallar_la_carga(tmp_path):
    def fail(_workers):
        raise MemoryError("sin memoria")

    runner = MeasurementRunner(fail, timeout=2, cgroup=tmp_path)

    with pytest.raises(RuntimeError, match="MemoryError: sin memoria"):
        runner.run("por_proceso", 1, Path("audio-sintético.ogg"), measure=False)


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX")
def test_measurement_runner_termina_y_recolecta_ante_timeout(tmp_path):
    runner = MeasurementRunner(lambda _workers: TranscriberBloqueado(), timeout=0.1, cgroup=tmp_path)

    with pytest.raises(TimeoutError, match="timeout esperando etapa inferred"):
        runner.run("por_proceso", 1, Path("audio-sintético.ogg"), measure=False)
