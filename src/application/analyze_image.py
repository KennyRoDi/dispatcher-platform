from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.domain.finding import Finding
from src.domain.image_detection import Detection, sensitive_findings
from src.domain.severity import SeverityRules, umbral_valido


class ObjectDetector(Protocol):
    def detect(self, path: Path) -> list[Detection]: ...


@dataclass(frozen=True)
class ImageSettings:
    mapa: Mapping[str, str]
    umbral_minimo: float
    reglas: SeverityRules

    def __post_init__(self) -> None:
        object.__setattr__(self, "umbral_minimo", umbral_valido(self.umbral_minimo, "umbral_minimo"))
        vacias = sorted(clase for clase, categoria in self.mapa.items() if not _categoria_valida(categoria))
        if vacias:
            raise ValueError(f"clases sin categoría en el mapa: {', '.join(vacias)}")


def _categoria_valida(categoria: object) -> bool:
    return isinstance(categoria, str) and bool(categoria.strip())


def analyze_image(detecciones: list[Detection], sha256: str, ajustes: ImageSettings) -> list[Finding]:
    return sensitive_findings(detecciones, sha256, ajustes.mapa, ajustes.umbral_minimo, ajustes.reglas)
