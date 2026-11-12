import shutil
import subprocess
from pathlib import Path

import pytest

from src.domain.frame_sampling import FrameSampling
from src.workers.multimedia_processor import FfmpegFrameExtractor

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="requiere ffmpeg y ffprobe"),
]


def generar_video(destino: Path, segundos: int) -> Path:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"testsrc=duration={segundos}:size=160x120:rate=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(destino)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return destino


def test_extraer_fotogramas_de_un_video_sintetico_con_ffmpeg_real(tmp_path):
    video = generar_video(tmp_path / "sintetico.mp4", segundos=12)
    salida = tmp_path / "fotogramas"

    frames = FfmpegFrameExtractor(FrameSampling(every_s=5, max_frames=20)).extract(video, salida)

    assert [f.t_s for f in frames] == [0, 5, 10]
    assert all(f.path.parent == salida and f.path.stat().st_size > 0 for f in frames)
    assert all(f.path.read_bytes()[:2] == b"\xff\xd8" for f in frames)


def test_el_tope_de_fotogramas_se_respeta_con_ffmpeg_real(tmp_path):
    video = generar_video(tmp_path / "sintetico.mp4", segundos=12)

    frames = FfmpegFrameExtractor(FrameSampling(every_s=1, max_frames=4)).extract(video, tmp_path / "fotogramas")

    assert [f.t_s for f in frames] == [0, 1, 2, 3]
    assert len(list((tmp_path / "fotogramas").glob("frame_*.jpg"))) == 4
