import re
from pathlib import Path

from src.adapters.media_generator import NEUTRAL, POSITIVE, generate_media
from src.domain.dataset_plan import DatasetParams, plan_dataset

MAX_NEUTRAL_SPREAD = 16


def _generate_default_plan(seed, tmp_path):
    calls: list[list[str]] = []

    def runner(args: list[str]) -> None:
        calls.append(list(args))
        Path(args[-1]).write_bytes(b"medio")

    files = generate_media(plan_dataset(seed, DatasetParams()), tmp_path, runner)
    images = [f for f in files if f.kind == "imagen"]
    sources = {Path(call[-1]): call[call.index("-i") + 1] for call in calls if "color=" in call[call.index("-i") + 1]}
    return images, [sources[f.path] for f in images]


def _rgb(source: str) -> tuple[int, int, int]:
    digits = re.search(r"color=c=0x([0-9a-f]{6})", source).group(1)
    return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))


def test_las_imagenes_del_plan_por_defecto_tienen_todas_un_color_distinto(tmp_path):
    images, sources = _generate_default_plan(7, tmp_path)

    assert len(images) == DatasetParams().images == 300
    assert len(set(sources)) == len(sources)


def test_los_colores_distintos_se_mantienen_con_otras_semillas(tmp_path):
    for seed in (1, 2, 3):
        images, sources = _generate_default_plan(seed, tmp_path / str(seed))

        assert len(set(sources)) == len(images)


def test_positivos_son_calidos_y_neutros_son_grises_aunque_varien(tmp_path):
    images, sources = _generate_default_plan(7, tmp_path)

    for media, source in zip(images, sources):
        red, green, blue = _rgb(source)
        if media.etiqueta == POSITIVE:
            assert red >= 200 and 120 <= green <= 200 and blue <= 90, source
        else:
            assert media.etiqueta == NEUTRAL
            assert max(red, green, blue) - min(red, green, blue) <= MAX_NEUTRAL_SPREAD, source
