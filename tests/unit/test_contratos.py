from datetime import datetime, timezone

import pytest

from src.application.ports import Analyzer, Clock
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.priority import Priority
from tests.contratos import comprobar_analyzer
from tests.dobles import FakeAnalyzer


def test_las_cuatro_prioridades_del_enunciado_estan_ordenadas():
    assert Priority.BAJA < Priority.MEDIA < Priority.ALTA < Priority.CRITICA


@pytest.mark.parametrize("nombre, prioridad", [("baja", Priority.BAJA), ("critica", Priority.CRITICA)])
def test_prioridad_se_lee_de_su_nombre(nombre, prioridad):
    assert Priority.from_name(nombre) is prioridad


def test_prioridad_desconocida_se_rechaza():
    with pytest.raises(ValueError):
        Priority.from_name("urgente")


def hallazgo(confianza=0.9):
    return Finding("amenaza", Severity.ALTA, confianza, EvidenceRef("abc", "linea 3"), "texto")


def test_hallazgo_enlaza_evidencia_a_su_fuente():
    assert hallazgo().evidence == EvidenceRef("abc", "linea 3")


@pytest.mark.parametrize("confianza", [-0.1, 1.1])
def test_confianza_fuera_de_rango_se_rechaza(confianza):
    with pytest.raises(ValueError):
        hallazgo(confianza)


def test_un_analizador_y_un_reloj_falsos_cumplen_los_puertos():
    class AnalizadorFalso:
        def analyze(self, path):
            return [hallazgo()]

    class RelojFijo:
        def now(self):
            return datetime(2026, 11, 3, tzinfo=timezone.utc)

    assert isinstance(AnalizadorFalso(), Analyzer)
    assert isinstance(RelojFijo(), Clock)


def test_el_analizador_falso_pasa_la_conformidad_de_analyzer(tmp_path):
    comprobar_analyzer(FakeAnalyzer([hallazgo()]), tmp_path / "chat.txt")
