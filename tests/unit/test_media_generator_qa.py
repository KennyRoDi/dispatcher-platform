import dataclasses
import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from src.adapters import media_generator
from src.adapters.media_generator import AUDIO_FORMATS, IMAGE_FORMATS, generate_media, run_ffmpeg
from src.domain.dataset_plan import IMAGE_CATEGORIES, DatasetParams, plan_dataset


PARAMS = DatasetParams(
    cases=2, light_heterogeneous=1, heavy_heterogeneous=1, messages=10, images=40, audios=20, heavy_bytes=1024
)


class Recorder:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> None:
        self.calls.append(list(args))
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"medio")


def _generate(seed=7, params=PARAMS, runner=None, out=None):
    runner = runner or Recorder()
    files = generate_media(plan_dataset(seed, params), out, runner)
    return files, runner


def test_cada_medio_queda_en_el_directorio_de_su_caso(tmp_path):
    files, _ = _generate(out=tmp_path)

    assert all(f.path.parent == tmp_path / f.case for f in files)


def test_nombres_numerados_desde_uno_y_consecutivos_por_caso_y_tipo(tmp_path):
    files, _ = _generate(out=tmp_path)

    for case in {f.case for f in files}:
        for kind in ("imagen", "audio"):
            numbers = [int(re.search(r"-(\d{3})\.", f.path.name).group(1)) for f in files if f.case == case and f.kind == kind]
            assert numbers == list(range(1, len(numbers) + 1))


def test_formatos_de_imagen_y_audio_rotan_dentro_de_cada_caso(tmp_path):
    files, _ = _generate(out=tmp_path)

    for case in {f.case for f in files}:
        images = [f.path.suffix.lstrip(".") for f in files if f.case == case and f.kind == "imagen"]
        audios = [f.path.suffix.lstrip(".") for f in files if f.case == case and f.kind == "audio"]
        assert images[: len(IMAGE_FORMATS)] == list(IMAGE_FORMATS)
        assert audios[: len(AUDIO_FORMATS)] == list(AUDIO_FORMATS)


def test_el_generador_crea_los_directorios_que_el_ejecutor_necesita(tmp_path):
    def exige_directorio(args):
        output = Path(args[-1])
        if not output.parent.is_dir():
            raise FileNotFoundError(output.parent)
        output.write_bytes(b"medio")

    assert _generate(runner=exige_directorio, out=tmp_path / "nuevo" / "anidado")[0]


def test_la_semilla_cambia_los_colores_y_fuentes_aunque_el_plan_sea_el_mismo(tmp_path):
    plan = plan_dataset(7, PARAMS)
    first, second = Recorder(), Recorder()

    generate_media(plan, tmp_path / "a", first)
    generate_media(dataclasses.replace(plan, seed=8), tmp_path / "b", second)

    strip = lambda calls, base: [[a.replace(str(base), "") for a in c] for c in calls]
    assert strip(first.calls, tmp_path / "a") != strip(second.calls, tmp_path / "b")


def test_etiquetas_de_imagen_vienen_mezcladas_no_agrupadas(tmp_path):
    files, _ = _generate(out=tmp_path)

    for categoria in IMAGE_CATEGORIES:
        labels = [f.etiqueta for f in files if f.kind == "imagen" and f.categoria == categoria]
        assert labels != sorted(labels) and labels != sorted(labels, reverse=True), categoria


def test_audios_alternan_tono_y_ruido_con_la_fuente_correspondiente(tmp_path):
    files, runner = _generate(out=tmp_path)
    by_output = {call[-1]: call for call in runner.calls}
    audios = [f for f in files if f.kind == "audio"]

    assert {f.etiqueta for f in audios} == {"tono", "ruido"}
    for audio in audios:
        source = by_output[str(audio.path)][by_output[str(audio.path)].index("-i") + 1]
        assert source.startswith("sine=" if audio.etiqueta == "tono" else "anoisesrc=")


def test_color_de_imagen_positiva_difiere_del_neutro(tmp_path):
    files, runner = _generate(out=tmp_path)
    by_output = {call[-1]: call for call in runner.calls}
    colors = {"positivo": set(), "neutro": set()}
    for image in (f for f in files if f.kind == "imagen"):
        call = by_output[str(image.path)]
        colors[image.etiqueta].add(re.search(r"c=0x([0-9a-f]{6})", call[call.index("-i") + 1]).group(1))

    assert all(max(int(c[i : i + 2], 16) for i in (0, 2, 4)) - min(int(c[i : i + 2], 16) for i in (0, 2, 4)) <= 16 for c in colors["neutro"])
    assert all(int(c[0:2], 16) >= 200 and int(c[4:6], 16) <= 90 for c in colors["positivo"])


