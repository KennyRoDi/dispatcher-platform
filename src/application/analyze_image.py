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
        if not isinstance(self.mapa, Mapping):
            raise ValueError(f"clases debe ser una tabla de clase a categoría: {self.mapa!r}")
        object.__setattr__(self, "mapa", dict(self.mapa))
        invalidas = sorted(clase for clase, categoria in self.mapa.items() if not _categoria_valida(categoria))
        if invalidas:
            raise ValueError(f"clases con categoría vacía o con espacios al borde: {', '.join(invalidas)}")


def _categoria_valida(categoria: object) -> bool:
    # Se rechaza en vez de normalizar: « arma » no casaría con la regla «arma» y quedaría en baja sin aviso.
    return isinstance(categoria, str) and bool(categoria) and categoria == categoria.strip()


def analyze_image(detecciones: list[Detection], sha256: str, ajustes: ImageSettings) -> list[Finding]:
    return sensitive_findings(detecciones, sha256, ajustes.mapa, ajustes.umbral_minimo, ajustes.reglas)
