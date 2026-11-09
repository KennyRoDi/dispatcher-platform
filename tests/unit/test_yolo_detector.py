import hashlib
import importlib
import re
import sys
import tomllib
import types
from pathlib import Path

import numpy as np
import pytest

from src.adapters.yolo_detector import YoloDetector
from src.domain.image_detection import Detection

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_REPO = RAIZ / "config" / "imagen.toml"
MODULO = "src.adapters.yolo_detector"
BIBLIOTECAS_PESADAS = ("ultralytics", "torch", "cv2")
NOMBRES_COCO = {0: "person", 43: "knife", 76: "scissors"}


# Imita la parte de un tensor de torch que un adaptador suele usar; los elementos siguen siendo de numpy.
class FakeTensor:
    def __init__(self, datos, dtype):
        self.datos = np.asarray(datos, dtype=dtype)

    def cpu(self):
        return self

    def numpy(self):
        return self.datos

    def tolist(self):
        return self.datos.tolist()

    def __iter__(self):
        return iter(self.datos)

    def __len__(self):
        return len(self.datos)

    def __getitem__(self, indice):
        return self.datos[indice]


class FakeBoxes:
    def __init__(self, cajas):
        self.xyxy = FakeTensor([caja for caja, _, _ in cajas] or np.empty((0, 4)), np.float32)
        self.conf = FakeTensor([conf for _, conf, _ in cajas], np.float32)
        self.cls = FakeTensor([cls for _, _, cls in cajas], np.float32)

    def __len__(self):
        return len(self.conf)


class FakeResults:
    def __init__(self, cajas, names):
        self.boxes = FakeBoxes(cajas)
        self.names = names


# Ultralytics admite model(fuente) y model.predict(fuente); ambos devuelven una lista de Results.
class FakeYolo:
    def __init__(self, cajas=(), names=None, error=None):
        self.cajas = list(cajas)
        self.names = names or NOMBRES_COCO
        self.error = error
        self.llamadas = []

    def __call__(self, fuente, **opciones):
        return self.predict(fuente, **opciones)

    def predict(self, fuente, **opciones):
        self.llamadas.append((fuente, opciones))
        if self.error is not None:
            raise self.error
        return [FakeResults(self.cajas, self.names)]


@pytest.fixture
def imagen(tmp_path):
    ruta = tmp_path / "foto.jpg"
    ruta.write_bytes(b"bytes sinteticos que simulan una imagen")
    return ruta


def test_cada_caja_se_traduce_a_detection_con_la_etiqueta_de_names(imagen):
    cajas = [
        ([12.2, 40.4, 180.1, 219.8], 0.91, 43),
        ([0.0, 5.0, 64.0, 128.0], 0.40, 0),
    ]

    detecciones = YoloDetector(FakeYolo(cajas)).detect(imagen)

    assert all(isinstance(deteccion, Detection) for deteccion in detecciones)
    assert [(d.label, d.box) for d in detecciones] == [("knife", (12, 40, 180, 220)), ("person", (0, 5, 64, 128))]
    assert [d.confidence for d in detecciones] == pytest.approx([0.91, 0.40])


def test_la_etiqueta_sale_de_names_del_resultado(imagen):
    modelo = FakeYolo([([1, 1, 2, 2], 0.8, 5)], names={5: "cuchillo_de_prueba"})

    [deteccion] = YoloDetector(modelo).detect(imagen)

    assert deteccion.label == "cuchillo_de_prueba"


def test_confianza_y_caja_quedan_en_tipos_nativos_de_python(imagen):
    [deteccion] = YoloDetector(FakeYolo([([10.6, 20.4, 30.5001, 40.9], 0.75, 43)])).detect(imagen)

    assert type(deteccion.confidence) is float
    assert all(type(coordenada) is int for coordenada in deteccion.box)
    assert deteccion.box == (11, 20, 31, 41)
    assert deteccion.confidence == pytest.approx(0.75, abs=1e-6)


def test_sin_cajas_devuelve_lista_vacia(imagen):
    assert YoloDetector(FakeYolo([])).detect(imagen) == []


def test_infiere_sobre_la_ruta_recibida_en_cpu(imagen):
    modelo = FakeYolo([([1, 1, 2, 2], 0.8, 43)])

    YoloDetector(modelo).detect(imagen)

    [(fuente, opciones)] = modelo.llamadas
    assert Path(fuente) == imagen
    assert opciones.get("device") == "cpu"


def test_archivo_que_no_es_imagen_se_rechaza_con_value_error(tmp_path):
    texto = tmp_path / "notas.jpg"
    texto.write_text("esto no es una imagen", encoding="utf-8")
    # Ultralytics responde así cuando no puede decodificar el archivo.
    modelo = FakeYolo(error=FileNotFoundError(f"Image Not Found {texto}"))

    with pytest.raises(ValueError, match="notas.jpg"):
        YoloDetector(modelo).detect(texto)


