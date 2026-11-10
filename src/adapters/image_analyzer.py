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
        reglas = SeverityRules.from_dict(datos, obligatoria=CATEGORIA_OBLIGATORIA)
        ajustes = ImageSettings(
            mapa=_requerido(datos, "clases"), umbral_minimo=_requerido(datos, "umbral_minimo"), reglas=reglas
        )
        return cls(detector, ajustes)

    def analyze(self, path: Path) -> list[Finding]:
        return analyze_image(self.detector.detect(path), sha256_de_archivo(path), self.ajustes)


def _requerido(datos: dict, clave: str) -> object:
    # Un valor por defecto ocultaría un archivo incompleto y cambiaría el análisis sin aviso.
    if clave not in datos:
        raise ValueError(f"falta {clave} en la configuración de imagen")
    return datos[clave]
