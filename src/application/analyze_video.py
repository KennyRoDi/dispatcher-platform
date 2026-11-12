import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from src.application.ports import Analyzer, FrameExtractor
from src.domain.evidence_position import frame_position
from src.domain.finding import EvidenceRef, Finding


class AnalyzeVideo:
    def __init__(
        self,
        extractor: FrameExtractor,
        image_analyzer: Analyzer,
        sha256_of: Callable[[Path], str],
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        self._extractor = extractor
        self._image_analyzer = image_analyzer
        self._sha256_of = sha256_of
        self._is_cancelled = is_cancelled

    def analyze(self, path: Path) -> list[Finding]:
        video_sha256 = self._sha256_of(path)
        frames_dir = Path(tempfile.mkdtemp(prefix="fotogramas-", dir=path.parent))
        try:
            frames = self._extractor.extract(path, frames_dir)
            if not frames:
                raise ValueError(f"{path.name}: no se pudo extraer ningún fotograma del video")
            return self._analyze_frames(frames, video_sha256)
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)

    def _analyze_frames(self, frames, video_sha256: str) -> list[Finding]:
        findings: list[Finding] = []
        for frame in frames:
            if self._is_cancelled():
                break
            detected = self._image_analyzer.analyze(frame.path)
            findings.extend(_anchored(finding, frame.t_s, video_sha256) for finding in detected)
        return findings


def _anchored(finding: Finding, t_s: float, video_sha256: str) -> Finding:
    evidence = EvidenceRef(video_sha256, frame_position(t_s, finding.evidence.position))
    return Finding(finding.category, finding.severity, finding.confidence, evidence, finding.detail)
