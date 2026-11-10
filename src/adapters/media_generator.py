import itertools
import random
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.domain.dataset_plan import IMAGE_CATEGORIES, DatasetPlan

ORIGIN = "sintetico"
LICENSE_NAME = "generado por el equipo, uso academico"

POSITIVE = "positivo"
NEUTRAL = "neutro"
FFMPEG_TIMEOUT_SECONDS = 300
FFMPEG_BASE = ["ffmpeg", "-y", "-loglevel", "error"]
IMAGE_FORMATS = ("png", "jpg")
IMAGE_SIZE = "128x128"
AUDIO_FORMATS = ("mp3", "wav", "flac", "ogg", "m4a")
AUDIO_SAMPLE_RATE = 44100
TONE_RANGE_HZ = (220, 880)
AUDIO_SOURCES = ("tono", "ruido")
NOISE_SEED_LIMIT = 2**31
COLOR_STEP = 8
POSITIVE_RANGES = ((200, 255), (120, 200), (0, 90))
NEUTRAL_RANGE = (48, 208)
NEUTRAL_MAX_SPREAD = 16
# Sin bitexact los muxers estampan datos no deterministas (p. ej. el serial aleatorio de ogg).
BITEXACT = ["-fflags", "+bitexact", "-flags:a", "+bitexact"]

# Codecs tomados de AUDIO_*/ffmpeg_args de scripts/build_dataset.py (I Proyecto); no se importa desde scripts/.
AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "96k"],
    "wav": ["-c:a", "pcm_s16le", "-ac", "1"],
    "flac": ["-c:a", "flac", "-ac", "1"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "96k"],
}

Runner = Callable[[list[str]], None]


@dataclass(frozen=True)
class MediaFile:
    case: str
    kind: str
    path: Path
    etiqueta: str
    categoria: str | None
    duration_s: int | None
    origen: str
    licencia: str
    semilla: int


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS)


def generate_media(plan: DatasetPlan, out_dir: Path, runner: Runner = run_ffmpeg) -> list[MediaFile]:
    rng = random.Random(plan.seed)
    image_slots = iter(_image_slots(plan, rng))
    durations = iter(plan.audio_durations)
    files: list[MediaFile] = []
    for case in plan.cases:
        case_dir = out_dir / case.name
        for index in range(case.images):
            categoria, etiqueta, color = next(image_slots)
            path = case_dir / f"{case.name}-imagen-{index + 1:03d}.{IMAGE_FORMATS[index % len(IMAGE_FORMATS)]}"
            _produce(runner, _image_args(color, path), path)
            files.append(_media(plan, case.name, "imagen", path, etiqueta, categoria=categoria))
        for index in range(case.audios):
            duration = next(durations)
            path = case_dir / f"{case.name}-audio-{index + 1:03d}.{AUDIO_FORMATS[index % len(AUDIO_FORMATS)]}"
            etiqueta, args = _audio_args(rng, duration, path)
            _produce(runner, args, path)
            files.append(_media(plan, case.name, "audio", path, etiqueta, duration=duration))
    return files


def _media(plan, case, kind, path, etiqueta, categoria=None, duration=None) -> MediaFile:
    return MediaFile(case, kind, path, etiqueta, categoria, duration, ORIGIN, LICENSE_NAME, plan.seed)


def _image_slots(plan: DatasetPlan, rng: random.Random) -> list[tuple[str, str, str]]:
    total = sum(case.images for case in plan.cases)
    categories = [IMAGE_CATEGORIES[position % len(IMAGE_CATEGORIES)] for position in range(total)]
    labels = {category: _shuffled_labels(plan, rng, category, categories.count(category)) for category in IMAGE_CATEGORIES}
    slots = [(category, labels[category].pop()) for category in categories]
    colors = {label: _distinct_colors(rng, label, sum(1 for _, other in slots if other == label)) for label in (POSITIVE, NEUTRAL)}
    return [(category, label, colors[label].pop()) for category, label in slots]


def _shuffled_labels(plan: DatasetPlan, rng: random.Random, category: str, count: int) -> list[str]:
    positives = round(plan.image_positive_ratio[category] * count)
    labels = [POSITIVE] * positives + [NEUTRAL] * (count - positives)
    rng.shuffle(labels)
    return labels


def _image_args(color: str, path: Path) -> list[str]:
    source = f"color=c=0x{color}:s={IMAGE_SIZE}"
    return FFMPEG_BASE + ["-f", "lavfi", "-i", source, "-frames:v", "1", str(path)]


def _distinct_colors(rng: random.Random, etiqueta: str, count: int) -> list[str]:
    palette = _palette(etiqueta)
    colors: list[str] = []
    while len(colors) < count:
        colors += rng.sample(palette, min(len(palette), count - len(colors)))
    return colors


# La paleta es una rejilla gruesa: dos colores contiguos pueden dar el mismo archivo tras la conversion YUV y la cuantizacion JPEG.
def _palette(etiqueta: str) -> list[str]:
    if etiqueta == POSITIVE:
        channels = [range(low, high + 1, COLOR_STEP) for low, high in POSITIVE_RANGES]
        triples = itertools.product(*channels)
    else:
        levels = range(NEUTRAL_RANGE[0], NEUTRAL_RANGE[1] + 1, COLOR_STEP)
        triples = (t for t in itertools.product(levels, repeat=3) if max(t) - min(t) <= NEUTRAL_MAX_SPREAD)
    return [f"{red:02x}{green:02x}{blue:02x}" for red, green, blue in triples]


def _audio_args(rng: random.Random, duration: int, path: Path) -> tuple[str, list[str]]:
    etiqueta = rng.choice(AUDIO_SOURCES)
    if etiqueta == "ruido":
        # anoisesrc sin seed usa una semilla aleatoria propia y rompe la reproducibilidad.
        source = f"anoisesrc=color=pink:amplitude=0.3:sample_rate={AUDIO_SAMPLE_RATE}:seed={rng.randrange(NOISE_SEED_LIMIT)}"
    else:
        source = f"sine=frequency={rng.randint(*TONE_RANGE_HZ)}:sample_rate={AUDIO_SAMPLE_RATE}"
    codec = AUDIO_CODECS[path.suffix.lstrip(".")]
    return etiqueta, FFMPEG_BASE + ["-f", "lavfi", "-i", source, "-t", str(duration)] + BITEXACT + codec + [str(path)]


def _produce(runner: Runner, args: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        runner(args)
        if not path.is_file():
            raise FileNotFoundError(f"ffmpeg no produjo {path}")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
