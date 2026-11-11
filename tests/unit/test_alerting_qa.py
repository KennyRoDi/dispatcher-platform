import asyncio
import json
import logging

import pytest

from src.application.alerting import AlertingFindingStore, SafeAlertPublisher, notify_case_closed
from src.domain.alert_policy import case_closed_alert, high_incident_alerts
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeAlertPublisher, FakeFindingStore

TEXTOS_HOSTILES = [
    'ñ"\n\t\\',
    "  \x00\x1f",
    "\ud800",
    "😀 emoji \U0001f600",
    "",
    "x" * 100_000,
]


def _alto(categoria="amenaza", posicion="p", sha="a" * 64, confianza=0.5, detail=""):
    return Finding(categoria, Severity.ALTA, confianza, EvidenceRef(sha, posicion), detail)


class PublicadorQueLanza:
    def __init__(self, error):
        self.error = error
        self.llamadas = 0

    def publish(self, kind, case_id, detail):
        self.llamadas += 1
        raise self.error


def _log():
    return logging.getLogger("test.alerting_qa")


@pytest.mark.parametrize("texto", TEXTOS_HOSTILES)
def test_detail_es_json_valido_ascii_y_conserva_el_texto(texto):
    alerta = high_incident_alerts("c", [_alto(categoria=texto, posicion=texto, sha=texto)])[0]
    alerta.detail.encode("utf-8")
    datos = json.loads(alerta.detail)
    assert (datos["categoria"], datos["posicion"], datos["sha256"]) == (texto, texto, texto)


def test_detail_no_emite_nan_ni_infinito():
    for hallazgo in (_alto(confianza=0.0), _alto(confianza=1.0)):
        json.loads(high_incident_alerts("c", [hallazgo])[0].detail, parse_constant=_prohibido)


def _prohibido(valor):
    raise AssertionError(f"constante no JSON: {valor}")


@pytest.mark.parametrize("confianza", [float("nan"), float("inf"), float("-inf"), -0.1, 1.1])
def test_finding_rechaza_confianza_no_valida_antes_de_alertar(confianza):
    with pytest.raises(ValueError):
        _alto(confianza=confianza)


def test_el_detail_del_hallazgo_nunca_se_filtra_a_la_alerta():
    secreto = "te voy a encontrar, mensaje privado de Ana"
    alertas = high_incident_alerts("c", [_alto(detail=secreto)])
    assert secreto not in alertas[0].detail
    assert "Ana" not in alertas[0].detail


def test_determinismo_misma_entrada_misma_alerta():
    hallazgos = [_alto("b", "2"), _alto("a", "1")]
    assert high_incident_alerts("c", hallazgos) == high_incident_alerts("c", hallazgos)


def test_lista_enorme_una_alerta_por_hallazgo_alto():
    hallazgos = [_alto(posicion=str(i)) for i in range(50_000)]
    publicador = FakeAlertPublisher()
    AlertingFindingStore(FakeFindingStore(), publicador).add("c", hallazgos)
    assert len(publicador.alertas) == 50_000
    assert json.loads(publicador.alertas[-1][2])["posicion"] == "49999"


def test_add_con_lista_vacia_guarda_y_no_alerta():
    interno, publicador = FakeFindingStore(), FakeAlertPublisher()
    AlertingFindingStore(interno, publicador).add("c", [])
    assert publicador.alertas == [] and interno.list("c") == []


def test_add_no_muta_la_lista_de_entrada():
    hallazgos = [_alto("a"), _alto("b")]
    copia = list(hallazgos)
    AlertingFindingStore(FakeFindingStore(), FakeAlertPublisher()).add("c", hallazgos)
    assert hallazgos == copia


@pytest.mark.parametrize("error", [KeyboardInterrupt(), asyncio.CancelledError(), SystemExit(1), GeneratorExit()])
def test_safe_publisher_no_absorbe_ninguna_base_exception(error):
    with pytest.raises(type(error)):
        SafeAlertPublisher(PublicadorQueLanza(error), _log()).publish("k", "c", "d")


@pytest.mark.parametrize("error", [RuntimeError("x"), OSError("x"), ValueError("x"), ConnectionError("x"), MemoryError()])
def test_safe_publisher_absorbe_cualquier_exception(error, caplog):
    with caplog.at_level(logging.ERROR):
        SafeAlertPublisher(PublicadorQueLanza(error), _log()).publish("k", "c", "d")
    assert caplog.records


def test_base_exception_del_publicador_no_pierde_lo_guardado():
    interno = FakeFindingStore()
    almacen = AlertingFindingStore(interno, SafeAlertPublisher(PublicadorQueLanza(KeyboardInterrupt()), _log()))
    with pytest.raises(KeyboardInterrupt):
        almacen.add("c", [_alto()])
    assert len(interno.list("c")) == 1


