import pytest

from src.domain.finding import Severity
from src.domain.image_detection import Detection, sensitive_findings
from src.domain.severity import SeverityRules

SHA = "a" * 64
MAPA = {"knife": "arma", "scissors": "arma", "dog": "animal"}
REGLAS = SeverityRules.from_dict(
    {
        "severidad": [
            {"categoria": "arma", "umbral": 0.5, "nivel": "alta"},
            {"categoria": "animal", "umbral": 0.5, "nivel": "media"},
        ]
    },
    obligatoria="arma",
)


def hallazgos(detecciones, umbral_minimo=0.25):
    return {h.category: h for h in sensitive_findings(detecciones, SHA, MAPA, umbral_minimo, REGLAS)}


@pytest.mark.parametrize("confianza", [-0.1, 1.1, float("nan")])
def test_detection_rechaza_confianza_fuera_de_rango(confianza):
    with pytest.raises(ValueError):
        Detection("knife", confianza, (0, 0, 10, 10))


@pytest.mark.parametrize("confianza", [0, 0.0, 1, 1.0])
def test_detection_acepta_confianza_en_los_extremos(confianza):
    assert Detection("knife", confianza, (0, 0, 10, 10)).confidence == confianza


@pytest.mark.parametrize(
    "caja",
    [(-1, 0, 10, 10), (0, 0, 10, -5), (0.5, 0, 10, 10), (0, 0, 10), (0, 0, 10, 10, 20), ("0", 0, 10, 10)],
)
def test_detection_rechaza_cajas_invalidas(caja):
    with pytest.raises(ValueError):
        Detection("knife", 0.9, caja)


def test_sin_detecciones_no_hay_hallazgos():
    assert sensitive_findings([], SHA, MAPA, 0.25, REGLAS) == []


def test_un_hallazgo_por_categoria_con_la_deteccion_de_mayor_confianza():
    resultado = hallazgos(
        [
            Detection("knife", 0.6, (1, 2, 3, 4)),
            Detection("dog", 0.7, (5, 6, 7, 8)),
            Detection("scissors", 0.95, (10, 20, 30, 40)),
        ]
    )

    assert set(resultado) == {"arma", "animal"}
    assert resultado["arma"].confidence == pytest.approx(0.95)
    assert resultado["arma"].evidence.position == "caja 10,20,30,40"
    assert resultado["arma"].severity is Severity.ALTA
    assert resultado["animal"].severity is Severity.MEDIA
    assert {h.evidence.object_sha256 for h in resultado.values()} == {SHA}


def test_umbral_minimo_incluye_el_valor_exacto_y_excluye_lo_inferior():
    assert set(hallazgos([Detection("knife", 0.25, (0, 0, 1, 1))])) == {"arma"}
    assert hallazgos([Detection("knife", 0.2499, (0, 0, 1, 1))]) == {}


def test_arma_bajo_el_umbral_de_severidad_queda_en_baja():
    assert hallazgos([Detection("knife", 0.4, (0, 0, 1, 1))])["arma"].severity is Severity.BAJA


def test_clase_fuera_del_mapa_se_ignora():
    assert hallazgos([Detection("person", 0.99, (0, 0, 1, 1))]) == {}


def test_es_determinista_ante_el_orden_de_entrada():
    detecciones = [Detection("knife", 0.6, (1, 2, 3, 4)), Detection("knife", 0.8, (5, 6, 7, 8))]

    assert hallazgos(detecciones) == hallazgos(list(reversed(detecciones)))


def test_detection_rechaza_coordenadas_booleanas():
    with pytest.raises(ValueError):
        Detection("knife", 0.9, (True, 0, 10, 10))


def test_empate_de_confianza_elige_la_misma_caja_sin_importar_el_orden():
    detecciones = [Detection("knife", 0.8, (1, 2, 3, 4)), Detection("knife", 0.8, (5, 6, 7, 8))]

    assert hallazgos(detecciones) == hallazgos(list(reversed(detecciones)))
