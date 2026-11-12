import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# Medición pendiente (SUP-48): cadencia y tope provisionales, sin dato medido que los fundamente.
EVERY_S_POR_DEFECTO = 5.0
MAX_FRAMES_POR_DEFECTO = 20


@dataclass(frozen=True)
class Frame:
    path: Path
    t_s: float


@dataclass(frozen=True)
class FrameSampling:
    every_s: float = EVERY_S_POR_DEFECTO
    max_frames: int = MAX_FRAMES_POR_DEFECTO

    def __post_init__(self) -> None:
        if isinstance(self.every_s, bool) or not isinstance(self.every_s, (int, float)):
            raise ValueError(f"FRAME_EVERY_S debe ser un número: {self.every_s!r}")
        if not math.isfinite(self.every_s) or self.every_s <= 0:
            raise ValueError(f"FRAME_EVERY_S debe ser positivo y finito: {self.every_s!r}")
        if isinstance(self.max_frames, bool) or not isinstance(self.max_frames, int) or self.max_frames <= 0:
            raise ValueError(f"FRAME_MAX debe ser un entero positivo: {self.max_frames!r}")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "FrameSampling":
        every_s, max_frames = env.get("FRAME_EVERY_S", "").strip(), env.get("FRAME_MAX", "").strip()
        try:
            return cls(
                float(every_s) if every_s else EVERY_S_POR_DEFECTO,
                int(max_frames) if max_frames else MAX_FRAMES_POR_DEFECTO,
            )
        except ValueError as error:
            raise ValueError(f"muestreo de fotogramas inválido: {error}") from error

    def timestamps(self, duration_s: float | None) -> list[float]:
        if duration_s is None or not math.isfinite(duration_s) or duration_s <= 0:
            cantidad = self.max_frames
        else:
            cantidad = min(self.max_frames, max(1, math.ceil(duration_s / self.every_s)))
        return [indice * self.every_s for indice in range(cantidad)]
