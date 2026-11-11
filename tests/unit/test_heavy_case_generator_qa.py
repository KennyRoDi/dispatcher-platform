import dataclasses
import subprocess
from pathlib import Path

import pytest

from src.adapters.heavy_case_generator import VIDEO_BITRATE_BPS, generate_heavy_cases
from src.adapters.media_generator import run_ffmpeg
from src.domain.dataset_plan import MIB, DatasetParams, plan_dataset

MIN_BYTES = 200 * MIB
PARAMS = DatasetParams(cases=8, light_heterogeneous=2, heavy_heterogeneous=3, messages=200, images=60, audios=24)


class SparseRunner:
    def __init__(self, size: int = MIN_BYTES):
        self.calls: list[list[str]] = []
        self.size = size

    def __call__(self, args: list[str]) -> None:
        self.calls.append(list(args))
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            handle.truncate(self.size)


def _plan_with_heavy_name(name: str):
    plan = plan_dataset(7, PARAMS)
    cases = tuple(dataclasses.replace(c, name=name) if c.heavy_bytes else c for c in plan.cases)
    return dataclasses.replace(plan, cases=cases)


def _duration(call: list[str]) -> int:
    return int(call[call.index("-t") + 1])


def test_el_borde_exacto_de_200_mib_se_acepta(tmp_path):
    files = generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path, SparseRunner(size=MIN_BYTES))

    assert all(f.bytes == MIN_BYTES for f in files)


def test_un_plan_sin_casos_pesados_no_ejecuta_ni_crea_nada(tmp_path):
    plan = plan_dataset(7, dataclasses.replace(PARAMS, heavy_heterogeneous=0))
    runner = SparseRunner()

    assert generate_heavy_cases(plan, tmp_path / "salida", runner) == []
    assert runner.calls == []
    assert not (tmp_path / "salida").exists()


def test_el_directorio_de_salida_inexistente_se_crea_con_sus_padres(tmp_path):
    files = generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path / "a" / "b" / "c", SparseRunner())

    assert all(f.path.is_file() for f in files)


def test_los_archivos_ajenos_del_caso_se_conservan(tmp_path):
    plan = plan_dataset(7, PARAMS)
    heavy = next(c for c in plan.cases if c.heavy_bytes)
    (tmp_path / heavy.name).mkdir()
    ajeno = tmp_path / heavy.name / "texto.txt"
    ajeno.write_text("hola")

    generate_heavy_cases(plan, tmp_path, SparseRunner())

    assert ajeno.read_text() == "hola"


def test_un_heavy_bytes_mayor_exige_y_entrega_ese_tamano(tmp_path):
    plan = plan_dataset(7, dataclasses.replace(PARAMS, heavy_bytes=300 * MIB))

    with pytest.raises(ValueError, match="300 MiB"):
        generate_heavy_cases(plan, tmp_path, SparseRunner(size=MIN_BYTES))


def test_la_duracion_pedida_alcanza_heavy_bytes_con_el_bitrate_fijo(tmp_path):
    plan = plan_dataset(7, dataclasses.replace(PARAMS, heavy_bytes=300 * MIB))
    runner = SparseRunner(size=300 * MIB)

    generate_heavy_cases(plan, tmp_path, runner)

    assert all(_duration(c) * VIDEO_BITRATE_BPS / 8 >= 300 * MIB for c in runner.calls)


def test_cada_caso_pesado_usa_una_semilla_de_ruido_distinta(tmp_path):
    runner = SparseRunner()

    generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path, runner)

    noises = [next(a for a in c if a.startswith("noise=")) for c in runner.calls]
    assert len(set(noises)) == len(noises)


def test_dos_semillas_dan_semillas_de_ruido_distintas(tmp_path):
    first, second = SparseRunner(), SparseRunner()
    generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path / "a", first)
    generate_heavy_cases(plan_dataset(8, PARAMS), tmp_path / "b", second)

    noise = lambda r: [next(a for a in c if a.startswith("noise=")) for c in r.calls]  # noqa: E731
    assert noise(first) != noise(second)


def test_un_nombre_de_caso_malicioso_no_escribe_fuera_del_destino(tmp_path):
    out_dir = tmp_path / "salida"
    plan = _plan_with_heavy_name("../escape")

    try:
        generate_heavy_cases(plan, out_dir, SparseRunner())
    except ValueError:
        pass

    assert not (tmp_path / "escape").exists()


def test_un_nombre_de_caso_absoluto_no_escribe_fuera_del_destino(tmp_path):
    outside = tmp_path / "fuera"
    plan = _plan_with_heavy_name(str(outside))

    try:
        generate_heavy_cases(plan, tmp_path / "salida", SparseRunner())
    except ValueError:
        pass

    assert not [f for f in tmp_path.rglob("*") if f.is_file() and (tmp_path / "salida") not in f.parents]


def test_si_falla_no_queda_el_directorio_vacio_del_caso(tmp_path):
    with pytest.raises(ValueError):
        generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path, SparseRunner(size=MIN_BYTES - 1))

    assert list(tmp_path.iterdir()) == []


def test_el_error_de_ffmpeg_expone_su_stderr(monkeypatch):
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr=b"Unknown encoder 'mpeg2video'")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(Exception, match="Unknown encoder"):
        run_ffmpeg(["ffmpeg"])
