import pytest

from scripts.measure.comparar_carga import (
    ESTRATEGIAS,
    _arguments,
    summarize_runs,
    validar_equivalencia,
)
from src.domain.transcription import TranscriptSegment


SEGMENTO = TranscriptSegment(0.25, 1.5, "texto", 0.875)


def test_validar_equivalencia_compara_todos_los_segmentos():
    salidas = {"por_proceso": [[SEGMENTO]], "workers_compartidos": [[SEGMENTO]]}

    assert validar_equivalencia(salidas) == salidas


@pytest.mark.parametrize(
    "salida",
    [
        TranscriptSegment(0.5, 1.5, "texto", 0.875),
        TranscriptSegment(0.25, 1.5, "texto", 0.5),
        TranscriptSegment(0.25, 1.6, "texto", 0.875),
        TranscriptSegment(0.25, 1.5, "otro", 0.875),
    ],
)
def test_validar_equivalencia_rechaza_diferencia_de_cualquier_campo(salida):
    salidas = {"por_proceso": [[SEGMENTO]], "workers_compartidos": [[salida]]}

    with pytest.raises(ValueError, match="no coinciden"):
        validar_equivalencia(salidas)


def test_validar_equivalencia_rechaza_estrategia_ausente():
    with pytest.raises(ValueError, match="faltan estrategias"):
        validar_equivalencia({"por_proceso": [[SEGMENTO]]})


def test_summarize_runs_calcula_media_rango_y_diferencia_de_baseline():
    runs = [
        {
            "strategy": "por_proceso", "workers": 1,
            "baseline": {"memory_current": 100},
            "snapshots": [{
                "stage": "loaded", "rss_bytes": 8, "pss_bytes": 6,
                "cgroup": {"memory_current": 110},
            }],
        },
        {
            "strategy": "por_proceso", "workers": 1,
            "baseline": {"memory_current": 100},
            "snapshots": [{
                "stage": "loaded", "rss_bytes": 12, "pss_bytes": 10,
                "cgroup": {"memory_current": 114},
            }],
        },
    ]

    [summary] = summarize_runs(runs)

    assert summary["repetitions"] == 2
    assert summary["metrics"]["pss_bytes"] == {
        "mean": 8, "min": 6, "max": 10, "range": 4
    }
    assert summary["metrics"]["memory_current_delta_bytes"] == {
        "mean": 12, "min": 10, "max": 14, "range": 4
    }


def test_cli_acepta_ambas_estrategias_y_procesos(tmp_path):
    config = tmp_path / "audio.toml"
    entrada = tmp_path / "audio.ogg"
    config.write_text("config sintética", encoding="utf-8")
    entrada.write_bytes(b"audio sintetico")

    args = _arguments([
        "--config", str(config), "--hilos", "1", "--entrada", str(entrada),
        "--procesos", "1", "2", "--estrategias", *ESTRATEGIAS,
        "--solo-validar", "--salida", str(tmp_path / "salida"),
    ])

    assert args.procesos == [1, 2]
    assert args.estrategias == list(ESTRATEGIAS)


def test_cli_rechaza_una_sola_estrategia(tmp_path):
    config = tmp_path / "audio.toml"
    entrada = tmp_path / "audio.ogg"
    config.touch()
    entrada.touch()

    with pytest.raises(SystemExit):
        _arguments([
            "--config", str(config), "--hilos", "1", "--entrada", str(entrada),
            "--procesos", "1", "--estrategias", "por_proceso",
            "--solo-validar", "--salida", str(tmp_path / "salida"),
        ])