def test_importar_el_modulo_no_importa_ultralytics_ni_torch(monkeypatch):
    # Un None en sys.modules hace fallar cualquier `import` de esa biblioteca, esté o no instalada.
    for biblioteca in BIBLIOTECAS_PESADAS:
        monkeypatch.setitem(sys.modules, biblioteca, None)
    monkeypatch.delitem(sys.modules, MODULO, raising=False)

    modulo = importlib.import_module(MODULO)

    assert hasattr(modulo, "YoloDetector")
    assert all(sys.modules[biblioteca] is None for biblioteca in BIBLIOTECAS_PESADAS)


@pytest.fixture
def pesos(tmp_path):
    ruta = tmp_path / "pesos" / "modelo_de_prueba.pt"
    ruta.parent.mkdir()
    ruta.write_bytes(b"pesos sinteticos, no son un modelo real")
    return ruta


def escribir_config(ruta, pesos, sha256):
    ruta.write_text(
        'umbral_minimo = 0.25\n\n[clases]\nknife = "arma"\n\n'
        '[[severidad]]\ncategoria = "arma"\numbral = 0.5\nnivel = "alta"\n\n'
        f'[modelo]\npesos = "{pesos}"\nsha256 = "{sha256}"\n',
        encoding="utf-8",
    )
    return ruta


def sha256_de(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


class UltralyticsFalso:
    def __init__(self):
        self.cargados = []

    def instalar(self, monkeypatch):
        modulo = types.ModuleType("ultralytics")
        modulo.YOLO = self._yolo
        monkeypatch.setitem(sys.modules, "ultralytics", modulo)
        return self

    def _yolo(self, ruta, *args, **kwargs):
        self.cargados.append(Path(ruta))
        return FakeYolo([([1, 2, 3, 4], 0.9, 43)])


def test_from_config_carga_los_pesos_una_sola_vez(monkeypatch, tmp_path, pesos, imagen):
    falso = UltralyticsFalso().instalar(monkeypatch)
    config = escribir_config(tmp_path / "imagen.toml", pesos.name, sha256_de(pesos))

    detector = YoloDetector.from_config(config, pesos.parent)
    for _ in range(3):
        [deteccion] = detector.detect(imagen)
        assert (deteccion.label, deteccion.box) == ("knife", (1, 2, 3, 4))

    assert falso.cargados == [pesos]


def test_from_config_importa_ultralytics_solo_al_cargar(monkeypatch, tmp_path, pesos):
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    config = escribir_config(tmp_path / "imagen.toml", pesos.name, sha256_de(pesos))

    with pytest.raises(ImportError):
        YoloDetector.from_config(config, pesos.parent)


def test_pesos_con_sha256_distinto_al_fijado_se_rechazan_antes_de_cargar(monkeypatch, tmp_path, pesos):
    falso = UltralyticsFalso().instalar(monkeypatch)
    otro_hash = hashlib.sha256(b"otro contenido").hexdigest()
    config = escribir_config(tmp_path / "imagen.toml", pesos.name, otro_hash)

    with pytest.raises(ValueError, match="sha256"):
        YoloDetector.from_config(config, pesos.parent)

    assert falso.cargados == []


@pytest.mark.parametrize(
    "modelo",
    [
        "",
        '[modelo]\nsha256 = "' + "a" * 64 + '"\n',
        '[modelo]\npesos = "yolo11n.pt"\n',
        '[modelo]\npesos = ""\nsha256 = "' + "a" * 64 + '"\n',
        '[modelo]\npesos = "yolo11n.pt"\nsha256 = "no es un hash"\n',
        'modelo = "yolo11n.pt"\n',
    ],
    ids=["sin-modelo", "sin-pesos", "sin-sha256", "pesos-vacio", "sha256-mal-formado", "modelo-texto"],
)
def test_from_config_con_modelo_mal_formado_falla_con_value_error(monkeypatch, tmp_path, pesos, modelo):
    falso = UltralyticsFalso().instalar(monkeypatch)
    config = tmp_path / "imagen.toml"
    config.write_text('umbral_minimo = 0.25\n\n[clases]\nknife = "arma"\n\n' + modelo, encoding="utf-8")

    with pytest.raises(ValueError):
        YoloDetector.from_config(config, pesos.parent)

    assert falso.cargados == []


def test_config_del_repositorio_fija_los_pesos_con_su_sha256():
    with open(CONFIG_REPO, "rb") as archivo:
        modelo = tomllib.load(archivo)["modelo"]

    assert modelo["pesos"].endswith(".pt")
    assert re.fullmatch(r"[0-9a-f]{64}", modelo.get("sha256", "")), "el sha256 debe calcularse sobre el archivo descargado"


def test_el_modulo_cita_ultralytics_y_su_licencia():
    fuente = (RAIZ / "src" / "adapters" / "yolo_detector.py").read_text(encoding="utf-8")

    assert "Ultralytics" in fuente
    assert "AGPL-3.0" in fuente
