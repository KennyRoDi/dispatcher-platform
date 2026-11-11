from collections import Counter
from pathlib import Path

import pytest

from src.adapters.media_generator import (
    LICENSE_NAME,
    ORIGIN,
    generate_media,
)
from src.domain.dataset_plan import IMAGE_CATEGORIES, DatasetParams, plan_dataset

AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
LABELS = {"positivo", "neutro"}
PARAMS = DatasetParams(
    cases=8, light_heterogeneous=2, heavy_heterogeneous=2, messages=200, images=60, audios=24, heavy_bytes=1024
)


class FakeRunner:
    def __init__(self, fail_on_call: int | None = None, leave_partial: bool = False):
        self.calls: list[list[str]] = []
        self.fail_on_call = fail_on_call
        self.leave_partial = leave_partial

    def __call__(self, args: list[str]) -> None:
        self.calls.append(list(args))
        output = Path(args[-1])
        if self.fail_on_call == len(self.calls):
            if self.leave_partial:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"parcial")
            raise RuntimeError("ffmpeg fallo")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"medio")


@pytest.fixture
def plan():
    return plan_dataset(7, PARAMS)


def _images(files):
    return [f for f in files if f.kind == "imagen"]


def _audios(files):
    return [f for f in files if f.kind == "audio"]


def _relative_calls(runner: FakeRunner, out_dir: Path) -> list[list[str]]:
    return [[arg.replace(str(out_dir), "") for arg in call] for call in runner.calls]


def test_genera_la_cantidad_exacta_de_imagenes_y_audios_del_plan(plan, tmp_path):
    files = generate_media(plan, tmp_path, FakeRunner())

    assert len(_images(files)) == sum(c.images for c in plan.cases) == 60
    assert len(_audios(files)) == sum(c.audios for c in plan.cases) == 24
    assert all(f.path.is_file() for f in files)


def test_cada_caso_recibe_sus_imagenes_y_audios(plan, tmp_path):
    files = generate_media(plan, tmp_path, FakeRunner())

    for case in plan.cases:
        assert len([f for f in _images(files) if f.case == case.name]) == case.images
        assert len([f for f in _audios(files) if f.case == case.name]) == case.audios


def test_formatos_de_archivo_son_de_imagen_y_audio(plan, tmp_path):
    files = generate_media(plan, tmp_path, FakeRunner())

    assert {f.path.suffix for f in _images(files)} <= IMAGE_SUFFIXES
    assert {f.path.suffix for f in _audios(files)} <= AUDIO_SUFFIXES


def test_cada_imagen_lleva_etiqueta_y_categoria_del_generador(plan, tmp_path):
    images = _images(generate_media(plan, tmp_path, FakeRunner()))

    assert {f.etiqueta for f in images} <= LABELS
    assert {f.categoria for f in images} <= set(IMAGE_CATEGORIES)
    assert {f.categoria for f in images} == set(IMAGE_CATEGORIES)


def test_proporcion_positiva_por_categoria_dentro_de_un_archivo_de_tolerancia(plan, tmp_path):
    images = _images(generate_media(plan, tmp_path, FakeRunner()))

    for categoria in IMAGE_CATEGORIES:
        group = [f for f in images if f.categoria == categoria]
        positives = Counter(f.etiqueta for f in group)["positivo"]
        expected = plan.image_positive_ratio[categoria] * len(group)
        assert abs(positives - expected) <= 1, categoria


def test_hay_imagenes_positivas_y_neutras(plan, tmp_path):
    images = _images(generate_media(plan, tmp_path, FakeRunner()))

    assert Counter(f.etiqueta for f in images).keys() == LABELS


def test_audios_tienen_la_duracion_del_plan_en_orden(plan, tmp_path):
    audios = _audios(generate_media(plan, tmp_path, FakeRunner()))

    assert tuple(f.duration_s for f in audios) == plan.audio_durations
    assert len(set(plan.audio_durations)) > 1


def test_ffmpeg_recibe_la_duracion_de_cada_audio(plan, tmp_path):
    runner = FakeRunner()
    audios = _audios(generate_media(plan, tmp_path, runner))
    by_output = {call[-1]: call for call in runner.calls}

    for audio in audios:
        args = by_output[str(audio.path)]
        assert args[args.index("-t") + 1] == str(audio.duration_s)


