import math
import random
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from src.adapters.media_generator import BITEXACT, FFMPEG_BASE, LICENSE_NAME, ORIGIN, Runner, produce, run_ffmpeg
from src.domain.dataset_plan import DatasetPlan, checked_case_name

VIDEO_KIND = "video"
VIDEO_EXTENSION = "mpg"
VIDEO_SIZE = "640x360"
VIDEO_FPS = 25
VIDEO_BITRATE_BPS = 40_000_000
VIDEO_MARGIN_SECONDS = 2
NOISE_SEED_LIMIT = 2**31
# mpeg2video con minrate=maxrate rellena hasta el bitrate fijo: el tamano depende de la duracion, no del contenido.
VIDEO_CODEC = ["-c:v", "mpeg2video", "-b:v", str(VIDEO_BITRATE_BPS), "-minrate", str(VIDEO_BITRATE_BPS), "-maxrate", str(VIDEO_BITRATE_BPS), "-bufsize", str(VIDEO_BITRATE_BPS), "-an"]


@dataclass(frozen=True)
class HeavyFile:
    case: str
    kind: str
    path: Path
    bytes: int
    origen: str
    licencia: str
    semilla: int


def generate_heavy_cases(plan: DatasetPlan, out_dir: Path, runner: Runner = run_ffmpeg) -> list[HeavyFile]:
    rng = random.Random(plan.seed)
    files: list[HeavyFile] = []
    for case in plan.cases:
        if not case.heavy_bytes:
            continue
        if not case.name or any(
            ruta.drive or ruta.root or len(ruta.parts) != 1 or ruta.parts[0] in (".", "..")
            for ruta in (PurePosixPath(case.name), PureWindowsPath(case.name))
        ):
            raise ValueError("el nombre de caso debe ser un nombre de directorio simple")
        path = out_dir / checked_case_name(case.name) / f"{case.name}-video-001.{VIDEO_EXTENSION}"
        produce(runner, _video_args(rng.randrange(NOISE_SEED_LIMIT), case.heavy_bytes, path), path, min_bytes=case.heavy_bytes)
        files.append(HeavyFile(case.name, VIDEO_KIND, path, path.stat().st_size, ORIGIN, LICENSE_NAME, plan.seed))
    return files


def _video_args(noise_seed: int, min_bytes: int, path: Path) -> list[str]:
    duration = math.ceil(min_bytes * 8 / VIDEO_BITRATE_BPS) + VIDEO_MARGIN_SECONDS
    source = f"testsrc2=size={VIDEO_SIZE}:rate={VIDEO_FPS}"
    noise = f"noise=alls=20:all_seed={noise_seed}"
    return FFMPEG_BASE + ["-f", "lavfi", "-i", source, "-t", str(duration), "-vf", noise] + BITEXACT + ["-flags:v", "+bitexact"] + VIDEO_CODEC + [str(path)]
