import hashlib
from pathlib import Path

import pytest

from src.adapters.image_analyzer import ImageAnalyzer
from src.application.analyze_image import ImageSettings
from src.application.ports import Analyzer
from src.domain.finding import Severity
from src.domain.image_detection import Detection
from src.domain.severity import SeverityRules
from tests.contratos import comprobar_analyzer

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = {"severidad": [{"categoria": "arma", "umbral": 0.5, "nivel": "alta"}]}


class FakeObjectDetector:
    def __init__(self, detecciones):
        self.detecciones = detecciones
        self.llamadas = []

    def detect(self, path):
        self.llamadas.append(path)
        return list(self.detecciones)


@pytest.fixture
def imagen(tmp_path):
    ruta = tmp_path / "foto.jpg"
    ruta.write_bytes(b"bytes sinteticos que simulan una imagen")
    return ruta


def analizador(detecciones, mapa=None, umbral_minimo=0.25):
    ajustes = ImageSettings(
        mapa=mapa or {"knife": "arma"},
        umbral_minimo=umbral_minimo,
        reglas=SeverityRules.from_dict(REGLAS, obligatoria="arma"),
    )
    return ImageAnalyzer(FakeObjectDetector(detecciones), ajustes)


def test_imagen_produce_categoria_y_confianza(imagen):
    detector = FakeObjectDetector([Detection("knife", 0.9, (12, 40, 180, 220))])
    ajustes = ImageSettings(
        mapa={"knife": "arma"}, umbral_minimo=0.25, reglas=SeverityRules.from_dict(REGLAS, obligatoria="arma")
    )

    hallazgos = ImageAnalyzer(detector, ajustes).analyze(imagen)

    assert len(hallazgos) == 1
    hallazgo = hallazgos[0]
    assert hallazgo.category == "arma"
    assert hallazgo.confidence == pytest.approx(0.9)
    assert hallazgo.severity is Severity.ALTA
    assert hallazgo.evidence.object_sha256 == hashlib.sha256(imagen.read_bytes()).hexdigest()
    assert hallazgo.evidence.position == "caja 12,40,180,220"
    assert "knife" in hallazgo.detail
    assert detector.llamadas == [imagen]


def test_sin_detecciones_devuelve_lista_vacia(imagen):
    assert analizador([]).analyze(imagen) == []


def test_clase_fuera_del_mapa_no_produce_hallazgo(imagen):
    assert analizador([Detection("person", 0.99, (0, 0, 10, 10))]).analyze(imagen) == []


def test_deteccion_bajo_el_umbral_minimo_no_produce_hallazgo(imagen):
    assert analizador([Detection("knife", 0.2, (0, 0, 10, 10))]).analyze(imagen) == []


def test_dos_cajas_de_la_misma_categoria_dan_un_hallazgo_con_la_mayor_confianza(imagen):
    detecciones = [Detection("knife", 0.6, (1, 1, 5, 5)), Detection("knife", 0.8, (10, 20, 30, 40))]

    hallazgos = analizador(detecciones).analyze(imagen)

    assert len(hallazgos) == 1
    assert hallazgos[0].confidence == pytest.approx(0.8)
    assert hallazgos[0].evidence.position == "caja 10,20,30,40"
    assert hallazgos[0].detail == "knife ×2"


def test_dos_clases_a_la_misma_categoria_se_agrupan(imagen):
    detecciones = [Detection("knife", 0.7, (1, 1, 5, 5)), Detection("scissors", 0.9, (2, 2, 8, 8))]

    hallazgos = analizador(detecciones, mapa={"knife": "arma", "scissors": "arma"}).analyze(imagen)

    assert len(hallazgos) == 1
    assert hallazgos[0].category == "arma"
    assert hallazgos[0].confidence == pytest.approx(0.9)
    assert hallazgos[0].evidence.position == "caja 2,2,8,8"
    assert "knife" in hallazgos[0].detail and "scissors" in hallazgos[0].detail


def test_image_analyzer_cumple_el_contrato_de_analyzer(imagen):
    instancia = analizador([Detection("knife", 0.9, (12, 40, 180, 220))])

    assert isinstance(instancia, Analyzer)
    comprobar_analyzer(instancia, imagen)


def escribir_config(ruta, clase='knife = "arma"', umbral_minimo=0.25, umbral=0.5, nivel="alta", categoria="arma"):
    ruta.write_text(
        f"umbral_minimo = {umbral_minimo}\n\n"
        "[clases]\n"
        f"{clase}\n\n"
        "[[severidad]]\n"
        f'categoria = "{categoria}"\n'
        f"umbral = {umbral}\n"
        f'nivel = "{nivel}"\n\n'
        "[modelo]\n"
        'pesos = "yolo11n.pt"\n',
        encoding="utf-8",
    )
    return ruta


def severidad_de_arma(config, imagen):
    detector = FakeObjectDetector([Detection("knife", 0.9, (12, 40, 180, 220))])
    return {h.category: h.severity for h in ImageAnalyzer.from_config(detector, config).analyze(imagen)}["arma"]


def test_from_config_con_toml_valido_produce_hallazgos(tmp_path, imagen):
    assert severidad_de_arma(escribir_config(tmp_path / "imagen.toml"), imagen) is Severity.ALTA


def test_cambiar_el_archivo_toml_cambia_la_severidad(tmp_path, imagen):
    config = tmp_path / "imagen.toml"

    antes = severidad_de_arma(escribir_config(config, nivel="alta"), imagen)
    despues = severidad_de_arma(escribir_config(config, nivel="media"), imagen)

    assert (antes, despues) == (Severity.ALTA, Severity.MEDIA)


def test_from_config_aplica_el_umbral_minimo_del_archivo(tmp_path, imagen):
    detector = FakeObjectDetector([Detection("knife", 0.5, (0, 0, 1, 1))])
    config = escribir_config(tmp_path / "imagen.toml", umbral_minimo=0.6)

    assert ImageAnalyzer.from_config(detector, config).analyze(imagen) == []


def test_configuracion_del_repositorio_marca_cuchillo_como_arma_alta(imagen):
    assert severidad_de_arma(RAIZ / "config" / "imagen.toml", imagen) is Severity.ALTA


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"clase": 'knife = ""'}, "knife"),
        ({"umbral_minimo": 1.5}, "umbral_minimo"),
        ({"umbral_minimo": -0.1}, "umbral_minimo"),
        ({"umbral": 1.5}, "umbral"),
        ({"nivel": "urgente"}, "urgente"),
        ({"categoria": "animal"}, "arma"),
    ],
    ids=["categoria-vacia", "umbral-minimo-alto", "umbral-minimo-negativo", "umbral-regla", "nivel", "sin-regla-arma"],
)
def test_from_config_rechaza_configuracion_invalida(tmp_path, cambios, mensaje):
    config = escribir_config(tmp_path / "imagen.toml", **cambios)

    with pytest.raises(ValueError, match=mensaje):
        ImageAnalyzer.from_config(FakeObjectDetector([]), config)