def test_interrupcion_del_usuario_no_deja_archivo_a_medias(tmp_path):
    def interrumpe(args):
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(args[-1]).write_bytes(b"parcial")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _generate(runner=interrumpe, out=tmp_path)

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_run_ffmpeg_no_usa_shell_y_limita_el_tiempo(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_ffmpeg(["ffmpeg", "-i", "a; touch pwn"])

    assert captured["args"] == ["ffmpeg", "-i", "a; touch pwn"]
    assert not captured["kwargs"].get("shell")
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == media_generator.FFMPEG_TIMEOUT_SECONDS > 0


def test_run_ffmpeg_propaga_el_timeout(monkeypatch):
    def lento(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", lento)

    with pytest.raises(subprocess.TimeoutExpired):
        run_ffmpeg(["ffmpeg"])


def test_archivo_previo_no_oculta_un_ejecutor_que_no_produce(tmp_path):
    _generate(out=tmp_path)

    with pytest.raises(FileNotFoundError):
        _generate(runner=lambda args: None, out=tmp_path)


def test_formatos_de_audio_e_imagen_quedan_repartidos_en_todo_el_plan(tmp_path):
    files, _ = _generate(seed=1, params=DatasetParams(), out=tmp_path)

    for kind in ("imagen", "audio"):
        counts = Counter(f.path.suffix for f in files if f.kind == kind)
        assert max(counts.values()) - min(counts.values()) <= 1, (kind, counts)


@pytest.mark.parametrize("seed", [0, 1, 7, -5, 2**63])
def test_plan_por_defecto_tiene_exactamente_el_redondeo_de_positivos_por_categoria(seed, tmp_path):
    plan = plan_dataset(seed, DatasetParams())
    files = generate_media(plan, tmp_path, Recorder())
    images = [f for f in files if f.kind == "imagen"]

    assert len(images) == 300 and len(files) - len(images) == 150
    for categoria in IMAGE_CATEGORIES:
        group = [f for f in images if f.categoria == categoria]
        positives = sum(f.etiqueta == "positivo" for f in group)
        assert len(group) == 75
        assert positives == round(plan.image_positive_ratio[categoria] * 75)


def test_la_fuente_de_ruido_fija_su_semilla_para_que_el_contenido_sea_reproducible(tmp_path):
    files, runner = _generate(out=tmp_path)
    noise = [c[c.index("-i") + 1] for c in runner.calls if c[c.index("-i") + 1].startswith("anoisesrc=")]

    assert noise
    assert all("seed=" in source for source in noise)


def test_produce_se_niega_a_dejar_un_archivo_menor_que_min_bytes(tmp_path):
    path = tmp_path / "caso" / "video.mpg"

    def runner(args):
        path.write_bytes(b"x" * 10)

    with pytest.raises(ValueError):
        media_generator.produce(runner, ["ffmpeg"], path, min_bytes=11)

    assert not path.exists()


def test_produce_acepta_un_archivo_que_alcanza_min_bytes(tmp_path):
    path = tmp_path / "caso" / "video.mpg"

    def runner(args):
        path.write_bytes(b"x" * 11)

    media_generator.produce(runner, ["ffmpeg"], path, min_bytes=11)

    assert path.stat().st_size == 11


def test_produce_borra_el_archivo_previo_antes_de_ejecutar(tmp_path):
    path = tmp_path / "caso" / "audio.wav"
    path.parent.mkdir()
    path.write_bytes(b"previo")
    visto = []

    def runner(args):
        visto.append(path.exists())
        path.write_bytes(b"nuevo")

    media_generator.produce(runner, ["ffmpeg"], path)

    assert visto == [False]


def test_heavy_case_generator_reutiliza_el_produce_de_media_generator():
    from src.adapters import heavy_case_generator

    assert getattr(heavy_case_generator, "produce", None) is media_generator.produce


def test_audio_durations_corta_da_un_error_claro_y_no_deja_archivos(tmp_path):
    plan = plan_dataset(7, PARAMS)
    corto = dataclasses.replace(plan, audio_durations=plan.audio_durations[:-1])

    with pytest.raises(ValueError, match="audio_durations"):
        generate_media(corto, tmp_path, Recorder())

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_run_ffmpeg_sin_stderr_igual_propaga_el_fallo(monkeypatch):
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr=None)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(Exception):
        run_ffmpeg(["ffmpeg"])


def test_el_error_de_ffmpeg_en_texto_expone_su_stderr_decodificado(monkeypatch):
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="No such file or directory".encode())

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(Exception, match="No such file or directory"):
        run_ffmpeg(["ffmpeg"])


@pytest.mark.parametrize("ratio", [-0.1, 1.5, float("nan")])
def test_ratio_de_positivos_fuera_de_rango_se_rechaza_sin_dejar_archivos(ratio, tmp_path):
    plan = plan_dataset(7, PARAMS)
    ratios = {**plan.image_positive_ratio, IMAGE_CATEGORIES[0]: ratio}

    with pytest.raises(ValueError, match="image_positive_ratio"):
        generate_media(dataclasses.replace(plan, image_positive_ratio=ratios), tmp_path, Recorder())

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_produce_informa_el_minimo_en_bytes_cuando_es_menor_que_una_mib(tmp_path):
    path = tmp_path / "caso" / "video.mpg"

    def runner(args):
        path.write_bytes(b"x")

    with pytest.raises(ValueError, match="1024 bytes"):
        media_generator.produce(runner, ["ffmpeg"], path, min_bytes=1024)
