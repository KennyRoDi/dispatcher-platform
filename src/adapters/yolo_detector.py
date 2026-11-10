# Detector de objetos con Ultralytics YOLO (https://docs.ultralytics.com), licencia AGPL-3.0.
# Pesos yolo11n.pt de la release v8.4.0 de https://github.com/ultralytics/assets, también AGPL-3.0.
import re
import tomllib
from pathlib import Path
from typing import Any

from src.adapters.hashing import sha256_de_archivo
from src.domain.image_detection import Detection

SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class YoloDetector:
    def __init__(self, modelo: Any) -> None:
        self.modelo = modelo

    @classmethod
    def from_config(cls, ruta_config: Path, directorio_pesos: Path) -> "YoloDetector":
        pesos, sha256 = _modelo_configurado(ruta_config)
        ruta_pesos = Path(directorio_pesos) / pesos
        if not ruta_pesos.is_file():
            raise FileNotFoundError(f"no se encuentran los pesos {ruta_pesos}")
        if sha256_de_archivo(ruta_pesos) != sha256:
            raise ValueError(f"el sha256 de {ruta_pesos} no coincide con el fijado en {ruta_config}")
        # Importación diferida: las unitarias y el resto del worker no cargan ultralytics ni torch.
        from ultralytics import YOLO

        return cls(YOLO(str(ruta_pesos)))

    def detect(self, path: Path) -> list[Detection]:
        try:
            resultados = self.modelo.predict(str(path), device="cpu", verbose=False)
        except FileNotFoundError as error:
            raise ValueError(f"no es una imagen legible: {path}") from error
        # Según la versión, Ultralytics omite con un aviso la imagen que no decodifica en vez de fallar.
        if not resultados:
            raise ValueError(f"no es una imagen legible: {path}")
        return _detecciones(resultados[0])


def _detecciones(resultado: Any) -> list[Detection]:
    cajas = resultado.boxes
    return [
        Detection(resultado.names[int(clase)], float(confianza), tuple(round(float(c)) for c in caja))
        for caja, confianza, clase in zip(cajas.xyxy.tolist(), cajas.conf.tolist(), cajas.cls.tolist())
    ]


def _modelo_configurado(ruta_config: Path) -> tuple[str, str]:
    with open(ruta_config, "rb") as archivo:
        modelo = tomllib.load(archivo).get("modelo")
    if not isinstance(modelo, dict):
        raise ValueError(f"falta la tabla [modelo] en {ruta_config}")
    pesos, sha256 = modelo.get("pesos"), modelo.get("sha256")
    if not isinstance(pesos, str) or not pesos:
        raise ValueError(f"[modelo] pesos debe ser un nombre de archivo no vacío: {pesos!r}")
    if not isinstance(sha256, str) or not SHA256_HEX.fullmatch(sha256):
        raise ValueError(f"[modelo] sha256 debe tener 64 dígitos hexadecimales en minúscula: {sha256!r}")
    return pesos, sha256
