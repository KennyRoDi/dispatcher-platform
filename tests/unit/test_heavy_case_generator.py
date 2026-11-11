from pathlib import Path

import pytest

from src.adapters.heavy_case_generator import LICENSE_NAME, ORIGIN, generate_heavy_cases
from src.domain.dataset_plan import MIB, DatasetParams, plan_dataset

MIN_BYTES = 200 * MIB
PARAMS = DatasetParams(cases=8, light_heterogeneous=2, heavy_heterogeneous=3, messages=200, images=60, audios=24)


class SparseRunner:
    def __init__(self, size: int = MIN_BYTES, fail_on_call: int | None = None):
        self.calls: list[list[str]] = []
        self.size = size
        self.fail_on_call = fail_on_call

    def __call__(self, args: list[str]) -> None:
        self.calls.append(list(args))
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            handle.truncate(self.size)
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("ffmpeg fallo")


class NoopRunner:
    def __call__(self, args: list[str]) -> None:
        pass


@pytest.fixture
def plan():
    return plan_dataset(7, PARAMS)


def _heavy_names(plan):
    return {c.name for c in plan.cases if c.heavy_bytes >= MIN_BYTES}


def _relative_calls(runner, out_dir: Path):
    return [[arg.replace(str(out_dir), "") for arg in call] for call in runner.calls]


def test_genera_un_archivo_por_caso_pesado_de_al_menos_200_mib(plan, tmp_path):
    files = generate_heavy_cases(plan, tmp_path, SparseRunner())

    assert {f.case for f in files} == _heavy_names(plan)
    assert len(files) == PARAMS.heavy_heterogeneous
    assert all(f.path.is_file() and f.path.stat().st_size >= MIN_BYTES for f in files)


def test_los_casos_no_pesados_no_producen_archivo(plan, tmp_path):
    runner = SparseRunner()
    generate_heavy_cases(plan, tmp_path, runner)

    assert len(runner.calls) == len(_heavy_names(plan))
    light = {c.name for c in plan.cases} - _heavy_names(plan)
    assert not any((tmp_path / name).exists() for name in light)


def test_el_tipo_es_video_o_documento(plan, tmp_path):
    files = generate_heavy_cases(plan, tmp_path, SparseRunner())

    assert {f.kind for f in files} <= {"video", "documento"}


def test_cada_registro_declara_origen_licencia_y_semilla(plan, tmp_path):
    files = generate_heavy_cases(plan, tmp_path, SparseRunner())

    assert ORIGIN == "sintetico"
    assert LICENSE_NAME == "generado por el equipo, uso academico"
    assert all(f.origen == ORIGIN and f.licencia == LICENSE_NAME and f.semilla == plan.seed for f in files)


def test_las_rutas_quedan_dentro_del_directorio_de_salida(plan, tmp_path):
    out_dir = tmp_path / "salida"
    files = generate_heavy_cases(plan, out_dir, SparseRunner())

    assert all(out_dir.resolve() in f.path.resolve().parents for f in files)


def test_misma_semilla_misma_rutas_y_argumentos(tmp_path):
    first, second = SparseRunner(), SparseRunner()
    files_a = generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path / "a", first)
    files_b = generate_heavy_cases(plan_dataset(7, PARAMS), tmp_path / "b", second)

    assert [(f.case, f.kind, f.path.relative_to(tmp_path / "a")) for f in files_a] == [
        (f.case, f.kind, f.path.relative_to(tmp_path / "b")) for f in files_b
    ]
    assert _relative_calls(first, tmp_path / "a") == _relative_calls(second, tmp_path / "b")


def test_caso_pesado_falla_si_no_alcanza_200_mib(plan, tmp_path):
    runner = SparseRunner(size=MIN_BYTES - 1)

    with pytest.raises(ValueError, match="200 MiB"):
        generate_heavy_cases(plan, tmp_path, runner)


def test_si_no_alcanza_200_mib_no_queda_archivo_parcial(plan, tmp_path):
    with pytest.raises(ValueError):
        generate_heavy_cases(plan, tmp_path, SparseRunner(size=MIN_BYTES - 1))

    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_si_el_ejecutor_falla_se_propaga_y_no_queda_archivo_parcial(plan, tmp_path):
    with pytest.raises(RuntimeError, match="ffmpeg fallo"):
        generate_heavy_cases(plan, tmp_path, SparseRunner(fail_on_call=1))

    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_un_archivo_previo_no_oculta_un_ejecutor_que_no_produjo_nada(plan, tmp_path):
    generate_heavy_cases(plan, tmp_path, SparseRunner())

    with pytest.raises(FileNotFoundError):
        generate_heavy_cases(plan, tmp_path, NoopRunner())