def test_audios_etiquetados_por_el_generador(plan, tmp_path):
    audios = _audios(generate_media(plan, tmp_path, FakeRunner()))

    assert all(f.etiqueta for f in audios)


def test_argumentos_de_ffmpeg_usan_lavfi_y_el_formato_de_salida(plan, tmp_path):
    runner = FakeRunner()
    files = generate_media(plan, tmp_path, runner)
    by_output = {call[-1]: call for call in runner.calls}

    assert len(runner.calls) == len(files)
    for media in files:
        args = by_output[str(media.path)]
        assert args[0] == "ffmpeg"
        assert args[args.index("-f") + 1] == "lavfi"
        assert args[args.index("-i") + 1]
    for image in _images(files):
        args = by_output[str(image.path)]
        assert "-frames:v" in args and args[args.index("-frames:v") + 1] == "1"
        assert "-t" not in args


def test_medios_llevan_origen_sintetico_licencia_y_semilla(plan, tmp_path):
    files = generate_media(plan, tmp_path, FakeRunner())

    assert ORIGIN == "sintetico"
    assert LICENSE_NAME
    for media in files:
        assert media.origen == "sintetico"
        assert media.licencia == LICENSE_NAME
        assert media.semilla == plan.seed


def test_misma_semilla_produce_mismos_argumentos_y_metadatos(plan, tmp_path):
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    first_runner, second_runner = FakeRunner(), FakeRunner()

    first = generate_media(plan_dataset(7, PARAMS), first_dir, first_runner)
    second = generate_media(plan_dataset(7, PARAMS), second_dir, second_runner)

    assert _relative_calls(first_runner, first_dir) == _relative_calls(second_runner, second_dir)
    describe = lambda files, base: [
        (f.case, f.kind, f.path.relative_to(base), f.etiqueta, f.categoria, f.duration_s) for f in files
    ]
    assert describe(first, first_dir) == describe(second, second_dir)


def test_semillas_distintas_producen_medios_distintos(tmp_path):
    first_runner, second_runner = FakeRunner(), FakeRunner()

    generate_media(plan_dataset(7, PARAMS), tmp_path / "a", first_runner)
    generate_media(plan_dataset(8, PARAMS), tmp_path / "b", second_runner)

    assert _relative_calls(first_runner, tmp_path / "a") != _relative_calls(second_runner, tmp_path / "b")


def test_todas_las_rutas_quedan_dentro_de_out_dir(plan, tmp_path):
    out_dir = tmp_path / "salida"
    runner = FakeRunner()
    files = generate_media(plan, out_dir, runner)

    root = out_dir.resolve()
    assert all(root in f.path.resolve().parents for f in files)
    assert all(root in Path(call[-1]).resolve().parents for call in runner.calls)
    assert len({f.path for f in files}) == len(files)
    assert [p for p in tmp_path.rglob("*") if p.is_file() and root not in p.resolve().parents] == []


def test_fallo_del_ejecutor_se_propaga(plan, tmp_path):
    with pytest.raises(RuntimeError, match="ffmpeg fallo"):
        generate_media(plan, tmp_path, FakeRunner(fail_on_call=3))


def test_fallo_del_ejecutor_no_deja_archivo_a_medias(plan, tmp_path):
    runner = FakeRunner(fail_on_call=3, leave_partial=True)

    with pytest.raises(RuntimeError):
        generate_media(plan, tmp_path, runner)

    assert not Path(runner.calls[2][-1]).exists()


def test_ejecutor_que_no_produce_archivo_falla(plan, tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_media(plan, tmp_path, lambda args: None)


def test_no_usa_ffmpeg_real_ni_toca_fuera_de_tmp(plan, tmp_path, monkeypatch):
    import subprocess

    def prohibido(*args, **kwargs):
        raise AssertionError("subprocess no debe usarse con ejecutor inyectado")

    monkeypatch.setattr(subprocess, "run", prohibido)
    monkeypatch.setattr(subprocess, "Popen", prohibido)

    assert generate_media(plan, tmp_path, FakeRunner())
