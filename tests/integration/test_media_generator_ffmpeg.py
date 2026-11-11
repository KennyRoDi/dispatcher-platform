import dataclasses
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.adapters.media_generator import AUDIO_FORMATS, generate_media
from src.domain.dataset_plan import DatasetParams, plan_dataset

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="requiere ffmpeg y ffprobe"),
]

PARAMS = DatasetParams(
    cases=2, light_heterogeneous=1, heavy_heterogeneous=1, messages=10, images=12, audios=10, heavy_bytes=1
)
CODEC_BY_SUFFIX = {
    ".png": "png",
    ".jpg": "mjpeg",
    ".mp3": "mp3",
    ".wav": "pcm_s16le",
    ".flac": "flac",
    ".ogg": "vorbis",
    ".m4a": "aac",
}
MP3_PADDING_SECONDS = 0.1


def _short_plan(seed=11):
    plan = plan_dataset(seed, PARAMS)
    return dataclasses.replace(plan, audio_durations=tuple(range(1, sum(c.audios for c in plan.cases) + 1)))


def _probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height", "-of", "json"]
    return json.loads(subprocess.run(command + [str(path)], capture_output=True, text=True, check=True).stdout)


def _digests(files) -> dict[str, str]:
    return {f.path.name: hashlib.sha256(f.path.read_bytes()).hexdigest() for f in files}


def test_ffmpeg_real_genera_archivos_validos_con_formato_y_duracion_del_plan(tmp_path):
    files = generate_media(_short_plan(), tmp_path)

    assert {f.path.suffix.lstrip(".") for f in files if f.kind == "audio"} == set(AUDIO_FORMATS)
    for media in files:
        info = _probe(media.path)
        assert info["streams"][0]["codec_name"] == CODEC_BY_SUFFIX[media.path.suffix], media.path.name
        if media.kind == "imagen":
            assert (info["streams"][0]["width"], info["streams"][0]["height"]) == (128, 128)
        else:
            assert abs(float(info["format"]["duration"]) - media.duration_s) <= MP3_PADDING_SECONDS, media.path.name


def test_misma_semilla_con_ffmpeg_real_produce_los_mismos_bytes(tmp_path):
    first = _digests(generate_media(_short_plan(), tmp_path / "a"))
    second = _digests(generate_media(_short_plan(), tmp_path / "b"))

    assert first.keys() == second.keys()
    assert {name for name in first if first[name] != second[name]} == set()
