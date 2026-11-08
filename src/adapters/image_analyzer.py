import tomllib
from pathlib import Path

from src.adapters.hashing import sha256_de_archivo
from src.application.analyze_image import ImageSettings, ObjectDetector, analyze_image
from src.domain.finding import Finding
from src.domain.severity import SeverityRules

CATEGORIA_OBLIGATORIA = "arma"


class ImageAnalyzer:
    def __init__(self, detector: ObjectDetector, ajustes: ImageSettings) -> None:
        self.detector = detector
        self.ajustes = ajustes

    @classmethod
    def from_config(cls, detector: ObjectDetector, ruta: Path) -> "ImageAnalyzer":
        with open(ruta, "rb") as archivo:
            datos = tomllib.load(archivo)
        ajustes = ImageSettings(
            mapa=datos.get("clases", {}),
            umbral_minimo=datos.get("umbral_minimo", 0.25),
            reglas=SeverityRules.from_dict(datos, obligatoria=CATEGORIA_OBLIGATORIA),
        )
        return cls(detector, ajustes)

    def analyze(self, path: Path) -> list[Finding]:
        return analyze_image(self.detector.detect(path), sha256_de_archivo(path), self.ajustes)
