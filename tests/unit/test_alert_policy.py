import json

import pytest

from src.domain.alert_policy import CASE_CLOSED, HIGH_INCIDENT, Alert, case_closed_alert, high_incident_alerts
from src.domain.finding import EvidenceRef, Finding, Severity


def _hallazgo(severidad, categoria="amenaza", sha="a" * 64, posicion="msg:3", detail="", confianza=0.9):
    return Finding(categoria, severidad, confianza, EvidenceRef(sha, posicion), detail)


def test_constantes_de_clase():
    assert HIGH_INCIDENT == "incidencia_alta"
    assert CASE_CLOSED == "caso_finalizado"


def test_solo_la_severidad_alta_es_incidencia():
    hallazgos = [_hallazgo(Severity.BAJA), _hallazgo(Severity.MEDIA), _hallazgo(Severity.ALTA)]

    alertas = high_incident_alerts("c1", hallazgos)

    assert len(alertas) == 1
    assert alertas[0].kind == HIGH_INCIDENT
    assert alertas[0].case_id == "c1"


def test_sin_hallazgos_altos_no_hay_alertas():
    assert high_incident_alerts("c1", [_hallazgo(Severity.BAJA), _hallazgo(Severity.MEDIA)]) == []
    assert high_incident_alerts("c1", []) == []


def test_una_alerta_por_hallazgo_alto_en_orden():
    hallazgos = [
        _hallazgo(Severity.ALTA, posicion="p1"),
        _hallazgo(Severity.BAJA, posicion="p2"),
        _hallazgo(Severity.ALTA, posicion="p3"),
    ]

    alertas = high_incident_alerts("c1", hallazgos)

    posiciones = [json.loads(a.detail)["posicion"] for a in alertas]
    assert posiciones == ["p1", "p3"]


def test_el_detalle_lleva_categoria_confianza_sha_y_posicion():
    hallazgo = _hallazgo(Severity.ALTA, categoria="grooming", sha="b" * 64, posicion="00:01:02", confianza=0.75)

    (alerta,) = high_incident_alerts("c1", [hallazgo])

    assert json.loads(alerta.detail) == {
        "categoria": "grooming",
        "confianza": 0.75,
        "sha256": "b" * 64,
        "posicion": "00:01:02",
    }


def test_alerta_no_copia_el_detalle_del_hallazgo():
    secreto = "te voy a encontrar mañana"
    hallazgo = _hallazgo(Severity.ALTA, detail=secreto)

    (alerta,) = high_incident_alerts("c1", [hallazgo])

    assert secreto not in alerta.detail
    assert set(json.loads(alerta.detail)) == {"categoria", "confianza", "sha256", "posicion"}


@pytest.mark.parametrize("estado", ["completed", "partially_completed", "failed"])
def test_cierre_con_estado_terminal_genera_alerta(estado):
    alerta = case_closed_alert("c9", estado)

    assert isinstance(alerta, Alert)
    assert alerta.kind == CASE_CLOSED
    assert alerta.case_id == "c9"
    assert estado in alerta.detail


@pytest.mark.parametrize("estado", ["cancelled", "pending", "processing", "running", "", "desconocido"])
def test_estado_no_terminal_o_cancelado_se_rechaza(estado):
    with pytest.raises(ValueError):
        case_closed_alert("c9", estado)