def test_fallo_al_guardar_con_base_exception_no_alerta():
    class Cancelado:
        def add(self, case_id, findings):
            raise asyncio.CancelledError()

    publicador = FakeAlertPublisher()
    with pytest.raises(asyncio.CancelledError):
        AlertingFindingStore(Cancelado(), publicador).add("c", [_alto()])
    assert publicador.alertas == []


def test_el_fallo_de_una_alerta_no_impide_las_siguientes():
    class FallaLaPrimera:
        def __init__(self):
            self.alertas = []

        def publish(self, kind, case_id, detail):
            if not self.alertas and not hasattr(self, "vista"):
                self.vista = True
                raise RuntimeError("primera falla")
            self.alertas.append(detail)

    destino = FallaLaPrimera()
    AlertingFindingStore(FakeFindingStore(), SafeAlertPublisher(destino, _log())).add("c", [_alto(posicion="1"), _alto(posicion="2")])
    assert len(destino.alertas) == 1


@pytest.mark.parametrize("estado", [None, "COMPLETED", "Completed", "completed ", "", "running", "pending", b"completed", 0])
def test_estados_desconocidos_se_rechazan_con_value_error(estado):
    with pytest.raises(ValueError):
        case_closed_alert("c", estado)


def test_estado_rechazado_no_publica_nada():
    publicador = FakeAlertPublisher()
    with pytest.raises(ValueError):
        notify_case_closed(publicador, "c", "cancelled")
    assert publicador.alertas == []


@pytest.mark.parametrize("case_id", ["", "caso con espacios", "../etc/passwd", "ñ\n\ud800", "x" * 10_000])
def test_case_id_raro_viaja_intacto_en_la_alerta(case_id):
    publicador = FakeAlertPublisher()
    notify_case_closed(publicador, case_id, "completed")
    assert publicador.alertas == [("caso_finalizado", case_id, '{"estado": "completed"}')]


# --- Defectos encontrados (xfail strict) ---


@pytest.mark.xfail(
    strict=True,
    reason="QA media: add(case_id, iterador) agota el iterador en inner.add y la segunda pasada no ve hallazgos; se guarda y no se alerta, en silencio. Arreglo: materializar `findings = list(findings)` antes de inner.add.",
)
def test_un_generador_pasado_a_add_se_guarda_y_alerta():
    interno, publicador = FakeFindingStore(), FakeAlertPublisher()
    AlertingFindingStore(interno, publicador).add("c", (h for h in [_alto()]))
    assert len(interno.list("c")) == 1
    assert len(publicador.alertas) == 1


@pytest.mark.xfail(
    strict=True,
    reason="QA media: AlertingFindingStore no aisla fallos; con un publicador sin SafeAlertPublisher, add propaga tras guardar y se pierden las alertas restantes. El SPEC delega el aislamiento en quien componga, pero nada lo impide. Arreglo: envolver el publicador en SafeAlertPublisher dentro del constructor o exigirlo por tipo.",
)
def test_publicador_sin_envolver_no_rompe_add_ni_pierde_alertas_restantes():
    class FallaLaPrimera:
        def __init__(self):
            self.llamadas = 0
            self.alertas = []

        def publish(self, kind, case_id, detail):
            self.llamadas += 1
            if self.llamadas == 1:
                raise RuntimeError("redis caido")
            self.alertas.append(detail)

    destino = FallaLaPrimera()
    AlertingFindingStore(FakeFindingStore(), destino).add("c", [_alto(posicion="1"), _alto(posicion="2")])
    assert len(destino.alertas) == 1


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: un estado no hashable (lista) da TypeError al hacer `status in frozenset`, no el ValueError del SPEC. Arreglo: comprobar isinstance(status, str) antes.",
)
def test_estado_no_hashable_se_rechaza_con_value_error():
    with pytest.raises(ValueError):
        case_closed_alert("c", ["completed"])


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: SafeAlertPublisher registra case_id y kind con %s; un case_id con salto de linea inyecta lineas falsas en el log. Arreglo: usar %r.",
)
def test_el_log_no_permite_inyectar_lineas_con_el_case_id(caplog):
    with caplog.at_level(logging.ERROR):
        SafeAlertPublisher(PublicadorQueLanza(RuntimeError("x")), _log()).publish("k", "a\nERROR falso", "d")
    assert "\n" not in caplog.records[0].getMessage()


@pytest.mark.xfail(
    strict=True,
    reason="QA baja: un publicador asincrono (coroutine function) se 'absorbe' sin error: la corrutina nunca se espera y la alerta se pierde sin log, solo RuntimeWarning. Arreglo: detectar inspect.isawaitable(resultado) y registrar/cerrar.",
)
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning", "ignore::RuntimeWarning")
def test_publicador_asincrono_no_pierde_la_alerta_en_silencio(caplog):
    class Asincrono:
        async def publish(self, kind, case_id, detail):
            return None

    with caplog.at_level(logging.ERROR):
        SafeAlertPublisher(Asincrono(), _log()).publish("k", "c", "d")
    assert caplog.records
