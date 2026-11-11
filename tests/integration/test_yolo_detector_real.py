import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("ultralytics")

from src.adapters.yolo_detector import YoloDetector  # noqa: E402
from src.domain.image_detection import Detection  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_REPO = RAIZ / "config" / "imagen.toml"
# Los pesos no se descargan aquí: se colocan antes, como indica la evidencia del SPEC de F-08.
DIRECTORIO_PESOS = Path(os.environ.get("F08_DIRECTORIO_PESOS", RAIZ))
# La muestra etiquetada llega en la parte 3; hasta entonces la imagen positiva se indica a mano.
IMAGEN_POSITIVA = os.environ.get("F08_IMAGEN_POSITIVA")


@pytest.fixture(scope="module")
def detector():
    try:
        return YoloDetector.from_config(CONFIG_REPO, DIRECTORIO_PESOS)
    except FileNotFoundError as error:
        pytest.skip(f"faltan los pesos fijados en config/imagen.toml dentro de {DIRECTORIO_PESOS}: {error}")


def test_imagen_positiva_produce_detecciones_validas_con_knife(detector):
    if not IMAGEN_POSITIVA or not Path(IMAGEN_POSITIVA).is_file():
        pytest.skip("define F08_IMAGEN_POSITIVA con una imagen propia o con licencia que muestre un cuchillo [B.3]")

    detecciones = detector.detect(Path(IMAGEN_POSITIVA))

    assert detecciones
    assert all(isinstance(deteccion, Detection) for deteccion in detecciones)
    assert all(type(deteccion.confidence) is float for deteccion in detecciones)
    assert "knife" in {deteccion.label for deteccion in detecciones}


def test_archivo_que_no_es_imagen_se_rechaza_con_value_error(detector, tmp_path):
    texto = tmp_path / "no_es_imagen.jpg"
    texto.write_text("texto sintetico con extension de imagen", encoding="utf-8")

    with pytest.raises(ValueError):
        detector.detect(texto)
